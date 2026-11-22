# fdperf on Adreno 740: per-block GPU profiling (a7xx)

Date: 17.11.2026. Task: answer the question "what is the bottleneck in RE4 - memory
or geometry/vertices" with per-block kernel counters (not `VK_KHR_performance_query`
- that path was rejected: 2-6 weeks of work and useless for RE4/vkd3d).

## Composition

| file | role |
|---|---|
| `tools/fdperf/fdperf.cfg` | main counter set (libconfig 1.8, see below) |
| `tools/fdperf/fdperf.cfg-vertex` | vertex set: per-client UCHE (VFD/TP/SP/PC) + full hw budget VFD/PC |
| `tools/fdperf/fdperf.cfg-vpc` | VPC-pressure set, written 21.11: the VPC budget (6) spent on `VS_BUSY`/`PS_BUSY`, `SP_COMPONENTS`, `NUM_VPCRAM_WRITE` and `LM_FULL_WAIT_FOR_INTP_END`, plus `PC_VERTEX_HITS` and the per-client **write**-request side. Run 21.11 as `vpcbase1`, `vpcbase2`, `hpbase`, `hpbase2`, `hp50`, `hp40`, `cb1`, `lrz2`, `fl111`, `fl121`, `nopref` (journal 40) |
| `tools/fdperf/fdperf.cfg-vpc2` | the other half of the same VPC budget: `WORKING`, `STALL_CYCLES_VFD_WACK`, `STALL_CYCLES_SP_LM`, `STALL_CYCLES_HLSQ_PRIM_ALLOC`, `STARVE_CYCLES_SP`. Run 21.11 as `vpc2b` |
| `tools/fdperf/fdperf.cfg-vpc3` | "is the VPC's own RAM the limit": `VPCRAM_FULL`, `WIT_FULL`, `STALL_CYCLES_VPCRAM_POS`, `STALL_CYCLES_LM_ACK`, `NUM_LM_REQ_HIT`. First runs 21.11 23:14 (`vpc3base`, `attrbuf`, queue 19) |
| `tools/fdperf/fdperf.cfg-tse`, `tools/fdperf/fdperf.cfg-tse2`, `tools/fdperf/fdperf.cfg-tse3` | the TSE question in three cuts of one **4-counter** TSE budget plus the 2-counter VSC budget: how much geometry TSE throws away (`INPUT_PRIM`, `OUTPUT_VISIBLE_PRIM`, `ZERO_PIXEL_PRIM`), why (`TRIVAL_REJ`, `ZERO_AREA`, `FACENNESS_CULLED`, `CLIPPED`), and whether a binning pass exists at all (`VSC_BUSY` + `VSC_INPUT_TILES`). They cannot be merged into one run, and each header says so. Run 21.11 as `cbbase`, `cbforce`, and 22.11 as `tse3cb2`, `tse3cb3` |
| `tools/fdperf/fdperf.cfg-bv`, `tools/fdperf/fdperf.cfg-bv2`, `tools/fdperf/fdperf.cfg-bv3` | written 22.11 for queue 20: the first cfgs in this repository to name the `BV_*` groups (`BV_VPC`, `BV_TSE`, and in `-bv` also `BV_PC`, `BV_TP`) instead of leaving them at their defaults, so the binning/visibility thread's own counters become readable. `-bv2` (no `BV_PC`/`BV_TP`) and `-bv3` (`BV_VPC` alone) were the trim test for why the VSC tile counter read 0 in those runs - the answer was the session, not the cfg (journal 40.12). Run 22.11 as `bvbase`, `bvforce`, `bvforce2`, `bvforce3`, `bvforce4`, `bvforce5` |
| `tools/fdperf/fdperf-windowed-delta.patch` | fix for the `-d` window in `fdperf.c` (see section Windows) |
| `scripts/fdperf-sample.sh [sec] [window-ms] [file] [cfg]` | background sampler: loop `sudo fdperf -r <window> -d` |
| `scripts/fdperf_sections.py` | the one loader for dumps, shared by every script that reads one: splits the ordinary groups from their `BV_*` twins (`load_sections()`; `load()` is the same call with the BV half discarded), drops `u64`-wrapped window deltas and `[invalid]`, and reports which names came only from the BV half |
| `scripts/fdperf-vpc-ratios.py <dump> [lo] [hi]` | the vertex-path ratios (VPC split, PC/VFD/UCHE coupling, DRAM by client); a counter the cfg did not program prints as `nan`, never as 0 |
| `scripts/fdperf-tse-ratios.py <dump> [lo] [hi]` | the TSE-discard ratios (visible/input, the reason counters, VSC busy and tiles fed) |
| `scripts/fdperf-vpcram-ratios.py <dump> [lo] [hi]` | the VPC's own memory system (`VPCRAM_FULL`, `WIT_FULL`, `STALL_CYCLES_VPCRAM_POS`, `LM_ACK`, `LM_REQ_HIT`) - a table for the `cfg-vpc3` half of the budget, which no other script can read |
| `scripts/fdperf-bv-table.py [--lo] [--hi] <dump> ...` | the two halves of one dump side by side, ordinary group against its `BV_*` twin - the only reader that wants both, and the table queue 20 is read from |
| `scripts/fdperf-arm-table.py [--lo] [--hi] [dir ...]` | one row per run: VPC busy, PC stall on VPC, UCHE arbiter stall, VFD/TP starve on UCHE, TP busy, TSE input and visible share, DRAM reads and p25 fps, over every `results/games/re4/*/fdperf-raw.txt`. Duty cycles are averaged over pinned-clock windows only (see "Reading a dump"), and the row says how many windows were dropped and what the dump's median clock was; which fps CSV belongs to which run is written in the script, not guessed |
| `scripts/fdperf-tile-table.py [--lo] [--hi] [dir ...]` | the binning-pass indicator for the nine runs that can answer that question: tiles/s and `VSC_BUSY` cut over the steady window and over the pinned-clock window, side by side, with the cfg and `TU_DEBUG` of each run written down in the script. Journal 40.12 is read from it |
| `scripts/fdperf-analyze.py <file> [tsv] [--freq MHz]` | per-window busy%/latencies/traffic |
| `scripts/fdperf-align.py <tsv> <freq-track> <csv> <csv-start>` | overlay windows onto the MangoHud CSV and cur_freq |
| `build/out/fdperf` | binary (Mesa 27, `meson -Dtools=freedreno`, build - in `docs/mesa-27-plan.md`) |

Run artifacts (RE4, Mesa 27):
- `results/games/re4/mesa27/` (17.11 16:01, main cfg): `fdperf-raw.txt`,
  `fdperf-per-window.tsv`, `freq-trace.txt`, `fps.csv`, `steady-state.txt`;
- `results/games/re4/mesa27-vertex/` (17.11 18:01, cfg-vertex, per-client):
  the same + `aligned.txt`; `steady-state.txt` - DRAM split by client.
- `results/games/re4/vpc-vpcbase1/` and the other `results/games/re4/{vpc,vpc2,vpc3,tse,tse2,tse3,tse-algo}-*/`
  directories (21.11, one per run, `fdperf-raw.txt` + `fdperf-per-window.tsv`): what they answer is
  journal 40 - the vertex-path split, the TSE discard, the CB/VSC question and the VPC's own RAM.
- What the 17.11 pair already answered without a new session - `VPC_VS_BUSY/VPC_BUSY` at 92.8-96.4 %
  with `PS_BUSY` never measured, 1.03 vertices fetched per input primitive against 3 submitted,
  `VPC_NUM_ATTR_REQ_LM` at 0.50 per vertex - is journal 38, which also records that the window filter
  written in `steady-state.txt` is not exactly reproducible (35 windows selected, 33 recorded) and that
  only ratios inside one sample set travel between runs. Journal 40 adds the second half of that
  warning: the game start is not content-synchronised, so two runs can be in different content at the
  same `t_rel`. The `cbbase`/`cbforce` pair of 21.11 is the example - VPC busy 68.9 % and 81.8 % there
  against 90.6-92.4 % in every other run of the day - and its absolute values are not comparable with
  the rest even though its within-pair comparison is.
- Two `PERF_VSC_*` selectors need care. `VSC_EOT_NUM` (value 3) reads 0.0/s over all 40 windows of a
  run where `VSC_BUSY` in the same windows is 2.57 Mc/s (`results/games/re4/tse2-tse2/`) - no signal.
  `VSC_INPUT_TILES` (value 4) works and is the counter that answers "is anything being binned at all":
  medians 56/s with CB off against 1,532/s under `TU_DEBUG=forcecb` (`results/games/re4/tse3-cbbase/`,
  `-cbforce`, journal 40.8), but it is an *event* counter (print it per second, never as a share of the
  core) and one window in 70 of `cbbase` came back as `18446744073709551290` = 2**64 - 82, a negative
  delta imaged as unsigned; averaged as printed it turns a few hundred into 4.5e11, which is how a
  working selector got written up as a broken one on 21.11. `scripts/fdperf_sections.py` drops such
  values and counts them. `VSC_BUSY_CYCLES` (0) and `VSC_STALL_CYCLES_UCHE` (2) respond normally. The
  same "exactly 0" behaviour was seen for `VPC_STALL_CYCLES_LM_ACK` (40) and `VPC_NUM_LM_REQ_HIT` (38)
  in both arms of journal 40.9.

## Requirements and pitfalls

- **fdperf is root-only.** `DRM_IOCTL_MSM_PERFCNTR_CONFIG` returns EPERM on the
  render node without root (msm keeps perfctr for itself). Hence the sudo in
  `fdperf-sample.sh`.
- **Do not combine with `TU_AUTOTUNE_FLAGS=preempt_optimize`** - it occupies
  the last two CP counters, fdperf conflicts.
- **libconfig 1.8** (in Fedora 44): the config syntax is incompatible with the
  usual one - groups only via `NAME = { }`, comments `//`, `/* */` and `#`
  (not `;`). `fdperf.cfg` in the repository is a working example.
- **A dump contains the block twice: the ordinary group and its `BV_*` twin** ("BV" = the
  binning/visibility thread, i.e. the CB side of the same hardware). The group list is
  `src/freedreno/registers/adreno/a7xx_perfcntrs.json`, which defines `BV_CP`, `BV_PC`, `BV_VFD`,
  `BV_VPC`, `BV_TP`, `BV_SP`, `BV_UFC`, `BV_TSE`, `BV_RAS`, `BV_LRZ`, `BV_HLSQ` after the ordinary
  groups. The register map, read in that file, says how separate they are: `BV_PC`, `BV_VFD`,
  `BV_VPC`, `BV_TP`, `BV_SP`, `BV_UFC` name the **same select register** as their ordinary twin but
  carry a `select_offset` (8, 8, 6, 12, 24, 4 - so `VPC_PERFCTR_VPC_SEL` holds 6 ordinary slots then
  6 BV slots), while `BV_TSE`, `BV_RAS`, `BV_LRZ`, `BV_HLSQ`, `BV_CP` have **no `select_offset`** and
  the same select register: their selects are the ordinary group's words. The *value* registers are
  separate anyway - in `results/raw/fdperf-bvbase.txt` the same slot of `TSE` and `BV_TSE` prints
  different numbers - which is why the two halves of a sample must be kept apart. Each twin also uses
  the same countable enum (`"type": "a7xx_vpc_perfcounter_select"` for both `VPC` and `BV_VPC`).
  Reading rules, all of them implemented in `scripts/fdperf_sections.py`: the ordinary group's value
  is the first occurrence; a name that occurs only after the split (`VPC_WORKING_CYCLES` in a
  `cfg-vpc3` run) is a BV counter and never the ordinary block's number; `scripts/fdperf-bv-table.py`
  is the reader that wants both halves. `scripts/fdperf-analyze.py` predates the split and takes the
  first occurrence - fine for its own tables, not for a counter the cfg did not program.
- **A cfg can address the BV groups, and it changes what the tool prints.** `fdperf.c`'s
  `config_restore()` looks up every group of `fd_perfcntrs()` by name in the cfg, so a `BV_VPC = {
  counter0 = 0; ... }` section is honoured: on an idle GPU, the BV half of a `cfg-bv` dump prints
  `PERF_PC_IA_PRIMITIVES`, `PERF_VPC_VPCRAM_FULL_CYCLES`, `PERF_VPC_WIT_FULL_CYCLES`,
  `PERF_TSE_INPUT_PRIM` where the same slots of a `cfg-tse3` dump print the group's first countables
  (`PC_WORKING_CYCLES`, `VPC_STALL_*`, `TSE_CLIPPING_CYCLES`). Measured in journal 40.11, runs
  `bvbase`/`bvforce3`, `results/games/re4/bv-*/`.
- **An unprogrammed `BV_*` half is not a measurement, and `cfg-bv` fixes that.** In a dump whose cfg
  names no BV group, whole groups of the BV half mirror the ordinary counter: in
  `results/games/re4/tse3-cbforce/fdperf-raw.txt` the BV copies of `TP_BUSY` are 100.076 %, of `CP_BUSY`
  100.076 %, of `UCHE_BUSY` 100.355 %, of `CCU_BUSY` 101.278 %, of `RB_BUSY` 100.668 % and of
  `PC_IA_PRIMITIVES`/`TSE_INPUT_PRIM`/`TSE_OUTPUT_VISIBLE_PRIM` 100.5-100.6 %. A select word that was
  never written keeps the previous run's value or zero, and the BV value register then reports the same
  event as the ordinary one. With `tools/fdperf/fdperf.cfg-bv` the halves are separate and comparable,
  and `scripts/fdperf-bv-table.py` is the reader for that. Journal 40.11.
- **`VSC_INPUT_TILES` is a per-session switch, and `scripts/fdperf-tile-table.py` is its reader.** On
  21.11, `cfg-tse3` fed tiles in 32 of its 40 steady windows with CB off (median 56/s) and in all 88 with
  `TU_DEBUG=forcecb` (median 1,532/s); on 22.11 every forced arm read 0 tiles in every window, and the
  unforced `bvbase` only in the 22 windows where the core was not at the pinned clock (median 16/s) -
  controls with no `BV_*` section included. Where it is nonzero it says a binning pass ran in that window;
  it cannot characterise a scene across runs, and no `BV_*` section was ever shown to affect it
  (journal 40.12).
- **Duty cycles are only comparable inside pinned-clock windows.** A 1 s window whose
  `PERF_CP_ALWAYS_COUNT` is not within 1 % of the pinned core clock (680 Mc/s in the 21.11/22.11 dumps)
  is a window where DVFS had not reached the pinned step, and averaging over it dilutes every percentage:
  `tse3-cbbase` reads 68.95 % over its 42 steady windows and 91.73 % over its 29 pinned-clock ones, and
  `bv-bvbase` 88.82 % over 38 against 91.68 % over 16 (journal 40.12, Correction 2). This is the
  counter-side twin of the MangoHud rule under "Healthy vs degenerate window", and stricter than the
  0.9 x line: a window at 649 MHz passes 0.9 x and still moves a mean by three points. Event counts
  (primitives/s, tiles/s, GB/s) are not diluted by the clock and are quoted over the steady window.
  `scripts/fdperf-arm-table.py` averages percentages over pinned-clock windows only, says how many
  windows it dropped, and prints the dump's median clock so a throttled run (`vpc-hp40`, median 585 MHz,
  no pinned window) cannot be read as a 680 MHz one.
- **Delivery of a `TU_DEBUG` flag is proved by one driver line, not by behaviour.** Unknown keys are
  ignored (`src/util/u_debug.c`, `debug_parse_flags_option`), so a bogus key proves nothing, and
  `GALLIUM_PRINT_OPTIONS=1` produced no line in the game log at all (run `bvforce2`, 0 hits). What
  works is `TU_DEBUG=startup`: the driver then logs `TU: info: TU_DEBUG=0x…`
  (`src/freedreno/vulkan/tu_util.cc:135`) plus `Created an instance`
  (`tu_device.cc:2133`). Use `TU_DEBUG=startup,<flag>` in any arm whose premise is a debug flag.

## Windows: why the patch and what the label interval means

The original `fdperf -d` (Mesa main) races with the first kernel sample: the
kernel produces the first sample one period after `PERFCNTR_CONFIG`, the
sample-kthread adds another couple of ms, and the fixed sleep+resample reads
either zero or "counter minus zero" - accumulated since the last reset, not a
window; `sample_time_delta` in that case is an absolute CP timestamp, and the
printed % is garbage. The fix (`tools/fdperf/fdperf-windowed-delta.patch`, a
patch to the tool only, not part of the 0001-0012 stack): poll until at least 2
kernel samples have been read, then print the delta between the last two - a
true single-window value, and the % is honest too. The legacy path (no kernel
stream, `dev.io`) is untouched.

Consequences for interpreting the sampler file:

- **One counter window = `period_ms`** from the file header (`fdperf -r 1000` ->
  1 s). The interval between `=== sample <t> ===` labels is ~2.2-3 s - that is
  process startup (sudo, config, waiting for two samples), NOT the window.
  Normalizing by the label interval is not allowed.
- Each fdperf process lives ~2.2-2.3 s; the label `t` is its start time. The
  middle of the counter window is ~`t + 1.65 s` (with a period of 1 s) - that
  is the offset in `fdperf-align.py`.
- The counters are GPU-global (CP perf): they see the whole GPU load while RE4
  is rendering. Do not run two `run-game.sh` in parallel (see README).
- **One `=== sample` block is one `fdperf` process**, because `scripts/fdperf-sample.sh`
  starts a fresh one per iteration - that is why every block carries its own
  `device: FD740` banner (in every dump of this repository the count of `device:` lines equals
  the count of sample labels). Two consequences: a block with no counters under the label is a
  process that died (`results/raw/fdperf-cbbase.txt` has one such block in 70), and the window
  read right after such a gap contains negative deltas imaged as unsigned - the values
  >= 2**63 that `scripts/fdperf_sections.py` drops and counts rather than averages. That is the
  origin of the `2**64 - 82` in journal 40.7, and the reason the sampler's stderr is not the only
  thing worth keeping.

## Clock domains (verified on a740, vkcube 720p/4K + governor pinning)

- **`RBBM_ALWAYS_ON` is not the core clock.** It is the GMU domain: max exactly
  19.2 MHz (the constant `ALWAYS_ON_FREQUENCY_HZ = 19200000` in `fdperf.c` - the
  tick of CP timestamps). At 220 and 680 MHz it gives 0.3-0.8 "MHz"; you cannot
  divide busy% by it (you would get >100%). `RBBM_*_BUSY` are printed by the
  analyzer in cycles/s, without percentages.
- **`CP_ALWAYS_COUNT` is the core domain when the GPU is saturated** (average
  565.7 MHz, max 680 by windows; under light load it is gated heavily: vkcube
  720p at 220 MHz gives ~4-9 "MHz").
- **`*_BUSY_CYCLES` count gfx-core cycles**: the vkcube test when switching
  220<->680 MHz (governor `performance` for the check, then back to
  `simple_ondemand`) showed a constant cycles/s at unchanged load - the counters
  are tied to core ticks, not to time. Therefore **block busy% =
  BUSY_CYCLES / (f_core x window)**, where f_core is the actual frequency of the
  window (in saturated RE4 windows ondemand holds 680 MHz - max).
- **`CP_BUSY` and `CP_SQE_IDLE` are both ~100%** in saturated windows: the
  semantics are strange, the interpretation is that the front-end waits on the
  saturated 3D pipe, i.e. GPU-bound, not CPU-bound (MangoHud confirms the CPU
  side: cpu_load ~58%).

### Where the clock actually comes from (devfreq, not pp_dpm_sclk)

On this kernel the GPU is a devfreq device, and that is the only clock control:

```sh
cat /sys/class/devfreq/3d00000.gpu/cur_freq              # Hz
cat /sys/class/devfreq/3d00000.gpu/governor              # simple_ondemand
cat /sys/class/devfreq/3d00000.gpu/available_frequencies # 220..680 MHz
```

`/sys/class/drm/card0/device/pp_dpm_sclk` does not exist here - `card0` is the
display controller (`msm_dpu`), not the GPU. For the fdperf alignment use
`3d00000.gpu/cur_freq` (see the wrapper at the end of this file), and pin the
governor (`performance`) only when a fixed frequency is the point of the
measurement; RE4 is memory/latency-bound at 680 MHz (findings 2026-11-19,
section 6.2), so pinning alone does not move fps.

### Healthy vs degenerate window

An RE4 window is usable only if MangoHud's `clocks` column holds 680 in-window
and `gpu_load` is 97-100%. The degenerate signature - flat ~1.86 fps,
`clocks=[220]`, `gpu_load` <= 21%, swap > 5 GiB, `min == max` - is a run that
never left the idle clock step (memory pressure, leftover `winedevice.exe`),
not a driver effect. Re-check `free -m` and kill leftovers before repeating;
never compare a window of one kind against the other.


## Multi-instance dividers

Raw `*_BUSY_CYCLES` sum all hardware instances of a block, so "busy% of the core
clock" without a divider gives >100%. The canonical Mesa formula
(`fd7_perfcntr.c`, `percent_shaders_busy`):
`SP_BUSY / (number_of_usptp x RBBM_STATUS_MASKED)`, where
`number_of_usptp = num_sp_cores x 2`. For FD740: `num_ccu = 6`
(`freedreno_devices.py`, `num_sp_cores = num_ccu`) -> **12 usptp**.

| block | divider | source |
|---|---|---|
| SP, TP | /12 | `number_of_usptp` (6 CCU x 2) |
| UCHE | /2 | empirical (2x `RBBM_UCHE_BUSY`, both hit ~680 MHz) |
| CCU | /6 | `num_ccu` |
| RB | /4 | empirical (4 RB instances) |
| VFD | N >= 8, exact value unknown | raw 730% of core; hits the ceiling at any N>=8 - for conclusions "saturated" is enough |

## hw counter budgets and silent ignore in fdperf

fdperf reads from cfg only `counter0..num_counters-1`, where `num_counters` is
the size of the group's hw table (a7xx, from `a7xx_perfcntrs.json.h`): UCHE=12,
CP=13, PC=8, VFD=8, VPC=6, TSE=4, RAS=4, HLSQ=6, TP=12, SP=24, RB=8, CCU=5,
LRZ=4, UFC=4, CMP=4, RBBM=4, VSC=2. Lines beyond the limit are **silently
ignored**: no error, no "reducing" in the output - the counter is simply absent
from the dump.

In the main `fdperf.cfg` the limit was exceeded: UCHE (19 of 12), PC (10 of 8),
RBBM (6 of 4), CCU (9 of 5), LRZ (7 of 4), CMP (7 of 4). So these counters
**were not measured at all** (there are no lines in `fdperf-raw.txt`, rather
than "they read 0"): `UCHE_EVICTS`, `UCHE_UBWC_READ/WRITE_BEATS`,
`UCHE_READ_REQUESTS_TP_UBWC/NONUBWC`, `UCHE_CCHE_TPH/DPH_QUEUE_FULL`,
`PC_VPC_PRIMITIVES`, `PC_3D_DRAWCALLS`, `RBBM_PC_DCALL_BUSY`,
`RBBM_PC_VSD_BUSY`, `CCU_DEPTH/COLOR_BLOCKS`, `CCU_2D_RD/WR_REQ`,
`LRZ_LRZ_WRITE`, `LRZ_PRIM_KILLED_BY_LRZ`, `LRZ_TOTAL_PIXEL`,
`CMP_VBIF_WRITE_DATA_CCU`, `CMP_VBIF_READ/WRITE_REQUEST`.
Within budget, but actually reading 0: `UCHE_GMEM_READ/WRITE_BEATS`.

Conclusion: **the state of UBWC compression from hw counters on this chip has
not been verified** (the GMEM-*_BEATS are dead; the UBWC counters never fit in
the budget either). The per-client set, where all groups are within the hw
budget: `tools/fdperf/fdperf.cfg-vertex` (it has no UBWC either - the UCHE
budget is exhausted by per-client counters; UBWC needs a separate cfg/run).

## Cross-check with the MangoHud CSV

- MangoHud CSV: 3 header lines, then one line per frame; `elapsed` is the
  **last column, in nanoseconds**; fps is the 0th; gpu_core_clock MHz is the
  7th. The time in the file name is ~the start of MangoHud (= `csv-start-epoch`
  in the aligner; in the 17.11 run - 1794902504.0).
- Steady state in the run: t_rel 37-106 s, fps 13.7-15.7 (p25 region), 680 MHz
  pinned, the profile is identical for ~70 s in a row. The criterion for
  selecting windows: `CP_ALWAYS_COUNT > 5e8` per 1 s window (~680 MHz) AND
  t_rel >= 35 s (loading/transition windows have a different load, HLSQ/CP
  dominate).

## Result: RE4, Mesa 27, DX12, steady state (33 windows @ 680 MHz)

Full numbers - `results/games/re4/mesa27/steady-state.txt`. Key points:

- **UCHE (L2): 90% busy, of which 39% is stall on the arbiters.** The bottleneck
  is L2 cache arbitration, not DRAM bandwidth.
- **UCHE->VBIF (DRAM) latency: 149 cycles/access ~ 220 ns** at 680 MHz;
  UFC miss - 212 cycles.
- **DRAM traffic: read 15.1 GB/s** (942 Mbeats/s x 16 B), write 0.3 GB/s -
  ~30% of the LPDDR5X peak (~51 GB/s). **We did not hit the bandwidth limit.**
- **The main side of the demand is the vertex path:** VFD is saturated (raw 4955
  Mcycles/s, starve-on-UCHE ~48-51% of the window), PC 92% (stall on VPC 63% -
  waiting for VS), VPC 91% (UCHE stall ~0% - pure computation). 255 M VS-invocations/s
  ~ 17.4 M/frame.
- **Vertex fetch (VFD counters): 32.0 B/vertex = 5.09 attr/vertex
  x 6.3 B/attr; 8.17 GB/s - this is demand on L2** (DECODED_ATTRIBUTE_BYTES),
  the fetch goes in the exact format size (6.3 B/attr - not 16B lines);
  PC_VS_INVOCATIONS/VFD_TOTAL_VERTICES = 1.000 - there is no instance
  amplification of fetch (vertices are fetched exactly per the number of
  VS-invocations). How much of this goes to DRAM - the per-client run (below):
  **only 2.3 GB/s (16%) - L2 caches ~73% of the vertex bytes**.
- The draw call rate in the run was **not measured**: CP_SQE_DRAW_EXEC ~ 0 in
  steady state (non-zero values 511/220 k/s - only in loading windows; the
  semantics of the counter for 3D draws is not confirmed), PC_3D_DRAWCALLS did
  not fit in the PC hw budget (8) - in `fdperf.cfg-vertex` it is present
  (counter7).
- **Textures:** TP 80% (starve UCHE ~48% + stall 19%) - also waiting for memory,
  but **UFC (texture computations) is only 26.7%** - it does not hit the limit
  in texture computations.
- SP 93.9% (/12), RB 82.5% (/4), CCU 47.7% (/6), TSE 79.6%, RAS 72.3%,
  LRZ 82.6%, HLSQ 99%, CP ~100%.
- Pixels: SP_PIXELS 451 M/s ~ 30.7 M/frame (4K x 4MSAA = 33.2 M) - full
  coverage; FS instructions 7.4 G/s.

## Vertex run (per-client, 17.11 18:01): DRAM split by client

`fdperf.cfg-vertex` (per-client UCHE 12/12, VFD 8/8, PC 8/8), 33 steady-state
windows, fps ~14-23 (faster than the 16:01 run, different content; the profile
structure is identical: PC 95%, UCHE 89.5%, SP 94.3%, TP 79.6%). Full numbers -
`results/games/re4/mesa27-vertex/steady-state.txt`.

- **DRAM read by client: TP (textures) 12.0 GB/s (81%), VFD (vertices)
  2.3 GB/s (16%), PC 0.4 (3%), SP 0.05 (0.3%).** The sum 922 Mbeats/s ~ total
  942 from the 16:01 run (the discrepancy = HLSQ/LRZ) - validation of the
  per-client counters is OK. **The largest DRAM consumer is textures, not
  vertices** (the estimate "54% of DRAM read is vertices" based on
  DECODED_ATTRIBUTE_BYTES was a mistake: that is demand on L2, not DRAM
  traffic).
- **Vertices are the largest demand on L2** (8.5 GB/s; L2 serves ~73% of the
  bytes, 27% goes to DRAM): VFD starve cycles = 55% of its BUSY (waiting for
  data from L2), STALL_VPC_ALLOC 12.5% (backpressure from the VS core). L2
  requests: TP 1914 M/s vs VFD 413 M/s.
- **The draw rate is measured for the first time (PC_3D_DRAWCALLS): 12.7 k/s ~
  765 draws/frame** (p25 781). CP_SQE_DRAW_EXEC in steady state ~0 - it does
  NOT count 3D draws (the mystery of the 16:01 run). PC starve_for_index 0.3% -
  the index buffer is not the bottleneck.
- UCHE->VBIF latency 154 cycles (226 ns) - as in the 16:01 run (149/219).

## Conclusion

The RE4 wall on this hardware is **the memory path: L2/UCHE arbitration + DRAM
latency (~220 ns), not DRAM bandwidth and not texture computations**.
The largest demand on L2 is the vertex path (VFD 8.5 GB/s, PC 95%); the largest
DRAM stream is texture fetch (TP 12 GB/s, 81% read). Hence the direction for
optimizations:

- vertices - the largest demand on L2 (8.5 GB/s, VFD starve 55%): reduce
  bytes/attribute on the application side (formats, attr set, vertex reuse) -
  it hits L2 pressure and VFD starve;
- textures - the largest DRAM stream (12 GB/s, 81% read): UBWC/texture
  formats, tiling - it hits DRAM latency (fixed ~220 ns);
- removing MSAA/resolution reduces both pixel and vertex demand, but does not
  change the nature of the bottleneck;
- batching draws (765/frame) - potential, but not the wall (CPU ~58%,
  PC starve_for_index 0.3%);
- UBWC: hw counters on a740 give no answer - `UCHE_GMEM_*_BEATS` are dead
  (they read 0), and the UBWC counters in both cfg did not fit in the UCHE hw
  budget (12) - see section "hw budgets"; it can only be checked indirectly
  (A/B of `TU_UBWC_*` options by fps) or with a separate cfg (evicting
  per-client);

## Reproducing the run

```sh
# one bash wrapper: sampler + freq track + game (see the 17.11 run)
nohup bash -c '
  ( scripts/fdperf-sample.sh 140 1000 /tmp/opencode/fdperf-XXX.txt > /tmp/opencode/fdperf-sampler.log 2>&1 & )
  ( timeout 150 bash -c "while :; do echo \"\$(date +%s.%3N) \$(cat /sys/class/devfreq/3d00000.gpu/cur_freq)\"; sleep 0.2; done" > /tmp/opencode/freq-XXX.txt & )
  env HUDLOG=120 HUDINTERVAL=100 scripts/run-game.sh patched 150 > /tmp/opencode/re4-run.log 2>&1
' &
# after completion:
python3 scripts/fdperf-analyze.py /tmp/opencode/fdperf-XXX.txt /tmp/opencode/fdperf-XXX.tsv
python3 scripts/fdperf-align.py /tmp/opencode/fdperf-XXX.tsv /tmp/opencode/freq-XXX.txt \
    /tmp/opencode/mangologs/<csv> <csv-start-epoch>
```

Vertex run (per-client UCHE, full VFD/PC budget):

```sh
# in the same wrapper, the 4th argument is the config:
#   scripts/fdperf-sample.sh 140 1000 /tmp/opencode/fdperf-vertex.txt tools/fdperf/fdperf.cfg-vertex
# validation: the sum of UCHE_RD_{VFD,TP,SP,PC} ~ UCHE->DRAM read (942 Mbeats/s in
# the 17.11 run); PC_3D_DRAWCALLS x fps ~ draws/frame
```
