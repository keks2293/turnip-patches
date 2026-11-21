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

`exp-1`..`exp-22` (there is no `exp-12`; `exp-18`, `exp-19` and `exp-20` are queued
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
| `scripts/ubwc-dump-analyze.py` | allocation dump analysis: metadata-plane shape, written chunks, how many metadata bytes were written (`--meta`, `--pitch`) |
| `scripts/sweep-8bpp-grid.sh` | runs `tp8bpp` over metadata grids through `TU_8BPP_UBWC` (works only on the exp-17 build) |
| `scripts/run-test.sh`, `scripts/run-b2i-matrix.sh`, `scripts/run-game.sh`, `scripts/fps-window.py`, `scripts/curate-game-log.sh` | running the test, the mode matrix, the game, the fps window |
| `scripts/fdperf-sample.sh`, `scripts/fdperf-analyze.py`, `scripts/fdperf-align.py`, `tools/fdperf/fdperf-windowed-delta.patch` | profiling (see `docs/fdperf-a7xx.md`) |
| `scripts/build-turnip*.sh`, `scripts/build-test.sh`, `container/` | building the driver and the test (there is no compiler on the device). `build-test.sh` installs the toolchain only if the image lacks it - on 20.11 a failed Fedora mirror download broke the build although the image had gcc and the headers |

## Logs that are cited as evidence

| log | what it proves |
|---|---|
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
| `results/fdperf-mesa27*/steady-state.txt` | the memory wall |
| `results/fps-gov-*.csv` | the governor is noise |
| `results/fps-ctrl100{,b}.csv` | the "1.86 fps" artefact |

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

## Key numbers and where they are owned

The number stays in the artifact or journal entry named here; this table is a lookup,
not a source.

| quantity | value | owner |
|---|---|---|
| fps stock / patched | 13.0 / 13.9 | journal 13 |
| fps under the 13.0 protocol | 14.94-15.09 | journal 13, `results/fps-ctrl100*.csv` |
| fdperf window | 13.7-15.7 | `docs/fdperf-a7xx.md` |
| DRAM read | 15.1 GB/s (~30 % of peak) | `docs/fdperf-a7xx.md`, `results/fdperf-mesa27*/steady-state.txt` |
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
