# Plan: what to check (new patch candidates + re-check of the "dead ends")

17.11.2026. RE4 A/B is paused; the task is to exhaust the options for new patches.
Each block: **facts -> what to check -> how -> criterion -> artifact**.

State after the server restart: `/tmp` is wiped (the ninja directory + ccache
are gone) - before any build, `meson setup` again + the PHONY fix
(`touch -d @0 /tmp/opencode/mesa27-build/build/PHONY`). The mesa27-src tree is
intact (9 M files, stage A+B not committed, rollback only via `git apply -R`).
`build/out-base` (base `c9dad346`) and `build/out-ab` (A+B `704aa643`) are in
place, the hash is correct. `build/out` is currently = base.

---

## 0. Premise: the BC copy path (candidate A) - blocks verification of 0012

**Facts** (baseline, stack 0001-0011, log `results/test-BCUBWC-baseline.log`):
- roundtrip (fill `vkCmdCopyBufferToImage` x2 + readback
  `vkCmdCopyImageToBuffer`, 512x512, pattern in the buffer) on the base is **broken for all
  three variants** (linear/nonmut/list):
  - `BC1_UNORM`: **32768/32768 words = 0** (nothing was copied);
  - `BC3_UNORM` / `BC7_UNORM`: the first **128 words (512 B = 32 blocks of 4x4,
    texel 0..127 of row 0)** are exact, then 0 (`bad[0]=128(r0,c128)`),
    "untouched(0xCD)=0" - the engine wrote the whole buffer, the tail is zeros.
- Both directions go through the **r2d engine** (`r2d_ops<CHIP>`,
  `tu_copy_buffer_to_image`/`tu_copy_image_to_buffer`, `tu_clear_blit.cc`).
  A7XX always goes through `r2d_src_buffer_unaligned` (fill) / `r2d_dst_buffer`
  (readback). The buffer is programmed as a **linear texture** of the BC format
  (`TPL1_A2D_SRC/DST_TEXTURE_*`), and the image - through `tu_cs_image_ref_2d` (tiling).
- 0012 A+B is verified only for **CEIL/memreq + create-checks**, not with data:
  the BC roundtrip is broken anyway, so **the real contents of a BC+UBWC image are
  not verified**. And RE4 loads BC textures exactly this way (vkd3d ->
  `vkCmdCopyBufferToImage`) -> if the path is broken, RE4's textures on the base are
  corrupted, and the 0012 A/B is noisy.

**What to check:**
1. **Which direction is broken** (fill vs readback). The discriminator: read
   the same image **not through r2d**, but through the TP (texture path) - a compute shader
   `texelFetch` into a buffer (TP BC works in RE4 - the game renders). If the TP readback
   gives the full pattern -> r2d readback is broken (fill is ok); if TP also shows
   "the first 512 B, then 0" -> fill is broken.
2. **Whether r2d on A7XX supports BC as a buffer/texture**: `blit_format_texture` ->
   `tu6_format_texture`, the `a6xx_format` tables; whether the r2d engine has an entry for
   BC (8B and 16B per block). Hypothesis: r2d can't do BC in the buffer representation ->
   it copies a partial/zero result.
3. **Candidate fix**: route BC copies through the **r3d (3D engine)**,
   as is already done for Y8/NV12 (`ops = &r3d_ops<CHIP>`, `tu_clear_blit.cc:2965`
   and `:3201`) - if r3d supports BC (shader fetch + write). Check
   that the r3d blit accepts BC src/dst.

**Criterion:** the established direction + the HW/driver cause; if the fix
works - candidate patch **0013** (BC copy through r3d), verification:
roundtrip BC1/BC3/BC7 EXACT on the base and on A+B.

**Artifact:** `results/test-BCcopy-<name>.log`, the journal entry it became (journal 21.8).

### Status (18.11)

- The direction is established: **fill OK (byte-exact), broken is the
  r2d-readback (image->buffer)** - the TP-readback (texelFetch) is 100% nz
  for BC3/7; the BC1 fill = the first-fill defect of section 20 (the second
  fill does not fix it completely, 86% nz). The premise "the RE4 textures
  are broken on the base" is **withdrawn**: the hot path of vkd3d
  (buffer->image) works; the T suffix "broken r2d-readback" is a static
  label of the test, not a measurement.
- Candidates: **0013v1** (FMT6_NONE -> `fd6_texture_format` in
  `r2d_dst_buffer`) - rejected (no change, `8c73a859`); **0013-A** (the
  surrogate format of the dst buffer only: 8B -> R32G32_UINT, 16B ->
  R32G32B32A32_UINT) - rejected (no change, `d73b0282`); **0013-B** (the
  SIZE of the image-src /4 for BC in `r2d_src`) - rejected (no change,
  `172344a7`) - i.e. the texel/block units of the SIZE are not the cause.
  The defect is identical on base/A+B/0013v1/0013a/0013b: BC1 - all zeros;
  BC3/7 - the first 512 B are exact, then ~76% of the words match, ~24% are
  zeros (the zero count varies between the runs, 15008-16000 ->
  uninitialized memory is read); the linear (no tiling/UBWC) and the UBWC
  images break the same way; all the controls are EXACT.
- **0013-C (in progress)**: for the BC-dst the setup programs `FMT6_NONE`
  into `RB_A2D_BLT_CNTL`/`GRAS_A2D_BLT_CNTL`/`SP_A2D_OUTPUT_INFO` + the
  `ifmt` from `format_to_ifmt(BC)` = **UNREACHABLE** (BC has one packed
  channel, no component bits -> garbage in the register). 0013-C programs
  the surrogate color format (one 4x4 block = one "texel" of the surrogate:
  8B -> R32G32_UINT, 16B -> R32G32B32A32_UINT, the precedent is
  `copy_buffer()`) into **all** the output registers + an honest `ifmt`,
  only on the image->buffer path (the fill is not touched - it works with
  FMT6_NONE).
- The fallback candidate: the `COPY` bit (pos 30, A7XX) in
  `RB_A2D_BLT_CNTL` - not programmed anywhere in the code, the meaning is
  unknown (a possible "raw copy").
- If 0013-C does not close it - next: routing the BC through r3d (from the
  original plan), or a dump of the readback buffer (T_DUMP in the U section
  of the test) for the structure of the zero words.

### Status close (18.11): the 0013 series is closed, the defect outgrew it

- 0013-C/D/E/F rejected as well (C: the surrogate color format in all output
  registers - no change; E was dead code; PITCH/SIZE/surrogate hypotheses all
  refuted - the defect is byte-identical on base/A+B/every 0013 variant).
- The T_DUMP structure (GEOM sweep + CPU-FILL) redefines the bug: the fill is
  byte-clean on the failing geometry too (CP[] raw read of the image = 100%
  fill), `other=0` (only exact words or zeros), and the zero-windows are
  **geometry- and state-dependent, format-agnostic** - a plain RGBA32 128x128
  fails with the old BC3-512 signature, 256x128/512x64/256x256 pass. The wording
  "readback addressing" held until the final verdict below - it is visibility,
  not addressing.
- **CLOSED the same evening (see the final section of `bugs-found.md`, journal 21.10): root cause = missing CCU clean on A7XX between b2i and the next
  reader in one submit.** `TU_I2B_SYNC=1` (FD_CCU_CLEAN_COLOR + WFI before the
  readback) and the producer-side variant both give 91/91 EXACT; invalidate-only
  and clean-without-WFI still fail. Fix candidate:
  `experiments/exp-13b-b2i-ccu-clean-candidate.patch` (validated as-is, no env:
  `results/test-BCcopy-0013cand.log`). The old "route BC through r3d" fallback is
  moot - the defect reproduces on r3d too and the fix is engine-agnostic.
- **Shipped (19.11) as `patches/0013-turnip-b2i-ccu-clean.patch`**, in the form
  the exp-15 matrix picked (mode 7: mark `CCU_CLEAN_COLOR|WAIT_FOR_IDLE` in
  `flush_bits`, execute nothing at the copy) - 94/94 EXACT over three repeats
  and zero cost per copy. The 18.11 objection (a clean+WFI per upload blit
  would be pure cost) applied to the per-copy forms only; the lazy form adds no
  work to a submit that does not already end in a flush point. Still no game
  fps A/B, and none is expected to show anything: RE4 submits between copy and
  use. Upstream remains the model form + a CTS repro, posted by the user (we do
  not post to mesa); `experiments/exp-13*`, `exp-15` and the final section of
  `bugs-found.md` carry everything needed for it.

---

## 1. Candidate B: the `QCTDD12766770` fast-clear quirk (patch 0008)

**Facts:**
- Patch 0008 in `a7xx_gen2` sets them **as a pair**: `has_generic_clear = True`
  (the speedup - event clear instead of cp_blit; measurements on 30.09: vkmark
  vertex/shading/texture **-61..-65 %**, RE4 0 %) + `QCTDD12766770 = True`
  (the limiter).
- `has_generic_clear` is read in **6 places**:
  1. `tu_clear_blit.cc:4460` `use_generic_clear_for_image_clear`
     (vkCmdClearColorImage/ClearDepthStencilImage) - **the only place where the
     quirk takes effect**: `!(QUIRK && image_is_r8g8)` -> R8G8 goes to cp_blit;
  2. `tu_clear_blit.cc:5315` (vkCmdClearAttachments -> generic, if there is no
     predication and the layout is known);
  3. `tu_cmd_buffer.cc:6870` (subpass begin gmem: skip the gmem clear);
  4. `tu_cmd_buffer.cc:6899` (subpass begin sysmem: skip the sysmem clear);
  5. `tu_cmd_buffer.cc:7104` (`tu7_emit_subpass_clear`);
  6. `tu_pass.cc:592` (renderpass cond config).
  I.e. apart from #1, generic clear on A740 is **already enabled everywhere** - "use it
  somewhere else" = narrow the exception in #1 specifically.
- Comment in the code: a fault with "Clearing VK_FORMAT_R8G8_* **with fast-clear
  value**, certain dimensions (e.g. 960x540), and having GMEM renderpass
  afterwards". But the code **blanket**-disables generic clear for **all** R8G8
  (not only with a fast-clear value, not only 960x540).

**Hypothesis (user):** the quirk is specifically about fast-clear; the blanket disable
of R8G8 is excessive; generic clear can be returned for R8G8 with **non**-fast-clear
values (and/or non-960x540).

**What to check:**
1. **What a "fast-clear value" is** in the code - where it is determined that a value
   is eligible for HW fast-clear (LRZ/RB) and which is not. *(Not found yet -
   the concrete step: search for `fast`/`lrz`/`clear value` in `tu_clear_blit.cc`,
   `tu_lrz.cc`, `fdl`.)*
2. **Whether the quirk is required on A740** - the experiment "turn it off and watch for a fault":
   - build variant: `QCTDD12766770 = False`, `has_generic_clear = True`
     (the rest of the stack as is). **It cannot be turned off at runtime**: `TU_FORCE_PROPS`
     and `FD_DEV_FEATURES` quirks only **set true**, they don't clear
     (`tu_device.cc:1785`, `freedreno_dev_info.py` - props only).
   - run: **vkmark** (full - many clear patterns) + **RE4**;
     catch a GPU fault: `dmesg` (kgsl fault/reset), a hang, frame corruption.
3. **Narrowing** (if the quirk is needed but excessive): move the check into the
   calling code (there `clear_value` is available), exclude only
   R8G8 + fast-clear value (and/or sizes like 960x540), leave the rest of R8G8
   on generic clear. Run vkmark + RE4, measure the gain.

**Criterion:** (a) the quirk isn't needed -> remove it from 0008 (R8G8 on generic clear),
check that there is no fault; (b) needed but excessive -> a narrowing patch (candidate
**0014**) + a gain measurement; (c) needed as is -> keep it.

**Patch 0008 description (improve):** rewrite the header, explicitly separating:
`has_generic_clear` = **performance** (event clear instead of cp_blit,
vkmark -61..-65 %, RE4 0 %), `QCTDD12766770` = **insurance** against a specific
fault (fast-clear value + R8G8 + sizes ~960x540 + GMEM renderpass); at
the time of the patch it was applied to all R8G8 (blanket, possibly excessive - see the plan).

**Artifact:** `results/test-fastclear-<name>.log` (vkmark), `dmesg` excerpts,
a journal entry (journal 15 is the one that measures this prop); a header edit in
`patches/0008-*.patch`.

### Status (18.11): closed by analysis - keep the blanket

- The quirk fires in exactly one of the six reads of
  `has_generic_clear` - `use_generic_clear_for_image_clear`
  (`tu_clear_blit.cc`): the blanket `!(QUIRK && image_is_r8g8)` -> every
  R8G8 image-clear goes to the cp_blit; the other five places
  (vkCmdClearAttachments, the subpass begin gmem/sysmem,
  `tu7_emit_subpass_clear`, the renderpass config) already get the
  generic-clear on the A740.
- The cost of the blanket is measured (30.09, `results/vkmark-ab-r8g8.txt`,
  a series of 8 runs, interleaved): gc_r8g8 is about gc within the noise -
  vertex -62.1% vs -63.1%, shading -64.2% vs -61.1%, texture -64.5% vs
  -64.5%, clear +1.8% vs +0.9%; RE4 0% (median 12.4, n=77, no frame
  divergence). I.e. the blanket zeroes the gain only for the R8G8
  image-clear - and "fast-clear value + 960x540 + GMEM" is exactly the
  pattern on which the fault; the RE4 credit of returning the R8G8 to the
  generic is about 0.
- Nothing to narrow it with: the full set of the faulty sizes is unknown
  (the comment in the code - "e.g. 960x540"), the fast-clear value is not
  defined separately in the code (not found in tu_clear_blit/tu_lrz/fdl).
  The build variant `QCTDD12766770=False` is not worth it: the fault risk in
  RE4 with ~0 new information and ~0 gain (see the measurement above).
- **Verdict: keep the blanket.** The win of `has_generic_clear`
  (-61..-65% vkmark vertex/shading/texture) is already obtained and does
  not depend on the quirk.

---

## 2. Re-check of R8 (`has_8bpp_ubwc` - "HW corruption")

**Facts:**
- On A740 the effective value is **False** (CEIL "base (has_8bpp_ubwc=0)").
  In `a7xx_base`/`a7xx_gen2` the flag is **not set** -> the `GPUProps` default is taken
  (False). Explicitly: `a6xx_base=True` (line 118), `a6xx_gen2/3/4=False`
  (190/204/234); the a7xx chain `[a7xx_base, a7xx_gen2]` doesn't inherit from a6xx.
- Gate: `tu_image.cc:386` `!has_8bpp_ubwc && blocksizebits==8 &&
  plane_count==1 -> return false` (R8 without UBWC).
- Early measurement (journal 21.7): `FD_DEV_FEATURES=has_8bpp_ubwc=1` ->
  CEIL[R8] `nonmut=0x42000 > lin` (the *driver* allocates a metadata plane), but
  the roundtrip readback is **all zeros** (65536/65536 MISMATCH). That number is
  not a statement about the chip: the metadata size comes from
  `fd6_ubwc_alloc_size()`.
- **Probe Z (20.11, answered, with a caveat).** NV12 Y plane = `FMT6_NV12_Y`,
  `cpp == 1`, UBWC grid `{32,8}`, **not** gated by the property (`ubwc_possible()`
  gates 8bpp only when `plane_count == 1`). It round-trips **EXACT** through r3d,
  both tiling flavors, 64x64 to 512x512 and heights 4..512, on the ship `.so`
  (`results/test-8bpp-tp8bpp-{stock,sizes}.log`). So the chip compresses a
  `cpp == 1` UBWC plane today. It does *not* follow that `R8_UNORM` would:
  `registers/adreno/a6xx_enums.xml:114-116` - "FMT6_NV12_Y is not compatible with
  FMT6_8_UNORM". Z proves capability for the video format, not for plain 8bpp.
- **What plain `R8_UNORM` does (20.11, `i2b`, the reader whose linear control is
  EXACT at every size): exactly 25.29 % of the texels read back, at 512x512,
  256x256, 64x64 and 512x32 - the top-left quarter, `x < W/2` and `y < H/2`, the
  rest reads `0x00`, first wrong texel always `x = W/2`.** The fraction does not
  depend on the image size (`results/test-8bpp-tp8bpp-sizes.log`). A copy-filled
  image (no 3D writer) reads 0.39 %, i.e. nothing, and its metadata plane stays
  zero (`results/test-8bpp-meta-shape.txt`).
- **Metadata geometry is not the lever.** Grid sweep (`exp-17`, `TU_8BPP_UBWC`)
  and a metadata *pitch* sweep (block width 4/2/1 -> pitch 128/256/512 B, plane
  64..256 KiB) leave both the written volume (1024 B at 512x512, all `0x1f`, four
  256-byte chunks, stride = 16 rows of the current pitch) and the readable 25.29 %
  untouched (`results/test-8bpp-meta-pitch-height.log`,
  `results/test-8bpp-grid-sweep.log`). The 3D writer spends **1 byte per 256
  texels** whatever the driver reserved (8/16 KiB) - the cell count of `{32,8}`,
  while Mesa reserves and walks `{16,4}`.
- Grids with `blockheight >= 8` validate and allocate (`memreq 0x41000`, only 4 KiB
  of metadata), then the **first submit that touches the image faults the GPU**;
  everything after `VK_ERROR_DEVICE_LOST` in those logs - including the AB rows -
  is void. Note the confound before re-reading the sweep: `fdl6_ubwc_tile_dimensions()`
  also switches the *data* tile to 64x16 when `blockheight == 16`, so those rows
  never tested metadata geometry alone; `{16,8}`/`{32,8}`/`{8,8}` are
  the clean rows and they fault.
- **Upstream.** Origin of the property: `0f770caa232` (Joshua Ashton, 23.09.2022),
  "Disable 8bpp_ubwc on a6xx gen2 - Fixes text corruption in VSCode on a680" - a
  workaround, no diagnosis, untouched since. In upstream `main` (raw file, 20.11)
  `has_8bpp_ubwc` occurs 4 times, all a6xx; a7xx/a8xx never set it. The NV12 Y
  branch that *does* work was fixed three times (`8ea6f17fdf93`, `fb2646e527e9`,
  `18399c041267`); `git apply -R --check` says `18399c041267` is already in
  `mesa27-src`, so "our tree lacks the per-plane plumbing" is false.
- The "one block row is safe, the step to the next row breaks" model (wrong
  vertical pitch) cannot be tested at `H <= 16`: there the probe's *linear* control
  fails too, in both readers. Probe defect at small images, recorded as such, not
  a UBWC result. See journal 22.1 before re-using any small-image number.
- The runtime override **works without a rebuild**: `FD_DEV_FEATURES=has_8bpp_ubwc=1`
  (it is a prop, `freedreno_dev_info.py`).

**What to check:**
1. **Descriptor / CCU programming for plain 8bpp** - the gap is now localized by
   shape, not guessed: metadata at 1 byte / 256 texels from the writer, a reader
   that resolves half the extent on each axis. Which UBWC grid field, metadata
   pitch and height alignment the driver programs for `FMT6_8_UNORM` versus
   `FMT6_NV12_Y`, and what the blob programs, is the open part; overriding only
   `fdl6_get_ubwc_blockwidth/height()` to `{32,8}` faults the GPU, so a fix is more
   than a table entry.
2. **Probe AB as a discriminator** (cheap, one build): if a copy-filled R8+UBWC
   image ever reads EXACT while the 3D-written one stays at 25 %, the bug is in the
   writer, which is a different patch than a descriptor fix. Today's AB rows at
   `blockheight >= 8` are post-fault and prove nothing - run it in a fresh process.
3. (optional) RE4 with `FD_DEV_FEATURES=has_8bpp_ubwc=1`: the game creates 754
   `R8_UNORM` + 72 `R8_UINT` images (journal 25), so this is the ~70 MiB hole -
   worth a run *after* a real patch, with the fault risk the grid sweep showed, and
   note UBWC on a 512x512 R8 image *costs* 8 KiB (`0x42000` vs `0x40000`), so small
   images lose even in the best case.

**Criterion:** a patch that makes probe AA (`build/tp8bpp`) round-trip EXACT
without faulting the GPU. Until then `has_8bpp_ubwc = False` on `a7xx_gen2` is the
correct default - justified by what the hardware writes and reads back, not by a
`memreq` counter, and not by "the hardware cannot" either (see probe Z above).

**Artifact:** `tests/tp8bpp.c` (+ `tests/tp_write.comp`,
`scripts/gen-tp-write-spv.sh`), `scripts/sweep-8bpp-grid.sh`,
`scripts/ubwc-dump-analyze.py`, `results/test-8bpp-tp8bpp-{stock,sizes}.log`,
`results/test-8bpp-meta-pitch-height.log`, `results/test-8bpp-meta-shape.txt`,
journal 22 (the whole second pass on 8bpp) and `ADR-0007`.

---

## 3. Re-check of R32G32B32 (96-bit, "no HW entry")

**Facts:**
- "No HW entry" is in fact a **driver gate**: `fd6_layout.c:127`
  `if (!util_is_power_of_two_or_zero(layout->cpp)) { layout->ubwc = false; }`
  with the comment "R8G8B8 and other 3 component formats don't get UBWC".
  For R32G32B32 (96 bits = **12 B/texel**) `cpp=12` - not a power of two ->
  UBWC is off. `ubwc_possible()` does **not** block it (the CEIL label
  "(ubwc_possible)" in the probes is a **wrong attribution**).
- **R32G32B32A32 (128 bits = 16 B/texel, a power of two) DOES get UBWC**
  (there is a compat token `FD6_UBWC_R32G32B32A32_INT`, `freedreno_ubwc.h:157`).
  CEIL(baseline): `R32G32B32_TYPELESS 12B/texel lin=nonmut=list=0x300000`
  (no ceiling) - this is 96-bit; 128-bit was not measured in the CEIL probe.

**What to check:**
1. **Confirm the gate**: `!util_is_power_of_two_or_zero(cpp)` in `fd6_layout.c`
   (not `ubwc_possible`), and that the CEIL label "(ubwc_possible)" is misleading - fix
   the probe/conclusion so that the attribution is honest.
2. **Confirm that R32G32B32A32 (128 bits) is really in UBWC**: add it to the
   CEIL probe (or take it from the U/CEIL logs) -> `nonmut > lin` is expected
   (+0x2000 of metadata).
3. **HW or driver**: the "powers of two only" restriction is more likely HW (UBWC
   works on byte widths that are powers of two), but it is not confirmed from the blob.
   A workaround is risky: `assert(!params->force_ubwc || layout->ubwc)` in
   `fd6_layout.c:150` will fire.
4. **Significance**: R32G32B32 (96 bits) is rare in games; the common R32G32B32A32
   (128 bits) is already in UBWC -> **low priority**.

**Criterion:** the exact gate + HW/driver classification + a significance estimate.
Most likely **the dead end is confirmed**, low priority.

**Artifact:** an edit of the analysis of the 36 classes (journal 21.6.3a), a CEIL log
with R32G32B32A32.

---

## Queue (20.11, updated 21.11)

Ordered by what unblocks what. A closed branch is not repeated here - it has an ADR in
[`decisions/`](decisions/); this file owns only the next actions.

0. **Done 20.11, updated 21.11, so it may become stale again**: `../mesa27-src` carries
   `0001` and `0002` as commits (`ac08003`, `9845cfb` on base `6dfa32a`) and `0003..0013`
   plus the `exp-14` inventory hook plus `exp-21` as working-tree changes - 8 files,
   +663/-80, measured on 21.11 after `exp-22` was reverted with `git apply -R`. The
   +529/-77 of the 20.11 note is that tree without `exp-21`. `0014` is deliberately not
   applied: its replacement is item 11. Leaving it out of a working tree changes nothing
   that is shipped; the release and `patches/0014-*.patch` stand, and a replacement has to
   earn them by measurement.
   How it was restored, since `git checkout`/`git restore` is forbidden there
   (`AGENTS.md`): the three uncommitted edits were saved with `git diff -- <file>` and
   undone with `git apply -R` (two of them were stale reverts of `0001` and `0002` left by
   the stock-prop builds; the third was the `exp-14` hook), then `0003..0013` were applied
   in order and `experiments/exp-14-image-inventory.patch` re-applied from its file.
   **Correction to the note that `0003` needs offsets resolved by hand**: with `0001` and
   `0002` committed, all eleven patches pass `git apply --check` and apply cleanly - no
   offsets, no fuzz, no `--3way`. The offset work was an artifact of applying them onto a
   tree where those two were missing. What is still true: `ls | head -1` picks the mesa26
   twin of `0002`, so name the file.
   Verified by marker, not by counter: `extra_wait_count = 0` (`0001`), the `0x44050000`
   id line (`0002`), `tu6_mutable_format_list_forces_linear` (`0004`),
   `tu6_format_list_swaps_are_uniform` (`0005`), `case PIPE_FORMAT_B8G8R8A8_UINT` (`0006`),
   `TU_FORCE_PROPS` (`0007`), `has_generic_clear` (`0008`), `tu6_format_list_has_swaps`
   (`0010`), `R16G16B16A16_UNORM` and `case PIPE_FORMAT_R32G32_FLOAT` in
   `freedreno_ubwc.h` (`0011`, `0012`), the `CLEAN` sites in `tu_clear_blit.cc` (`0013`),
   `TU_IMG_INV` (`exp-14`), `mutable_compat_class` present (`exp-21`) - and
   `tu6_mutable_compat_class` absent (`0014` off). A marker
   says the code is present; it does not say it compiles or behaves: that is the rebuild
   below.
   Not run: a rebuild of this tree to reproduce the `imginv4` column of
   `results/imginv-3variants.txt` (`0001..0013` + `exp-14`, the control build that column
   was made on). Precedent for spending a build on that: `results/test-restore-shipstack.log`.
1. **exp-18 - the 64-bit UBWC class** (no patch file yet). Volume: 650.8 MiB, not 4 GB
   (journal 28). The two facts this item used to say must be measured first are measured,
   in journal 31: probe `CEIL` gained a fourth image (a `MUTABLE` image created with **no**
   `VkImageFormatListCreateInfo`) and it ran against the shipped stack, the bare Mesa 27
   base and the system driver - `results/test-CEIL-nolist-{p14,mesa27base,mesa26system}.log`.
   Four things came out of it, all of them for or against writing this patch:

   * the 64-bit class **has a ceiling**: a plain (non-`MUTABLE`) `R16G16B16A16_FLOAT`,
     `_UNORM`, `_SNORM` or `R32G32_FLOAT` image gets the metadata plane, `+0x2000` at
     8 B/texel, on all three drivers;
   * `_SNORM` is part of the reserve, not a control - the snorm refusal in
     `ubwc_possible()` is conditional on `ubwc_unorm_snorm_int_compatible`, which is True on
     `a7xx_gen2`;
   * **no** `nolist` image reaches a ceiling, on either Mesa 27 build, and the `nolist`
     column is identical between the base and the shipped stack on all seventeen rows: the
     refusal is upstream's, in `format_list_ubwc_possible()` and
     `tu6_mutable_format_list_ubwc_compatible()`, both byte-identical at refs `mesa-26.2.6`
     and `main`, where `TODO: limit based on compatiblity class` is still in place;
   * what `0011`/`0012` recovered is now measured against the base, not against the working
     stack: five `list` rows move from `GATE REMOVED` to `gate is not in the way`.

   So the item is not "unlock a format" but "reverse a current, deliberate default", which
   raises the bar for it. Rejected before writing it: the variant that keeps UBWC on a
   no-list image when the *base* format is unswapped and in the UNORM/SNORM/INT group - a
   view may pick any member of the class, and the 32-bit class contains both byte orders,
   which are the two shapes journal 24.1 measured broken (the same rule proposed from
   outside, reviewed in journal 30). Shape: (a) move `format_list_reinterprets_r8g8_r16()`
   and `format_list_has_swaps()` out of the `!mutable_ubwc_fc` branch - today the
   `is_mutable` branch skips them, which is why the prop tiles 16-bit no-list images, a real
   hazard; (b) implement `TODO: limit based on compatiblity class` in
   `format_list_ubwc_possible()` against `tests/vk-fmt-classes.json`, using the **strict**
   Vulkan class (not 0014's block class), with the accepted risk on legal but non-UBWC
   members (`E5B9G9R9`, `R64_*`) written down and a `perf_debug` counter. `exp-21` is the
   seam for it: with one decision function the class the layout is answered with and the
   class the compression is answered with are two arguments instead of one shadowed pointer.
   Gate: matrix 94 EXACT plus the `UBR` and `XV` rows unchanged, and a no-list cast probe
   before any volume claim. Two measured additions from journal 31: the `nolist` column of
   the `CEIL` rows is the direct readout of the change (it must move to `has UBWC` for the
   compatible classes and stay where it is for the rest), and the layout consequence must be
   read with probe `NL`, because `CEIL` compares sizes and cannot tell tiled from linear.
   **NOT BUILT, NOT MEASURED.**

   **State 21.11 - the hardware question in this item is answered, the rule is not written.**
   Two things moved (journal 32):

   * the rule was **modelled** before being written:
     `python3 scripts/fmt-list-gate-check.py --strict-class` ports `ubwc_possible()`,
     `fd6_ubwc_compat_mode()` (with the `0006`/`0011`/`0012` rows) and the no-list refusal to
     Python and answers for all 23 Vulkan classes. Result: 0 of 23 granted as the rule reads,
     1 of 23 (128-bit) once the members `fd6_format_table.c` gives no texture format to are
     excluded, **2 of 23** (128-bit and 64-bit) once one further pair of compat labels is
     folded. Artifact `results/model-strict-class-nolist.txt`. A model, nothing in it ran on
     the GPU;
   * that one pair was **measured**: `fd6_ubwc_compat_mode()` answers
     `FD6_UBWC_R16G16B16A16_INT` for five members of the 64-bit class and
     `FD6_UBWC_R32G32_INT` for three, which is the only line of the model still refusing that
     class - and probe `XMC` (`probe_xmc()`, with the `TU_UBWC_64B_MIX` knob of
     `experiments/exp-22-ubwc-64b-mix-knob.patch`, not for ship) shows the two behaving as
     **one cell** on this A740: with the knob on, the mixed `{R16G16B16A16_UINT,
     R32G32_UINT}` create carries the `0x2000` metadata tail and reads `0/262144` wrong
     texels through a view of its own family and through a view of the other one, with the
     same-family, the uncompressed and the deliberate-breakage controls all behaving. The
     knob changes two lines of a 621-line log out of the whole driver. Artifact
     `results/test-xmc-64bit-compat.log`.

   What that does and does not buy: the 64-bit class is the first class with both a model
   answer and a measurement behind it, and `exp-18 (b)` is no longer argued from a table.
   It does not make the rule safe: the measurement covers one geometry, no `STORAGE` usage
   and one reader engine, and the members the rig deliberately avoided (`R64_UINT`,
   `R64_SINT`, reachable through `STORAGE`, refused by `ubwc_possible()` for their own
   reasons) are still why the class cannot simply be granted - open question 14. The item
   stays **NOT BUILT, NOT MEASURED** for the patch itself. And the rig that asked the
   question: `experiments/exp-22-ubwc-64b-mix-knob.patch` (`TU_UBWC_64B_MIX`) was built
   21.11 as `build/out-exp22/libvulkan_freedreno.so`, `0e934fc6b3e0…`, used, and
   **reverted from the tree** the same day - it is a measurement hook, its header says NOT
   FOR SHIP, and nothing is queued on it beyond being there so journal 32 can be repeated.
   `fold_64()` in `scripts/fmt-list-gate-check.py` is its mirror in the model.

   **State 21.11, later the same day - open question 14 is measured, so the last avoidance in
   this item is gone.** Probe `XR64` (new in `tests/rp6-vkd3d-sparse-test.c`: fill by a
   buffer-to-image copy in the base format, read every 64-bit word through an `r64ui` storage
   image, then `imageAtomicAdd(+1)` per word and read again) ran against the released stack and
   against a build of `experiments/exp-23-ubwc-nolist-64-knob.patch`
   (`build/out-exp23/libvulkan_freedreno.so`, `2b61554b26ba…`) with the knob off and on. A 64-bit
   image created **without** a list, with `STORAGE` in the usage and with UBWC kept, stays tiled,
   carries the `+0x2000` tail, and reads byte-exact through `R64_UINT` - including after
   `imageAtomicAdd(+1)` per word, where every word comes back exactly +1. A list that *names*
   `R64_UINT` is refused compression with the knob on and off, which is the code's
   `FD6_UBWC_UNKNOWN_COMPAT` path and confirms the question could not have been asked through a
   list at all. Artifact [`../results/test-xr64-nolist-64-ubwc.log`](../results/test-xr64-nolist-64-ubwc.log),
   journal 37; the hook was taken out with `git apply -R` naming one file and `git diff --stat` in
   `../mesa27-src` is back to the recorded 8 files, +663/-80. What that buys: the rule can be
   written without an unmeasured hardware assumption about the member the rig used to avoid. What
   it does not buy: it is not a compression claim (open question 15), it is one geometry,
   `sparseImageInt64Atomics=0`, and the write paths into such an image (`clear`, `blit`, `r2d`)
   are not exercised. Added by journal 38, and it changes what this item is *for*: the per-client
   DRAM split in `results/fdperf-mesa27-vertex/steady-state.txt` puts SP at 0.05 GB/s of 14.8
   (0.3 % of reads) against TP at 81 %, and a class whose only reader is a storage image is an
   SP-side client - so no fps argument can be made for this grant on this workload. The case for
   it is coverage of a legal create, which is a weaker reason to spend a build than the volume
   number this item used to lead with.
2. **exp-19 - who is wrong about R8, the writer or the reader**. Probe AB (the same
   `R8_UNORM` + UBWC image, filled by `vkCmdCopyBufferToImage`) read by `i2b` in a fresh
   process, both at the base grid and at `{32,8}`. Cheaper than one build. If AB ever
   reads EXACT while AA does not, the 3D writer is at fault and the fix is not the
   descriptor work ADR-0007 declines. The AB rows of the 20.11 sweep are post-fault and
   are not measurements.
3. **The honest bare base**: run the inventory on `build/out-stock-inv`
   (`23ccf659c90d3ddf…`, stock + `exp-14`, no prop). Partly done 20.11: journal 31 ran the
   probe matrix on it - the first use of that build - and it is the control that shows the
   no-list UBWC refusal is upstream's. What is still not done is the game: the inventory run
   that gives the three-variant scale of journal 27 its true zero point.
   **Done for the other half 21.11**: the inventory that was queued here against
   `build/out-exp21` is run and matches `imginv5` per create (journal 36,
   `results/test-exp21-inventory-ab.log`), which closes item 11's gate. What is still open in
   this item is the bare base itself - the `build/out-stock-inv` column of the three-variant
   scale, which is the run that gives journal 27 its true zero point.
4. **Ship stack + prop + inventory**: the fourth column that the caveat in journal 27
   needs (the pair A/B differs by the whole stack, not only by the prop). About four
   minutes of build.
5. **fps A/B for mode 7** (`0013`): the correctness case does not depend on it, and the
   expectation on a latency-bound game is small (ADR-0008), so it is low priority.
6. **Who creates the DEPOSED no-list images** - vkd3d or DXVK. Not separated, and it
   decides which path the exp-18 verification must cover: vkd3d means the driver lever is
   the whole story, DXVK means the same fix has to be verified on the DX11 path too. There
   is no env lever on the vkd3d side: the empty-list branch in `resource.c`
   (`disable_compression`) is compiled in.
7. **Probes to add to the test**: b2i -> sampler inside a renderpass; b2i -> dispatch;
   secondary-CB b2i -> primary i2b (the boundary journal 21.10 leaves uncovered).
8. **R32G32B32 (96-bit)** - the re-check in section 3 above, still worth one run: it most
   likely confirms the dead end and lowers its priority.
9. **Documentation**, two open pieces, neither of them a measurement:
   - a distilled how-to page over the operational journal entries 7-12 and 19 (driver
     swap, running the game and reading its logs, the `vkCreateInstance` rejection and its
     real cause, the stale build image). The entries stay as they are; the page is the
     version you read while working.
   - the Russian left outside the archive. `AGENTS.md` says a passage is translated when
     it is touched; these were not touched, so they are listed instead of quietly kept:
     `scripts/imginv-stats.py` and `scripts/imginv-classes.py` (their own output labels)
     and the annotation headers of
     `results/{series-autotune,series-drirc,vkmark-ab-autotune,vkmark-ab-r8g8,vkmark-flags,test-8bpp-meta-shape}.txt`
     and `results/fdperf-mesa27{,-vertex}/steady-state.txt`. Translating the two scripts
     means re-running them over `results/raw/` and checking that every number in
     `results/imginv-3variants.txt` comes out identical - the labels may change, the
     counters may not.

   After editing any entry run `scripts/gen-journal-index.py`; the index and
   `docs/journal/manifest.json` are generated, not edited.

10. **exp-20 - does the game ever reinterpret a mutable image** (no file yet; one hook
    line, one rebuild, one 150 s run; the hook is stack-independent, item 0 only decides
    whether it runs against the ship stack). `exp-14` logs `vkCreateImage`; nothing in
    this repository has ever recorded a view creation. Extend the hook to the view path: base format, view
    format, `MUTABLE_FORMAT` bit, and whether the view format sits in the base's texel
    compatibility class (`tests/vk-fmt-classes.json`). Report the count of views whose
    format is not the base, split into same byte order and cross order. Why a rebuild is
    worth it: journal 24.4 shows that 24.1 does not exclude the prop's broken shape for the
    1630.2 MiB of 32-bit and 16-bit no-list mutable images the prop tiles, because a
    no-list `MUTABLE_FORMAT` image is reinterpretable by spec without a list. Zero casts
    closes the last gap in a shipped direction's argument and makes ADR-0001's "the shape
    is not created here" a complete sentence; a non-zero count means the prop is unsafe on
    a shape that carries volume. The verdict of ADR-0001 does not move either way - the
    prop frees no patch and adds no compression (journal 24.3, 27).

11. **`exp-21` - one layout-decision function, the candidate that replaces `0014`**
    (`experiments/exp-21-mutable-one-decision.patch`, tail
    `experiments/exp-21b-predicates-static.patch`; graduation number `0016`, because
    `0015` is spoken for by ADR-0009 and numbers are not reused). Status 21.11: written
    20.11, applies clean to `0001..0013` and reverts clean, **built** 21.11 as
    `build/out-exp21/libvulkan_freedreno.so` (`d49d094a8d6e…`) and **measured
    equivalent** to the released stack on every probe the rig had when the two logs were
    taken (test binary `63848afdba52bfa0…`, i.e. before the `XMC` section of journal 32 was
    added) - journal 33, `results/test-exp21-equiv-p14.log`: 598 lines against 598, **0
    differing lines** against `c17d02bcaae9a960…`, including the six `MISMATCH` and six
    `FAIL` rows, which are the known breakage of ADR-0001 and ADR-0007. What is left of its
    gate is the game column, item 3. It is an alternative to `patches/0014-*.patch`, not a
    stack on top of it: both define the compatibility-class enumerator.
    The operator's direction: keep the gain, do not enter the broken things, and make the
    shape a path rather than a patch-shaped exception.

    Correcting what this item said before the file was written, since the code disagrees
    with it in two places. `0014` does *not* substitute the class only at the call site: it
    does it inline in `tu_image_init()` **and** inside
    `tu6_mutable_format_list_forces_linear()` through a static
    `tu_mutable_format_list_or_class()`, which is why its second `tu_formats.cc` hunk is a
    comment and not a call - journal 21.12 and `docs/bugs-found.md` already described this
    correctly, only this item had it wrong. And `0014` carries **no dev-info prop**: adding
    one scoped to `a7xx_gen2` would change the answer on gen1 and gen3, so it is not a
    refactor detail but a separate decision (and `info->chip >= 7` stays wrong either way -
    the rule is not a chip capability).

    What is actually duplicated, read off the shipped diff: the *synthesis* (an inline
    `VkFormat[64]` plus its own `VkImageFormatListCreateInfo` in the create path, the same
    thing again behind `or_class()`), and the *decision* (the tail of
    `forces_linear()`, repeated in `tu_image_init()` as an inline copy of the three
    predicates). Plus a naming cost: `fmt_list` is shadowed with the synthesized list, so
    the `perf_debug` line says "fmt list present" about an image whose application passed
    none, and only `ubwc_list` holds the truth. `exp-21` removes all three: one static
    `mutable_compat_class()`, the create path calls `forces_linear()` like the query does,
    `fmt_list` keeps its meaning, and the class is handed to the layout predicates only -
    `tu6_mutable_format_list_ubwc_compatible()` sees the application's list and nothing
    else, which is the seam `exp-18` needs (the strict class, not the block one: journal
    24.4). Two lines of `forces_linear()` change and both are about reachability, not about
    an image: NV12 answers "not linear" (what `0009` decided; its other caller is the sparse
    query, which refuses multi-planar formats before asking), and the class no longer reaches
    the UBWC predicate (`fd6_ubwc_compat_mode()` has one row per format, so a class of two or
    more members is never "compatible" - no consequence today, structurally the wrong seam).

    Not smaller, and the item should not pretend otherwise: `0014` is 5 hunks `+128/-5`,
    `exp-21` is 7 hunks `+127/-16`, `exp-21b` 4 hunks `+16/-18`. It buys one decision path
    instead of two and a public surface that does not grow (`0014` exports
    `tu6_mutable_compat_class()`; `exp-21` exports nothing and `exp-21b` returns the three
    predicates to `static`). Applying either to the current stack asks no rebase - both
    were generated against `0001..0013`, pass `git apply --check`, and revert to the same
    `+529/-77` (verified 20.11). The ownership that matters for a *future* rebase:
    `format_list_has_swaps()`/`format_list_reinterprets_r8g8_r16()` were statics in
    `tu_image.cc` at the base and `0004` moved and exported them, `swaps_are_uniform()` is
    `0005`'s and `0010` rewrote it - so `exp-21b` touches the hunks of three patches, which
    is why it is its own file and its own gate.

    Four things it must not enter, each with the record that says so: `is_mutable`/
    `MUTABLEEN` (journal 21.4, 14.5.1, ADR-0009); the UBWC predicates
    `format_list_ubwc_possible()` and `tu6_mutable_format_list_ubwc_compatible()` - that is
    exp-18 and it needs the strict class, not the block class (journal 24.4, 27: +0.2 %);
    `props.ubwc_all_formats_compatible`, which has three consumers and would also move the
    sparse gate and the sparse create refusal (journal 24.1, 24.3, ADR-0001); and the
    `0004` refusal for classes that still force linear, without which the silent-zero
    sparse hole returns (ADR-0002).

    Gate, in this order:

    1. an **equivalence run** - **met 21.11, both halves**. Rig half: the same test binary
       against the two drivers with the **full logs** compared, 0 differing lines (journal 33).
       Game half, the form this item asked for first: two inventory runs on `build/out-exp21`
       against the `imginv5` column, read per create
       (`results/test-exp21-inventory-ab.log`, journal 36) - 784 create signatures present in
       both sessions, **0** with a different `tile=`/`ubwc=` verdict, 0 signatures present in
       only one of them, and the same class shares (32-bit and 16-bit still 0.0 % tiled, the
       no-list tiled volume 2 438.6 MiB against the reference 2 450.3). The first of the two
       runs had `MANGOHUD` off while the reference had it on, which cost 19 create signatures
       to an overlay font atlas; journal 36 keeps that as the record of the confound.
    2. ~~the 94-row matrix~~ - **corrected 21.11**. The sentence this one replaces asked for
       the matrix as part of this gate; the matrix is produced by `scripts/run-b2i-matrix.sh`
       on a driver carrying the `exp-15` rig, and neither `build/out-exp21` nor the released
       build has it (`grep -ac TU_B2I_SYNC` = `0` on both). So the item is not pending, it
       does not apply to a build of this tree: the matrix gates *tiling* changes, and
       `exp-21` moves no layout for any create that has a list. The rig rows that do apply
       are the ones the equivalence already covers - `NL`, `XV`, `UBR`, `S`, `N` - and
       `0014` v2 is why "the counter is green" is not a gate (ADR-0006);
    3. only then decide `exp-21b` and the graduation, and re-run the probes of
       `0005`/`0009`/`0010` after their context moves.

12. **The driconf perf options the props search never covered** (journal 34; no build
    needed, no new code). Five options are perf-relevant and off for this game; two are
    candidates, one is held on a precondition that fails, one is a feature trade and one is
    unreachable on a740 (journal 34.2, and journal 35.1 for the held one).
    `TU_FORCE_PROPS` (journal 15) covers boolean device properties, and the
    env switches of journal 13/15.5 cover autotune and draw states. Neither touched Turnip's
    `perf`/`misc` driconf groups (`src/freedreno/vulkan/tu_drirc_gen.py`), which are overridden
    by an environment variable of the same name and change the command stream:

    * `tu_disable_conservative_fdm_binning` - **held, not a candidate yet** (journal 35.1): the
      option is gated on `pass->has_fdm` at both of its sites, and a render pass can only have an
      FDM attachment if an image was created with the density-map usage bit. The game's three
      inventories contain 0 such images in 11 984 creates, so in the inventoried scenes the option
      cannot fire, whatever its upstream number ("**Improves performance up to 4% on A7XX.**") is
      worth. It returns to the queue only after a game run shows an FDM attachment, which needs a
      one-line driver log and a build;
    * `tu_allow_concurrent_binning` - A7xx concurrent binning, disabled by default "because it
      regresses performance on desktop games", where the phrase describes an x86 discrete GPU
      rather than this SoC running a desktop game through vkd3d-proton;
    * `disable_conservative_lrz` - stops the conservative default from disabling LRZ writes on
      draws that blend and write depth (`tu_lrz.cc:1524`, `:1533`); safe only if the game does
      not contain the three-draw sequence the code comment above those lines spells out, which a
      screenshot comparison is supposed to answer.

    Correctness on every shape the rig creates is already established (journal 34.3,
    `results/test-perfprops-rig.log`: four forced runs, 0 differing lines of 621, each carrying
    the driver's own `ATTENTION: ... overridden by environment` line) - and is explicitly not a
    verdict, because all three act in a renderpass and the rig has no textured depth renderpass.

    What is left is the fps A/B, which needs the game and therefore most of the 7.3 GiB of this
    machine (`free -m` at the time of journal 34: 1.1 GiB available). Protocol as in journal
    15.5, interleaved within one session, `HUDINTERVAL=100`:

    ```sh
    source scripts/env.sh
    TAG=cb1  tu_allow_concurrent_binning=true         HUDLOG=150 scripts/run-game.sh patched 170
    TAG=lrx1 disable_conservative_lrz=true            HUDLOG=150 scripts/run-game.sh patched 170
    # plus a base run between each, and scripts/fps-window.py for p25 over frames with fps < 30
    # the FDM option is not in the list: journal 35.1 shows it has nothing to attach to in the
    # inventoried scenes, so forcing it would measure an inert switch
    ```

    Gate order per option: a screenshot pair (`HUD=1`, the same camera position as the base
    shot, compared with `scripts/pixelcheck.py`) **before** any fps number - both remaining
    options change what is drawn: LRZ invalidation is a correctness trade by definition, and
    concurrent binning can drop primitives when a binner and a raster pass disagree (the same
    class of risk the FDM option documents as see-through gaps). An option that gains fps and
    changes the picture is a trade the operator decides on, not a patch. vkmark, the second rig
    of journal 15, is no longer installed, so the game is currently the only workload that
    exercises these paths.

    Expectation, said before the run rather than after: the wall is `UCHE` at 90 % busy and
    ~220 ns to `VBIF` (ADR-0008), and every lever tried so far on this game has been zero, so
    both remaining candidates are likely zeros. That is a reason to run them in one evening
    session, not a reason to skip them: neither has ever been asked here.

13. **What the game does when the driver reports less memory** (journal 34.4; no build, no new
    code). The other kind of option in the same surface: not the command stream but the report.
    `heap_memory_percent` (a "common vk" driconf option, `tu_drirc_gen.py:8-12`, environment name
    `heap_memory_percent`) feeds `tu_get_system_heap_size()`; at its default `0.0` the driver takes
    the heuristic branch and reports a percentage of RAM as the one DEVICE_LOCAL heap - the numbers,
    measured on this machine, are owned by journal 34.4 and `results/vulkaninfo-heap-report.log`,
    four `vulkaninfo` runs. The reported budget is separate
    and follows free memory (0.9 of it, hard-coded at `tu_device.cc:2269`), so it needs no patch to
    be honest, only a smaller heap to become the binding number.

    Why this and not another probe: journal 17 measured vkd3d peaking at 3129 MiB of its own
    resources, turnip holding 3490 MiB of BOs, system RAM 7.24 of 7.32 GiB and swap 4.95 GiB. The
    report is bigger than what the machine was able to back. Nothing here says the report is wrong,
    and nothing here says shrinking it helps - what vkd3d-proton does with a smaller heap is
    unmeasured, and on a driver with one memory heap it may equally fail an allocation.

    Run with the game, one option at a time, interleaved with base as in journal 15.5, and the
    memory logging of journal 17 rather than a bare fps number:

    ```sh
    source scripts/env.sh
    TAG=hp50 heap_memory_percent=0.5 VKD3D_CONFIG=log_memory_budget VKD3D_DEBUG=info \
        HUDLOG=150 scripts/run-game.sh patched 170
    # base run between each; compare vkd3d's peak, the MangoHud ram_used/swap_used, and p25
    ```

    Values to try: `0.5` (the heap then sits above journal 17's vkd3d peak - the safe probe) and
    `0.4` (just below it). Both are measured rows in the artifact, so the game runs start from
    reported sizes that are known rather than computed. Not the 0.05 that the artifact uses as a
    control: that is a cap demonstration, and an allocation failure there would be an artefact of
    the value, not a result.

    Record the reported heap **and** the reported budget at every value, and expect them to differ.
    Re-reading the artifact (2026-11-21) pulls out the number that decides how much this check can
    show: while the heap is reported as 5.49 GiB, the budget is reported as 980 MiB, because
    `vk_physical_device_heap_budget()` (`vk_physical_device.h:180-198`) takes the smaller of the heap
    and `0.9 x MemAvailable + heap_used`, and this machine had under 1 GiB free in every one of the
    five runs. So the number an application is told it may reach is already about five times below
    the heap here, and a run at `0.5` or `0.4` may move a figure that was never binding. Only logging
    both separates "no effect" from "effect on the loose number".

    What each outcome would mean, said in advance: lower swap with the same vkd3d peak means the
    engine was sizing itself against the report and the report was misleading; the same swap and
    the same fps means the report is ignored by this stack and the whole branch closes with a
    measurement instead of a guess; an allocation failure or a black screen means vkd3d trusts the
    report and the branch closes too, in the other direction - and in that case the honest artifact
    is the failure, kept in `results/`.

14. **DX11 against DX12 on the same scene - the API-isolation check** (no code, one game
    session, and a decision first). The inference to be tested is the operator's: if the block
    profile of the wall (VPC ~91 %, PC waiting on VPC 63 %, UCHE 90 % with ~39 % arbiter stall,
    TP and VFD starving on UCHE ~48-51 %) comes back the same through the DX11 branch (DXVK) as
    through the DX12 branch (vkd3d-proton), the wall is not in the translation layer and not in
    `sparseResidencyImage2D`, but in what the RE Engine asks of this GPU and of turnip - and the
    levers that remain would act on both branches at once.

    Status of the premise: **never established.** Journal 11.2 records one attempt, via
    `[Render] Capability` in `local_config.ini`, and it failed for a known reason - the game
    rewrites the key, it is an output, not an input. The route that was never tried is the command
    line: `re4.exe` carries `via.render.RenderDeviceAPI` with the strings `DirectX11` /
    `DirectX12` / `OpenGL` / `Vulkan`, and `scripts/run-game.sh` takes `GAMEARGS=` for exactly
    this. So step 0 is getting a DX11 launch at all, and its discriminator is in the game log:
    the vkd3d markers (`d3d12_device_create`, the SM 6.6 feature block) must **disappear**, and the
    game must write `DirectX11` into `[Render] Capability` of the prefix's `local_config.ini`
    (reading that file is how the API is verified, per the script header - it cannot be told by
    eye). If the vkd3d markers are still there, the game is still on DX12 and no measurement was
    taken.

    Then measure the same thing twice, with `tools/fdperf/fdperf.cfg-vertex`:
    `scripts/fdperf-sample.sh <sec> <window-ms> <file> tools/fdperf/fdperf.cfg-vertex`, and compare
    **ratios, not levels**: per-client DRAM reads (the TP/VFD/PC/SP split), UCHE busy and its
    arbiter stall, `VFD_STARVE_CYCLES_UCHE`, vertices per primitive, draws per frame. Levels are
    not comparable: the two DX12 runs of 17.11 already differ by content (14.7 fps against mean
    23.5, both recorded in their `steady-state.txt`), and a DX11 branch changes content further
    (no ray tracing, different preset). Journal 38's window rule applies: only quantities that are
    ratios inside one sample set travel between runs.

    Said in advance, what each outcome would mean: the same ratios on both branches excludes the
    translation layer and D3D11-vs-D3D12 sparse residency as the cause of the wall, and moves the
    lever search to the vertex/geometry side (queue 15) and to the game's own settings, both of
    which act on both branches; a different split - e.g. the TP share of DRAM reads collapses -
    means part of the wall has an API-side cause, and the DXVK branch becomes the ground for
    measuring that part. Two caveats to carry into the run, both from journal 11.2: a DXVK run
    verifies nothing the vkd3d patch stack was made for (no `12_0`, no SM 6.6 there), it speaks
    about the driver and about the wall; and if the DX11 branch does not render on this driver,
    the honest artifact is the failure log in `results/`, not an inference. Blocked with queues
    12 and 13 on the same thing: the memory wall of this machine (7.32 GiB, the browser has to be
    closed before `scripts/run-game.sh`).

**Closed 21.11, journal 40.6** - the game cannot be put on DX11 by any route tried here. The command line
carries no DX-flavoured flag: `grep -a -o -E '.{0,18}-[a-zA-Z_]*dx[12][12]?.{0,18}'` over the
233690016-byte `re4.exe` prints nothing, and `via.render.RenderDeviceAPI` / `DirectX11` / `DirectX12`
appear only as the reflection enum. Launching with `GAMEARGS="-dx11"`, with `GAMEARGS="-forceDX11"`, and
with `WINEDLLOVERRIDES='d3d12='` (the dll disabled, so neither vkd3d-proton nor a wine builtin can be
loaded) left all three runs on D3D12: `results/game-patched-dx11dx11.log`, `…-dx11forceDX11.log` and
`…-d3doff.log` each still contain `d3d12_device_create_vkd3d_queues`, and the game rewrites
`Capability=DirectX12` into `local_config.ini`. Renaming the prefix's `d3d12.dll`/`d3d12core.dll` was
rejected without running it: that would route the game to wine's own D3D12-on-wined3d, which answers
nothing about DXVK. `VKD3D_FEATURE_LEVEL` is closed as a lever separately (journal 40.6): vkd3d-proton
v3.1's `d3d12_device_caps_override` only raises capabilities and assigns `max_feature_level`, and `11_1`
against `12_1` measured identical to 0.1 point on every block ratio. The API-isolation check stays closed
until a title that can choose its API is on this machine.

15. **The VPC/varyings question, and the counters that can actually ask it** (cfg written 21.11;
    one game session, shared with 12/13/14). Two claims were put forward as the next lever: ir3
    leaving non-position work in the *binning* vertex shader (so VFD and VPC pay per mesh twice),
    and excess or unpacked varyings saturating the VPC. Journal 38 worked out what is already
    answered, from the committed dumps of the two 17.11 runs - and it is more than expected:
    `VPC_VS_BUSY/VPC_BUSY` 92.8-96.4 %, `VPC_WORKING/VPC_BUSY` 66.9-69.3 %, VPC stall on UCHE
    0.00 %, 1.03 vertices fetched per input primitive against 3 submitted (reuse ~2.9:1), and
    `VPC_NUM_ATTR_REQ_LM` at 0.50 per vertex against ~5 attributes per vertex. The binning half is
    closed by the compiler source: `lower_binning()` deletes every binning-variant output that is
    not position/psize/clip/viewport/layer (`ir3_nir.c:1204-1233`), and the attribute loads are
    kept deliberately ("binning and draw pass VS use same VBO state", `ir3_compiler_nir.c:6007-6030`)
    - so the residue of double vertex work is fetch-side, not varying math; `tu_pipeline.cc:690`
    also records that "varyings are packed" already (`tu_pipeline.cc:685`). And no a7xx counter names binning at all, so
    the two passes cannot be separated by counters.

    What still needs the run, and is the only reason to spend it: `VPC_PS_BUSY_CYCLES` (17) - never
    measured, and until it is, "the interpolate side is idle" is not supported, only unmeasured;
    `VPC_SP_COMPONENTS` (10) and `VPC_NUM_VPCRAM_WRITE` (25) - the first quantities that say what
    flows through the VPC per vertex; `VPC_LM_FULL_WAIT_FOR_INTP_END` (24) - the interpolate-wait
    signature; `PC_VERTEX_HITS` (19) - the direct measure of the 2.9:1 reuse; and
    `UCHE_WRITE_REQUESTS_SP` (15) / `UCHE_WRITE_REQUESTS_VPC` (16), the per-client **write** side
    that no cfg has ever carried. All of them are in `tools/fdperf/fdperf.cfg-vpc` inside the group
    hw budgets (VPC 6/6, PC 8/8, UCHE 12/12), with the selectors read out of
    `a7xx_perfcntrs.xml` as its header records; `scripts/fdperf-analyze.py` gained the rows.

    Pre-register the reading so the run cannot be talked into a conclusion afterwards: if
    `SP_COMPONENTS / VS_INVOCATIONS` is large and moves with `NUM_VPCRAM_WRITE`, while `PS_BUSY` is
    a real share of `BUSY`, the VPC pressure is varying-side, and the only driver-side knob of that
    kind is the per-varying mode table `tu6_vpc_varying_mode()` / `tu6_emit_vpc_varying_modes()`
    (`tu_pipeline.cc:677-730` and `734-776`, interp mode and `PS_REPL_*`) - name the change after
    the number, not before it. If instead `PS_BUSY` stays a small share and `LM_FULL_WAIT_FOR_INTP_END` stays near
    zero while `VFD_STALL_CYCLES_VPC_ALLOC` (12.5 % in the 17.11 vertex run) does not move, the
    "varyings are choking the VPC" branch closes with a measurement and the remaining vertex
    question is the fetch side, where the measured facts already say ~1 vertex per primitive and
    5 attributes per vertex. This item produces no patch by itself; it says whether a patch is
    worth proposing, and ADR-0008 (no driver-side fps lever found for this game) is the prior it
    has to beat.

16. **The value of what `0014` v1 already shipped - 2450.3 MiB of no-list textures, never measured**
    (no new patch: one hand-made build without `0014` in a copy of the tree, one game session with the
    sampler; shares the machine with 12/13/14/15 and with the 7.32 GiB memory wall).

    Journal 39 closed the half of the no-list question that wanted *more*: the 1024 creates /
    1630.8 MiB left in linear are required linear by the Vulkan compatibility-class rule (the class of
    an uncompressed colour format is its texel block, `src/vulkan/registry/vk.xml` `class=` rows quoted
    in 39.1) plus the fact that the A740 tiled path cannot express a reinterpreting view's order
    (`fd6_pipe2swap()`, `fd6_format_table.c:399-404`, with `is_mutable` false on this path). No
    predicate - `!is_swapped_format(base)`, an `is_r8g8` subclass, anything - can narrow a set that is
    defined by the block size, so there is no v3 to write and no value question to ask about those
    bytes. What is left is the half that is already in the release: v1 moved 1450 creates /
    **2450.3 MiB** from linear to tiled (`results/nolist-residue-p14.log`, regenerate with
    `python3 scripts/nolist-residue.py results/raw/game-patched-imginv5.log`), and that has never been
    measured for traffic or fps - journal 21.12 says as much about its own run ("fps is not what this
    run measures - the inventory is"), and the 17.11 fdperf runs predate `0014` (entries 21.11 and
    21.12 are both dated 18.11), so the committed profile - TP 12.0 GB/s of 14.8, 81 % of DRAM reads,
    `results/fdperf-mesa27-vertex/steady-state.txt` - is a baseline with those images in linear.

    ```sh
    # A = the ship stack as released.  B = the same stack without 0014, in a COPY of the tree:
    #   `git apply -R patches/0014-*.patch` does not work (journal 39.7 measured it: the tree's 0014
    #   text and the committed patch file are different texts), so B is made by hand in a copy.
    cp -a ../mesa27-src ../mesa27-src-no0014          # 370 MB, 23 GB free
    # in the copy, put the NULL back where 0014 substituted the class - tu_formats.cc:351
    #   mutable_views(): return fmt_list unchanged, and drop the fmt_list==NULL branch at :409
    #   (that is the state the stock predicates were written for; the added functions become dead)
    # build B from the copy (container, -j2, docs/howto-measure.md), record its .so hash
    # ACCEPT B only if exp-14's inventory shows the pre-0014 signature: MUTABLE with listn=0 and
    # 0 MiB tiled, the imginv4 row of results/imginv-3variants.txt.  Never the .so hash.
    # one session per build, base run between them, sampler on the steady stretch:
    scripts/fdperf-sample.sh 130 1000 results/fdperf-0014ab/A.txt tools/fdperf/fdperf.cfg-vertex
    python3 scripts/fdperf-analyze.py results/fdperf-0014ab/A.txt
    HUDLOG=150 scripts/run-game.sh patched 170
    # the ship tree is never touched by this: B lives in ../mesa27-src-no0014 and is deleted after
    ```

    Compare ratios inside one sample set, never levels (journal 38: the two 17.11 runs are 14.7 against
    mean 23.5 fps of different content, and only within-run ratios travel). The quantities: TP's GB/s
    and its share of DRAM reads, `UCHE` busy and its arbiter stall, the TP starve counters, fps.
    Pre-registered reading: if 2450.3 MiB of linear-to-tiled changes neither TP's 81 % share nor its
    GB/s measurably, then the largest layout change in this stack is worth no traffic, ADR-0008 gains a
    second and much bigger instance, layout closes as a lever and `0014` stays only because it is
    correct and free. If TP traffic falls and fps does not move, the wall is confirmed elsewhere and
    queue 15 is the only vertex question left. If fps moves, the number belongs in `docs/release.md` as
    the first measured gain of a shipped patch - and the run is invalid unless the inventory of that
    same build still reports the same 2450.3 MiB tiled, checked with the script above.

17. **The autotune cost model, nudged the way an outside build nudges it** (journal 30's
    addition; one line, one build, and a probe first that needs neither).
    `WinNative-Emu/Drivers` ships a "-b (balance)" variant whose only Turnip change left over from
    upstream restructurings is the GMEM bandwidth multiplier: `apply_balance_variant.py` rewrites
    ```c
    gmem_bandwidth = (gmem_bandwidth * 11 + total_draw_call_bandwidth) / 10;
    ```
    (`../mesa27-src/src/freedreno/vulkan/tu_autotune.cc:1065`, whose own comment says "The magic
    numbers of 11 and 10 are randomly chosen") to `* 10`. That is not a bandwidth change: it moves
    the estimate from `1.1g + 0.1d` to `g + 0.1d`, so the `select_sysmem = sysmem_bandwidth <=
    gmem_bandwidth` decision at `:1066` shifts by 10 % of the pass' GMEM bandwidth **towards GMEM**.
    Their other tweak, `drawcall_count > 5`, does not exist in this tree - the gate is now
    `mod_flag::BIG_GMEM && rp_state->drawcall_count >= 10` (`:1881`) with the old `< 5` living in
    `ignore_small_rp` (`:1862`) - which is also their own MAINTENANCE.md note, verified here.

    Step 0, before any build of the tweak: does RE4 ever select SYSMEM at all? The decision is
    printed only by `at_log_bandwidth_h`, and that is behind the compile-time
    `TU_AUTOTUNE_DEBUG_LOG_BANDWIDTH 0` (`tu_autotune.cc:25-30`), so there is no env way to see it -
    it needs an `exp-24` hook (flip that one constant, NOT FOR SHIP) and one session, then count the
    `autotune-bw <hash>: selecting SYSMEM|GMEM` lines per render-pass hash. If the game never picks
    SYSMEM, the tweak is inert for RE4 by construction and this item closes without a second build.

    Pre-registered reading if step 0 does show SYSMEM passes: only decisions inside that 10 % band
    can flip, so a zero is the likely answer - and the direction is one this machine has already
    paid for: journal 15.5 measured `TU_AUTOTUNE_FLAGS=big_gmem` at -1.5 fps (about -12 %) on this
    game, i.e. "more GMEM" is the harmful side, not the neutral one. A gain would be the first
    measured fps gain from an autotune change here, and would need the opposite nudge (`* 12`) to
    show that the direction is the mechanism rather than run noise.

18. **The TSE discard: 71.9 % of the primitives die after the vertex path, so where can a reject move?**
    (journal 40.2; two cheap runs and one decision, no build). Measured on the ship stack: TSE input
    255.19 Mc/s, visible 71.62 Mc/s (28.06 %), and the discard is 21.1 % trivial-reject, 17.7 %
    face-culled, 27.0 % zero-pixel, 0.33 % zero-area, 0.14 % clipped. Three sub-steps, in order of cost:

    a. **Is the equality real or tautological?** In four dumps `PERF_TSE_INPUT_PRIM` and
       `PERF_PC_IA_PRIMITIVES` are identical to the sample (ratio 1.0000), which is read as "nothing is
       discarded between the IA and TSE". It could also be the same counter exposed twice. One run with a
       cfg that samples only one of them and a known-different second one settles it; until then journal
       40.2's wording ("two readings, not decided") is the wording to repeat.
    b. **Repeat `TU_AUTOTUNE_ALGO=prefer_gmem`** (1-2 runs, `fdperf.cfg-tse`, `fdperf-tse-ratios.py`) so
       that 13.72 against the 15.15-15.24 cluster becomes a number of record instead of a single run -
       journal 40.4 already shows it does not touch the discard ratio (73.8 % against 71.9 %), so this is
       about the frame-rate cost, not about the lever.
    c. **Only then decide where a reject could move.** The driver writes no reject state before TSE that we
       control: `PC_PRIM_VTX_CNTL` (whose degenerate bits would do it) is not emitted anywhere in
       `src/freedreno/vulkan/` - `grep -rn PC_PRIM_VTX_CNTL src/freedreno/vulkan/` gives nothing, the state
       comes from CP microcode - and the degenerate population it would remove does not exist (0.33 %
       zero-area). The face-cull 17.7 % needs projected area, i.e. post-VS by construction. What is left
       is the 21.1 % trivial reject (outside the viewport) and the 27.0 % zero-pixel: the first is the only
       one a driver could in principle move earlier, the second is a property of the mesh, and the honest
       first experiment for it is a game-settings A/B (mesh quality / LOD bias), not a Mesa patch.

**Closed by measurement and by the source, 21.11, journal 40.2/40.8.** The three sub-steps came back
this way: (a) the `TSE_INPUT_PRIM == PC_IA_PRIMITIVES` equality holds in four dumps of different cfgs,
which is either "nothing is discarded before TSE" or the same counter exposed twice - the wording stays
undecided, but the discard itself is measured (71.9 %, with the reason breakdown of 40.2). (b) The
`TU_AUTOTUNE_ALGO` arms and the `TU_DEBUG=forcecb` arm all leave `VSC_BUSY` at 0.21-0.65 % of the core
and the discard at 71.8-73.8 %, and the driconf default in this tree is `tu_allow_concurrent_binning =
False` (`tu_drirc_gen.py:31`, "the CB is disabled by default because it regresses performance on
desktop games"), with nothing in `/usr/share/drirc.d/00-turnip-defaults.conf` turning it on: there is no
binning pass in this workload to hand the geometry to. (c) The varyings question is answered by the
mechanism, not by a counter: `ir3_link_shaders` (`ir3_shader.h:1387`, called at `tu_pipeline.cc:802`)
walks the **fragment shader's** inputs and derives `varmask` and `max_loc` ("the size required for each
vertex in the VPC in DWORD's") from them, so a VS output the FS does not read is neither fetched nor
counted in the per-vertex size; and the measured payload is small (`VPC_NUM_VPCRAM_WRITE` 2.62 per
invocation, `VFD_NUM_ATTRIBUTES` 5.08 per vertex). What remains open in this queue item is only the
semantics of `VPC_PS_BUSY` (no `desc=` in the XML); `fdperf.cfg-vpc3` was run as part of queue 19 below.

19. **Closed 21.11, journal 40.9: the VPC attribute buffer is not a lever.** The premise was that on
    A740 the sysmem attribute buffer is a too-small 0x20000; in this tree the answer is that our
    generation never programs one at all. `emit_vpc_attr_buf` (`tu_cmd_buffer.cc:647-652`) returns
    immediately unless `props.has_gmem_vpc_attr_buf`, and that property with
    `sysmem_vpc_attr_buf_size = 0x20000` / `gmem_vpc_attr_buf_size = 0xc000` exists only in `a7xx_gen3`
    (`freedreno_devices.py:854-856`), not in `a7xx_base`/`a7xx_gen2`. Upstream's own probe
    `TU_FORCE_PROPS=has_gmem_vpc_attr_buf` substitutes those sizes and logs
    `TU_FORCE_PROPS: vpc_attr_buf_size sysmem=0x20000 gmem=0xc000` (`tu_device.cc:1799-1806`), and the
    log of `results/fdperf-vpc3-attrbuf/` carries 9 such lines against 0 in the control, so delivery is
    proved. Measured with `tools/fdperf/fdperf.cfg-vpc3` (`vpc3base` against `attrbuf`,
    `scripts/fdperf-vpcram-ratios.py`): VPC busy 91.70 % against 90.86 %, `VPCRAM_FULL` 50.84 % against
    50.82 % of busy, `WIT_FULL` 1.25 % against 1.25 %, `STALL_CYCLES_VPCRAM_POS` 0.44 % against 0.42 %,
    p25 14.71 against 14.73 fps. Nothing moved, so no `a7xx_gen2` device-props change is proposed. The
    one number worth keeping from this pair is `VPC_VPCRAM_FULL_CYCLES` at ~51 % of the VPC's busy time:
    the largest single named component of the wall found so far, and it does not respond to the
    attribute buffer. `STALL_CYCLES_LM_ACK` and `NUM_LM_REQ_HIT` read exactly 0 in both arms, so the LM
    hit rate is `NOT MEASURED` rather than 0 %.

20. **Closed 22.11, journals 40.11 and 40.12: the `BV_*` groups are addressable, and in the runs that
    were made they had no work to do.** `tools/fdperf/fdperf.cfg-bv` names `BV_VPC`/`BV_TSE`/`BV_PC`/
    `BV_TP` and the selects land: on an idle GPU the BV half of the same slots prints the requested names
    (`PC_IA_PRIMITIVES`, `VPC_VPCRAM_FULL_CYCLES`, `TSE_INPUT_PRIM`) where a cfg without BV sections
    prints the group's first countables (`results/fdperf-bv-idle-labelcheck.txt`). The register map in
    `a7xx_perfcntrs.json` says how separate they are: `BV_PC`/`BV_VFD`/`BV_VPC`/`BV_TP`/`BV_SP`/`BV_UFC`
    share their ordinary twin's select register with a `select_offset`, `BV_TSE`/`BV_RAS`/`BV_LRZ`/
    `BV_HLSQ`/`BV_CP` have none and so share the very words; the value registers are separate.
    Measured (`cfg-bv`, six arms `results/fdperf-bv-*/`, p25 15.15-15.29): the BV banks report
    0.06-0.08 % of the core on their own `BUSY`/`WORKING` counters and 0/s on every per-primitive counter
    in them (`BV_PC` `PC_IA_PRIMITIVES`, `BV_TSE` `TSE_INPUT_PRIM`/`TSE_OUTPUT_VISIBLE_PRIM`, `BV_VPC`
    `VPCRAM_FULL`/`WIT_FULL`), with CB off and with `TU_DEBUG=forcecb` whose delivery the driver logged
    (`tu_util.cc:135`, `TU: info: TU_DEBUG=0x1000000001`). Two things the measurement is **not**: it is
    not a statement about a working BV thread, because 40.12 shows the 22.11 sessions had no binning pass
    to count: every forced arm read 0 tiles in every window (`cfg-tse3` and plain `forcecb` included),
    and the unforced `bvbase` fed tiles only in the 22 windows where the core was not at the pinned clock
    (median 16/s), against 1,532/s in all 88 windows of the 21.11 `cbforce` arm; and the earlier habit of
    reading the unprogrammed BV half is dead - whole groups of it mirror the ordinary counter
    (100.0-100.6 % in `cbforce`), which is also what settles the 950-967 % `BV_TP` number 40.8 left
    uninterpreted (the 12-instance TP sum, mirrored). Queue 21 asks the real question again in a session
    that bins.

21. **Get one run where CB actually engages, and read the BV counters in it** (no build; journals 40.11
    and 40.12 leave the question here). On 22.11 every forced arm read `VSC_INPUT_TILES` = 0 in every
    window - `cfg-tse3` without any BV section included, and with `forcecb` delivered and logged - where
    21.11's `cfg-tse3` + `forcecb` arm fed 1,532 tiles/s in all 88 windows and its CB-off twin in 32 of 40
    at a median of 56/s (`results/fdperf-tse3-cbforce/`, `results/fdperf-tse3-cbbase/`,
    `scripts/fdperf-tile-table.py`). So the flag was set and the driver still did not bin: `forcecb`
    clears one gate (`tu_cmd_buffer.cc:3506`) and the other reasons (`cb_disable_reason`) stay, and what
    decides them is not visible in any log of this repository. Arms: a scene or stretch where the tile
    counter is nonzero again - the first step is to find one, and the cheapest probe is a short `cfg-tse3`
    sampling run over a longer session, since the 21.11 arms produced tiles at the same clock and content
    type - then that arm with `cfg-bv` and no flag, and the same with `forcecb`. One hint from 40.12 about
    where to look: the only 22.11 windows that fed tiles were `bvbase`'s 22 windows whose
    `CP_ALWAYS_COUNT` was below the pinned clock (median 649 MHz), and its 16 pinned-clock windows fed
    none - so a stretch where the geometry node has slack is the candidate, and the clock has to be read
    in the same sample, not assumed. Reading fixed now: if during windows with tiles > 0 the `BV_TSE`
    `TSE_INPUT_PRIM` and `BV_PC` `PC_IA_PRIMITIVES` stay 0, the BV thread provably never runs primitives
    and the CB direction is closed by direct measurement; if they rise, journal 40.2's discard has to be
    re-asked per thread, because the ordinary TSE counters then describe only the non-bin pass. Caveat
    carried forward: an unprogrammed `BV_*` half is not a measurement (40.11: whole groups mirror the
    ordinary counter), so the comparison has to be made inside one `cfg-bv` run, between its own ordinary
    and BV halves.

Not in the queue, because closed by a record: `ubwc_all_formats_compatible` on gen2
(ADR-0001), 0015/MUTABLEEN as a game fix (ADR-0009), the `ubwc_coherency_quirk` on gen2
(ADR-0010), BC + UBWC (ADR-0004), any 8bpp UBWC patch (ADR-0007), removing any shipped patch
(`patches/DROPPED.md`), and tiling the no-list residue by splitting the class on the base format -
built and measured wrong as `0014` v2 (`patches/DROPPED.md`, the `XV` rows of
`results/test-0014v2-matrix.log`), and closed again on the spec's own class rule in journal 39, so
the "which sub-split is safe" question does not need re-asking. Driver-side fps levers are closed
too (ADR-0008), with one exception:
the driconf `perf`/`misc` options of queue 12 are not among the switches that record measured,
so three of them are asked for once instead of assumed. Outside patch stacks keep
proposing versions of the ideas closed above: `journal 30` maps four files from one such
stack to these records, so the next outside proposal can be checked against a verdict
instead of against a build.

## Open questions

| # | question | status |
|---|---|---|
| 1 | the ~2 % lost on the first fill into a fresh image, inside the driver | the probe-side part is documented (journal 20); whether a driver-side component remains is not established, the hypothesis is the same CCU race (journal 21.10) |
| 2 | moving `WAIT_FOR_IDLE` into `ExecuteCommands` | proposed, +2 lines, NOT MEASURED |
| 3 | the price of mode 7 in RE4 | correctness matrix exists, no fps A/B |
| 4 | who creates the DEPOSED no-list images | vkd3d or DXVK, not separated (queue 6) |
| 5 | the 1024/262144 residue in the tiled run | unexplained, 0.39 %, does not change any verdict (journal 21.5) |
| 6 | fast clear under `_SFLOAT` (0012) | a byte round trip cannot see it; needs its own probe |
| 7 | 12_1 | blocked by `VK_EXT_fragment_shader_interlock`, which Turnip does not implement (ADR-0011) |
| 8 | the 32- and 16-bit classes in lazy deposition | they reinterpret the layout; a separate analysis, and the reason 0014 leaves them linear on purpose |
| 9 | R8 + UBWC: writer or reader | exp-19 (queue 2) |
| 10 | UBWC format variants for `R16G16B16A16_FLOAT` and `R32G32_FLOAT` | answered, journal 31: there is no "format variant" to look for (UBWC is a layout flag, and the layout never consults `fd6_ubwc_compat_mode()`); the class has a ceiling, both formats reach it as plain images, and `0012` is what gives them a compat mode - on the bare Mesa 27 base their classes lose UBWC |
| 11 | does vkd3d view a mutable RE4 image through another format of the same class | NOT MEASURED, exp-20 (queue 10): the inventories record creates, not views |
| 12 | is a `VkImageFormatListCreateInfo` with `viewFormatCount == 0` the same as passing no list | NOT MEASURED, and `exp-21` deliberately keeps `0014`'s answer (an empty list is forwarded, and the predicates answer it as the worst case). The spec's wording makes them equal, but the inventories cannot tell the two apart - both are `listn=0` - so this is not a question a replay answers |
| 13 | why does the system driver give UBWC to a `MUTABLE` image with no list, where both Mesa 27 builds refuse it | ONE ROW, journal 31: `B8G8R8A8_UNORM`, `nolist=0x102000` against `0x100000`. Not in the two refusal functions (byte-identical to refs `mesa-26.2.6` and `main`), so it is either elsewhere in 26.2 or in the distribution's own patches (`mesa-vulkan-drivers-26.2.6-1.fc44.armada`, not in this repository). Chasing it would need the downstream source; it changes no verdict, and `exp-18` does not depend on it |
| 14 | does a `R64_UINT`/`R64_SINT` view of a UBWC image work, once `STORAGE` makes it legal | ANSWERED 21.11, journal 37: probe `XR64` built the shape and ran it - a no-list `MUTABLE` image with `STORAGE` in the usage, UBWC kept by the `TU_UBWC_NOLIST_64` knob of `experiments/exp-23-ubwc-nolist-64-knob.patch`, stays tiled with the `+0x2000` tail and reads `0/262144` wrong through an `r64ui` storage image, including after `imageAtomicAdd(+1)` per word. It also settled the shape question: a list that *names* `R64_*` is refused compression by `FD6_UBWC_UNKNOWN_COMPAT` with the knob on and off, so the no-list create was the only place the question could be asked at all. `results/test-xr64-nolist-64-ubwc.log`. Still open inside the answer: `sparseImageInt64Atomics=0` on this device, so the sparse corner is unmeasured, and journal 38 puts the class on the SP client, which is 0.3 % of measured DRAM reads |
| 15 | is the compressor actually writing compressed bytes, or only a metadata plane | NOT MEASURED by any rig here. Every UBWC claim in this repository rests on the `+0x2000` allocation signature, which journal 22.2 says is an allocation and not a compression claim. The direct detector is a fast-clear that leaves the bytes untouched in a UBWC image and does not in a linear one; it is not written, and journal 32's verdict is stated so as not to need it |
| 16 | does any of the reachable driconf perf options change fps in RE4 | NOT MEASURED, queue 12 (journal 34.3 covers correctness on the rig only, and the rig has no textured depth renderpass). Two candidates remain, `tu_allow_concurrent_binning` and `disable_conservative_lrz`, both expected zeros given ADR-0008; the third, `tu_disable_conservative_fdm_binning`, lost its precondition in journal 35.1 (0 density-map images in 11 984 creates) and is held until an FDM attachment is observed. Needs the game, so it needs most of this machine's 7.3 GiB |
| 17 | what does the game do when the driver reports less memory than the heap it reports today | NOT MEASURED, queue 13. The report itself is measured - journal 34.4, `results/vulkaninfo-heap-report.log`, five `vulkaninfo` runs over `heap_memory_percent` - and the queue names the two values to try in the game. What vkd3d-proton does under a smaller report is not, and journal 17's 3129 MiB peak against 4.95 GiB of swap is why the question is not empty |
| 18 | is any of the 22 shading-rate images ever attached to a render pass, and at what rates | NOT MEASURED. Journal 35.1 counts the images and journal 35.2 measures the capability, but a usage bit is a declaration: the driver has no log line for `subpass->fsr_attachment != VK_ATTACHMENT_UNUSED`, so the check needs one added `if` plus a build, then a game run. Without it, "the game uses VRS" stays an inference, and not even the driver's own per-subpass register write can be observed from a log |
| 19 | what did the 2450.3 MiB that `0014` v1 moved out of linear buy in traffic or fps | NOT MEASURED, queue 16 (no new patch: a B build without `0014` made in a copy of the tree - `git apply -R` does not work, open question 20 - then one A/B session). Journal 39 sizes what no rule can move (the 1630.8 MiB residue, required linear by the Vulkan class rule plus `fd6_pipe2swap()`), so this is the only no-list number left. The committed profile that looks like an answer - `results/fdperf-mesa27-vertex/steady-state.txt`, TP 12.0 GB/s and 81 % of DRAM reads - was sampled 17.11, and `0014` is journal 21.12, dated 18.11: that run is a with-everything-linear baseline, not a before/after |
| 20 | does the committed `patches/0014-turnip-mutable-no-list-tiling.patch` describe the tree that built the shipped `c17d02bcaae9…` | NOT SETTLED. Journal 39.7: `git apply -R --check` of that file fails on the recorded ship-stack tree at `tu_formats.cc:261`, and the texts differ by function names (`tu6_mutable_compat_class` vs the tree's static `mutable_compat_class`/`mutable_views`) and by comment wording. The difference cannot change a result, so no verdict in journal 39 depends on it - but it decides how queue 16 makes its B build, and a shipped patch file that is not the built text is a reference-table error worth fixing once, by regenerating the file from the tree and recording in `docs/release.md` which hash it belongs to |

## Pitfalls (reminder)

- `/tmp` is wiped: before a build, `meson setup` + `touch -d @0 build/PHONY`;
  silence from ninja is a trap, cross-check the mtime/hash of the .so.
- Quirks are **not cleared** at runtime (only props via `FD_DEV_FEATURES`/
  `TU_FORCE_PROPS`) - to "turn a quirk off" you need a build variant.
- Don't run two `run-game.sh` in parallel; a build and a game - not
  at the same time (RAM 7.3 GiB); `-j2`; fdperf ROOT only.
- Verification of each step: the patch is in the binary, the loaded driver = the built one
  (hash/mtime), CEIL controls; RC=0 from ninja is not proof of a build.

## Status (19.11, corrected 20.11): 0014 - the shipped form is v1, not the block rule

*Written 19.11, corrected 20.11. The text below used to say that on this branch `0014` is
the block-only rule and that the `XV` probe was the remaining gate. That was true at
19.11 noon; the same evening the block rule was built and measured broken, so the branch
keeps v1.*

What the correction is: `patches/0014-turnip-mutable-no-list-tiling.patch` is the shipped
form - it enumerates the base format's compatibility class and hands the predicates a
synthesized `VkImageFormatListCreateInfo`. The block-only variant is
`patches/dropped/0014-turnip-mutable-no-list-tiling-block-rule.patch`: it tiles
`RGBA8->BGRA8` and `BGRA8->RGBA8` on the tiled non-mutable path, and the failure is
visible in the `XV` rows while the 94-row counter stays EXACT (journal 24.3, ADR-0006).

The open part of that note survives, and it is exactly why the class rule is not extended
to UBWC casually: a read through a view of a *different member* of the block, on a tiled
image with UBWC off, has still never been measured, by either form.

Checked so far: `git apply --check` for 0001-0014 on `6dfa32a85f91`, no `--3way`
and no fuzz; the test compiles clean with `scripts/build-test.sh` flags. Not
built as a driver, not run: the device is the bench and the build script refuses
to start while `re4.exe` runs.
