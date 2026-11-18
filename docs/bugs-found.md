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

**REFUTED 18.11** (0013-F executed: PITCH = block row changed nothing; the same
defect reproduces with plain RGBA32, where both pitch conventions coincide, and
on the r3d engine). The real root cause is in the final section below. Kept as
the evidence trail.

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
| F | src PITCH = block row (2048/1024) | executed, rejected (byte-identical failures) |
| G | the register space at large | closed: GEOMDBG shows the programmed src registers structurally identical on failing and passing geometries; `TU_I2B_R3D=1` moves some cases and breaks others, the core fails on both engines |
| H | **CCU coherence, not addressing** | **CONFIRMED - see the final section**; the whole 0013 numbering is retired, the fix is candidate `exp-13b` |

## Final (18.11): root cause - no CCU clean between buffer->image and the next reader in the same submit (A7XX)

**Root cause**. On A7XX the CP_BLIT (r2d) writes of `CmdCopyBufferToImage` land in
the CCU and are not guaranteed visible to readers until an explicit CCU clean;
`tu_copy_buffer_to_image`/`tu_copy_image_to_buffer` emit no cache operations at all
(`r2d_teardown` is "nothing to do here"), and a pipeline barrier outside a
renderpass inserts nothing into the CS (the flush bits of `cmd->state.cache`
collapse onto the batch/submit). So a `CopyImageToBuffer` (or any UCHE read) later
in the same submit reads pre-copy memory. Turnip knows the rule - "On A7XX, blit
cache flushes are required to ensure blit writes are visible via UCHE. This isn't
necessary on A6XX, all writes should be visible implicitly"
(`tu_cmd_buffer.cc:421`), "CP_BLIT writes to the CCU ... we need to flush manually
here" (`tu_clear_blit.cc:6101`, `store_3d_blit`), the staging copy path flushes
precisely this way (`:3645`) - only the public copy commands skip it. This is also
the a6xx/a7xx asymmetry: the same r2d code works on 6xx by the implicit-visibility
rule, 7xx requires the clean.

**Experiment chain** (all logs `results/test-BCcopy-*`, one variable per run):

| Step | Result |
|---|---|
| GEOMDBG src-register dump, failing vs passing geometries | structurally identical registers, only sizes differ -> register-value hypotheses closed |
| `TU_I2B_R3D=1` (all readbacks over the 3D engine) | the core failures persist (128x128, BC@512, 32x256); 256x64-linear is fixed, 256x256-linear breaks -> not engine-specific |
| `TU_B2I_WFI=1` (WFI after the fill) | no change -> not a pipeline-drain issue |
| `TU_I2B_ROWS=1` (per-row blits, the "6xx way") | the same column windows `[128,192)+[320,384)` survive in the first ~15 rows only -> timing at traversal start, not addressing |
| CPU-FILL probe | image memory 100% byte-clean via CPU while the readback still fails -> GPU-side visibility, not storage |
| `TU_I2B_SYNC=1` (CLEAN_COLOR + CACHE_INVALIDATE + WFI before the readback) | **91/91 EXACT, 0 MISMATCH** |
| `TU_I2B_SYNC=3` (CLEAN_COLOR + WFI only) | 0 MISMATCH - the UCHE invalidate is not needed |
| `TU_I2B_SYNC=2` (CACHE_INVALIDATE + WFI only) | 19 MISMATCH, old signature - invalidating reads alone does not help |
| `TU_I2B_SYNC=4` (CLEAN_COLOR without WFI) | 19 MISMATCH - the event write is async, the WFI is required |
| `TU_B2I_CLEAN=1` (producer side: CLEAN_COLOR + WFI at the end of b2i) | 0 MISMATCH |
| no-env control on the same binary | 19 MISMATCH - the env gating is real |

**Why it looked like geometry/BC/state magic**: which dirty lines a reader still
misses depends on CCU capacity, tiling and the command-buffer history (the test
reuses VA ranges across cases) - hence the run-to-run zero-count drift (15488..16032)
and the format-agnostic, "geometry-dependent" signatures. BC@512/BC1@100%-zeros and
plain RGBA32 128x128 are one and the same defect.

**Upstream**: mesa main still has no cache operation in either copy function
(verified 18.11 against gitlab `main`, `tu_clear_blit.cc`) - this is not our lag.
The closed blob reads the same geometries correctly, so the HW only needs the
event write that turnip omits.

**Fix**: `experiments/exp-13b-b2i-ccu-clean-candidate.patch` - at the end of
`tu_copy_buffer_to_image` (CHIP >= A7XX), in the native flush-tracking idiom:
`cmd->state.cache.flush_bits |= TU_CMD_FLAG_CCU_CLEAN_COLOR |
TU_CMD_FLAG_WAIT_FOR_IDLE; tu_emit_cache_flush<CHIP>(cmd)` (tu6_emit_flushes
orders the WFI after the clean - both are required). Validated 91/91 EXACT with
no env: raw-event-write form `results/test-BCcopy-0013cand.log`, flush_bits form
`results/test-BCcopy-0013candb.log`. Open before shipping as 0013: the RE4 cost
of one clean+WFI per b2i (b2i is the texture-upload hot path). The zero-cost
form, and what upstream would actually write: b2i only *marks* the bit and the
outside-renderpass pipeline barrier executes the pending `cmd->state.cache`
flushes on the spot (all app patterns that submit between copy and use stay
flush-free, and b2i->shader-read in one submit gets fixed too). The env-knob
bundle used for the A/B is `experiments/exp-13-i2b-ccu-clean-env-bundle.patch`.

**Shipping decision (18.11): not a candidate for the RE4 stack, no game
measurement.** Games/vkd3d-proton submit between the copy and its use (readbacks
run as their own command list, uploads are submitted before use), so RE4 never
executes the in-submit chain - that is exactly why the game always looked fine
while the CTS-style probe failed 19/19. The producer-side clean would add a
clean+WFI to every upload blit to fix a path the game does not walk: pure cost,
zero benefit. The thread's output is a standalone upstream/CTS correctness
finding (mesa main affected; blob unaffected), with both fix forms validated and
the barrier form being the one worth posting upstream, with a CTS repro.
