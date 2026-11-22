# 13. Performance: FPS doesn't depend on anything in the driver

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

The task was to raise FPS in RE4 by editing the driver. It didn't work out, and
this is a positive result: **stock Mesa gives the same 13 fps** as the patched
one.

### 13.0 Measurement protocol (standard, 2026-11-18)

The comparison window is **elapsed 40–50 s from launch**: the first 40 s are the
game's fixed intro, the next 10 s are the 3D main menu. The scene is
deterministic and needs no scripted gameplay, so every run reproduces it
exactly. Notes:

- in the MangoHud CSV `elapsed` is in **nanoseconds** (divide by 1e9); a parser
  that filters it as seconds silently gets an empty window;
- the metric is `p25` of `fps` inside the window, 100 ms sampling
  (`HUDINTERVAL=100`), ~100 samples;
- a run may only be compared window-to-window and with the **same driver
  build**, checked by `sha256sum` of `build/out/libvulkan_freedreno.so`. Any
  rebuild invalidates the earlier windows of that series; cross-version numbers
  are reference only.

The tables below predate this protocol and were measured as described in each
section.

### 13.1 What was checked

The same segment, nine configurations. The metric is `p25` of the scene's frame
fps; loading and menu frames (50–85 fps) are excluded by the `fps < 30`
threshold, otherwise they inflate the number (in the "blur off" run the window
caught the loading and produced a nonexistent 17 fps).

| config | fps p25 | RAM peak | swap peak |
|---|---|---|---|
| stock (user's measurement) | 13.0 | — | — |
| patch, 12_0 base | 13.9 | 7.23 | 5.15 |
| patch, 11_1 force | 13.7 | 7.27 | 5.36 |
| softfloat32 off | 13.8 | 7.30 | 5.53 |
| `prefer_gmem` allocation | 12.9 | 7.27 | 5.55 |
| resolution 960x540 | 13.7 | 7.30 | 5.54 |
| shadows off | 10.8 | 7.31 | 6.52 |
| blur off | 2.2 | 7.23 | 4.33 |

RAM is in gigabytes, swap is in gigabytes. Total RAM in the system is 7.32 GiB.

### 13.2 Conclusions per hypothesis

- **Software FP32 emulation costs nothing.** `tu_nir_lower_softfloat32`
  rewrites every FP instruction into a call from `float32.glsl`, but with
  `enable_softfloat32=false` FPS doesn't change. So the game is not bound by
  arithmetic, and the 12_0 requirement doesn't cost performance.
- **Pixels don't matter.** 960x540 is 0.49x of the area, FPS +1. `frametime`
  meanwhile got worse (51 → 64 ms). `gpu_load` rose from 80% to 88%, i.e. on
  this GPU the load percentage is not indicative.
- **Feature level 11_1 doesn't help** (13.7 versus 13.9).
- **Memory allocation doesn't help**: `prefer_gmem` is no faster than
  `prefer_sysmem`.
- **Shadows and blur are not the cause**: disabling them worsens the result.

### 13.3 What is actually loaded

- CPU: 1.65 cores out of 8 in total, maximum per thread 29%. No single thread
  is loaded — the threads are idle, yet a frame is still 75 ms.
- GPU: `simple_ondemand`, `cur_freq` up to 680 MHz — the `max_freq` ceiling;
  the governor is ruled out. The governor can't be verified: writing to
  `devfreq` requires sudo.
- Memory: RAM 7.23–7.31 GB out of 7.32 GiB, i.e. 100% in every run. Swap grows
  from 3.1 up to 6.5 GB over a run, `so` up to 155 MB/2s, but `si` only
  2.6 MB/s and `wa` median 4% — no throttling in the face.

Summary: neither CPU, nor GPU, nor memory is loaded, yet a frame is 75 ms.
Stock Mesa is also 13 fps, so the limit is the hardware and the amount of
memory, not a turnip defect. FPS here cannot be raised by the driver.

### 13.4 A method error that had to be fixed

`ps -eLo` gives average CPU since process start, not instantaneous, and a
process's `pcpu` can exceed 100%. For an instantaneous per-thread picture,
deltas of `/proc/<pid>/task/*/stat` over a fixed window are computed.

### 13.5 GPU frequency governor: not a lever (18.11, protocol 13.0)

Hypothesis: `simple_ondemand` oscillates 220-680 MHz (18k transitions in
`trans_stat` since boot) and costs fps; `performance` pins 680. Checked per
13.0 — window 40-50 s, same build (sha256 `c9dad346…` of
`build/out/libvulkan_freedreno.so` in all three runs), governor switched
through `/sys/class/devfreq/3d00000.gpu/governor` (root), `trans_stat` reset
before the runs.

| run, governor | p25 | mean | min/max | frametime | clocks in window |
|---|---|---|---|---|---|
| 16:28, `performance` | 15.01 | 15.38 | 14.2/17.5 | 65.1 ms | 680 |
| 16:44, `simple_ondemand` | 14.94 | 15.37 | 13.2/17.9 | 65.2 ms | 680 |
| 16:49, `performance` | 15.09 | 15.42 | 14.3/17.4 | 64.9 ms | 680 |

`performance` versus `simple_ondemand`: +0.10 fps by p25 — noise. The reason is
visible in every row: gpu_load 98% and 680 MHz already in the window,
i.e. `ondemand` reaches the ceiling there (as `docs/fdperf-a7xx.md` warned from
the counter side). The end state is the distro default `simple_ondemand`.

CSVs: `results/games/re4/fps-gov-{ondemand,performance}.csv` (the 16:28 CSV was deleted
by the next run — `HUDLOG` recreates the log directory, so keep CSVs out of
`/tmp/opencode/mangologs` right after a run; the row above records the parsed
numbers, same build).

Side observation from the same runs (vmstat delta over ~180 s with the game,
16:44-16:52): `pgmajfault` +159886 (~900/s), `pswpin` +159328 pages (~620 MB
from zram), `pswpout` +4771. The system runs with zram ~7.0/7.9 GiB used; the
game thrashes swap. That is a lever candidate for the memory side, not the
GPU side.
