# Plan: what to check (new patch candidates + re-check of the "dead ends")

Updated 23.11.2026. Two things are live here: the **queue** below, ordered by what unblocks what, and
the **open questions** table at the end. A closed branch is not repeated - it has an ADR in
`docs/decisions/` or a journal entry, and the queue line says so in two sentences. The four
"re-check the dead end" blocks of 17-18.11 are closed and moved to
`docs/archive/2026-11-17-plan-recheck-blocks.md` (summary table where they used to be).

State of the rig, so a queue line can be read without asking:

* `build/out` is the ship stack `4c3cdb210082`; the shipped `c17d02bcaae9a960…` and tag
  `27.0.0-devel-p14` are untouched, and no queue item below changes them without a measurement first.
* A driver build (queues 1 and 10 are the two that need one) needs the container, `-j2`, ccache under
  `/tmp`, and a machine with the game closed: ~3.5 GiB of the 7.3 GiB is free while wine services linger,
  and stale wine services have to be killed with `kill -9` (the normal exit path leaves them). A build
  of this tree is reproducible (journal 40.28: the same tree twice, `f80d33ab2077` both times), so a
  hash difference is a source difference - and no tree on this machine rebuilds the ship hash.
* The game's own `local_config.ini` is a measurement variable, not environment: journal 40.19 showed
  `AppShadowCache` is worth 49 % of the frame's primitives, so every arm writes the setting into its
  own `meta.txt` and a chain restores the file byte-identically (`docs/howto-measure.md`).
* The screenshot is a content check only while the panel is powered; with the output off the kernel
  holds no framebuffer and every capture method returns black (`scripts/drm-state.py`).

---

## Closed re-check blocks of 17-18.11 (moved out, 22.11)

The four blocks that used to sit here asked "is this candidate real, or is the recorded dead end a
driver gate we mistook for hardware?". All four were answered by 20.11 and none owns a number, so the
text was moved whole to `docs/archive/2026-11-17-plan-recheck-blocks.md` (unedited, because its value
is that a later reader can see how each verdict moved) and this is the only copy of the verdicts that
the plan keeps:

| block | verdict | owner |
|---|---|---|
| 0. the BC copy path, which blocked verifying `0012` with data | not a BC defect: the fill is byte-clean and the readback loses windows because A7XX had no CCU clean between `buffer->image` and the next reader in one submit; shipped as `0013` in the lazy form, 94/94 EXACT over three repeats | ADR-0005, journal 21.10, `patches/0013-turnip-b2i-ccu-clean.patch` |
| 1. the `QCTDD12766770` fast-clear quirk (`0008`) | closed by analysis - the blanket stays. Taking it off costs -61..-65 % in vkmark (vertex/shading/texture), and no targeted form was shown to be safe | the header of `patches/0008-*.patch` |
| 2. `has_8bpp_ubwc` ("HW corruption") | stays `False`. `{16,4}` is not the cause: `{16,4}/{32,4}/{64,4}` corrupt identically and `{16,8}/{32,8}/{8,8}` fault the GPU (journal 22.4, the exp-17 grid) | ADR-0007, journal 22.1, 22.2 |
| 3. `R32G32B32`, 96-bit ("no HW entry") | a driver gate, `!util_is_power_of_two_or_zero(cpp)` in `fd6_layout.c`, not a missing hardware entry; the 128-bit format already gets UBWC, so the class has no game significance | journal 21.6.3a, journal 31 |

---
---

## Queue (opened 20.11, updated 23.11)

Ordered by what unblocks what. A closed branch is not repeated here - it has an ADR in
[`decisions/`](decisions/); this file owns only the next actions.

### Status 23.11, after chain38 - the live list

The table is the only place that says what is left; the numbered items below keep the reasoning.
Seven items were closed reading the queue against what is already measured, and the reason for each is
on its own line below: 5, 8, 17, 21, 22, 23, 26.

| queue | what is missing | what it costs | what moves if it comes back |
|---|---|---|---|
| 1 `exp-18` | the rule, not a question: (a) the two list predicates out of the `!mutable_ubwc_fc` branch, (b) `TODO: limit based on compatiblity class` against the strict Vulkan class | one build + the 94-row matrix + the `NL`/`UBR`/`XV` rows | the only open direction (`streams/mutable-lazy-deposition`); its hardware half is answered by 31, 32, 37 |
| 10 `exp-20` | one hook line on the view path, one rebuild, one 150 s run | build + session | the last gap in `0014`/ADR-0001's argument (question 11), and a gate on 1 |
| 6 | who creates the DEPOSED no-list images, vkd3d or DXVK | one launch on the DXVK branch plus the inventory | which branch 1's verification has to cover |
| 2 `exp-19` | the `AB` rows at the base grid and at `{32,8}`, in a fresh process | probe only, no build | whether ADR-0007's blocker is the 3D writer or the descriptor |
| 13 | what vkd3d-proton does under a smaller heap report (`0.5`, `0.4`) | two sessions with journal 17's memory logging | the 7.32 GiB wall; the one memory question with a decision on it |
| 14 | step 0: a DX11 launch at all, then the same block profile | two sessions | whether the wall survives the translation layer |
| 3, 4 | the `build/out-stock-inv` column and the ship+prop column of journal 27's scale | two runs, one ~4-minute build | the true zero point of the three-variant scale, and nothing else |
| 7, 9 | the three probes, and the two documentation pieces | no measurement | test coverage and legibility |
| 31 | run `tools/fdperf/fdperf.cfg-vpc4` (written, NOT RUN: PC 39, 17, 10 in, 2, 4, 21 out) in the session of 10 | the same session, no build | the vertex-cache hit rate (19/39) and the first dead-primitive rate on this rig |
| 32 | one line at `tu_shader.cc:3878`: `0, 0` instead of the two `UINT32_MAX` promotion limits of `nir_opt_varyings_bulk`, then the usual A/B | build + session | whether turnip's varying-to-uniform promotion, which RADV turns off, costs anything against this title's UCHE/SP wall (40.34) |
| 33 | `fdperf.cfg-bv` with `forcebin` on the Shadow-Cache-on frame, once, so `BV_*` rows exist at a `tile_count` that `cb21-h1` also reached (3-14 tiles) | session, no build | a control for 40.30's aliasing verdict using a variable no counter can fake; no committed dump has a binned `cfg-bv` window on that frame |
| 34 | a probe set with a known VS→FS interface (1, 2, 4, 8 vec4 varyings, same geometry), run once outside the game | session, no build | a unit for `VPC_SP_COMPONENTS` / `SP_EXPORT_VPC_TRANS` or their retirement: they are one signal of unknown unit, 0.63-1.04 per vertex (40.34) |

Nothing else is open beyond 31-34: 31 rides on 10's session, 33 and 34 are sessions with no build, and 32 is the
last driver change standing in the vertex tract. Where 40.34 leaves the VPC itself: busy 86-92 % of one core and
working two thirds of that, the stall is its own attribute RAM (0.48 of a core full on the ship frame, 0.61 on the
Shadow-Cache frame), no VPC counter needs a divider, and the attribute-buffer size is not programmable on this
generation - so the direction has no measured opening left except 32. 16 is closed by 40.29 and 40.31, 21 by 40.30,
18(a) by 40.32; 17 and 22 have no buyer after 40.18's render-mode ladder; 23 is answered by 40.18; 5 has no decision
on it since ADR-0008; 26's remaining half is a disassembly question that no shipped patch depends on.

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

   **State 23.11, supersedes the two stale parts of the note above.** `git diff --stat` in
   `../mesa27-src` is 12 files, +787/-81, not 8 files +663/-80: the tree now also carries `0014`
   in its one-decision form (`mutable_compat_class()` at `tu_formats.cc:290`, `mutable_views()` at
   `:351` - the text `patches/0014-*.patch` was regenerated to on 23.11, `docs/release.md`
   provenance), the `TU_FORCE_PROPS` hook `exp-25` (queue 26, `tu_device.cc:1717-1816`), and the
   `TU_DBG_RM_HIST` render-mode rig of queue 22 (`tu_cmd_buffer.cc`, `tu_util.cc`) which is written
   and still unbuilt (`docs/artifacts.md` row 24). So the marker pair "`mutable_compat_class`
   present / `tu6_mutable_compat_class` absent" no longer tells `0014` off from `0014` on - both
   texts define `mutable_compat_class`. What tells the difference is the inventory signature, which
   is how 40.29 accepted its two build trees. Two facts about this tree, both measured in 40.28 and
   worth repeating here because every build plan inherits them: the queue-16 A/B trees are `cp -a`
   copies, never this one; and this tree minus both rigs builds `f80d33ab2077`, which is not the
   ship `4c3cdb210082`, so no build made here reproduces the release and a build hash is only ever
   compared to another build hash.
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
   DRAM split in `results/games/re4/mesa27-vertex/steady-state.txt` puts SP at 0.05 GB/s of 14.8
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
5. **Closed 23.11, no decision attached: fps A/B for mode 7** (`0013`). The correctness case never
   depended on it (94/94 EXACT over three repeats, ADR-0005), and the two things this run could have
   said are already said: ADR-0008 closed driver-side frame-rate levers, and 40.18's ladder priced the
   render-mode axis on this title in four rungs (forced sysmem 15.18, default 15.34, GMEM without
   binning 13.74, GMEM plus binning 10.27, p25 95-150 s). A run would add a fifth number to a table
   with no decision hanging under it. Question 3 closes with it.
6. **Who creates the DEPOSED no-list images** - vkd3d or DXVK. Not separated, and it
   decides which path the exp-18 verification must cover: vkd3d means the driver lever is
   the whole story, DXVK means the same fix has to be verified on the DX11 path too. There
   is no env lever on the vkd3d side: the empty-list branch in `resource.c`
   (`disable_compression`) is compiled in.
7. **Probes to add to the test**: b2i -> sampler inside a renderpass; b2i -> dispatch;
   secondary-CB b2i -> primary i2b (the boundary journal 21.10 leaves uncovered).
8. **Closed 23.11, no decision attached: R32G32B32 (96-bit).** The re-check in section 3 above asked
   whether the dead end is a driver gate or a missing hardware entry, and that was answered twice over:
   it is the gate `!util_is_power_of_two_or_zero(cpp)` in `fd6_layout.c` (journal 21.6.3a), and the
   class has no ceiling to lose in the first place - the 128-bit control gets UBWC while the 96-bit rows
   in `fd6_format_table.c` have no render-buffer entry at all (journal 21's table, corrected again in
   31/32). The run would confirm a dead end whose shape is known, and no committed inventory records a
   single 96-bit create by the game, so it has no volume to argue about either. If the class ever shows
   up in an inventory, the check reopens by itself.
9. **Documentation**, two open pieces, neither of them a measurement:
   - a distilled how-to page over the operational journal entries 7-12 and 19 (driver
     swap, running the game and reading its logs, the `vkCreateInstance` rejection and its
     real cause, the stale build image). The entries stay as they are; the page is the
     version you read while working.
   - the Russian left outside the archive. `AGENTS.md` says a passage is translated when
     it is touched; these were not touched, so they are listed instead of quietly kept.
     Re-counted 23.11 (`grep -cP '[а-яА-Я]'`), because the list itself had gone stale:
     `scripts/imginv-stats.py` is **done** - translated 23.11, `results/imginv-3variants.txt`
     regenerated from it with its numbers unchanged, which that file's own header records.
     What is left is one script and eight annotation headers, with line counts so the job can
     be sized: `scripts/imginv-classes.py` (6), `results/series-autotune.txt` (35),
     `results/series-drirc.txt` (16), `results/vkmark-ab-autotune.txt` (4),
     `results/vkmark-ab-r8g8.txt` (22), `results/vkmark-flags.txt` (14),
     `results/test-8bpp-meta-shape.txt` (38), `results/games/re4/mesa27/steady-state.txt` (35),
     `results/games/re4/mesa27-vertex/steady-state.txt` (42). Translating the script means
     re-running it over `results/raw/` and checking that every number comes out identical - the
     labels may change, the counters may not. The eight artifacts are hand-written headers over
     generated tables, so there the header moves and the table is not retyped.

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

11. **`exp-21` - CLOSED 23.11: this text is `0014` now**
    (`experiments/exp-21-mutable-one-decision.patch`, tail
    `experiments/exp-21b-predicates-static.patch`). The operator's decision: replace
    `0014` with this text without a further equivalence run - journals 33 and 36 already
    measured it equal, and the queue-16 A arm was built from exactly this text (journal
    40.29). The reserved number `0016` is retired with the experiment. The rest of this
    item is the record of why the candidate existed and the rebase notes it carries.
    Status 21.11: written
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

12. **Closed 23.11: none of the reachable driconf `perf` options changes RE4's fps.** The driconf perf
    options the props search never covered (journal 34; no build needed, no new code). Five options are
    perf-relevant and off for this game; two are candidates, one is held on a precondition that fails,
    one is a feature trade and one is unreachable on a740 (journal 34.2, and journal 35.1 for the held
    one). Both candidates came back zeros: concurrent binning as `TU_DEBUG=forcecb` (journal 40.8) and
    `disable_conservative_lrz` on the cached-shadow frame (journal 40.23), the held FDM option never
    leaving its "nothing to attach to" state (journal 35.1).
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
      rather than this SoC running a desktop game through vkd3d-proton. **Closed 22.11 by journal
      40.8**: the same switch is reachable without a build as `TU_DEBUG=forcecb`, and forcing it
      changed nothing; `allow_concurrent_binning` is settled as `forcecb` 18x against `nocb` being
      the gen2 default;
    * `disable_conservative_lrz` - stops the conservative default from disabling LRZ writes on
      draws that blend and write depth (`tu_lrz.cc:1524`, `:1533`); safe only if the game does
      not contain the three-draw sequence the code comment above those lines spells out, which a
      screenshot comparison is supposed to answer. **Closed 23.11 by journal 40.23**: measured on
      the cached-shadow frame, `lrz-nocons` 27.13 p25 over 14 kept windows against a
      same-configuration cluster of 26.53-26.67, with every LRZ counter unchanged - a zero, and a
      zero of a switch with almost nothing to give, because LRZ kills 0.54 % of the frame's input
      primitives in the first place.

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

    **Correction, 23.11.** The paragraph above is kept as written; both questions it asks have been
    asked since, and both answered zero - `forcecb` in journal 40.8 and `disable_conservative_lrz` in
    journal 40.23, the latter measured on the cached-shadow frame rather than on the 15 fps setting the
    protocol was drafted against. The screenshot-pair gate this item insisted on was never needed,
    because nothing gained fps to trade the picture for.

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
loaded) left all three runs on D3D12: `results/games/re4/game-patched-dx11dx11.log`, `…-dx11forceDX11.log` and
`…-d3doff.log` each still contain `d3d12_device_create_vkd3d_queues`, and the game rewrites
`Capability=DirectX12` into `local_config.ini`. Renaming the prefix's `d3d12.dll`/`d3d12core.dll` was
rejected without running it: that would route the game to wine's own D3D12-on-wined3d, which answers
nothing about DXVK. `VKD3D_FEATURE_LEVEL` is closed as a lever separately (journal 40.6): vkd3d-proton
v3.1's `d3d12_device_caps_override` only raises capabilities and assigns `max_feature_level`, and `11_1`
against `12_1` measured identical to 0.1 point on every block ratio. The API-isolation check stays closed
until a title that can choose its API is on this machine.

15. **Closed 22.11, journal 40.14: the varyings payload is small and the VPC does not wait on it; the
    occupancy of the VPC's sub-units stays undecoded.** The counters this item asked for were already
    programmed by `tools/fdperf/fdperf.cfg-vpc` and sat unread in the ten 21.11 arms:
    `LM_FULL_WAIT_FOR_INTP_END` is 1.0-1.1 % of the core (1.2 % of `VPC_BUSY`), `NUM_VPCRAM_WRITE` 2.62
    and `SP_COMPONENTS` 0.89 per VS invocation in every arm, `VFD_STALL_CYCLES_VPC_ALLOC` 12.4 % of VFD
    busy against 12.5 % in the 17.11 vertex run, `PC_VERTEX_HITS` 0.65 per IA vertex. So the branch
    "excess or unpacked varyings saturate the VPC" is closed on the payload and the wait signature, and
    the knob it named - `tu6_vpc_varying_mode()` / `tu6_emit_vpc_varying_modes()` - has no measurement
    behind it and stays untouched. What the pre-registration did not expect: `VPC_PS_BUSY` is
    83.7-84.5 % of the core, not a small share - but with `VPC_BUSY` 91.5 % and `VPC_VS_BUSY` 88.7 % the
    three cannot be phases of one pipe, and neither the XML nor the tree describes them, so no
    "interpolation is the wall" claim is available from these counters. `UCHE_WRITE_REQUESTS_VPC` reads
    exactly 0 in every arm while `..._SP` reads 47-49 M/s: a measured zero whose wiring on a7xx is not
    described, so it is recorded and not used.

    **Corrected 23.11 by journal 40.33, which also names the two sentences above it.** `PC_VERTEX_HITS` is
    not a reuse figure and 0.65 is not a hit rate: the counter's denominator (`PC_TAG_CHECKED_VERTICES`, PC
    selector id 39) was programmed by no cfg here until `fdperf.cfg-vpc4` and appears in no committed dump, so
    the raw reading can only be divided by something borrowed - 1.82-1.90 per delivered vertex, or 0.646-0.655
    per IA vertex, in the three arms above - and it exceeds the delivered vertex count in every window. The
    reuse the item quotes (2.9:1) stays valid, it is `PC_IA_VERTICES/VFD_TOTAL_VERTICES` from journal 38 and
    a property of the game's meshes. The measurement the operator's 23.11 question asked for is queued as
    item 31; the driver-side half of that question has nothing to check (40.33).

    (The text below is the pre-registration as it stood on 21.11; it is kept because the reading it fixed
    is what 40.14 was judged against.)

    Two claims were put forward as the next lever: ir3
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
   **Status 23.11: closed, both halves measured, and the second one needed no run.** 40.29 reproduced
   both inventory signatures on the two dedicated builds (`88bab928c520` with `0014`, `7ae5f008caa8`
   without) and found no frame-rate separation. 40.31 then read the DRAM column that `counters.txt`
   printed as `n/a` out of the same committed dumps: TP is 81.86 % of reads with `0014` and 82.11 %
   without, 14.82 against 14.62 GB/s total, and the spread between two sessions of one configuration
   here is 1.74 %. So the pre-registered branch came true - the largest layout change in this stack is
   worth no measured traffic - ADR-0008 gains a second and much bigger instance, layout closes as a
   lever, and `0014` stays as correctness and volume. Nothing is left in this item.
    sampler; shares the machine with 12/13/14/15 and with the 7.32 GiB memory wall).

    Status 23.11: **run and accepted** (chain37, journal 40.29). B is the pre-`0014` inventory (0 MiB
    tiled), A the with-`0014` one (1450 creates / 2450.3 MiB, 60.0 %) - both on dedicated builds, to the
    tenth of a MiB. fps does not separate A from B at this frame's resolution, so the value of the patch
    is the tiled volume and the bandwidth behind it, not a frame-rate lever. The file itself is now the
    one-decision text (journal 40.29, `patches/0014-*.patch` header).

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
    `results/games/re4/mesa27-vertex/steady-state.txt` - is a baseline with those images in linear.

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
    scripts/fdperf-sample.sh 130 1000 results/games/re4/0014ab/A.txt tools/fdperf/fdperf.cfg-vertex
    python3 scripts/fdperf-analyze.py results/games/re4/0014ab/A.txt
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
   **Status 23.11: closed without a build, because 40.18 priced the direction the nudge moves.** The
   tweak shifts `select_sysmem` towards GMEM, and GMEM is the slower mode on this title in both of its
   forms: forced sysmem 15.18, default 15.34, GMEM without binning 13.74, GMEM plus binning 10.27
   (p25 95-150 s, 40.18), with the same shape on the cached frame in queue 24. Step 0 (does RE4 ever
   pick SYSMEM) cannot rescue a change whose only effect is to move passes towards a mode this game
   loses by 10-33 %, so `exp-24` is not built.
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
   **Status 23.11: closed - (a) by 40.32, (b) by 40.18, (c) by 40.2/40.25 as written.** (a) The two
   counters are not one counter exposed twice: 0 of 256 windows in five committed dumps print them
   equal, they differ in every window and agree to 1e-5, so "nothing is discarded between the collector
   and TSE" is the reading and 40.2's "not decided" retires. (b) The `prefer_gmem` repeat has no buyer
   after 40.18's ladder - 40.4 already showed the discard ratio unmoved (73.8 against 71.9 %), so what
   was left was the cost of a mode this title loses by 10-33 %. What survives here is a wording item,
   not a run: the meaning of `VPC_PS_BUSY`/`VS_BUSY`, which has no `<desc>` in the XML.
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
(22.11: the counter half of (c) is measured now - queue 15 closed by journal 40.14, which adds the
wait signature `LM_FULL_WAIT_FOR_INTP_END` at 1.0-1.1 % of the core and confirms the payload in nine
arms; what stays open there is exactly the same thing, the meaning of `PS_BUSY`/`VS_BUSY`.)

19. **Closed 21.11, journal 40.9: the VPC attribute buffer is not a lever.** The premise was that on
    A740 the sysmem attribute buffer is a too-small 0x20000; in this tree the answer is that our
    generation never programs one at all. `emit_vpc_attr_buf` (`tu_cmd_buffer.cc:647-652`) returns
    immediately unless `props.has_gmem_vpc_attr_buf`, and that property with
    `sysmem_vpc_attr_buf_size = 0x20000` / `gmem_vpc_attr_buf_size = 0xc000` exists only in `a7xx_gen3`
    (`freedreno_devices.py:854-856`), not in `a7xx_base`/`a7xx_gen2`. Upstream's own probe
    `TU_FORCE_PROPS=has_gmem_vpc_attr_buf` substitutes those sizes and logs
    `TU_FORCE_PROPS: vpc_attr_buf_size sysmem=0x20000 gmem=0xc000` (`tu_device.cc:1799-1806`), and the
    log of `results/games/re4/vpc3-attrbuf/` carries 9 such lines against 0 in the control, so delivery is
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
    prints the group's first countables (`results/games/re4/bv-idle-labelcheck.txt`). The register map in
    `a7xx_perfcntrs.json` says how separate they are: `BV_PC`/`BV_VFD`/`BV_VPC`/`BV_TP`/`BV_SP`/`BV_UFC`
    share their ordinary twin's select register with a `select_offset`, `BV_TSE`/`BV_RAS`/`BV_LRZ`/
    `BV_HLSQ`/`BV_CP` have none and so share the very words; the value registers are separate.
    Measured (`cfg-bv`, six arms `results/games/re4/bv-*/`, p25 15.15-15.29): the BV banks report
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
   **Status 23.11: closed by 40.30 (chain38, `cb21-{c0,c1,h0,h1}`).** The stretch was found without a
   build: on the Shadow-Cache-off frame under `forcecb`, 8 of 40 steady windows feed tiles (3-14 tiles
   per ~2 s window) and only in windows where the core had sagged to 662-678 MHz - 40.12's hint, read
   in the same sample and confirmed - while the cache-on arm with the same delivered flag reads 0 tiles
   in all 40, so the other `cb_disable_reason`s keep their decision. The pre-registered trigger did not
   fire: the `BV_*` primitive halves rise in exactly those eight windows, but each is a fixed 14x or 2x
   multiple of that window's own tile count and the half still reads `BV_TP` busy at 945 % of a core
   (40.8's unprogrammed signature), so they are not per-thread counts; at face value they are <=196
   primitives against the same window's 247-254 M/s. fps says it without counters: 15.14 against 15.18
   with the flag, and 26.23 against 26.53 in a pair where neither arm binned - so 1.1 % is what two
   identical sessions differ by here. The CB direction closes with 40.12, 40.18 and this, no further
   `cfg-bv` run is queued, and no document may quote a `BV_*` primitive counter as a count.
    window - `cfg-tse3` without any BV section included, and with `forcecb` delivered and logged - where
    21.11's `cfg-tse3` + `forcecb` arm fed 1,532 tiles/s in all 88 windows and its CB-off twin in 32 of 40
    at a median of 56/s (`results/games/re4/tse3-cbforce/`, `results/games/re4/tse3-cbbase/`,
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

22. **Render-mode reason histogram (needs a build, queue 16 can carry it).** No "enable binning"
    patch is justified: forcing GMEM+binning costs a third of the fps and forcing sysmem changes
   **Status 23.11: closed, nothing can act on its answer.** The rig is written and sits in the tree
   (`TU_DBG_RM_HIST`, `docs/artifacts.md` row 24, never built). Both GMEM forms are slower than the
   sysmem default on both frames (40.16, 40.18, 40.20 with queue 24), so a histogram of *why* passes
   stay out of binning cannot point at a win; and 40.30 shows what the game does with binning when the
   gate is forced anyway - 3-14 tiles in 8 of 40 windows, no frame-rate change. The rig stays in the
   tree as an unrun diagnostic; the item leaves the queue.
    nothing (journal 40.16). What is left is the diagnostic - a once-per-second histogram of
    `force_render_mode_reason` (`tu_cmd_buffer.cc:1424-1487`, never logged, only traced), modelled on
    `tu_dbg_log_gmem_load_store_skips()` (`tu_util.cc:593-642`): which reason covers how many passes.

23. **UBWC attribution (chain24 running 22.11: `gmem-nobin`, `tr-nocomp-perf`, `tr-noupload2`).**
    Existence and price are closed - 2 % of RE4's DRAM reads are compressed, taking compression off
   **Status 23.11: closed by 40.18, which is the chain24 entry this item was waiting for.** The
   attribution is answered: in the shipped vkd3d-proton's RE4 profile the compression switch applies to
   `Z32_FLOAT` and `Z32_FLOAT_S8X24_UINT` only - 177 lines, 0 colour formats, against 2495 `... due to
   mutable formats` lines for the colour class - so the compressed 2 % is depth and the class `0014`
   moves is outside it. `tr-noupload2` is the clean second session asked for here (p25 15.19 against
   15.26, 52 of 52 pinned), so `no_upload_hvv` is a zero on fps as well. The per-image `TU_DEBUG=perf`
   line needs a build and 40.18 already says its answer would move no measured number; queue 16's
   traffic cut (40.31) closes the "which images" angle from the other side.
    costs +0.9 % read / +10 % write and no fps (journal 40.17). Open: *which* images those 317 MB/s
    belong to - Turnip's per-image lines need `TU_DEBUG=perf`, and whether `0014`'s images are inside
    that class is queue 16's A/B. `tr-noupload` needs a second session (its first ran a light scene).

24. Closed by journal 40.20 (chain27, `results/games/re4/render-mode-two-frames.txt`): on the cached-
    shadow frame - half the primitives, `VPC_BUSY` 85.6 % - GMEM is still -14.4 % and forced binning
    -29.3 % against the default, the same as the -10.4 % / -33.1 % on the heavy frame. The sysmem
    default is not tuned to the game's worst shadow setting, it is right on both frames, and forced
    sysmem ties the default again (-0.7 %).

25. Closed by journal 40.21 (chain28, `results/games/re4/occupancy-two-frames.txt`): with
    `AppShadowCache=1` the vertex path is still the busiest block - `VPC_BUSY` 85.54 % against 91.57 %
    on the cache-off frame, `VS_BUSY` 80.65 %, `PS_BUSY` 76.97 % - and the primitive collector waits on
    it 12.7 points less. Nothing else became the wall: no block in `fdperf.cfg-vpc` goes from idle to
    busy. The 26.7 fps frame is the same wall with 6 points of slack, so open question 21 is answered
    and the "+9…13 % for a non-geometry fix" ceiling of 40.10/40.15 still applies to this frame.

26. **The never-forceable gen3 properties: `has_alias_rt` is the one candidate worth a build** (needs
    queue 16's build; the audit is journals 40.24 and `docs/a7xx-gen-props.md`).
   **Status 23.11: closed as a game question; what remains is a disassembly diff, and nothing ships on
   it.** 40.29 delivered the property (`TU_FORCE_PROPS: has_alias_rt` in the run log) and it moves
   nothing: 1.8 % on TSE input against the same-build control, 0.06 points of VPC busy, 1.2 % fps. The
   open half - whether the pass engages at all, i.e. fewer preamble `mov`s - no longer needs a game
   session or the panel: it is two disassemblies of the same pipeline cache with and without the prop
   (`TU_DEBUG=dumpshaders`), offline against the tree. It is not queued, because the wall is the vertex
   path at 85.5-91.6 % busy (40.21), this pass edits the fragment stage's output preamble, and no
   shipped patch carries `has_alias_rt` - neither answer changes a number or a decision here. A finding
   from that diff belongs in `docs/a7xx-gen-props.md`.

    Status 23.11: **run, counters only** - the operator's decision for this arm (journal 40.29):
    `exp-25` is built into both queue-16 trees, `TU_FORCE_PROPS=has_alias_rt` is applied (the delivery
    line is in the run log) and moves nothing on `cfg-vertex`: the largest counter delta against the
    same-build control is 1.8 % on TSE input, VPC busy differs by 0.06 %. The `cfg-vpc` preamble-mov
    signature this item asked for and the picture check are NOT MEASURED, so the column that would
    separate "the pass does not engage" from "it engages and is free" is still open.

    Of the properties only `a7xx_gen3`/A8XX set, ten are in the `TU_FORCE_PROPS` table and were swept
    in journals 15.7 and 34; the rest cannot be raised at runtime (`tu_device.cc:1750-1770` is a fixed
    list): `has_alias_rt`,
    `has_sw_fuse`, `new_control_regs`, `subpass_fence_cleans_resolve`, `gs_vpc_adjacency_quirk`. The
    last four are a raytracing fuse, a crashdec register rename, a resolve-wait behaviour and an A750
    hardware bug - none is a feature A740 is losing. `has_alias_rt` is different: the two registers its
    driver side writes, `SP_PS_OUTPUT_CONST_CNTL` and `SP_PS_OUTPUT_CONST_MASK`, are
    `variants="A7XX-"` (`a6xx.xml:4242`, `:4245`) and `tu_shader.cc:2890` already emits them for any
    A7XX, so the gate is a per-chip blob observation, not a missing register. What to run: add the name
    to the `TU_FORCE_PROPS` list (one line, same table), build, and A/B `TU_FORCE_PROPS=has_alias_rt`
    on the cached-shadow frame with `fdperf.cfg-vpc` - the pass removes constant components from FS
    output registers, so the visible signature is fewer preamble `mov`s and slightly less VS/PS work,
    both of which that cfg prints. It decides whether one more gen3 software feature is free on gen2
    or whether the gate is protecting a real hardware difference; the correctness side is a picture
    check, so a run is only usable if the scene is also captured with the panel on.

27. **The two third-party "locked behind gen3" claims that do not survive inspection** (no build, no
    run - recorded so the claim does not have to be re-investigated). Checked against
    `results/device-features-a740.txt` (both the distribution's driver and the ship stack, `vulkaninfo
    --show-all`) and against the source: `sparseResidencyImage3D` is `false` in both runs and the name
    occurs nowhere in `src/freedreno/`, with `sparseResidencyStandard3DBlockShape = false` at
    `tu_device.cc:1349` - no generation gets it, so it is not a lock our patch could remove;
    `sparseResidencyAliased` is already `true` in both runs and comes from `has_sparse_prr`
    (`tu_device.cc:495-509`), not from `ubwc_all_formats_compatible`; `VK_EXT_descriptor_buffer` and
    `VK_EXT_attachment_feedback_loop_layout` are exposed on this device today;
    `VK_KHR_fragment_shader_barycentric` and `VK_EXT_post_depth_coverage` are absent in both runs
    because the driver has no extension-table entry for them at all - and there is no `gen >= 3`
    condition anywhere in `src/freedreno/vulkan/` (the only matches for `a7xx_gen3` are a comment at
    `tu_lrz.cc:60` and the `TU_FORCE_PROPS` table), so "added for A750 and never tested on A740" cannot
    be the shape of that gate. What is left of the claim is a real but different question, and it is
    queue 26.

28. **`VK_KHR_ray_tracing_pipeline` on a device that answers ray queries** - CLOSED 23.11 by inspection,
    journal 40.26, no build. `VK_KHR_ray_query` and `VK_KHR_acceleration_structure` are exposed
    (`results/device-features-a740.txt:13`, `:15`), gated on `has_raytracing =
    props.has_ray_intersection && (!props.has_sw_fuse || kernel_fuse)` (`tu_device.cc:214-216`) with
    `has_ray_intersection` set for `a7xx_gen2` already (`freedreno_devices.py:825`) and `has_sw_fuse`
    only for `a7xx_gen3` (`:868`); the driver's comment names A740 explicitly (`tu_device.cc:209-213`).
    `VK_KHR_ray_tracing_pipeline` occurs zero times in `src/freedreno/`, so it is not implemented for
    any generation and gen2 loses nothing an A750 has. Nothing here needs it for RE4.

29. **The outside "geometry plan" for the 40.21 wall - closed by inspection, recorded so it is not
    re-investigated** (journal 40.25, no build, no run). Its four items: VSC/VPC/PC limits "under-set on
    gen2" - `num_vsc_pipes = 32` in every A7XX entry including FD740's, the VPC sizes that do differ
    (`has_gmem_vpc_attr_buf`, `0x20000`/`0xc000`) measured as a zero twice (15.2, 40.9), and no geometry
    tuning register is written by the driver at all; DGC - Turnip has no implementation and the shipped
    `d3d12core.dll` names the extension (`results/vkd3d-ext-strings.txt`), so the gap is real but it is
    CPU-side work against a GPU-side wall; async compute via `tu_knl_kgsl.cc` - there is no compute-only
    queue family here and no `/dev/kgsl-3d0` (`results/queues-a740.txt`); `VK_EXT_descriptor_heap` - the
    name occurs zero times in the shipped D3D12 layer, so RE4 cannot use it through this stack.

30. **What one vertex costs through the VPC - CLOSED 23.11 by journal 40.27, from committed dumps, no run.**
    Attribute bytes and components per vertex are the same on the two measured frames (31.81 against
    33.03 B/vertex while the frame rate differs by 74 %), so the VPC's RAM pressure is a volume problem and
    not a width problem, and the "make each vertex cheaper" family has no measured opening.

31. **The vertex-cache hit rate, and the first dead-primitive rate - run `fdperf.cfg-vpc4` in the session
    queue 10 owes anyway** (journal 40.33 is why this is the live half of the operator's 23.11 question). The
    cfg is written and NOT RUN: `tools/fdperf/fdperf.cfg-vpc4` is `fdperf.cfg-vpc` with PC 2, PC 4 and PC 21
    traded for id 39 `PC_TAG_CHECKED_VERTICES`, id 17 `PC_DEAD_PRIM` and id 10 `PC_STARVE_CYCLES_FOR_INDEX`
    (the PC group is capped at 8 and every cfg that carries hits uses all 8; ids are the `value=` attribute of
    the counter name in `../mesa27-src/src/freedreno/registers/adreno/a7xx_perfcntrs.xml`). It decides two
    things no committed dump answers: the pre-transform hit rate (19 over 39) - whether the game's vertices do
    hit the cache, which the 2.9:1 mesh-sharing ratio of journal 38 only bounds - and whether degenerate or
    restart topology is present at all, which no counter in any committed dump here has ever spoken of. No
    build, no new arm, no new window convention (20-105 s at the pinned clock).

### Numbers 24, 25 and 30: closed items whose numbers are still cited

Added 23.11, because `AGENTS.md` makes the number an address ("`journal 22.3` must resolve without
searching") and three records cite queue items that the list above no longer carries. Each line is a pointer;
the verdict lives where it points.

* **queue 24** - does the render-mode verdict of the heavy frame survive on the light (cached-shadow) one:
  journal 40.20 (chain27). Closed: it survives, the sysmem default is not tuned to the worst setting.
* **queue 25** - where the vertex path sits on the cached-shadow frame: journal 40.21 (chain28). Closed:
  still the busiest block, with 6 points of slack it cannot use.
* **queue 30** - what one vertex costs per vertex, on both frames: journal 40.27, and item 30 above.


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

32. **Turn off varying-to-uniform promotion and see whether this title misses it** - one line, NOT BUILT
    (journal 40.34 is where the call site and the RADV contrast are recorded). `tu_shader.cc:3878` calls
    `nir_opt_varyings_bulk(shaders, n, true, UINT32_MAX, UINT32_MAX, link_opts, ...)`; per `nir.h:5832` those
    two arguments are `max_uniform_comps` and `max_ubos`, the limits on promoting a varying into a FS constant
    or UBO load, and `radv_pipeline_graphics.c:1257` passes `0, 0`. Turnip is therefore more aggressive than
    RADV on a title whose wall is UCHE/L2 and the pixel side (40.34: SP at 94 % of its pipes in both frames),
    which makes promotion a cost candidate rather than a saving. Arm: `max_uniform_comps = 0`, `max_ubos = 0`,
    ship stack, one 150 s session per side, pinned clock. Decide on `UCHE_READ_REQUESTS_SP`, `SP_BUSY`,
    `VPC_BUSY`/`VPC_VPCRAM_FULL` and p25; a zero in all four closes the direction as an ADR, because it would
    mean the promotion never fires on this shader set.

33. **The control 40.30 cannot get from its own dumps: `BV_*` at a shared `tile_count`, two frames apart**
    (journal 40.34 checked that no committed dump allows the cut). Of the four `cfg-bv` arms only `cb21-h1`
    binned (8 of 40 steady windows, 3-14 tiles) and the other three have no binned window at all, so there is
    no tile-count overlap between the 15 fps and the 26 fps frame. Arm: `fdperf.cfg-bv` with
    `TU_DEBUG=startup,gmem,forcebin` on the Shadow-Cache-on frame, same save, one session. Decide by
    comparing rows at equal `tile_count` against `cb21-h1`'s windows: if a `BV_*` row is the same at 4 tiles
    on 8.4 M primitives/frame as on 16.7 M, 40.30's aliasing verdict has an independent variable behind it;
    if it moves with geometry, 40.30 is reopened. Recorded as a control, not as a measurement.

34. **Give `VPC_SP_COMPONENTS` and `SP_EXPORT_VPC_TRANS` a unit, or take both names out of the documents**
    (journal 40.34: they are equal in every window of the 33 arms that program both, so they are one signal
    and the per-vertex 0.63-1.04 is in a unit nothing describes). The cfg comments that explained them as
    "components handed to the FS" and "the other side of the varyings traffic" are corrected in place. Arm: a
    probe with a known interface - one vertex shader writing 1, 2, 4 and 8 vec4 outputs to the same fragment
    shader, same geometry, run once per setting outside the game (vkmark's framework or the vkcube rig), both
    selectors programmed. Decide: if the counter moves by 4 per added vec4 the unit is components and the
    reading means RE4's interface is tiny; by 1 per vec4 it is a vec4-shaped transaction; by nothing, the
    selector is inert and both names are retired like `UCHE_GMEM_*_BEATS`. Until then no document here may
    quote a per-vertex varying count, which is what question 24's evidence silently lacked.

35. **Does A740 hardware honour the VPC attribute-buffer registers, or does it drop them** - the question
    behind "are the gen2 sizes 0 because the block is absent or because nobody wrote them" (operator 23.11).
    **PARKED 23.11, by the operator after 40.35 ("пропускаем")**: nothing measured it, and it is parked
    with the question open, not answered. What exists for a later reader: the probe and its cfg and the
    arm table are built and committed (`tests/vpc-attrbuf.c`, `tools/fdperf/fdperf.cfg-attrbuf`,
    `scripts/run-attrbuf-sweep.sh`, all **NOT RUN**), what is known is in 40.35 and question 27, and the
    two obstacles that made it expensive are recorded below (the pass renders in sysmem, and the kernel
    will not give the GMEM figure, queue 36).

    The rest of this item is the plan as written, kept so the run does not have to be re-designed:
    Source cannot settle it: `a6xx.xml:3227-3239` declares `VPC_ATTR_BUF_GMEM_SIZE`/`_BASE` (0x9308/0x9309)
    and `PC_ATTR_BUF_GMEM_SIZE` (0x9b09) with `variants="A7XX"`, which covers A740 but is a family tag, not a
    sub-generation test, and 40.9's forced-prop arm proves only that the writes are not fatal (four minutes,
    no fault, every counter unmoved to 0.1 points). Synthetic, no build: an attribute-heavy probe (16 vec4 VS
    outputs, ~256 K vertices, slow FS, one GMEM-mode render pass) in five arms - stock; forced prop at the
    gen3 sizes; forced with `FD_DEV_FEATURES=gmem_vpc_attr_buf_size=4096`; the same at `131072`; and a
    prop-off arm with a smaller render target as the bin-count control, because the same number also shrinks
    `usable_gmem_size_gmem` by `num_ccu * size` (`tu_device.cc:1871`) and that alone changes work per bin.
    Delivery is proved twice per arm: the `TU_FORCE_PROPS: vpc_attr_buf_size sysmem=… gmem=…` log line (it
    fills defaults only into zeros, so the env value survives) and the bin count. Decide: if
    `VPC_VPCRAM_FULL`, `VPC_WIT_FULL`, `VFD_STALL_CYCLES_VPC_ALLOC` and `VPC_NUM_VPCRAM_WRITE` per vertex move
    monotonically from 4 KiB to 128 KiB at identical output, the block is real on A740, the gen2 zeros are an
    upstream props gap worth a patch, and the in-game sweep reopens; if a 32x range moves nothing while the
    bins do move, the registers are inert here and the direction closes as a negative ADR rather than a null
    result. Stay at or below 0x20000 and use no GS or adjacency: `gs_vpc_adjacency_quirk` says certain VPC
    sizes hang on a750 and nothing says the inverse is safe on a740.
    23.11, two things the smoke run settled before any arm was measured (`/tmp/opencode/vab-smoke.txt`
    and its dump, 11 windows at 680 MHz - to be re-taken into `results/synthetics/attrbuf/` with the
    first real arm): the pass renders **in sysmem** (`VSC_INPUT_TILES` 0 in all 11 windows, `VSC_BUSY`
    0.0009 M/s against a 680 MHz clock), and in that mode `VPC_VPCRAM_FULL` is 0 where the game shows
    50-71 %, so the arms would be comparing four counters that do not move. The probe has to be made to
    bin before the prop arms mean anything (`TU_DBG_RM_HIST`, the render-mode histogram of exp-24, is
    not in the ship `.so`, so the mode is read from the counters). The second finding is that the kernel
    will not say the GMEM size (queue 36), so the arms are built on an absolute `TU_GMEM` budget instead
    of on `G - 6S`: control arm `TU_GMEM=B`, prop arm `TU_GMEM=B+6S`, both ending at the same usable
    GMEM by construction, with no kernel read anywhere. What the run did give: the probe holds the VPC
    busy for 1.00 of a core (680.0 M/s against `CP_ALWAYS_COUNT` 680.0 M/s) and *working* for 0.447 of
    it, writes 2.00 `VPC_NUM_VPCRAM_WRITE` per vertex, and `VFD_STALL_CYCLES_VPC_ALLOC` is 11.6x the
    clock - the profile of a vertex-dominated synthetic that never bins. Two more columns came out of
    that dump and belong to queue 31, not here: `VPC_WIT_FULL` is 5.79x the clock while
    `VPC_LM_FULL_WAIT_FOR_INTP_END` is 0 (the probe's stall has a different name than the game's), and
    `PC_TAG_CHECKED_VERTICES` reads **0** in a mesh of 24576 independent triangles where every vertex
    must pass the cache - the same nothing-as-a-denominator that 40.33 complained about, now measured
    against its own control.

36. **Find out why `DRM_IOCTL_MSM_GET_PARAM` answers EINVAL to userspace while the driver's own init,
    which fails hard if it fails, succeeds** (found building the queue-35 probe, 23.11). Measured:
    `GPU_ID`, `GMEM_SIZE`, `MAX_FREQ`, `HIGHEST_BANK_BIT`, `pipe` 0 and 1, with the request number Mesa
    itself builds (`DRM_IOWR(DRM_COMMAND_BASE + 0x00, struct drm_msm_param)`, 24 B), on `/dev/dri/card0`
    and `/dev/dri/renderD128`, as the invoking user and as root - EINVAL in every case. Yet `/dev/dri/`
    holds only `card0` and `renderD128`, their uevent says `DRIVER=msm_dpu`, the probe holds both open
    while it draws, and its GPU mapping comes from `renderD128`. Arm: run the ship driver under
    `strace -e trace=ioctl` (the host has no strace; the container's, with `--pid=host`, will do) and
    see which node and which request it reads GMEM with. Decided nothing while queue 35 is parked (23.11),
    and worth the ten minutes anyway: a GMEM figure is the kind of number a later script will want, and
    "the kernel answers EINVAL to a request the driver's own init sends successfully" is a fact about this
    machine that no document here currently explains.
    Decides: whether any script here may compute a
    GMEM figure from the kernel at all - today the answer is no, which is why queue 35's arms are built
    on absolute `TU_GMEM` budgets.

## Open questions

| # | question | status |
|---|---|---|
| 1 | the ~2 % lost on the first fill into a fresh image, inside the driver | NOT MEASURED, and as of 23.11 it is not a queued check either: journal 20's own title calls it a probe defect, journal 29 class 4 is the mitigation (warm up before measuring), every probe in the suite now warms up, and `0013` closed the readback case it was thought to share. Whether a driver-side component remains is an unexplained behaviour with no decision hanging on it |
| 2 | moving `WAIT_FOR_IDLE` into `ExecuteCommands` | SUPERSEDED 23.11 by journal 21.11. The hypothesis it rested on - that `CmdExecuteCommands` loses the lazy bits - is refuted there: `tu_EndCommandBuffer` for a non-renderpass CB always does `tu_clean_all_pending()` + `tu_emit_cache_flush()`, `tu_CmdExecuteCommands` does the same for the primary before chaining secondaries (`tu_cmd_buffer.cc:6480-6487`), and `0013` puts `WAIT_FOR_IDLE` straight into `flush_bits`, where the nearest flush point executes it. No separate bit carry is needed |
| 3 | the price of mode 7 in RE4 | CLOSED 23.11 with queue 5: ADR-0008 plus 40.18's render-mode ladder (forced sysmem 15.18, default 15.34, GMEM without binning 13.74, GMEM plus binning 10.27, p25 95-150 s) leaves no decision a fifth rung could change |
| 4 | who creates the DEPOSED no-list images | vkd3d or DXVK, not separated (queue 6) |
| 5 | the 1024/262144 residue in the tiled run | unexplained, 0.39 %, does not change any verdict (journal 21.5). 23.11: it is the same kind of thing as the collector/TSE gap of 40.32 (2.6e-5 between two counters read across one fdperf window), so it is a note about counter granularity rather than a check anyone owes |
| 6 | fast clear under `_SFLOAT` (0012) | a byte round trip cannot see it; needs its own probe |
| 7 | 12_1 | blocked by `VK_EXT_fragment_shader_interlock`, which Turnip does not implement (ADR-0011) |
| 8 | the 32- and 16-bit classes in lazy deposition | they reinterpret the layout; a separate analysis, and the reason 0014 leaves them linear on purpose |
| 9 | R8 + UBWC: writer or reader | exp-19 (queue 2) |
| 10 | UBWC format variants for `R16G16B16A16_FLOAT` and `R32G32_FLOAT` | answered, journal 31: there is no "format variant" to look for (UBWC is a layout flag, and the layout never consults `fd6_ubwc_compat_mode()`); the class has a ceiling, both formats reach it as plain images, and `0012` is what gives them a compat mode - on the bare Mesa 27 base their classes lose UBWC |
| 11 | does vkd3d view a mutable RE4 image through another format of the same class | NOT MEASURED, exp-20 (queue 10): the inventories record creates, not views |
| 12 | is a `VkImageFormatListCreateInfo` with `viewFormatCount == 0` the same as passing no list | CLOSED 23.11 as not answerable on this rig - which is what the old status said in longer words. The spec makes the two equal, both print `listn=0` in every inventory, and `exp-21` deliberately keeps the worst-case answer. A distinction no instrument here can observe is not a queue item |
| 13 | why does the system driver give UBWC to a `MUTABLE` image with no list, where both Mesa 27 builds refuse it | CLOSED 23.11: deciding it needs the distribution's own Mesa sources (`mesa-vulkan-drivers-26.2.6-1.fc44.armada`, not in this repository), it changes no verdict, and `exp-18` does not depend on it. The row stays as the record of what was dropped and why |
| 14 | does a `R64_UINT`/`R64_SINT` view of a UBWC image work, once `STORAGE` makes it legal | ANSWERED 21.11, journal 37: probe `XR64` built the shape and ran it - a no-list `MUTABLE` image with `STORAGE` in the usage, UBWC kept by the `TU_UBWC_NOLIST_64` knob of `experiments/exp-23-ubwc-nolist-64-knob.patch`, stays tiled with the `+0x2000` tail and reads `0/262144` wrong through an `r64ui` storage image, including after `imageAtomicAdd(+1)` per word. It also settled the shape question: a list that *names* `R64_*` is refused compression by `FD6_UBWC_UNKNOWN_COMPAT` with the knob on and off, so the no-list create was the only place the question could be asked at all. `results/test-xr64-nolist-64-ubwc.log`. Still open inside the answer: `sparseImageInt64Atomics=0` on this device, so the sparse corner is unmeasured, and journal 38 puts the class on the SP client, which is 0.3 % of measured DRAM reads |
| 15 | is the compressor actually writing compressed bytes, or only a metadata plane | ANSWERED 22.11, journal 40.17: yes, bytes. In RE4's steady stretch the bus carries 317 MB/s of `PERF_UCHE_UBWC_READ_BEATS` and 37 MB/s of `..._WRITE_BEATS` against 15.59 / 0.29 GB/s of VBIF traffic - 2.0 % of the read bytes, 2.4 % of the texture client's requests - and the switch that proves the counter means what it says is on the application side: `VKD3D_CONFIG=disable_color_compression,disable_depth_compression` in the shipped vkd3d-proton drives all four UBWC counters, and the TP UBWC request counter, to exactly zero in 52 of 52 samples while the CMPDECMP write-data column doubles. `tools/fdperf/fdperf.cfg-traffic`, `scripts/fdperf-traffic-table.py`, `results/games/re4/traffic-ubwc-ab.txt`. Also measured in the same pair: taking compression off costs +0.9 % DRAM read, +10 % DRAM write and no measurable frame rate. Still open inside the answer: which images the 317 MB/s belongs to - the counters are global, so whether `0014`'s images are inside that 2 % is queue 16, not this |
| 16 | does any of the reachable driconf perf options change fps in RE4 | ANSWERED 23.11, journal 40.23 and queue 12: no. `disable_conservative_lrz` 27.13 p25 (14 windows) against a same-configuration cluster 26.53-26.67 with every LRZ counter unchanged; concurrent binning was already a zero as `TU_DEBUG=forcecb` (journal 40.8); the FDM option has no attachment to act on (journal 35.1, 0 density-map images in 11 984 creates) |
| 17 | what does the game do when the driver reports less memory than the heap it reports today | NOT MEASURED, queue 13. The report itself is measured - journal 34.4, `results/vulkaninfo-heap-report.log`, five `vulkaninfo` runs over `heap_memory_percent` - and the queue names the two values to try in the game. What vkd3d-proton does under a smaller report is not, and journal 17's 3129 MiB peak against 4.95 GiB of swap is why the question is not empty |
| 18 | is any of the 22 shading-rate images ever attached to a render pass, and at what rates | CLOSED 23.11, no buyer. Journal 35.1 counts the 22 images and 35.2 measures the capability, and the attach question needs one `if` plus a build - but 40.21 prices the ceiling: `PS_BUSY` 76.97 % against `VPC_BUSY` 85.54 % on the cached frame and 91.6 % on the ship frame, so removing fragment work cannot lift a vertex-bound frame. Whether the game uses VRS would be a curiosity with nothing downstream of it |
| 19 | what did the 2450.3 MiB that `0014` v1 moved out of linear buy in traffic or fps | ANSWERED 23.11, both halves: fps by 40.29 (A 26.12, B 25.62, ship 26.52 - inside a band this frame cannot resolve), traffic by 40.31 read out of the same committed dumps (TP 81.86 % of reads with `0014` against 82.11 % without, 14.82 against 14.62 GB/s total, same-configuration spread 1.74 %). The largest layout change in this stack is worth no measured traffic; layout closes as a lever and `0014` stays as correctness and volume (queue 16) |
| 20 | does the committed `patches/0014-turnip-mutable-no-list-tiling.patch` describe the tree that built the shipped `c17d02bcaae9…` | SETTLED 23.11. `patches/0014-*.patch` was regenerated to the one-decision text the tree carries and the queue-16 A arm was built from (`docs/release.md` records the p14 binary as the older text, measured equal in journals 33, 36, 40.29), and 40.28 established the harder fact underneath it: this tree minus both rigs builds `f80d33ab2077`, not the ship `4c3cdb210082`, so no build on this machine reproduces the release and a hash is only ever compared against another build hash. `git apply -R` still fails on the shared tree (it carries `exp-14`, `exp-25` and the `TU_DBG_RM_HIST` rig, plus the 0004/0005 drift 40.28 names), which is why A and B are `cp -a` copies - queue 0's state line |
| 21 | what is the wall at 26.7 fps, i.e. with the game's Shadow Cache on | ANSWERED 22.11, journal 40.21 (`results/games/re4/occupancy-two-frames.txt`): the same wall with 6 points of slack - `VPC_BUSY` 85.54 % against 91.57 %, `VS_BUSY` 80.65 %, `PS_BUSY` 76.97 %, and the primitive collector waits on the vertex path 12.7 points less. No block goes from idle to busy, so the "+9…13 % for a non-geometry driver fix" ceiling of 40.10/40.15 stands on this frame too |
| 22 | what do `LRZ_BUSY_CYCLES`, `RAS_STALL_CYCLES_LRZ` and `RB_STARVE_CYCLES_LRZ_TILE` actually count on A7XX | CLOSED 23.11 as a check, kept as a rule: 40.23's bar on quoting `LRZ_BUSY_CYCLES`, `RAS_STALL_CYCLES_LRZ` and `RB_STARVE_CYCLES_LRZ_TILE` as a cost costs nothing, because no verdict after it rests on them (40.26 and 40.27 argue from `VPCRAM_FULL`, `WIT_FULL`, `LM_*`). Deciding the semantics needs a synthetic depth-overdraw pass in the rig, and nothing downstream waits for it |
| 23 | is `alias.rt` correct on A740, given that its two registers are declared for A7XX | CLOSED 23.11 with queue 26: the prop is delivered and moves no counter and no fps (40.29 - 1.8 % on TSE input against the same-build control, 0.06 points of VPC busy, 1.2 % fps); whether the pass engages is a diff of two disassemblies with and without `TU_FORCE_PROPS=has_alias_rt`, offline, and no shipped patch carries the property, so neither answer changes a number here |
| 24 | does RE4's shader set push varyings through the VPC that the fragment stage never reads (the one live sub-point of the outside geometry note of 23.11) | ANSWERED IN BOTH HALVES 23.11, journal 40.26: the fp16 half is a measured zero (`IR3_SHADER_DEBUG=nofp16` moves `VPCRAM_FULL` by 0.38 points of busy and p25 fps by 1.0 %, delivery of the flag unproven), and the dead-output half is closed by the code - the driver sizes the interpolators from what the FS reads (`tu_pipeline.cc:744`, `:683`, `:802`), so an unmatched VS output gets no slot. What remains is not "dead varyings" but the width itself, and that is measured: queue 30 closed 23.11 by journal 40.27 from committed dumps - per vertex the two frames are the same workload (31.81 against 33.03 B/vertex while the frame rate differs by 74 %), so the "make each vertex cheaper in the VPC" family has no measured opening. 23.11, 40.34: the `SP_COMPONENTS` column of that entry is withdrawn - it is one signal with `SP_EXPORT_VPC_TRANS` and has no unit - but the width argument stands on `VFD_DECODED_ATTRIBUTE_BYTES` and `VFD_NUM_ATTRIBUTES`, which are unaffected; the varying count itself is queue 34 |
| 25 | is the vertex path recomputing vertices because of a driver setting - vertex cache size, `prim_restart`, topology - as vkd3d-proton might provoke (operator, 23.11) | ANSWERED 23.11, both halves, journal 40.33. Driver side: nothing to check - `tu_pipeline.cc` (5345 lines) has no cache size, cache mode, restart or topology state, and turnip never reads `max_pc_dest_regs`; restart is written from the game's own dynamic IA state (`tu_cmd_buffer.cc:8703-8725`, `primitive_restart_enabled && indexed`). Counter side: the reuse this repository quotes (2.9:1, journal 38) is mesh sharing, an upper bound on what a cache could save, and the cache's own hit rate has never been measured - `PC_VERTEX_HITS` (id 19) is in nine of the thirteen cfgs, its denominator `PC_TAG_CHECKED_VERTICES` (id 39) in none that has run. That is queue 31, whose cfg (`tools/fdperf/fdperf.cfg-vpc4`) is written and NOT RUN. Whether RE4 uses primitive restart or strip topologies at all is unmeasured and unmeasurable with the cfgs that exist |
| 27 | does the A740 attribute-buffer hardware exist, or only its absence from the gen2 prop table | PARKED 23.11 (operator, after 40.35; queue 35 parked with the probe built and not run). Unanswered, not answered: the hardware half was never measured. What is settled: the prop, both sizes and all three CS emissions are gated on `has_gmem_vpc_attr_buf`, the field is labelled "Vertex attrib cache (a750+)" and `a7xx_gen3` is the only a7xx generation that sets it, so on a740 the registers are never written and the GMEM layout never consults them (40.34). 23.11 (40.35): the other half of the explanation - that a base block sets the value and the FD740 entry merely stays silent - is refuted by importing the generator and reading the **merged** props: the three names appear in no block before `a7xx_gen3`, while control props do reach FD740 from `a7xx_base` (`results/props-a7xx-vpc-attr-buf.txt`), so the zero is a declaration gap in the driver and nothing more. What is not settled: whether the silicon has the carve-out at all - `a6xx.xml` declares the registers for the whole `A7XX` variant, which includes A740, and 40.9's forced-prop run shows the writes are accepted and change nothing. The synthetic in 35 separates the two, with a bin-count control arm for the confound that the same number also shrinks usable GMEM |
| 26 | is the VPC a compute wall, and is its attribute RAM full because it spills or because the consumer below drains slowly | ANSWERED IN PART 23.11, journal 40.34, no run: it is not compute (`WORKING/BUSY` 0.630-0.687) and the stall is named (`VPCRAM_FULL` 50-52 % of busy on the ship frame, 71 % on the Shadow-Cache frame, i.e. 0.48 against 0.61 of a core), it needs no divider (max `VPC_BUSY/CP_ALWAYS_COUNT` 0.9345 over all 72 dumps, against 12.05 for SP), and the spill half of the fork is unanswerable with these counters - `UCHE_WRITE_REQUESTS_VPC` is 0.000 in every window of all 15 arms that program it, the same dead-zero pattern as 40.15 and `VPC_NUM_LM_REQ_HIT`. What the dumps do say is that fullness grows on the frame with half the geometry, which is the shape of backpressure and not of supply. Mechanism stays open: no counter here measures credits, and no size knob exists on this generation, so nothing downstream waits for it |

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
