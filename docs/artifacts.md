# Artifact inventory

What each file in this repository is for, and what it proves. Reference only: no
conclusion lives here, the journal and the ADRs own those. When you add an artifact,
add a row here and say in the file itself how to regenerate it.

## Shipped patches (`patches/`)

| # | what it does | what verified it |
|---|---|---|
| 0001 | disables cross-sync graphics/sparse (works around a fault storm on the A740) | image patch |
| 0002 | chip-id A830 (port of the ROCKNIX patch) | image patch; on Mesa 27 the id line already exists upstream, so the patch is a no-op there |
| 0003 | disables bindless UBO const lowering in ir3 (ROCKNIX) | image patch |
| 0004 | lifts the sparse-residency gate, refuses sparse+MUTABLE with no list | `sparseResidencyImage2D` 0 -> 1; the hole shows as `SUCCESS -> FEATURE_NOT_PRESENT` |
| 0005 | uniform-swap lists keep the tiling | probe `S`: FAIL -> PASS |
| 0006 | B8G8R8A8 -> one INT compat type | `memreq 0x100000 -> 0x102000` |
| 0007 | `TU_FORCE_PROPS` (env override of device props) | a tool, not a behaviour change |
| 0008 | gen2 generic clear | vkmark -61..-65 % (vertex/shading/texture) |
| 0009 | NV12 + MUTABLE: remove only the tiling ban | probe `N`: `FEATURE_NOT_PRESENT -> SUCCESS` |
| 0010 | a single-channel format does not argue about channel order | 2 of 72 classes; BGRA8 EXACT |
| 0011 | R16/10-bit rows in the UBWC compat table | `CEIL`: a ceiling exists; 36 -> 44 classes |
| 0012 | `_SFLOAT` in the integer compat classes | 31 -> 36 classes; EXACT |
| 0013 | CCU clean after `buffer->image` on A7XX (deferred bits) | 19 MISMATCH -> 0, 94/94, three repeats |
| 0014 | mutable with no list: the compatibility class instead of `NULL` | probe `NL`: 8/8 layouts and round trips; +2201 MiB tiled by the model, 2170 MiB measured. A candidate that keeps the rule and removes its duplication stands in `experiments/exp-21-mutable-one-decision.patch` (queue 11, NOT BUILT); it replaces this file only if the equivalence run agrees |

`0001`-`0003` belong to the image recipe (they cannot be removed from `image-build/`);
`0004`-`0014` are this project's stack. Origin of `0001`-`0003`: `patches/PATCHES.md`.
Rejected candidates and the criterion for rejecting: `patches/DROPPED.md` and the files
under `patches/dropped/`.

A row here is a pointer, not a summary: *why* a patch exists and what it must not do is
the header of `patches/00NN-*.patch` (and the class-by-class table of `0014` is there, not
here), the verdict is an ADR in `docs/decisions/`, the measurement is a journal entry.

## Experiments (`experiments/`, never for commit)

`exp-1`..`exp-23` (there is no `exp-12`; `exp-18`, `exp-19` and `exp-20` are queued
and have no file - the queue owns those numbers), full discussion in
`experiments/README.md` and in the journal entry named below.

| exp | question | verdict | journal |
|---|---|---|---|
| 1 | can gen2 reinterpret a UBWC image | no | 16 |
| 2 | does `MUTABLEEN` itself break things | yes | 21 |
| 3 | does a create-time refusal remove the game's error message | discussed, no volume case | 4 |
| 4 | `WZYX` forced when `is_mutable` | all corruption lives in the swap | 21.3 |
| 5 | UBWC without `MUTABLEEN` | not possible, the bit is not at fault | 21.4 |
| 6 | cross-order `{BGRA8, RGBA8}` tiled+UBWC | the mechanism works, the semantics change -> reverted | 16 |
| 7 | NV12: remove only the tiling ban | -> 0009 | 18 |
| 8 | `_SFLOAT` in integer classes | -> 0012 | 20.5 |
| 9 | single-channel does not argue about the swap | -> 0010 | 21.3 |
| 10 | `is_mutable` without UBWC/sparse | breaks BGRA8 (one swap instead of two) | 21.4 |
| 11 | R16/10-bit | -> 0011 | 21.6 |
| 13/13b | clean before i2b | 91/91 -> 0013 | 21.8 |
| 14 | image inventory (`TU_IMG_INV=1`) | 4062 MiB of `MUT listn=0` in linear -> 0014 | 21.12 |
| 15 | 16 `TU_B2I_SYNC` modes | mode 7 -> 0013 | 21.11 |
| 16 | stock Mesa 27 + one line `ubwc_all_formats_compatible` in `a7xx_gen2` | the prop alone breaks `MUTABLE+SPARSE` creates: 73 EXACT against 76 on stock | 26 |
| 17 | is `{16,4}` in `fdl6_get_ubwc_blockwidth()` the cause of the 8bpp corruption | no: {16,4}/{32,4}/{64,4} corrupt identically, {16,8}/{32,8}/{8,8} fault the GPU; a diagnostic override, never part of a shipped stack | 22.4 |
| 21 | can `0014`'s rule be written once: one function decides the mutable layout, the create calls it, the class reaches the layout predicates only | candidate that replaces `0014` (graduation number `0016`); applies clean on `0001..0013`; **built** 21.11 (`build/out-exp21`, `d49d094a8d6e…`) and **measured indistinguishable** from the released stack on every probe of that run - `results/test-exp21-equiv-p14.log`; the game inventory column is what is left of its gate | 21.12, 33 |
| 21b | with the create path no longer comparing predicates, do the three predicates (`0004`'s two and `0005`'s) go back to `static` | tail of 21, kept as its own gate because it lands on the definitions `0005`/`0010` wrote; **NOT BUILT** | 21.12 |
| 22 | do `FD6_UBWC_R16G16B16A16_INT` and `FD6_UBWC_R32G32_INT` describe one cell of the compressor on this chip (`TU_UBWC_64B_MIX`, folds that one pair and nothing else) | one cell in the paths probed: with the knob on, the mixed `{R16G16B16A16_UINT, R32G32_UINT}` create carries the metadata tail and reads `0/262144` wrong through a view of either family; the knob moves two lines of a 621-line log. Reverted from the tree after the run | 32 |
| 23 | does a UBWC 64-bit image made **without** a format list read and write correctly through an `R64_UINT` storage image (`TU_UBWC_NOLIST_64`: declines the no-list UBWC demotion for 8-byte base blocks, nothing else) | in the probed shape yes: the create keeps the metadata tail (`+0x2000`), stays tiled, reads `0/262144` wrong through `r64ui` and comes back exactly +1 per word after `imageAtomicAdd(+1)`; a list that *names* `R64_UINT` is refused compression with the knob on and off, which is why the question had to be asked without a list. Reverted with `git apply -R` after the run | 37 |

## Tools

| file | role |
|---|---|
| `tests/rp6-vkd3d-sparse-test.c` | the main test: probes `U`/`T`/`S`/`V`/`N`/`CEIL`/`NL`/`X`/`XV`/`XMC`/`Y` plus the 94-row matrix. `CEIL` measures four images per row, the fourth being a `MUTABLE` image with no format list (journal 31). `XMC` is the only probe that fills and reads: a 64-bit image, one view per UBWC compat family, plus a `DETECT` shape whose fill is broken on purpose so that "0 wrong" stays a statement (journal 32.2) |
| `tests/rp6-vkd3d-sparse-xmc_{u32x4,u32g32}.glsl` -> `tests/rp6-vkd3d-sparse-xmc_spv.h` (`scripts/gen-xmc-spv.sh`) | the two integer readers of probe `XMC`: the same texel fetched as four 16-bit channels and as two 32-bit words, `usampler2D` so that no `[0,1]` decode sits between memory and answer. `glslangValidator` needs `-S comp` for a `.glsl` file |
| `tests/tp8bpp.c` + `tests/tp_write.comp` (`scripts/gen-tp-write-spv.sh`) | standalone 8bpp+UBWC probe: `Z` (NV12 Y), `AA` (`imageStore` writer), `AB` (2D copier), each with a LINEAR control and a dump of the whole allocation. Build: `podman run --rm -v …/tests:/work:Z -v …/build:/out:Z localhost/mesa-build-fedora44-wsi-glslang-vulkan bash -c 'cd /work && gcc -O2 -Wall -o /out/tp8bpp tp8bpp.c -lvulkan'`; size via `-DW=… -DH=…`. Read the header: the tool prints the number of WRONG elements |
| `tests/repro-first-fill.c` | minimal repro of the "~2 % on the first fill" effect |
| `tests/vk-fmt-classes.json`, `scripts/gen-vk-fmt-classes.py` | the Vulkan texel compatibility classes, generated from `vk.xml` (provenance inside the file): which view formats are legal for a base format, with and without a list - the table that decides both `0014`'s rule and journal 24.4 |
| `scripts/gen-journal-index.py` | regenerates `docs/analysis.md` and `docs/journal/manifest.json` from the journal entries |
| `scripts/fmt-list-gate-check.py` | model of the gate (`--vkd3d`, `--no-list`, `--exp-9`, `--blockers`). `--strict-class` is the exp-18 model: the three UBWC predicates ported to Python, asked of all 23 Vulkan classes, with `fold_64()` mirroring the `exp-22` knob so the measured pair and nothing else can widen a class. A model, never a measurement (its header says so) |
| `scripts/imginv-stats.py`, `scripts/imginv-classes.py` | inventory counters (mutable from `flags & 0x8`, not from the `mutable=` field) |
| `scripts/imginv-usage-bits.py`, `scripts/nolist-residue.py` | the two inventory cuts that answer "what did the application ask for" (usage bits, with `HOST_TRANSFER` 0x400000 counted) and "how much is left demoted" (no-list `MUTABLE` residue per base format, with a `small` column for the stock `width0 < 16 * blockwidth` fallback); both print the bit/flag values they used, so a wrong constant is visible instead of silent |
| `scripts/class-order-check.py` | offline, no build: runs `tu6_format_list_has_swaps()` / `tu6_format_list_reinterprets_r8g8_r16()` over the whole **compatibility class** of a base format, using `tests/vk-fmt-classes.json` and the swap column of `fd6_format_table.c`; prints per base whether its class can be tiled at all |
| `scripts/ubwc-dump-analyze.py` | allocation dump analysis: metadata-plane shape, written chunks, how many metadata bytes were written (`--meta`, `--pitch`) |
| `scripts/sweep-8bpp-grid.sh` | runs `tp8bpp` over metadata grids through `TU_8BPP_UBWC` (works only on the exp-17 build) |
| `scripts/run-test.sh`, `scripts/run-b2i-matrix.sh`, `scripts/run-game.sh`, `scripts/fps-window.py`, `scripts/curate-game-log.sh` | running the test, the mode matrix, the game, the fps window |
| `scripts/fdperf-sample.sh`, `scripts/fdperf-analyze.py`, `scripts/fdperf-align.py`, `tools/fdperf/fdperf-windowed-delta.patch` | profiling (see `docs/fdperf-a7xx.md`) |
| `scripts/fdperf-vpc-ratios.py`, `scripts/fdperf-tse-ratios.py`, `scripts/fdperf-vpcram-ratios.py` | the steady-window ratio tables for the three cuts of the vertex path: the vertex-path ratios (VPC split, PC/VFD/UCHE coupling, DRAM by client), the TSE-discard ratios (visible/input, the reason counters, VSC busy and tiles fed), and the VPC's own memory system (`VPCRAM_FULL`, `WIT_FULL`, `LM_*`). Each prints a counter it cannot see as missing rather than as 0 |
| `scripts/fdperf_sections.py` | the one dump loader behind those scripts: `load_sections()` separates the ordinary counter groups from their `BV_*` twins (`a7xx_perfcntrs.json`) so a BV-only name is never read as the block's own, and drops `u64`-wrapped window deltas (`2**64-82` seen in `fdperf-cbbase`) instead of averaging them; `load()` is the ordinary-only view the ratio scripts use |
| `scripts/fdperf-bv-table.py [--lo] [--hi] <dump> ...` | the two halves of one dump side by side, ordinary group against its `BV_*` twin - the only reader that wants both, and the table journal 40.11 is written from. Cycle counters are given as Mc/s and % of the core, event counters per second, and a counter of the ordinary group that the cfg never programmed prints `-` rather than the BV value under the same name |
| `scripts/fdperf-arm-table.py [--lo] [--hi] [dir ...]` | the cross-run comparison: one row per `results/games/re4/*` run with VPC busy, PC stall on VPC, UCHE arbiter stall, VFD/TP starve on UCHE, TP busy, TSE input and visible share, DRAM reads and p25 fps. It states its windows in the header (counters 20-105 s, fps 60-90 s, the same window every journal-40 fps number was taken on), averages every duty cycle over pinned-clock windows only and says how many windows it dropped and what the dump's median clock was, prints `-` for a counter the cfg did not program, and says `NOT MEASURED` with a note when no fps file is mapped - which runs map to which `results/games/re4/fps-*.csv` is written down in the script's `FPS` table |
| `scripts/fdperf-tile-table.py [--lo] [--hi] [dir ...]` | the binning-pass indicator across the nine runs that can be asked about it: `PERF_VSC_INPUT_TILES` and `VSC_BUSY` cut over the steady window and over the pinned-clock window, side by side, with each run's cfg and `TU_DEBUG` written down in the script rather than inferred. Journal 40.12 is read from it, and it is the file that shows the tile counter is a per-session property |
| `tools/fdperf/fdperf.cfg`, `tools/fdperf/fdperf.cfg-vertex`, `tools/fdperf/fdperf.cfg-vpc`, `…-vpc2`, `…-vpc3`, `…-cfg-tse`, `…-cfg-tse2`, `…-cfg-tse3` | the counter sets: "who owns the wall", "who owns DRAM and the vertex fetch", "what is the vertex path busy with", "why the VPC is busy" (the `WORKING`/cross-block-wait half of the same budget), "is the VPC's own RAM the limit", "how many primitives does TSE throw away", "why", and "is anything binned at all" (`VSC_BUSY` + `VSC_INPUT_TILES`). The TSE cuts and the VPC cuts split hardware budgets of 4 and 6 and cannot be merged into one run; each header names its budget use and what had to be left out |
| `tools/fdperf/fdperf.cfg-bv`, `…-cfg-bv2`, `…-cfg-bv3` | 22.11, journal 40.11: the first cfgs here to name the `BV_*` groups instead of leaving them at their defaults - `-bv` programs `BV_VPC`/`BV_TSE`/`BV_PC`/`BV_TP`, `-bv2` drops `BV_PC`/`BV_TP`, `-bv3` keeps `BV_VPC` alone. The three exist to find which section, if any, takes the VSC tile counter away (it did not: `cfg-tse3`, which has no BV section at all, read 0 tiles/s in the 22.11 session too) |
| `results/games/re4/<cfg>-<tag>/` | one directory per 21.11/22.11 game run (`fdperf-raw.txt` + `fdperf-per-window.tsv`), the artifacts every ratio table in journal 40 is re-cut from; `results/games/re4/fps-<tag>.csv` is the matching MangoHud file |
| `results/games/re4/bv-idle-labelcheck.txt` | an idle-GPU pair of `fdperf -r 200 -d` dumps, `cfg-tse3` against `cfg-bv`, kept for its **labels**: it is what proves a `BV_*` cfg section reaches the BV groups (`PERF_PC_IA_PRIMITIVES`, `PERF_VPC_VPCRAM_FULL_CYCLES`, `PERF_TSE_INPUT_PRIM` appear in the BV half only with `cfg-bv`), the control journal 40.11 is read against |
| `scripts/build-turnip*.sh`, `scripts/build-test.sh`, `container/` | building the driver and the test (there is no compiler on the device). `build-test.sh` installs the toolchain only if the image lacks it - on 20.11 a failed Fedora mirror download broke the build although the image had gcc and the headers |

## Logs that are cited as evidence

| log | what it proves |
|---|---|
| `results/games/re4/game-patched.log` | journals 8 and 9: the patched driver failing `vkCreateInstance`, and the same run after rebuilding with WSI. Care, learned 21.11: `scripts/run-game.sh` without `TAG=` writes here, so a bare run overwrites a cited artifact - always pass `TAG=`, and re-cut this file from git if it was clobbered |
| `results/test-b2isync-{0..15}.log` | the exp-15 mode matrix |
| `results/test-BCcopy-i2b*.log` | 91/91 for i2b |
| `results/test-BCcopy-0013cand*.log` | 91/91 for b2i (both forms) |
| `results/test-r8-split-{on,off}.log` | R8: content corruption, not a readback artefact |
| `results/test-y-8bpp-{on,off}.log` | R8 + UBWC compared on two independent readers (`d2r` and `texelFetch`): with `has_8bpp_ubwc=1` both are wrong, with `0` both are EXACT |
| `results/test-y-8bpp-sweep-blockwidth.log` | metadata-geometry sweep through `TU_8BPP_UBWC` (exp-17, matrix probe): the grid is not the cause; the `16x8`/`32x8` branches are `VK_ERROR_DEVICE_LOST` |
| `results/test-8bpp-grid-sweep.log` | the same sweep with the standalone tool: memreq, what reads back, how many metadata bytes were written - 1024 bytes whatever the reserve |
| `results/test-8bpp-tp8bpp-stock.log`, `results/test-8bpp-tp8bpp-sizes.log` | probes Z/AA/AB on the ship `.so 4c3cdb21`: NV12 EXACT; R8 wrong in 74.71 % of elements (a readable quarter); the 2D copier writes no metadata; the LINEAR controls are exact. Sizes 512/256/64: the readable fraction is 25.29 % at every size, first wrong texel `x = W/2` |
| `results/test-8bpp-meta-pitch-height.log` | metadata pitch sweep (64 -> 512 B) and image height: always 1024 B written, always 25.29 % readable |
| `results/test-8bpp-meta-shape.txt` | allocation-dump analysis: the AA metadata plane (1024 of 8 KiB, all `0x1f`), the zero metadata of AB, the dense metadata of a working NV12 |
| `results/test-z-nv12-y8.log` | NV12 Y (`cpp == 1` UBWC, grid `{32,8}`, not gated by the prop) round-trips EXACT in both tilings |
| `results/test-r8-has8bpp-{on,off}.log` | the first R8 measurement with the flag (October); superseded by the split and Y runs |
| `results/test-CEIL-*.log` | UBWC ceilings, measured with three images (journal 21.6.2) |
| `results/test-CEIL-nolist-{p14,mesa27base,mesa26system}.log` | the same probe with a fourth image - a `MUTABLE` image with no format list - on the ship stack, the bare Mesa 27 base and the system driver: the 64-bit class has a ceiling, and nothing reaches it without a list on either Mesa 27 build (journal 31) |
| `results/test-V-*.log` | tiling of a BGRA8 UAV |
| `results/model-strict-class-nolist.txt` | what a strict class rule for a no-list `MUTABLE` image would grant on a7xx_gen2, class by class, in four blocks: as it reads, on the Mesa 27 base, with the members the format table cannot lay out excluded, and with the measured 64-bit pair folded. Generated by `scripts/fmt-list-gate-check.py --strict-class`; a model, no GPU involved (journal 32.1) |
| `results/test-xmc-64bit-compat.log` | the two 64-bit UBWC compat labels on A740: three runs of one binary (released driver, the `exp-22` tree with the knob off, the same `.so` with `TU_UBWC_64B_MIX=1`), the whole-log diff, the `XMC` sections verbatim, the `SGL`/`NOL`/`DETECT` controls. Both families read `0/262144` wrong through a view of the other (journal 32.3) |
| `results/test-exp21-equiv-p14.log` | `exp-21` against the released stack: one test binary, two drivers, **full** logs compared, 0 differing lines of 598, verdict-word counts, the sections listed, and the header naming what the equality does not cover (journal 33) |
| `results/test-perfprops-rig.log` | the driconf perf options outside `TU_FORCE_PROPS`, on the released driver: what each of the five is in the driver's own words, where the value is read, which one a740 cannot reach without a build, and five full runs of one test binary compared as text - 0 differing lines of 621 for each of the four forced options, each carrying the driver's own line proving the option was applied. Not a performance measurement, and the file says so (journal 34.3) |
| `results/vulkaninfo-heap-report.log` | what the driver reports about memory on this machine: five `vulkaninfo` runs against the released driver with `heap_memory_percent` at its default and at 0.5/0.4/0.25/0.05, the reported `size` and `budget` verbatim, the memory-type control, and the code path both numbers come from. A report, not a footprint, and the file says which column follows the option (journal 34.4) |
| `results/test-uq-quirk-{off,on}.log`, `results/test-uq-after-removal.log` | the `ubwc_coherency_quirk` on gen2: not reproducible, and the probe's removal verified |
| `results/test-p14-{base,ubwc-allformats}.log` | A/B of the prop on the ship driver through `TU_FORCE_PROPS` |
| `results/test-gen2flag-table.log`, `results/test-gen2flag-minstack.log` | the prop in the gen2 table (same behaviour as the env override); the reduced stack (two new FAILs, so no patch is freed) |
| `results/test-restore-shipstack.log` | rebuilding the ship stack reproduces the p14 matrix line for line |
| `results/test-0014v2-matrix.log`, `…-forceflag.log` | 0014 v2 broken on `RGBA8->BGRA8`/`BGRA8->RGBA8` while the 94-row counter does not see it |
| `results/test-stock-mesa27-matrix.log`, `results/test-stock-flag-matrix.log` | stock 76 EXACT against 73 with the prop: the prop alone breaks `MUTABLE+SPARSE` creates |
| `results/imginv-3variants.txt` | the counters for the three inventories (no 0014 / with 0014 / stock + prop); the tables in journal entry 27 reproduce from this file, the raw game logs are not in git |
| `results/nolist-residue-p14.log` | the no-list `MUTABLE` split on the p14 stack: 2474 creates / 4081.1 MiB, 1450 / 2450.3 MiB tiled by `0014` v1, 1024 / 1630.8 MiB residue per base format with SAMPLED/STORAGE columns and a `small` column (84 creates / 0.9 MiB linear by the stock width fallback, which is not a rule decision) |
| `results/games/re4/mesa27*/steady-state.txt` | the memory wall |
| `results/test-xr64-nolist-64-ubwc.log` | the `R64_UINT` storage read and `imageAtomicAdd` round trip over a UBWC 64-bit image made without a format list, on three drivers: the released stack, the `exp-23` hook off, the hook on |
| `results/games/re4/fps-gov-*.csv` | the governor is noise |
| `results/games/re4/fps-ctrl100{,b}.csv` | the "1.86 fps" artefact |

Raw game and driver logs live in `results/raw/` and are gitignored: a curated file in
`results/` is what git sees and what a claim may cite.

## Captures of other people's work (`results/external/`)

Not artifacts of a measurement - no build hash and no device is involved. They are kept so
an outside proposal can be read without depending on somebody else's repository staying
online, and so the claim "their stack contains X" can be separated from "their stack
contains X in a form that applies to Mesa 27.0-devel". Owned by journal 30.

| file | what it is |
|---|---|
| `results/external/sherft2607-turnip-adreno722-duo/repo-tree.txt` | the file list with byte sizes and which files that builder applies, from the GitHub tree API (`766b5ef7034f`), plus the stack grouped by kind |
| `…/30-tu-z-mutable.py`, `…/33-tu-z-bgra-swap.py.off`, `…/34-tu-z-mutable-swap.py.off`, `…/35-tu-z-mutable-safe.py.off`, `…/37-tu-z-bgra-companion.py.off` | the five mutable/BGRA-related scripts, captured byte-for-byte with `curl`; the sizes match the ones the API reports |
| `…/apply-check.txt` | the dry run of those five against six source files of `../mesa27-src`: which anchors land, which do not, with the command to regenerate |
| `results/external/winnative-emu-drivers/tree.txt`, `…/size-check.txt`, `…/capture.txt` | the Drivers tree pinned at `c71f600a2977` (35 blobs / 331161 B) with the byte sizes the API reports, the list of which of those files were captured (20, all matching their size) and the commands to redo the capture |
| `…/winnative-emu-drivers/{README.md,MAINTENANCE.md,verify_patches.sh,build_turnip.sh,build_wn_turnip.sh,build_linux_turnip.sh,build-linux-turnip.yml,release_notes.py}` | the stack's own description: variants, per-patch upstream status, the CI assertion that every patch landed, the Android and Linux build recipes |
| `…/winnative-emu-drivers/patches/{apply_a7xx_gen2_ubwc_hint.py,apply_a7xx_gen1_quirks.py,apply_balance_variant.py,apply_perf_variant.py,disable_64b_image_atomics.py,add_ubwc_swapchain_usage.py,apply_a8xx_gpus.py,fix_a8xx_dev_info.py}`, `…/linux/{README.md,patch_mesa.py,package.py,verify_patches.py,verify_packages.py}` | the patch scripts themselves, byte-for-byte, as the input to journal 30's mapping table |
| `results/external/winnative-emu-components/{tree.txt,size-check.txt,capture.txt,README.md,VKD3D/README.md,DXVK/README.md,Proton/README.md,contents.json,default.json}` | the Components tree at `3b7c0efdb9c4` (23 blobs / 669318 B) and its catalog: the layers above the driver (box64, DXVK, vkd3d-proton x86 and ARM64EC, FEXCore, Proton); the `.wcp` packages are release assets, not repository files |

## Key numbers and where they are owned

The number stays in the artifact or journal entry named here; this table is a lookup,
not a source.

| quantity | value | owner |
|---|---|---|
| fps stock / patched | 13.0 / 13.9 | journal 13 |
| fps under the 13.0 protocol | 14.94-15.09 | journal 13, `results/games/re4/fps-ctrl100*.csv` |
| fdperf window | 13.7-15.7 | `docs/fdperf-a7xx.md` |
| DRAM read | 15.1 GB/s (~30 % of peak) | `docs/fdperf-a7xx.md`, `results/games/re4/mesa27*/steady-state.txt` |
| texture-read DRAM | 12.0 GB/s (81 %) | same |
| VFD L2 | 8.5 GB/s | same |
| latency UCHE -> VBIF | ~220 ns | same |
| draws per frame | 765 | same |
| vkd3d memory | 3129 MiB | journal 17 |
| turnip BO memory | 3490 MiB | journal 17 |
| linear textures | 4062 of 7977 MiB (50.9 %) | journal 21.12, `experiments/exp-14-image-inventory.patch` |
| no-list model | 1756 -> ~2200 MiB | `scripts/fmt-list-gate-check.py --no-list` |
| vkd3d classes | 72 | `tests/vk-fmt-classes.json` |
| UBWC classes, stock -> stack | 31 -> 36 | journal 21.6 |
| exp-15, mode 7 | 94 EXACT / 0 MISMATCH | journal 21.11, `results/test-b2isync-7.log` |
| i2b matrix | 91/91 | journal 21.8 |
| R8 UBWC memreq | `0x40000 -> 0x42000` | journal 21.7 |
| R16 UBWC memreq | `0x80000 -> 0x82000` | `results/test-CEIL-*.log` |
| UBWC share of the RE4 texture pool | 48.6 % (ship + 0014) / 48.8 % (stock + prop) | `results/imginv-3variants.txt`, journal 27 |
| UBWC reserve if the class rule reached the UBWC predicates | 4595.7 MiB, 56.8 % | journal 28 |
| classes a strict class rule grants, on a7xx_gen2 | 0 of 23 as it reads; 1 of 23 (128-bit) excluding members with no `fd6_format_table.c` row; 2 of 23 with the measured 64-bit fold | `results/model-strict-class-nolist.txt`, journal 32.1 |
| cross-label read of a 64-bit UBWC image (4x16 create, 2x32 view and the reverse) | 0 wrong texels of 262144, both directions | `results/test-xmc-64bit-compat.log`, journal 32.3 |
| `exp-21` against the shipped stack, full default run | 0 differing lines of 598 | `results/test-exp21-equiv-p14.log`, journal 33 |
| driconf perf options outside `TU_FORCE_PROPS` that this game has never run with | 5 exist; 4 are reachable by environment, 3 of those are perf candidates, 1 needs a build (`has_independent_icache_miss` is FD750-only) | `src/freedreno/vulkan/tu_drirc_gen.py`, journal 34.2 |
| those options on the test rig, full logs | 0 differing lines of 621 for each of the four | `results/test-perfprops-rig.log`, journal 34.3 |
| DEVICE_LOCAL heap the driver reports on this machine, at the default `heap_memory_percent` | 5.49 GiB = 0.75 of 7.32 GiB (heuristic branch, `os_misc.h:170`); the budget is 0.9 of free memory and does not follow the option until the heap falls below it | `results/vulkaninfo-heap-report.log`, journal 34.4 |
| which usage bits the game's images carry - shading rate, density map | 21 / 22 / 22 shading-rate images (`R8_UINT`, tiled, no UBWC, 12.0 MiB) and **0** density-map images in the three inventories | `results/imginv-usage-bits.log`, journal 35.1 |
| what the driver exposes for `VK_KHR_fragment_shading_rate` on a740 | extension revision 2; texel size 8x8 min == max; largest `maxFragmentSize` 4x4; 16 coverage samples; no layered attachments, no interlock | `results/vulkaninfo-vrs.log`, journal 35.2 |
| `exp-21` against the shipped `0014`, read per create in the game | 784 create signatures present in both inventories, **0** with a different `tile=`/`ubwc=` verdict, 0 present in only one; no-list tiled 2438.6 MiB against the reference 2450.3 | `results/test-exp21-inventory-ab.log`, journal 36 |
| `R64_UINT` view of a UBWC 64-bit image made without a list (`TU_UBWC_NOLIST_64`) | load 0 wrong of 262144 and exactly +1 per word after `imageAtomicAdd(+1)`; a list that names `R64_*` keeps `tail=0x0` with the knob on and off | `results/test-xr64-nolist-64-ubwc.log`, journal 37 |
| the Vulkan compatibility class of a no-list `MUTABLE` image **is its texel block** | spec: "Uncompressed color formats are compatible with each other if they occupy the same number of bits per texel block as long as neither or both are alpha formats"; in-tree copy of the same grouping - the `class=` attribute of `src/vulkan/registry/vk.xml` at `6dfa32a`: `32-bit` on `R8G8B8A8_UNORM` (32968), `B8G8R8A8_UNORM` (33014), `R32_UINT` (33313), `R16G16_SFLOAT` (33226), `B10G11R11_UFLOAT_PACK32` (33432), `A2R10G10B10`/`A2B10G10R10` (33098/33134); `16-bit` on `R8G8_UNORM` (32866) and `R16_UNORM` (33172) | journal 39.1 (spec + vk.xml), 39.6 (the driver says the same thing: `tu_formats.cc:115-149` answers a NULL list with "the app may reinterpret to any compatible format"; vk.xml even encodes the alpha exception as `class="8-bit alpha"`, `A8_UNORM` alone at 32838) |
| the residue a wider no-list rule would have to move, and why it is not a candidate | 1024 creates / **1630.8 MiB** of the 2474 / 4081.1 no-list `MUTABLE` creates (`0014` v1 tiles the other 1450 / 2450.3); all SAMPLED, 1012.1 MiB also STORAGE. Split: 971 creates / 1630.2 MiB of 16-bit- and 32-bit-class bases, linear because their class holds another swap (32-bit: 13 of 45 members are `WXYZ`; 16-bit: 6 of 21 with three different swaps) or another 2-byte geometry (14 members not `tu_is_r8g8`) - and `fd6_pipe2swap()` (`fd6_format_table.c:399-404`) returns `WZYX` for every tiled format while `is_mutable` stays false on this path (printed as `mutable=0` in all 4177 inventory lines); plus 53 creates / 0.65 MiB linear by the stock `width0 < 16 * blockwidth` fallback | `results/nolist-residue-p14.log`, `python3 scripts/class-order-check.py`, journal 39.1-39.3, 39.6 |
| host-transfer (`VK_IMAGE_USAGE_HOST_TRANSFER_BIT = 0x400000`) images in the game - the only precondition of the driver's own BGRA8 swap TODO | **0** in all three inventories (3638 / 4176 / 4170 creates); largest usage mask seen is `0x117` | `results/imginv-usage-bits.log`, journal 37.4(c) |
| the vertex path, recomputed from the committed 17.11 dumps with no new run | `VPC_VS_BUSY/VPC_BUSY` 92.8-96.4 % (`PS_BUSY` never measured); `VPC_WORKING/VPC_BUSY` 66.9-69.3 %; 1.03 vertices fetched per input primitive against 3 submitted (reuse 2.9:1); `VPC_NUM_ATTR_REQ_LM` 0.50 per vertex against ~5 attributes; VPC stall on UCHE 0.00 % | `results/games/re4/mesa27/fdperf-raw.txt`, `results/games/re4/mesa27-vertex/fdperf-raw.txt`, journal 38 |
