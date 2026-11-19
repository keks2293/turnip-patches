# fdperf on Adreno 740: per-block GPU profiling (a7xx)

Date: 17.11.2026. Task: answer the question "what is the bottleneck in RE4 - memory
or geometry/vertices" with per-block kernel counters (not `VK_KHR_performance_query`
- that path was rejected: 2-6 weeks of work and useless for RE4/vkd3d).

## Composition

| file | role |
|---|---|
| `tools/fdperf/fdperf.cfg` | main counter set (libconfig 1.8, see below) |
| `tools/fdperf/fdperf.cfg-vertex` | vertex set: per-client UCHE (VFD/TP/SP/PC) + full hw budget VFD/PC |
| `tools/fdperf/fdperf-windowed-delta.patch` | fix for the `-d` window in `fdperf.c` (see section Windows) |
| `scripts/fdperf-sample.sh [sec] [window-ms] [file] [cfg]` | background sampler: loop `sudo fdperf -r <window> -d` |
| `scripts/fdperf-analyze.py <file> [tsv] [--freq MHz]` | per-window busy%/latencies/traffic |
| `scripts/fdperf-align.py <tsv> <freq-track> <csv> <csv-start>` | overlay windows onto the MangoHud CSV and cur_freq |
| `build/out/fdperf` | binary (Mesa 27, `meson -Dtools=freedreno`, build - in `docs/mesa-27-plan.md`) |

Run artifacts (RE4, Mesa 27):
- `results/fdperf-mesa27/` (17.11 16:01, main cfg): `fdperf-raw.txt`,
  `fdperf-per-window.tsv`, `freq-trace.txt`, `fps.csv`, `steady-state.txt`;
- `results/fdperf-mesa27-vertex/` (17.11 18:01, cfg-vertex, per-client):
  the same + `aligned.txt`; `steady-state.txt` - DRAM split by client.

## Requirements and pitfalls

- **fdperf is root-only.** `DRM_IOCTL_MSM_PERFCNTR_CONFIG` returns EPERM on the
  render node without root (msm keeps perfctr for itself). Hence the sudo in
  `fdperf-sample.sh`.
- **Do not combine with `TU_AUTOTUNE_FLAGS=preempt_optimize`** - it occupies
  the last two CP counters, fdperf conflicts.
- **libconfig 1.8** (in Fedora 44): the config syntax is incompatible with the
  usual one - groups only via `NAME = { }`, comments `//`, `/* */` and `#`
  (not `;`). `fdperf.cfg` in the repository is a working example.
- **The second block of lines in the fdperf dump is the BV groups** (BV_SP_*,
  BV_TP_* - "countable by default", Mesa prints them separately). The analyzer
  resolves duplicate names as "first occurrence" - the BV lines do not get in
  the way.

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

Full numbers - `results/fdperf-mesa27/steady-state.txt`. Key points:

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
`results/fdperf-mesa27-vertex/steady-state.txt`.

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
