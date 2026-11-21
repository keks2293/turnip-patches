# 30. Two outside Turnip patch stacks reviewed: neither carries the A740 fast-path, and the two closest patches are verdicts this repository already has (20.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

**Question.** The operator pointed at two outside patch sets: a "Turnip-Z" patch
collection (files numbered 01, 15, 16, 17, 25, 30, 33, 34, 35, 36, 37) and the repository
`sherft2607/turnip-adreno722-duo`, whose builder applies a subset of them by file name.
The question is narrow: does any of them already contain what queue item 8 (exp-18) asks
for - keep a `VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT` image *tiled* when the application gave
no `VkImageFormatListCreateInfo`, on a chip with `ubwc_unorm_snorm_int_compatible`? A
second version of the same proposal, written by the operator, asked to go further and keep
UBWC on in that case by filtering on the base format.

**Method.** Three steps, none of which touches the Mesa tree or the GPU.

1. The file list with byte sizes, and which files that builder applies, was captured from
   the GitHub tree API into `results/external/sherft2607-turnip-adreno722-duo/repo-tree.txt`
   (tree `766b5ef7034f9425f52054f8e69bdafb0cdc8118`). Their convention, quoted there: a
   file renamed to `*.py.off` is switched off, and a script that runs but changes nothing
   only produces a warning while the build continues.
2. The five mutable/BGRA-related scripts (30, 33, 34, 35, 37) were captured byte-for-byte
   with `curl` into the same folder; the sizes match the ones the API reports.
3. All five were dry-run in a copy of six source files from `../mesa27-src` at commit
   `9845cfb` (base `6dfa32a85f91` + `0001` + `0002`; neither commit touches those six
   files), which is where each script's own anchor matching shows whether it would land.
   The command and the output are `results/external/sherft2607-turnip-adreno722-duo/apply-check.txt`.

Of the whole stack, ten files are applied (`01, 15, 16, 17, 25, 30, 36, 56, 57, 58`) and
the rest carry `.off`; of the mutable/BGRA group, only 30 is applied. The applied set is
Android-side work (gralloc, `AHardwareBuffer`, swapchain usage, per-chip register blobs
for A722) plus sysmem rendering: `repo-tree.txt` groups it by kind.

**Mapping, file by file.** "Here" names the entry or decision that already owns the same
question - which is the point of this entry: none of the candidates opens a new branch.

| external file | what it does, in its own docstring | the same question here | state here |
|---|---|---|---|
| `30-tu-z-mutable.py` (applied) | clears `force_linear_tile` and sets `tile_mode = TILE6_3` **only** inside `if (modifier == DRM_FORMAT_MOD_QCOM_COMPRESSED)`; states that it "leaves 100% of game-internal `VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT` handling untouched" | there is nothing to fix on this stand: no gralloc-imported image arrives with that modifier. The no-list case is answered by the compatibility class in `0014` (journal 21.12) | applies, and is a no-op here (`apply-check.txt`); does not propose UBWC for a no-list image |
| `34-tu-z-mutable-swap.py` (`.off`) | sets `is_mutable = true` for swapped lists on a7xx without `ubwc_all_formats_compatible`, so `fdl` emits the per-view swap and `MUTABLEEN` | exp-10, journal 21.4, and ADR-0009 | measured "no": the goal was not reached (the `R32_UINT` view did not change by one byte) and the BGRA side broke, `261119/262144` `MISMATCH`, the swap applied once instead of twice. It also does not apply to this tree at all (`apply-check.txt`) |
| `35-tu-z-mutable-safe.py` (`.off`) | keep tiled and turn UBWC off when every swapped format in the list is `B8G8R8A8_UNORM`/`_SRGB`; with no list the predicates return "worst case", so its rule leaves such an image tiled with UBWC off | journal 21.12 and patch `0014`, which answer the same predicate with the whole texel-compatibility class instead of a BGRA8 exception, and journal 24.4 for why UBWC stays off there | the same direction, already shipped in a stronger form; does not apply (`apply-check.txt`) |
| `33-tu-z-bgra-swap.py` + `37-tu-z-bgra-companion.py` (both `.off`) | give `B8G8R8A8_UNORM`/`_SRGB` their table swap (`WXYZ`) on every path, then rewrite the channel order everywhere so the memory really holds B,G,R,A: a NIR pass on fragment `store_output`, the colour write mask, three clear-value paths, the blit source swap, `copy_format()` | nothing in this game asks for it - the ship stack's inventory shows zero lists mixing byte order (ADR-0009) and the cross-order no-list classes are the ones `0014` deliberately leaves linear (journal 24.4, 1630.2 MiB), where `fd6_pipe2swap()` does not force `WZYX` at all | applies cleanly (33 matches `fd6_format_table.c:403-404`, all 13 anchors of 37 match), `NOT MEASURED`, not carried |

The two facts worth keeping from the dry run, both verifiable in `apply-check.txt`:

* 34 and 35 anchor on `if (r8g8_r16 || (fmt_list_has_swaps && z_mutable < 1)) {`. That
  line is produced by an older form of 30; the 30 currently in the repository defines no
  `TU_Z_MUTABLE` and never edits that line, and Mesa 27 reads
  `if (r8g8_r16 || fmt_list_has_swaps) {` (`tu_image.cc:659`). So the two files that come
  closest to exp-18 are dead code in that stack - and because their builder only warns on
  a no-op, they would be missing from a release even if they were switched on.
* 33 and 37 are the only mutable-adjacent files that would land on Mesa 27.0-devel here,
  and they are the pair that changes channel semantics on every write path. That is the
  opposite of this repository's rule that a tiling patch may only pull images out of
  linear (`AGENTS.md`, working rules): it is a colour fix, not a layout fix, and it has no
  observed defect to fix in RE4.

**Verdict.** Nothing to merge, and no queue item changes. The specific rule the operator
proposed - when there is no list, keep UBWC if the *base* format is not a swizzled format
and belongs to the UNORM/SNORM/INT group - cannot be made safe by looking at the base
format, because the whole point of a list-less mutable image is that a view may pick any
format of the class: the 32-bit class contains `B8G8R8A8_UNORM`, `R8G8B8A8_UNORM` and
`R32_UINT` at once (journal 24.4, `tests/vk-fmt-classes.json`), which are precisely the
two shapes the flag broke in journal 24.1 (`XV[BGRA8_as_RGBA8]` and `U[B8G8R8A8_UAVLIST]`).
The unit of the decision has to be the class, not the base format - which is what `0014`
already does for tiling, and what exp-18(b) is about for UBWC.

**What this does not show.** Nothing from either stack was built or run, so no statement
here is about what those patches do on hardware; the claim is only about what their
scripts edit. The other 37 files of that repository, the `WinNative-Emu/Drivers` scripts
they are ports of, and the release pages the operator cited (`Vauzi-17/710`,
Mesa release notes) were not captured and are not reviewed here, except that the applied
set's kinds are listed in `repo-tree.txt`. `17-wn-apply-perf-variant.py` (a per-chip
register blob, 13 KB) is the one applied file whose subject this repository has not
measured in that form; journal 13 and ADR-0008 say RE4's frame time does not respond to
driver levers, which is a reason not to spend a build on it, not a measurement of it.

**Artifact status.** Committed under `results/external/sherft2607-turnip-adreno722-duo/`:
`repo-tree.txt`, `apply-check.txt`, and the five scripts as captured
(`30-tu-z-mutable.py` 2348 B, `33-tu-z-bgra-swap.py.off` 2479 B,
`34-tu-z-mutable-swap.py.off` 2925 B, `35-tu-z-mutable-safe.py.off` 3647 B,
`37-tu-z-bgra-companion.py.off` 11818 B). They are evidence about somebody else's work, not
artifacts of a measurement: no build hash and no device is involved. Nothing under
`patches/`, `experiments/` or `build/` changed, and `../mesa27-src` was not written to.

### Addition (21.11): the WinNative-Emu repositories themselves, captured and mapped

**Why.** The entry above reviewed a downstream port and named its origin only in passing: the
sentence "the `WinNative-Emu/Drivers` scripts they are ports of ... were not captured" is now
out of date for those two repositories, and this paragraph replaces it. The operator pointed at
the origin's own repositories, so the same question - is there anything here that this machine
does not already have measured - is asked of them directly.

**What they are.** Three repositories, all pinned by commit before anything is quoted:

| repository | what it is, in its own words | at capture |
|---|---|---|
| `WinNative-Emu/Drivers` (tree `c71f600a2977a141f21a922c9ed2e14fb09b13d3`, 35 blobs / 331161 B) | "Turnip Drivers built by WinNative Development Team": upstream Mesa main + idempotent Python patch scripts, released as Android Adrenotools zips (`v1.19`, 30.09.2026) and as a separate Linux glibc/aarch64 series (`linux-v0.1.2`, 29.09.2026) | 20 files captured byte-for-byte, sizes verified against the API (`size-check.txt`); 15 left as listings |
| `WinNative-Emu/Components` (tree `3b7c0efdb9c49ec289367b325db2dc79785acd87`, 23 blobs / 669318 B) | nightly builds of the layers that sit above the driver: box64, DXVK, vkd3d-proton (x86/x86_64 and ARM64EC), FEXCore, Proton, plus the `.wcp` catalog (`contents.json`) | 6 files captured, 17 listings only |
| `WinNative-Emu/WinNative` | the Android app that runs Windows Steam/Epic/GOG builds on top of the two above | not captured, nothing Turnip-side in it |

**Mapping, against what is already measured here.**

| their file | their claim | state here |
|---|---|---|
| `patches/apply_a7xx_gen2_ubwc_hint.py` (1590 B) | "A7xx_gen2 inherits a7xx_base, which does not set `enable_tp_ubwc_flag_hint`. Without this hint, certain Vulkan UI / compositor passes show vertical-line corruption on FD740 (SD8 Gen 2) and X1-85 silicon" - appends `GPUProps(enable_tp_ubwc_flag_hint = True)` to the `[a7xx_base, a7xx_gen2]` block anchored on the X1-85/FD740 `add_gpus` list | the same prop, measured here the other way. Our tree keeps it `False` in `a7xx_gen2` (`freedreno_devices.py:821`, comment "Most devices with a740 have blob v6xx which doesn't have this hint set"), and upstream sets `True` only in two other gen2 blocks - X1-45/FD735/A735 (`:1177`) and FD740v3 / Quest 3 (`:1320`) - while our chip's block (`GPUId(chip_id=0x43050a01, name="FD740")`, `:1235`) keeps the `False`. Forcing it `True` on this machine gives vkmark noise and **artifacts in RE4** (journal 15.4, `results/test-props2-*`), which is why `docs/a7xx-gen-props.md` says the prop "must not be enabled". Not carried; the prop is closed here |
| `patches/disable_64b_image_atomics.py` (1588 B) + `MAINTENANCE.md` "Retired patches" | cleared `has_64b_image_atomics` on gen2 and gen3 because an upstream 64-bit image-atomic path hung the GPU after the first submit on A8xx in UE5/vkd3d SM6.6 titles; retired in 1.12 because turning it off makes vkd3d-proton report `AtomicInt64OnTypedResourceSupported = FALSE` | nothing to do here: `has_64b_image_atomics = True` on gen2 (`freedreno_devices.py:828`) and RE4 runs. Kept as the name of a fallback if a SM6.6 title ever hangs on this GPU after submit - NOT MEASURED here, and the hang they describe was on A8xx, not gen2 |
| `patches/apply_a7xx_gen1_quirks.py` (1931 B) | forces `has_early_preamble`/`has_scalar_predicates` `False` in `a7xx_gen1` (A720/A725/A730) | not this chip: this machine is gen2 (`docs/release.md`: `FD740`, a7xx gen2, chip_id `0x43050a01`) |
| `patches/apply_balance_variant.py` (1700 B) | the "-b" variant nudges the autotune cost model: GMEM bandwidth multiplier `11 -> 10`; its other tweak (`drawcall_count > 5`) is reported as "removed upstream (now `>= 10`)" | the only lever in the whole stack that is not already covered here, and its anchors check out in our tree: `gmem_bandwidth = (gmem_bandwidth * 11 + total_draw_call_bandwidth) / 10;` at `tu_autotune.cc:1065` (upstream's own comment on that line calls 11 and 10 "randomly chosen"), and the restructured gate at `:1881` (`mod_flag::BIG_GMEM && rp_state->drawcall_count >= 10`) with `< 5` now in `ignore_small_rp` (`:1862`). `11 -> 10` makes the GMEM estimate `g + d/10` instead of `1.1g + 0.1d`, i.e. it moves the SYSMEM/GMEM decision by 10 % of the pass' GMEM bandwidth **towards GMEM** - the direction that already cost 1.5 frames in journal 15.5 (`TU_AUTOTUNE_FLAGS=big_gmem`). NOT MEASURED; it is queue 17 of `docs/plan-next-checks.md`, and the cheap discriminator comes first: if RE4 never selects SYSMEM, the tweak cannot do anything, and that answer needs a build only because the decision is logged by `at_log_bandwidth_h` behind the compile-time `TU_AUTOTUNE_DEBUG_LOG_BANDWIDTH 0` (`tu_autotune.cc:25-30`) |
| `linux/patches/0001` (105680 B, `VK_EXT_mesh_shader` emulated as compute) and `0002`-`0006` (subgroup size 32 on A8XX 64-wide waves, cube-map directions, bindless invalidation, KGSL command-stream lifetimes) | "needed by DX12 Ultimate games such as FINAL FANTASY VII REBIRTH" | a different chip (`0002`-`0006` are A8XX) and a subject RE4 does not raise: our tree exposes no mesh-shader feature at all (`grep -c 'EXT_shader_meshlet\|meshShader\|taskShader' src/freedreno/vulkan/tu_device.cc` = 0, no `shader_meshlet` under `src/freedreno/`). Kept as a named source if a mesh-shader title is ever put on this GPU; nothing was built |
| `build_linux_turnip.sh` (the Linux/aarch64 recipe) | `--buildtype release -Dvulkan-drivers=freedreno -Dfreedreno-kmds=msm,kgsl -Dgallium-drivers= -Dplatforms=wayland,x11 -Dopengl=false -Dgbm=disabled -Dglx=disabled -Degl=disabled -Dllvm=disabled -Dvulkan-layers= -Dtools= -Dvideo-codecs= -Dxmlconfig=disabled` | a cross-check of our own recipe, `scripts/build-turnip-mesa27.sh:44-59`. Same in everything that can move a measurement (release buildtype, freedreno-only, gallium empty, llvm disabled, both WSIs); two deliberate differences: they build both KMDs (`msm,kgsl`) while we build `msm` only and fail the build if the `.so` does not import `drmGetVersion` (`:62-70`), and they set `-Dxmlconfig=disabled` while we leave drirc reading on, which is how the driconf options of queue 13 are reachable without a patch |
| `MAINTENANCE.md` + `verify_patches.sh` (2812 B, root, not `patches/`) | their three-state rule for every patch script - "already applied / anchor present / anchor absent" - and a CI assertion, because "a patch script whose anchor drifted against upstream Mesa logs a warning and continues, so the archive still builds and installs - it is simply missing the fix" | the same failure mode this entry found in the ported stack (34/35 of that stack anchor on a line their own 30 no longer writes). Their answer is a CI assertion over the build log; ours is the applied-patch inventory and the matrix signature rather than the `.so` hash (journal 39.7). It supports the rule already in `AGENTS.md` and changes no queue item |

**Verdict.** Nothing to merge, and no shipped row changes. One new queue item (17, the GMEM
cost-model nudge) and one named fallback (the 64-bit image-atomic switch, only if an SM6.6
title hangs after submit on this GPU). The A740-related patch of that stack, the UBWC hint, is
the inverse of a measurement this repository already owns, so it stays closed.

**What this does not show.** Nothing from either repository was built, installed or run: no
driver was downloaded, and `.wcp` release assets are not in the repositories. The claims about
their patches are about what the scripts edit and what their own MAINTENANCE/README say, and the
"device-confirmed" results quoted in those files (the RedMagic green-screen fix, the A8xx
image-atomic hang) are theirs, not ours. The two tree listings and the size check are regenerable
with the commands in `capture.txt` of each folder.
