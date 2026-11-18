# Bugs found (r2d BC copy, A7XX)

Date: 2026-11-18. Tree: mesa27-src HEAD `6dfa32a` (upstream mesa main, 2026-11-03) +
the 0001-0012 stack + A+B (the uncommitted diff of 10 files). Chip: A740 (A7XX).
Test: `tests/rp6-vkd3d-sparse-test.c`, the U probe (A2D roundtrip) + the T probe
(SP texelFetch).

## Bug 1. The dead code of 0013-E (a bug in our experiment) - the "rejection" was a no-op

**Where**: `src/freedreno/vulkan/tu_clear_blit.cc`, the 0013-E hunk (:3216-3229, :3249-3254).

```c
enum pipe_format dst_format =
   copy_format(src_image->vk.format, info->imageSubresource.aspectMask);  // :3187-3188
enum pipe_format src_format =
   copy_format(src_image->vk.format, info->imageSubresource.aspectMask);  // :3189-3190
...
bool bc_img_buffer_src =
   util_format_is_compressed(src_format) &&      // :3227 - src_format is already the surrogate!
   util_format_get_blockwidth(src_format) == 4 &&
   util_format_get_blockheight(src_format) == 4;
```

`copy_format()` (tu_clear_blit.cc:~2214) translates any compressed format into a
surrogate by block size: `case 8 -> PIPE_FORMAT_R32G32_UINT` (BC1),
`case 16 -> PIPE_FORMAT_R32G32B32A32_UINT` (BC3/BC7).
`util_format_is_compressed(PIPE_FORMAT_R32G32B32A32_UINT) == false` **always** ->
`bc_img_buffer_src == false` -> the re-emission of
`TPL1_A2D_BLT_CNTL.type = A6XX_TEX_IMG_BUFFER` (:3249-3254) **never executed**.

**Consequence**: the 0013-E verdict "identical to base" = a no-op; the
TYPE=IMG_BUFFER hypothesis was **not tested** (reclassified as "untested").

**Fix (0013-E2)**: the condition on the image's original format:
`vk_format_is_compressed(src_image->vk.format)` + the 4x4 block.

## Bug 2. (suspected root cause, upstream) the PITCH units on the A2D readback image-src path

**Symptom**: the readback of a 512x512 BC image (image->buffer, r2d) is broken in
all 3 layout variants:
- BC3: 3612/16384 zero blocks, the block columns are =32..47 (mod 48) =
  [32,47]+[80,95]; the 768B window = 512B of data + 256B of zeros; the data
  "punches through" the zero slots in 64B chunks; the coverage in a row varies
  20-32 of the 32 zero columns.
- BC1: 99.85% zero words (32720/32768), 16360 full zero blocks.
- The fill (buffer->image) is byte-clean (the T dump is about the ffmpeg
  oracle: {0: 68600, 1: 190737, 2: 2807}).

**Register comparison** (A7XX; `TYPE = A6XX_TEX_2D` (1) is the default in both
directions - emitted explicitly in `r2d_setup_common` :743-746 for
`CHIP > A6XX`; the `a6xx_tex_type` enum: A6XX_TEX_2D=1, A6XX_TEX_IMG_BUFFER=5):

| Register | Fill src (buffer, WORKS) | Readback src (image, BROKEN) |
|---|---|---|
| `TPL1_A2D_SRC_TEXTURE_INFO.COLOR_FORMAT` | FMT6_32_32_32_32_UINT (surrogate, `blit_format_texture`, r2d_src_buffer :576-589) | FMT6_32_32_32_32_UINT (surrogate, fd6_view: `storage_format = texture_format = fd6_texture_format(args->format)`, :236-238/:264/:468) |
| `TPL1_A2D_SRC_TEXTURE_SIZE` | 128x128 (blocks, explicit after `copy_compressed` :2913) | 128x128 (blocks, fd6_view.cc:172-186: the BC3 layout blockwidth 4, the args surrogate blockwidth 1 -> `nblocksx`) |
| `TPL1_A2D_SRC_TEXTURE_PITCH` | **2048** (bytes of a block row: 128x16B, `r2d_src_buffer` :589) | **512** (bytes of a texel row: fdl `pitch0 = align(nblocksx x cpp)`, freedreno_layout.h:333; cpp = block_bytes/4 = 16/4 = 4; 128x4 = 512) |

BC1: fill 1024 vs readback 256. **The only value that differs is PITCH**
(INFO and SIZE matched after the 0013-B/D checks and the correction below).

**Encoding** (a6xx.xml:4534-4540, variants A7XX-): `PITCH` = bits 3..23, no shift
(raw bytes; the macro shifts `<<3`). The XML comment: "Bits from 3..9 must be
zero unless 'TPL1_A2D_BLT_CNTL::TYPE' is A6XX_TEX_IMG_BUFFER, which allows for
lower alignment" -> the value must be a multiple of 128; 512 and 2048 both
satisfy it - this is a **value/units error**, not illegality. The dst register
`RB_A2D_DEST_BUFFER_PITCH` encodes 64B words (`shr=6`); the fill dst works with
X = 2048/64 = 32.

**Why uncompressed formats do not catch it**: for them the bytes of a texel
row == the bytes of a block row (a block = 1 texel) -> both conventions
coincide. Only the 4x4 BC breaks: BC1 256!=1024, BC3/BC7 512!=2048 (the
difference is exactly x4 = the block height).

**The SP path (the T probe) works with the same 512**: the TP hardware
interprets the pitch as the bytes of a texel row and multiplies by the block
height (4) itself -> 2048. The A2D engine, judging by the working fill, expects
the bytes of a block row.

**Model of the corruption mechanism (unconfirmed, as a guide)**: the A2D pulls
the src in 64B sectors with a stride of 768B (12 sectors): 8 data sectors +
4 gaps -> the zero columns [32,47]+[80,95] per 768B window; the drift of
y*512 mod 768 explains the variation of the coverage across rows (20-32/32).

**Experiments** (one register at a time, rollback
`git checkout HEAD -- src/freedreno/vulkan/tu_clear_blit.cc`):
- **0013-E2**: re-emit `TPL1_A2D_BLT_CNTL.type = A6XX_TEX_IMG_BUFFER` (5), the
  condition on `src_image->vk.format`. The IMG_BUFFER XML doc: "lower alignment
  requirements than A6XX_TEX_2D, available since A7XX".
- **0013-F**: re-emit `TPL1_A2D_SRC_TEXTURE_PITCH = iview->pitch x blockheight`
  (= 2048 for BC3/7, 1024 for BC1) after `ops->src` - reproduces the
  configuration of the working fill-src. Priority if E2 does not close it.

## Correction. `TPL1_A2D_SRC_TEXTURE_INFO.COLOR_FORMAT` = the surrogate, not the storage

fd6_view.cc (the view for A2D is created through
`tu_image_view_copy(&src, src_image, src_format, ...)` :3256-3258 with the
surrogate pipe format from `copy_format`):
- :236-238 `texture_format = fd6_texture_format(args->format, tile_mode, is_mutable)`;
- :264 `storage_format = texture_format` (the only exceptions: d24s8 and
  R64_SINT/UINT, :265-275);
- :468 `TPL1_A2D_SRC_TEXTURE_INFO = ...COLOR_FORMAT(storage_format) | TILE_MODE | ...`.

-> On the readback the engine sees the src as an **ordinary R32G32B32A32_UINT
128x128 linear texture** (BC1: R32G32_UINT) and does not know that BC3 is in
the memory. The earlier statement "INFO = the BC3 storage" - an error,
refuted. Consequence for the U dumps: the non-zero words = the exact bytes of
the bitstream (the 24 U-BC1 blocks byte-for-byte, the BC3 "exact pattern") -
**the engine does not decode BC**, it copies the raw 16B words; the corruption
is in the addressing, not in the codec.

## Status of the 0013 series (updated)

| # | Hypothesis | Status |
|---|---|---|
| v1 | fill rework | rejected (the fill is clean) |
| A | dst format surrogate | rejected |
| B | src SIZE/4 | rejected (SIZE was already correct: 128x128 blocks) |
| C | re-emit the output registers | rejected |
| D | src COLOR_FORMAT surrogate + SIZE/4 | rejected (COLOR_FORMAT was already the surrogate - see the Correction; only SIZE/4 was effective) |
| E | `BLT_CNTL.type=IMG_BUFFER` | **was not tested (dead code, Bug 1)** -> E2 |
| F | src PITCH = block row (2048/1024) | to execute (priority, Bug 2) |
