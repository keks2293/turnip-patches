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

**Artifact:** `results/test-BCcopy-<name>.log`, a section in `analysis.md`.

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
  fails with the old BC3-512 signature, 256x128/512x64/256x256 pass. So the
  hypothesis space was never "BC units in A2D" - it is r2d readback addressing
  on small/odd geometries.
- Next: A/B of the programmed registers, failing vs passing geometries
  (`[GDBG-i2b]` dump, `results/test-BCcopy-geomdbg.log`), then either a
  register fix or the verdict "CP_BLIT HW behavior on A740" with BC copies
  routed through r3d (the original fallback).

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
a section in `analysis.md`; a header edit in `patches/0008-*.patch`.

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
- Early measurement (analysis §21.7): `FD_DEV_FEATURES=has_8bpp_ubwc=1` ->
  CEIL[R8] `nonmut=0x42000 > lin` ("the hardware can do 8bpp UBWC"), but the roundtrip
  readback is **all zeros** (65536/65536 MISMATCH) -> "HW corruption" -> keep False.
- The runtime override **works without a rebuild**: `FD_DEV_FEATURES=has_8bpp_ubwc=1`
  (it is a prop, `freedreno_dev_info.py`).

**What to check:**
1. **The exact source of False on A740**: confirm that the `GPUProps` default for
   an unset bool is False (the `GPUProps` class in `freedreno_devices.py`), and that
   on a7xx the flag was deliberately not raised (rather than simply forgotten).
2. **Re-interpreting the "HW corruption"**: all zeros in the readback is either (a) real
   HW corruption of 8bpp UBWC, or (b) the same **r2d copy bug** as with BC (block 0)?
   R8 is not BC, and the other non-UBWC formats roundtrip cleanly -> r2d works for them,
   so (a) is more likely. But isolate it: TP/compute readback of an R8
   UBWC image (if there are zeros there too - the corruption is in the UBWC decoder itself, not in r2d).
3. **Upstream**: do newer chips (a7xx_gen3 / a8xx) set `has_8bpp_ubwc=True`?
   If yes -> this is a **gen2-specific HW bug**, not
   "corruption in general" - rewrite the conclusion in §21.7 more precisely.
4. (optional) RE4 with `FD_DEV_FEATURES=has_8bpp_ubwc=1`: does RE4 use
   R8+UBWC, is there corruption/a fault in the game.

**Criterion:** a refined conclusion (gen2 HW bug vs default oversight; whether the "corruption"
is real vs an r2d artifact). Most likely **keep False**, but with an exact
justification.

**Artifact:** an edit of §21.7 in `analysis.md`, CEIL/U logs with the flag.

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

**Artifact:** an edit of the analysis of the 36 classes (`analysis.md` §21.6.3a), a CEIL log
with R32G32B32A32.

---

## Priority and order

1. **Block 0 (BC copy)** - re-framed 18.11: the 0012 verification premise is
   withdrawn (0012 retired, §21.9), but the block stayed alive as its own
   correctness bug: the r2d readback zero-windows are geometry/state-dependent,
   not BC- and not UBWC-dependent (a plain RGBA32 128x128 fails the same way).
   The fix is a candidate on its own, 0012 no longer blocks anything.
2. **Block 1 (fast-clear)** - a real performance lever (generic clear
   is already enabled, the only question is the R8G8 exception) + an improvement of the 0008 description.
3. **Block 3 (R32G32B32)** - a quick re-check, most likely it will confirm the dead end
   and lower its significance (128-bit is already in UBWC).
4. **Block 2 (R8)** - a re-check, most likely it will keep False, but will refine the conclusion.

## Pitfalls (reminder)

- `/tmp` is wiped: before a build, `meson setup` + `touch -d @0 build/PHONY`;
  silence from ninja is a trap, cross-check the mtime/hash of the .so.
- Quirks are **not cleared** at runtime (only props via `FD_DEV_FEATURES`/
  `TU_FORCE_PROPS`) - to "turn a quirk off" you need a build variant.
- Don't run two `run-game.sh` in parallel; a build and a game - not
  at the same time (RAM 7.3 GiB); `-j2`; fdperf ROOT only.
- Verification of each step: the patch is in the binary, the loaded driver = the built one
  (hash/mtime), CEIL controls; RC=0 from ninja is not proof of a build.
