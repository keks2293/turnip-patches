# 40. 71.9 % of the primitives the VPC shades are thrown away by TSE, and it is not a GMEM/SYSMEM mode choice (21.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules
for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or
`journal N.M`, where the number is also the start of the file name.

Bottom line: on the ship stack, in the same 1 s sample, `PERF_TSE_INPUT_PRIM` equals
`PERF_PC_IA_PRIMITIVES` and `PERF_TSE_OUTPUT_VISIBLE_PRIM` is 28.1 % of it - so three quarters of the
primitives that pay for vertex shading die at TSE, 27 points of that as zero-pixel (sub-pixel) rejects;
this is not something the GMEM/SYSMEM switch recovers, because the driver already renders RE4 in SYSMEM
(our own driconf default for the `vkd3d` engine) and forcing GMEM makes the frame rate worse (13.72 vs
the 15.15-15.24 cluster) while the discard ratio stays where it was. The VSC (visibility-stream) group
cannot answer the "does the binning pass cull" question at all on this chip - its hardware budget is 2
and the group contains no per-primitive counter. Also closed here: the `VKD3D_FEATURE_LEVEL` thread
(vkd3d-proton v3.1 semantics + the log-rank trap that hid its own message), the DX11 route (queue 14),
the fragment-shader texture prefetch (already on, removing it is a no-op), concurrent binning (in this
tree `tu_allow_concurrent_binning` defaults to False, and `TU_DEBUG=forcecb` leaves the discard at
71.9 %, the VSC at ~0.4 % of the core and the binning/visibility counter banks at 0 primitives/s, with CB
off and forced (40.8, 40.11; 40.12 adds that those runs never started a binning pass, so that is not a
measurement of a working BV thread), and the VPC
attribute buffer (`TU_FORCE_PROPS=has_gmem_vpc_attr_buf` delivers - the driver logs the a750 sizes - and
moves nothing, 40.9). The "why no binning" question is closed as far as the free knobs reach: the reasons
the driver has are named in code and five of them are silent at every debug level (40.15), and forcing
GMEM + HW binning in the same session takes the frame rate from 15.3 to 10.2 fps (40.16), so the sysmem
choice is not a wrong guess that a patch could undo. What stays open is the wall itself: `VPC_BUSY` 91 %,
of whose time
`VPC_VPCRAM_FULL_CYCLES` accounts for ~51 % - the largest single named component measured so far - and
whose sub-unit occupancy (`VS_BUSY` 88.7 %, `PS_BUSY` 84.1 % of the core) has no semantics in any register
description in the tree (40.14).

## 40.1 What was run

| run | driver state | sampler cfg | dump (committed) |
|---|---|---|---|
| `tse1` | ship stack `4c3cdb210082`, no env | `tools/fdperf/fdperf.cfg-tse` | `results/games/re4/tse-tse1/fdperf-raw.txt` |
| `tse2` | ship stack, no env | `tools/fdperf/fdperf.cfg-tse2` | `results/games/re4/tse2-tse2/fdperf-raw.txt` |
| `algo-prefer_gmem` | + `TU_AUTOTUNE_ALGO=prefer_gmem` | `fdperf.cfg-tse` | `results/games/re4/tse-algo-prefer-gmem/fdperf-raw.txt` |
| `algo-bandwidth` | + `TU_AUTOTUNE_ALGO=bandwidth` | `fdperf.cfg-tse` | `results/games/re4/tse-algo-bandwidth/fdperf-raw.txt` |
| `forcecb` | + `TU_DEBUG=forcecb` | `fdperf.cfg-tse` | `results/games/re4/tse-forcecb/fdperf-raw.txt` |
| `cbbase`, `cbforce` | none, and + `TU_DEBUG=forcecb` | `fdperf.cfg-tse3` | `results/games/re4/tse3-cbbase/`, `results/games/re4/tse3-cbforce/` |
| `vpc3base`, `attrbuf` | none, and + `TU_FORCE_PROPS=has_gmem_vpc_attr_buf` | `fdperf.cfg-vpc3` | `results/games/re4/vpc3-vpc3base/`, `results/games/re4/vpc3-attrbuf/` |

All four: one RE4 session, 110 x 1 s sample sets, the steady window `t_rel` 20-105 s (40 windows), core
pinned at 680 MHz, analysis with `scripts/fdperf-tse-ratios.py` (written for this entry: it prints a
missing counter as missing, because the TSE budget is 4 and the size of the discard and the reason for
it cannot be sampled in one run - `docs/fdperf-a7xx.md`, "hw counter budgets").

The two new cfgs cost nothing to trust: the non-TSE blocks are copied from `fdperf.cfg-vpc`, and in `tse2`
the anchors of the vertex story come back where `cfg-vpc` put them (VPC busy 91.7 %, `VPC_VS_BUSY/VPC_BUSY`
96.85 %, `PC_STALL_CYCLES_VPC/PC_BUSY` 68.89 %, UCHE arbiter stall 42.62 %, VFD starve on UCHE 56.10 %,
DRAM reads 15.71 GB/s with TP at 12.77 GB/s). A change in the TSE slots that leaves those where they were
is what makes the TSE numbers about the game rather than about the counter selection.

## 40.2 The discard, and what kind of discard it is

`tse1` (mean over 40 windows, M primitives/s):

| counter | value | share |
|---|---|---|
| `PERF_PC_IA_PRIMITIVES` | 255.19 | - |
| `PERF_TSE_INPUT_PRIM` | 255.19 | 1.0000 of IA |
| `PERF_TSE_OUTPUT_VISIBLE_PRIM` | 71.62 | 28.06 % of the input |
| `PERF_TSE_ZERO_PIXEL_PRIM` | 68.94 | 27.02 % of the input |
| drop = input - visible | 183.58 | **71.9 % of the input** |

`tse2`, the reason counters (different run, same cfg shape; the input of that run is not in this cfg):

| counter | M/s | share of the 183.58 M/s drop above | share of the input |
|---|---|---|---|
| `PERF_TSE_TRIVAL_REJ_PRIM` | 53.93 | 29.4 % | 21.1 % |
| `PERF_TSE_FACENESS_CULLED_PRIM` | 45.20 | 24.6 % | 17.7 % |
| `PERF_TSE_ZERO_PIXEL_PRIM` (from `tse1`) | 68.94 | 37.6 % | 27.0 % |
| `PERF_TSE_ZERO_AREA_PRIM` | 0.83 | 0.45 % | 0.33 % |
| `PERF_TSE_CLIPPED_PRIM` | 0.35 | 0.19 % | 0.14 % |

`ZERO_AREA_PRIM` at 0.33 % of all input kills the hypothesis that this workload is full of degenerate
triangles that a cull bit would remove - there is nothing to remove there. `TSE_CULLED_PRIMS` and
`TSE_ZERO_AREA_PRIMS` (with an S), the names used in the operator's note for this queue item, do not
exist in `src/freedreno/registers/adreno/a7xx_perfcntrs.xml`; the real names are singular and are quoted
above.

`TSE_BUSY_CYCLES` is 542.19 Mc/s = 79.73 % of 680 MHz in `tse1`, which is an independent confirmation of
the 79.6 % figure in `results/games/re4/mesa27/steady-state.txt` (17.11, a different cfg and a different
week). In the same four dumps `TSE_INPUT_PRIM` and `PC_IA_PRIMITIVES` are equal to the sample
(ratio 1.0000 in all of them), i.e. nothing between the IA and TSE drops a primitive. Two readings of
that equality, and this entry does not decide between them: either every primitive really is passed
through, or the kernel exposes the same counter twice under two names. It is not quotable as "no culling
happens before TSE" without a run that samples only one of the two.

The names carry no documentation: `desc=` occurs 0 times in `a7xx_perfcntrs.xml`, so "trivial reject =
outside the viewport" and "zero pixel = no coverage after rasterisation" are readings of the counter
names, not quotes.

## 40.3 The VSC group cannot ask the question it was proposed for

`PERF_VSC_*` on a7xx is five counters in total - `BUSY_CYCLES` (0), `WORKING_CYCLES` (1),
`STALL_CYCLES_UCHE` (2), `EOT_NUM` (3), `INPUT_TILES` (4) - and the hardware budget of the group is 2
(`docs/fdperf-a7xx.md`, table of budget sizes). There is no per-primitive counter in it, so "is the
visibility stream culling the invisible primitives before the draw pass" is not a question this group can
ask, in any combination of its slots.

What it does answer, from the committed 17.11 runs (`results/games/re4/mesa27/fdperf-raw.txt`,
`results/games/re4/mesa27-vertex/fdperf-raw.txt`, windows >= 35 s) and from `tse1`/`tse2`: `VSC_BUSY` is
3.7 / 3.9 Mc/s (0.54 / 0.57 % of the core) in 17.11 and 2.59 / 2.57 Mc/s (0.38 %) tonight, and 85.1 /
85.6 % of that small busy time is `VSC_STALL_CYCLES_UCHE`. The block is idle more than 99 % of the time;
whatever the visibility stream decides, it is not where the time goes. `PERF_VSC_EOT_NUM` reads 0.00 M/s
in `tse2` - that selector is not usable, and this entry does not read anything into it.

The counters that do speak to geometry wasted in the binning pass are in the CP group, and they are
already sampled by `fdperf.cfg-vpc`: `PERF_CP_PREDICATED_DRAWS_KILLED` is 0.0/s in every 21.11 run, and
`PERF_CP_DEAD_DRAWS_IN_BIN_RENDER` is 542.5 / 0.0 / 5.0 per second across `vpcbase1` / `vpcbase2` /
`hpbase2` and 0.0/s in `tse1` and `tse2` - run-unstable and at most a few per cent of `CP_CONTEXT_DONE`
(~39-43 k/s), so the dead-draw share is not what makes the VPC busy.

## 40.4 Why there is no visibility stream to begin with, and the switch that was worth trying

The reason the front end runs every primitive is in our own stack, not in the game. The installed
driconf defaults, `/usr/share/drirc.d/00-turnip-defaults.conf` line 40, inside the
`<engine engine_name_match="vkd3d">` block:

```xml
<!-- DX games almost always tend to prefer SYSMEM over GMEM, so we just hardcode
     this for VKD3D-Proton. -->
<option name="tu_autotune_algorithm" value="prefer_sysmem" />
```

and `../mesa27-src/src/freedreno/vulkan/tu_autotune.cc:100-101` defines what that value means:

```c
   PREFER_SYSMEM = 3, /* Always use SYSMEM unless we have strong evidence that GMEM is better. */
   PREFER_GMEM = 4,   /* Always use GMEM unless we have strong evidence that SYSMEM is better. */
```

SYSMEM rendering has no GMEM binning and therefore no visibility stream, which is consistent with
`VSC_BUSY` = 0.38 %. The environment beats driconf for this key (`tu_autotune.cc:277-283`), so the switch
is testable without a build, and that is the cheapest known attack on the VPC wall: if the binning pass
carried the 71.9 % away from the vertex path, `prefer_gmem` would show it.

It does not. One run per arm, same window rule, same cfg (`fdperf-tse-ratios.py`):

| arm | p25 fps, 60-90 s window | discard = 1 - visible/input | VSC busy | VPC busy | `PC_STALL_VPC/PC_BUSY` | UCHE arbiter | VFD starve | DRAM reads |
|---|---|---|---|---|---|---|---|---|
| default (`prefer_sysmem` from driconf) = `tse1` | not measured (no CSV) | 71.9 % | 0.38 % | 91.6 % | 68.53 % | 43.40 % | 55.73 % | 15.65 GB/s |
| `algo-bandwidth` (Mesa's default algorithm, no SYSMEM bias) | 14.88 | 71.9 % | 0.26 % | 91.8 % | 60.33 % | 40.65 % | 54.70 % | 15.38 GB/s |
| `algo-prefer_gmem` | 13.72 | 73.8 % | 0.21 % | 92.4 % | 55.23 % | 39.96 % | 51.90 % | 14.93 GB/s |

The frame-rate base for the same driver is the cluster of clean runs measured tonight - `fl111` 15.20,
`fl121` 15.20, `vpc2b` 15.20, `tse2` 15.24, `nopref` 15.15, `vpcbase2` 15.16 - with `vpcbase1` at 14.12 as
the low end. Against that, `prefer_gmem` at 13.72 is a loss of about 10 %, in the same direction as
journal 15.5's `TU_AUTOTUNE_FLAGS=big_gmem` (-1.5 fps, about -12 %), and `bandwidth` at 14.88 is at or a
little below the cluster: the in-tree `prefer_sysmem` default is on the better side, and there is nothing
to win by removing it.

That the environment variable reaches the autotuner was checked, not assumed - `TU_DEBUG=startup` makes
the driver print the value it parsed (`tu_autotune.cc:300-301`), verbatim from
`results/games/re4/game-patched-algopg.log` and `results/games/re4/game-patched-algobogus.log`:

```
TU: info: TU_AUTOTUNE_ALGO=4 (prefer_gmem)
TU: warning: Unknown TU_AUTOTUNE_ALGO 'nonsense', using default
TU: info: TU_AUTOTUNE_ALGO=0 (nonsense)
```

(`VPC busy` and `PC_STALL_VPC` do move between arms - 68.53 % to 55.23 % - so the arms are not the same
run; but the discard ratio, the thing the switch was supposed to change, did not move.)

## 40.5 Texture prefetch is already on, and turning it off is a no-op

The proposal was to *enable* fragment-shader texture prefetch for the vkd3d shaders. In this tree it is
already enabled for this chip: `src/freedreno/common/freedreno_devices.py:739` sets
`has_fs_tex_prefetch = True` in `a7xx_base` (only `a8xx_gen2` turns it off), and the consumer is
`src/freedreno/ir3/ir3_context.c:118`, gated on `MESA_SHADER_FRAGMENT`. The only available experiment is
the inverse, through the documented override `FD_DEV_FEATURES=has_fs_tex_prefetch=0`
(`freedreno_devices.py:112`), run 21.11 as `nopref`: TP stall on UCHE / TP busy 20.18 % against 20.16 %
(`fl111`) and 23.30 % (`vpcbase1`), DRAM reads 15.65 GB/s with TP at 12.73 GB/s = 81.3 %, UCHE VBIF
latency 147.5 cycles/access, p25 15.15 - all inside the spread of the base runs. There is no prefetch
gain to chase here.

## 40.6 Two closed threads: the feature level, and the DX11 route

`VKD3D_FEATURE_LEVEL` was tried at `11_1` and `12_1` and produced nothing, and the reason it produced
nothing is now read in the source rather than inferred. vkd3d-proton `v3.1`
(`libs/vkd3d/device.c`, `d3d12_device_caps_override`): every capability it touches is raised with
`max(...)` or set `TRUE`, and then

```c
    caps->max_feature_level = fl_override;
    WARN("Overriding feature level: %#x.\n", fl_override);
```

so `11_1` lowers the reported level and cannot lower the shader model (the SM 6.6/6.7/6.8 "Enabling
support" lines in the log come from `d3d12_device_caps_init_shader_model` and are unaffected). The
override does happen - verbatim, from `results/games/re4/game-patched-fl111w.log` with `VKD3D_DEBUG=warn`:

```
warn:vkd3d-proton:d3d12_device_caps_override: Overriding feature level: 0xb100.
```

and the negative control, `results/games/re4/game-patched-flbogusw.log`:

```
warn:vkd3d-proton:d3d12_device_caps_override: Unrecognized feature level nonsense.
```

The earlier runs at `VKD3D_DEBUG=info` showed no such line, which is a log-level trap and not a missing
override: `libs/vkd3d-common/debug.c` orders the levels `none(1) err(2) info(3) fixme(4) warn(5)
trace(6)` and filters with `if (vkd3d_dbg_get_level(channel) < level) return;`, so `info` *hides* `warn`,
and `all` is not one of the names in the table at all (an unset or unparsed value falls back to `fixme`,
which also hides `warn`). Anything that quotes a `warn:vkd3d-proton:` line has to say which debug level
the run used. Measured effect of `11_1` against `12_1`, same driver, steady 20-105 s: p25 15.20 against
15.20, VPC busy 91.6 % against 91.6 %, `PC_STALL_VPC/PC_BUSY` 68.78 % against 68.84 %, UCHE arbiter
42.64 % against 42.67 %, VFD starve 56.25 % against 56.11 %. Zero, as the source implies it should be.

Queue 14 (run RE4 through DX11/DXVK instead) is closed as unreachable by the routes tried, in order: the
`[Render] Capability` key in `local_config.ini` is an output, not an input (journal 11.2); RE4's own
binary contains no DX-flavoured command-line flag - `grep -a -o -E '.{0,18}-[a-zA-Z_]*dx[12][12]?.{0,18}'`
over the 233690016-byte `re4.exe` prints nothing, while `via.render.RenderDeviceAPI` / `DirectX11` /
`DirectX12` exist only as the reflection enum - and launching with `GAMEARGS="-dx11"` and
`GAMEARGS="-forceDX11"` left the game on the D3D12 path; `WINEDLLOVERRIDES='d3d12='` did too. All three
runs still log `warn:vkd3d-proton:d3d12_device_create_vkd3d_queues:` (a D3D12 device with queues) and the
game still writes `Capability=DirectX12` back into `local_config.ini`
(`results/games/re4/game-patched-dx11dx11.log`, `…-dx11forceDX11.log`, `…-d3doff.log`).

## 40.7 Two measurement defects found while doing this

1. **The fixed-time screenshot gate is vacuous.** The screenshots of `tse1`, `tse2`, `algo-prefer_gmem`,
   `algo-bandwidth`, `hpbase` and `cb1`/`lrz2` are 11181-byte files whose pixel mean is 0.0 - a black
   frame - and `scripts/pixelcheck.py` still answers "background identical" when both pictures are black.
   A gate that is satisfied by two black images proves nothing; flag runs are now gated on log markers
   (the expected `overridden by environment` line, no vkd3d OOM, the device-creation marker) and the
   screenshot is only compared after checking that the mean is not 0.
2. **The 60-90 s window is not the same content in every run.** `hpbase2` shows `max=424.4` fps and
   clocks `[220, 475, 680]` inside that window, `vpcbase2` `max=462.7`, `nopref` `max=282.5`: those runs
   were in a menu or a loading stretch, so their `mean` is not comparable and only `p25` of the tight runs
   (max 15-19 fps) should be quoted.
3. **The runner lost two frame-rate CSVs, and the reason was in the runner.** `/tmp/opencode/session.sh`
   copied the HUD output with `cp /tmp/opencode/mangologs/*.csv /tmp/opencode/fps-$TAG.csv`; MangoHud
   writes both `re4_<date>.csv` and `re4_<date>_summary.csv`, and `cp` of two sources onto one file name
   fails, so `tse1` (CSV gone) and `forcecb` (recovered by hand from `mangologs`, now
   `results/games/re4/fps-forcecb.csv`) had no fps table. The runner now takes the newest non-`_summary` CSV. The
   rule for this repository: a run whose CSV is missing is reported with fps `NOT MEASURED`, as `tse1` is.

## 40.8 There is a binning switch, it is off by our own configuration, and forcing it did nothing

The premise that this generation's driver uses binning/visibility (the "BV" thread, whose block the
`PERF_VSC_*` counters count) unless something blocks it was checked in the tree, and for this tree it
is the other way round. `../mesa27-src/src/freedreno/vulkan/tu_drirc_gen.py:31`:

```python
        B("tu_allow_concurrent_binning", False,
          "Allow concurrent binning on A7XX+, the CB is disabled by default because it regresses performance on desktop games",
          c_name="allow_concurrent_binning"),
```

`grep -c concurrent_binning /usr/share/drirc.d/00-turnip-defaults.conf` = 0, and the only in-tree file
that turns it on is a CI profile (`src/freedreno/ci/deqp-freedreno-a750-vk.toml:44`, for the A750).
So in every run this repository has ever made, CB is off - which is the configuration-level reason
for `VSC_BUSY` 0.21-0.57 % (40.3), not a per-renderpass heuristic.

The switch is reachable without a build: `TU_DEBUG=forcecb` (`tu_util.cc:57`,
`TU_DEBUG_FORCE_CONCURRENT_BINNING`) is applied at `tu_device.cc:2086`
(`if (TU_DEBUG(FORCE_CONCURRENT_BINNING)) instance->drirc.perf.allow_concurrent_binning = true;`), and
`TU_DEBUG=nocb` forces the other way. The per-renderpass reasons the driver still disables CB with,
for the record, are `tu_cmd_buffer.cc:3210-3225` - "disable_cb", "LRZ fast clear disabled", "partial
LRZ fast clear", "globally disabled" - and for GMEM `:3478-3480`, "xfb/prim-gen/prim-counters/vtx-stats
query is running" and "hw binning disabled". CB is not a GMEM-only path: `tu7_emit_concurrent_binning_sysmem`
(`:3270`) implements it for sysmem render passes and is called from the sysmem path at `:3350-3351`.

Measured, run `forcecb` (21.11 22:43, `TU_DEBUG=forcecb`, `fdperf.cfg-tse`, ship stack):

| | default (`tse1`) | `forcecb` |
|---|---|---|
| `VSC_BUSY` | 2.59 Mc/s = 0.38 % | 2.63 Mc/s = 0.39 % |
| discard = 1 - visible/input | 71.9 % | 71.9 % |
| VPC busy | 91.6 % | 90.6 % |
| `PC_STALL_CYCLES_VPC/PC_BUSY` | 68.53 % | 68.61 % |
| UCHE arbiter stall | 43.40 % | 43.64 % |
| VFD starve on UCHE | 55.73 % | 55.49 % |
| DRAM reads | 15.65 GB/s | 15.36 GB/s |
| p25 fps, 60-90 s | not measured | 15.15 |

What that does and does not say. The VSC did not wake up and the discard did not move, so at the
counter level the switch changed nothing. It is **not** proof that the flag was ignored: the driver
records the CB state as a string (`cb_disable_reason`) and exports it only into the render-pass trace
(`tu_cmd_buffer.cc:3072`, inside `trace_start_render_pass`), never to stderr, so no log line in a
run of this repository can show whether CB was enabled for RE4's passes. The question that settles it
is whether the VSC is fed tiles at all, which needs `PERF_VSC_INPUT_TILES` (value 4, never sampled
here) - `tools/fdperf/fdperf.cfg-tse3` was written for it with the reading fixed in its header.

Also found in this reading, and untested: the VPC attribute buffer in GMEM is gated by the same kind
of device property, and our chip does not have it. `tu_cmd_buffer.cc:647-652`:

```c
emit_vpc_attr_buf(struct tu_cs *cs, struct tu_device *dev, bool gmem)
{
   if (!dev->physical_device->info->props.has_gmem_vpc_attr_buf)
      return;
```

`has_gmem_vpc_attr_buf` with `sysmem_vpc_attr_buf_size = 0x20000` and `gmem_vpc_attr_buf_size = 0xc000`
is set for `a7xx_gen3` (`src/freedreno/common/freedreno_devices.py:854-856`) and nowhere in
`a7xx_base`/`a7xx_gen2`, so on A740 those registers are never emitted. Upstream exposes a hook for
exactly this experiment (`tu_device.cc:1799-1806`), and it logs its own effect:

```c
            /* VPC in GMEM without buffer sizes is useless: the cache is not
             * allocated, while accesses go by a zero size. We substitute the
             * a750 (a7xx_gen3) values if not set explicitly, and say so.
             */
            if (!strcmp(item, "has_gmem_vpc_attr_buf")) {
               if (!info->props.sysmem_vpc_attr_buf_size)
                  info->props.sysmem_vpc_attr_buf_size = 0x20000;
```

so `TU_FORCE_PROPS=has_gmem_vpc_attr_buf` is a no-build probe of the VPC attribute cache with a
delivery line in the log (`TU_FORCE_PROPS: vpc_attr_buf_size sysmem=0x20000 gmem=0xc000`). It is a
measurement hook, not a proposed patch: the property is absent for this generation for a reason this
entry does not investigate, and a GPU fault in that arm would be the answer, not a setback.

Two runs with `tools/fdperf/fdperf.cfg-tse3` (`VSC_BUSY` + `VSC_INPUT_TILES`) were made to test
whether CB feeds the VSC any tiles at all, and both are flawed, so they are recorded as flawed:

* `PERF_VSC_INPUT_TILES` is unusable on this kernel: `cbbase` reports 449,920,587,163 Mc/s, which is
  five orders of magnitude above the core clock, so the selector does not mean "tiles" as the name
  suggests. `cbforce` reports 0.00. Neither is quoted.
* The anchors of the pair are not on the reference cluster of the day - VPC busy 68.9 % (`cbbase`) and
  81.8 % (`cbforce`) against 91.6-92.4 % in the `cfg-vpc`/`cfg-tse` runs, `TSE_INPUT_PRIM` 179.6 and
  213.9 Mc/s against 245.7-255.2 - so the two sessions were not in the same content as the others
  (11.6's unsynchronised start, and here the screenshot is a real frame, 1.3 MB, not the black 11 kB
  one), and their absolute values cannot be compared with 40.2. They also lost their fps CSVs (only
  MangoHud's `_summary.csv` was written).
* The one within-pair signal that survives: `VSC_BUSY` 2.14 Mc/s (`cbbase`, 0.31 % of the core) against
  4.45 Mc/s (`cbforce`, `TU_DEBUG=forcecb`, 0.65 %). Forcing CB roughly doubles a block that occupies
  about half a per cent of the GPU. The discard stayed at 71.8 % in both.

**Correction, 21.11 23:35, of the first and the last of those three bullets.** The sentence
"`PERF_VSC_INPUT_TILES` is unusable on this kernel: `cbbase` reports 449,920,587,163 Mc/s" was an
artifact of my own averaging script, not of the selector, and the `INPUT_TILES` half of the pair is
reproducible. One sample in 70 of `results/raw/fdperf-cbbase.txt` prints
`PERF_VSC_INPUT_TILES: 18446744073709551290`, i.e. 2**64 - 82: a negative window delta shown as an
unsigned 64-bit value. Averaged as printed, that one sample turned a counter whose other 69 windows
read 0-21,728 into the number quoted above. (22.11, for exactness: that dump carries 70 sample labels
and 68 tile values, one of them the wrapped one, and the rest run 0 to 28,306 over the whole file and
0 to 21,728 inside `t_rel` 20-105 s. It is also a committed artifact now,
`results/games/re4/tse3-cbbase/fdperf-raw.txt`, which is what `scripts/fdperf_sections.py` re-reads.) The
same class of defect was already written up in
journal 22.1 (quoting a tool's printed number without reading how it is produced), and it is now
filtered in the script: `scripts/fdperf_sections.py`, shared by the three ratio scripts, drops values
>= 2**63 and counts them, and separates the two halves of a sample. The second half is the set of
`BV_*` groups defined by `src/freedreno/registers/adreno/a7xx_perfcntrs.json` (`BV_CP`, `BV_PC`,
`BV_VFD`, `BV_VPC` with num 6 and `select_offset` 6, `BV_TP`, `BV_SP`, `BV_UFC`, `BV_TSE` num 4,
`BV_RAS`, `BV_LRZ`, `BV_HLSQ`), i.e. the binning/visibility copies of the same blocks, whose countable
lists are the *same* enums as the ordinary groups (`"type": "a7xx_vpc_perfcounter_select"` for both
`VPC` and `BV_VPC`) - which is why one dump carries `PERF_VPC_BUSY_CYCLES` twice. A name that appears
only in that half (e.g. `PERF_VPC_WORKING_CYCLES` in a `cfg-vpc3` run) is a BV-thread counter and must
not be quoted as the ordinary block's; the scripts now say so instead of printing a value. Re-run of
the same two dumps:

| `fdperf.cfg-tse3`, window 20-105 s | `cbbase` (CB off, the default) | `cbforce` (`TU_DEBUG=forcecb`) |
|---|---|---|
| windows used | 40 of 70 (1 value dropped as wrapped) | 88 of 118 |
| `VSC_INPUT_TILES`, per s: min / median / max | 0 / 56 / 21,728 | 775 / 1,532 / 8,957 |
| windows with **zero** tiles | 8 of 40 | 0 of 88 |
| `VSC_INPUT_TILES`, mean | 1,678/s | 1,674/s |
| `VSC_BUSY`, median | 2.57 Mc/s = 0.38 % | 3.14 Mc/s = 0.46 % |
| discard = 1 - visible/input | 71.8 % | 71.9 % |

So the switch is *seen* by the hardware: with `forcecb` every window is fed tiles (775 at the least)
where the default run leaves a fifth of the windows at zero, and the mean is unchanged. The VSC is
being fed in both arms - ~1.7 thousand tiles/s, which at the 15 fps of these runs is on the order of
100 tiles per frame, far less than a full-screen binning pass - and the discard does not move in
either arm (71.8 % vs 71.9 %). That keeps the conclusion of 40.4/40.8 as it was, now with the
mechanism visible instead of inferred: the difference CB makes here is in *when* the VSC works, not
in how many primitives survive TSE.

The claim "`VSC_EOT_NUM` reads 0.00 Mc/s (unusable selector)" is **not** corrected: with the wrapped
values and the second section filtered out, `tse2` still reports 0.0/s over 40 windows while
`VSC_BUSY` in the same windows is 2.57 Mc/s (`scripts/fdperf-tse-ratios.py`).

Also corrected here, because it was quoted in the `forcecb` comparison: `CP_DEAD_DRAWS_IN_BIN_RENDER`
and `CP_PREDICATED_DRAWS_KILLED` are not usable as rates in this workload. Over the 20-105 s window
they are 0 in most windows with isolated bursts - `tse1` 0 in all 52 samples; `tse2` one sample at
224,010 and its partner at 224,035; `cbbase` 25 of 71 samples nonzero, max 895,910; `cbforce` 118 of
119 nonzero but max 9,417 - so any per-second figure from them is a mean over bursts, and the
"60.3/s" figure that appeared in the table above is not supported. Whether a bin render happens is
answered by `VSC_INPUT_TILES` above, not by these two.

The BV copies of the blocks, read as what they are (the second occurrence of a name inside a sample,
same 20-105 s window, the five dumps of 21.11 named in this entry), say the same thing as the VSC
tiles from the driver side:

| BV group counter, median over the window | `tse1` | `forcecb` | `cbbase` | `cbforce` | `vpc3base` |
|---|---|---|---|---|---|
| `BV_VPC` `VPC_BUSY_CYCLES` | 0.45 Mc/s = 0.07 % | 0.44 = 0.06 % | 0.48 = 0.07 % | 0.51 = 0.08 % | 0.47 = 0.07 % |
| `BV_TSE` `TSE_BUSY_CYCLES` | 0.14 = 0.02 % | 0.14 = 0.02 % | 0.15 = 0.02 % | 0.16 = 0.02 % | not programmed |
| `BV_LRZ` `LRZ_BUSY_CYCLES` | 0.16 = 0.02 % | 0.15 = 0.02 % | 0.17 = 0.02 % | 0.18 = 0.03 % | 0.17 = 0.02 % |

So the binning/visibility copies of the VPC, TSE and LRZ are at two to eight hundredths of a per cent
in every run, and `TU_DEBUG=forcecb` does not move them (0.44 against 0.45 Mc/s median). One BV counter
must **not** be quoted this way: the BV copy of `TP_BUSY_CYCLES` reads 6.5 G/s, i.e. 950-967 % of a
one-second window of a 680 MHz core. Either it is a sum over the 12 TP instances (the instance
dividers are in docs/fdperf-a7xx.md) or the BV select was never programmed and that register is not the
BV thread's counter; that is not decided here, so the number is recorded and not used. What would
decide it is addressable without a code change - `fdperf.c`'s `config_restore()` looks every group of
`fd_perfcntrs()` up in the cfg by name, and `BV_VPC`/`BV_TSE` are groups, so a cfg with explicit
`BV_VPC = { ... }` and `BV_TSE = { ... }` sections would program the BV selects directly - and it is
queue 20 of docs/plan-next-checks.md, not run.

On the varyings question, the same reading of the tree gives a definite answer about the mechanism:
`ir3_link_shaders` (`src/freedreno/ir3/ir3_shader.h:1387`, called from `tu_pipeline.cc:802`) builds the
link map by walking **the fragment shader's inputs** (`ir3_next_varying(fs, j)` over `fs->inputs_count`),
and `ir3_link_add` derives from them both `varmask` ("bitset of locations used") and `max_loc` ("the size
required for each vertex in the VPC in DWORD's"). A VS output the FS does not read is therefore not in
the fetch map and does not extend the per-vertex size. `nir_remove_dead_variables` over
`nir_var_shader_in | nir_var_shader_out` also runs in `ir3_nir_lower_io` (`ir3_nir.c:1018`). Consistent
with that, the measured per-invocation payload is already small: `VPC_NUM_VPCRAM_WRITE` 2.62 per
invocation, `SP_COMPONENTS` 0.89 per invocation, `VFD_NUM_ATTRIBUTES` 5.08 per vertex
(`scripts/fdperf-vpc-ratios.py`, `results/games/re4/vpc-vpcbase1/fdperf-raw.txt`). What is *not* established
is that `VPC_PS_BUSY` means "packing varyings for the FS" - `a7xx_perfcntrs.xml` has no descriptions - so
the claim "the VPC spends its 91 % packing varyings" stays an inference. The other half of that
question, whether the VPC's own RAM is what limits it, was measured after this paragraph was written
and is 40.9 below.

## 40.9 The VPC attribute buffer: our generation never programs it, and forcing it changes nothing

The lever proposed by the operator was the VPC attribute buffer: RE4 renders in sysmem mode, and the
attribute/position buffer in sysmem is 0x20000 on the generation that has one. Checked in the tree, an
A740 does not have one at all - so the question is not "is 128 KiB enough" but "is the buffer emitted
at all":

* `tu_cmd_buffer.cc:647-652` - `emit_vpc_attr_buf()` returns before writing anything unless
  `dev->physical_device->info->props.has_gmem_vpc_attr_buf`;
* `src/freedreno/common/freedreno_devices.py:854-856` sets `has_gmem_vpc_attr_buf` with
  `sysmem_vpc_attr_buf_size = 0x20000` and `gmem_vpc_attr_buf_size = 0xc000` for **`a7xx_gen3` only**;
  `a7xx_base` and `a7xx_gen2` (what an A740 uses, rows at :1177 and :1320) do not set it;
* upstream ships the probe (`tu_device.cc:1799-1806`): forcing the property substitutes the a750 sizes
  and says so - "VPC in GMEM without buffer sizes is useless: the cache is not allocated, while
  accesses go by a zero size."

Two runs, no build, both with `tools/fdperf/fdperf.cfg-vpc3` (the VPC's own memory system: the six-slot
VPC budget spent on `VPCRAM_FULL`, `WIT_FULL`, `STALL_CYCLES_VPCRAM_POS`, `STALL_CYCLES_LM_ACK`,
`NUM_LM_REQ_HIT` plus `BUSY`), command as in queue 19:

```
SAMPCFG=tools/fdperf/fdperf.cfg-vpc3 /tmp/opencode/session.sh vpc3base
SAMPCFG=tools/fdperf/fdperf.cfg-vpc3 env TU_FORCE_PROPS=has_gmem_vpc_attr_buf /tmp/opencode/session.sh attrbuf
```

Delivery is proved from the game log, 9 lines each in `results/games/re4/game-patched-attrbuf.log`, 0 in
`results/games/re4/game-patched-vpc3base.log` (the raw files are `results/raw/game-patched-{attrbuf,vpc3base}.log`):

```
TU: info: TU_FORCE_PROPS: has_gmem_vpc_attr_buf
TU: info: TU_FORCE_PROPS: vpc_attr_buf_size sysmem=0x20000 gmem=0xc000
```

The numbers (`scripts/fdperf-vpcram-ratios.py results/games/re4/vpc3-*/fdperf-raw.txt 20 105`, 40 and 39
one-second windows, core pinned at 680 MHz):

| counter | `vpc3base` | `attrbuf` | reading |
|---|---|---|---|
| `VPC_BUSY_CYCLES` | 623.5 Mc/s = 91.70 % | 617.9 Mc/s = 90.86 % | the wall itself, unchanged |
| `VPC_VPCRAM_FULL_CYCLES` | 317.0 Mc/s = 46.62 % of the core, 50.84 % of busy | 314.0 / 46.18 % / 50.82 % | half of the VPC's busy time is its own RAM not accepting a write |
| `VPC_WIT_FULL_CYCLES` | 7.8 Mc/s = 1.25 % of busy | 7.7 / 1.25 % | not a limit |
| `VPC_STALL_CYCLES_VPCRAM_POS` | 2.7 Mc/s = 0.44 % of busy | 2.6 / 0.42 % | not a limit |
| `VPC_STALL_CYCLES_LM_ACK` | 0.0 | 0.0 | reads zero in both arms |
| `VPC_NUM_LM_REQ_HIT` | 0.0 | 0.0 | reads zero in both arms |
| p25 fps, 60-90 s | 14.71 (n=299, max 16.6) | 14.73 (n=299, max 18.2) | no difference |

Reading. Forcing the property delivered - the driver logged the a750 sizes and the registers are
emitted - and nothing moved: VPC busy within 0.8 points, `VPCRAM_FULL` within 0.02 points of busy,
fps within 0.02. The direction is closed as a lever, and it is closed *without* a driver patch, which
is the outcome queue 19 was written to allow. Two side observations from the same pair, both stated as
counter behaviour rather than as hardware facts:

* `VPC_VPCRAM_FULL_CYCLES` at ~51 % of the VPC's busy time is the largest single component of the wall
  measured so far, and it does not respond to the attribute buffer. As a reading of the name it says
  "the VPC's own RAM could not take a write", which is what you would expect if the block is writing
  per-primitive output as fast as it can; whether it is a *cause* of the 91 % is not established here.
* `VPC_STALL_CYCLES_LM_ACK` and `VPC_NUM_LM_REQ_HIT` read exactly 0 in all 89 windows of the two runs.
  Like `VSC_EOT_NUM` in 40.3, that is a selector that gives no signal here, so the LM hit-rate line of
  the script prints nothing for these runs rather than a hit rate.

The pair is also the second instance of the content problem noted in 40.7: both arms of this pair sit at
p25 14.71/14.73 while the day's reference cluster is 15.15-15.24, so the *absolute* fps of these two
runs belongs to the pair, not to the table of arms in 40.2.

## 40.10 What this does not show

* One run per arm for the autotune A/B. The p25 of the clean base runs spans 15.15-15.24, and
  `vpcbase1` sits at 14.12, so `bandwidth` at 14.88 is within the unexplained run-to-run spread; only
  `prefer_gmem` at 13.72 is clearly outside it, and it needs a repeat before it becomes a number of record.
* The discard ratio is measured; the statement "those primitives cost the VPC its busy cycles" is an
  inference from `VPC_BUSY` 91.6-92.4 % plus `PC_STALL_CYCLES_VPC/PC_BUSY` 68.5-68.9 % in the same
  samples, not a per-primitive cost measured by any counter.
* `ZERO_PIXEL_PRIM` / `TRIVAL_REJ_PRIM` semantics are readings of names; a manual description does not
  exist in the tree.
* Nothing about the game settings was tested (LOD, resolution): the sub-pixel 27 % is a property of the
  scene as configured, and this entry says nothing about how much of it a settings change would remove.
* No patch, no ship-stack change, no `patches/` file was written for this entry; the driver state is the
  released `4c3cdb210082…` in every run, with only environment variables changed
  (`TU_AUTOTUNE_ALGO`, `TU_DEBUG=forcecb`, `TU_FORCE_PROPS`).
* Whether the CB was enabled for RE4's render passes in the `forcecb` arms is still not shown directly:
  the driver keeps the reason as a string (`cb_disable_reason`) and exports it only into the render-pass
  trace (`tu_cmd_buffer.cc:3072`), never to stderr. The counter-level answer (tiles fed to the VSC every
  window under `forcecb`, 20 % of windows empty without it) is the closest measurement so far, and queue
  20 (an explicit `BV_VPC`/`BV_TSE` cfg) is the direct one.
* The `BV_*` copies of the groups are quoted only where they are consistent across runs (medians
  0.02-0.08 %); `BV_TP` `TP_BUSY_CYCLES` at 950-967 % of a one-second window is recorded and not
  interpreted, and the BV selects were never programmed deliberately.
  (22.11: they were programmed, `BV_TP` is the 12-instance TP sum mirrored, and those 0.02-0.08 % medians
  were readings of unprogrammed selects - 40.11 and 40.12.)
* `VPC_STALL_CYCLES_LM_ACK` and `VPC_NUM_LM_REQ_HIT` read exactly 0 in both arms of 40.9, so the LM hit
  rate is `NOT MEASURED`, not 0 %.
* The `vpc3base`/`attrbuf` pair is its own content cluster on p25 (14.71/14.73 against the day's
  15.15-15.24), and the `cbbase`/`cbforce` pair is its own again on the counter side (VPC busy 68.9 % and
  91.6 %). Within-pair comparisons in this entry are sound; cross-pair absolute values are not.
  (22.11: this bullet is void on the counter side - both of those percentages were means over windows in
  which the core was not at 680 MHz, and on pinned-clock windows the pair is 91.73 % and 91.67 %, i.e. the
  same VPC pressure as the rest of the day; and the last sentence about the BV selects was overtaken by
  programming them. See 40.12's Correction 2 and 40.11.)

## 40.11 The binning/visibility counter groups can be programmed deliberately (queue 20)

**Why.** 40.8 could ask the CB question only through one proxy, `VSC_INPUT_TILES`, because every cfg of
this repository programs the ordinary counter groups and never names a `BV_*` group - the
binning/visibility thread's own copy of the same block. The dump prints those copies regardless, which
is where 40.8's 0.02-0.08 % medians came from; what was missing was the right to call them the BV
thread's. `fdperf.c`'s `config_restore()` resolves every group of `fd_perfcntrs()` by name in the cfg,
so `tools/fdperf/fdperf.cfg-bv` (new) has `BV_VPC`, `BV_TSE`, `BV_PC`, `BV_TP` sections whose selects
are deliberately different from the defaults.

**Control, run on an idle GPU** (`results/games/re4/bv-idle-labelcheck.txt`): fdperf prints the *label* of
whatever it programmed, so the same slots of the BV half are compared between a `cfg-tse3` run (no BV
section) and a `cfg-bv` run. `cfg-tse3` prints a group's first countables there - `PERF_PC_WORKING_CYCLES`,
`PERF_VPC_STALL_CYCLES_UCHE`, `PERF_TSE_CLIPPING_CYCLES` - and `cfg-bv` prints exactly what was asked
for: `PERF_PC_IA_PRIMITIVES`, `PERF_VPC_VPCRAM_FULL_CYCLES`, `PERF_VPC_WIT_FULL_CYCLES`,
`PERF_TSE_INPUT_PRIM`, `PERF_TSE_OUTPUT_VISIBLE_PRIM`. The sections reach the BV groups.

**The register map, read in `a7xx_perfcntrs.json`, says how separate the two halves are.** `BV_PC`,
`BV_VFD`, `BV_VPC`, `BV_TP`, `BV_SP`, `BV_UFC` name the same select register as their ordinary twin and
add a `select_offset` (8, 8, 6, 12, 24, 4), i.e. `VPC_PERFCTR_VPC_SEL` holds six ordinary slots and
then six BV slots; `BV_TSE`, `BV_RAS`, `BV_LRZ`, `BV_HLSQ`, `BV_CP` have no `select_offset`, so their
selects *are* the ordinary group's words. The value registers are separate anyway: in
`results/games/re4/bv-bvbase/fdperf-raw.txt` slot 0 of `TSE` reads 247 M primitives/s and slot 0 of
`BV_TSE` reads 0.

**What was run** (all on the ship stack `4c3cdb210082`, env only; dumps
`results/games/re4/bv-{bvbase,bvforce,bvforce2,bvforce3,bvforce4,bvforce5}/fdperf-raw.txt`; one RE4
session each, 110 x 1 s windows, core pinned to 680 MHz - which `bvbase` held in only 16 of its 38
steady windows, see the notes under the numbers table):

| arm | cfg | driver env | purpose |
|---|---|---|---|
| `bvbase` | `cfg-bv` | none | CB off (the drirc default of 40.8), BV halves programmed |
| `bvforce` | `cfg-bv` | `TU_DEBUG=forcecb` | the same with CB forced |
| `bvforce2` | `cfg-bv` | `TU_DEBUG=forcecb GALLIUM_PRINT_OPTIONS=1` | an attempt at a delivery line: **it produced none** (0 hits in the log), because `u_debug.c`'s print path never reached the game log |
| `bvforce3` | `cfg-bv` | `TU_DEBUG=startup,forcecb` | the working delivery control: the driver logs `TU: info: TU_DEBUG=0x1000000001` (`tu_util.cc:135`; bit 36 = `FORCE_CONCURRENT_BINNING`, `tu_util.h:75`) and `Created an instance` (`tu_device.cc:2133`) |
| `bvforce4` | `cfg-bv2` (no `BV_PC`, no `BV_TP`) | `TU_DEBUG=startup,forcecb` | which BV section kills the VSC tile counter |
| `bvforce5` | `cfg-bv3` (`BV_VPC` only) | `TU_DEBUG=startup,forcecb` | the same question from the other side |

**The numbers** (mean over `t_rel` 20-105 s, `scripts/fdperf-bv-table.py`, which is the one reader that
keeps both halves of a dump):

| counter | ordinary group, `bvbase` | `BV_*` copy, `bvbase` | ordinary group, `bvforce3` | `BV_*` copy, `bvforce3` |
|---|---|---|---|---|
| `VPC_BUSY_CYCLES` | 604.00 Mc/s = 88.8 % | 0.43 = 0.063 % | 623.27 = 91.7 % | 0.44 = 0.065 % |
| `VPC_WORKING_CYCLES` | not programmed | 0.16 | not programmed | 0.17 |
| `VPC_VPCRAM_FULL_CYCLES` | 317.35 | 0.00 | 334.11 | 0.00 |
| `VPC_WIT_FULL_CYCLES` | not programmed | 0.00 | not programmed | 0.00 |
| `PC_BUSY_CYCLES` | 626.82 = 92.2 % | 0.06 | 646.87 = 95.1 % | 0.06 |
| `PC_IA_PRIMITIVES` | 247.27 M/s | 0.0/s | 254.00 M/s | 0.0/s |
| `TSE_INPUT_PRIM` | 247.28 M/s | 0.2/s | 254.00 M/s | 0.0/s |
| `TSE_OUTPUT_VISIBLE_PRIM` | 69.61 M/s | 0.2/s | 71.33 M/s | 0.0/s |
| `TSE_BUSY_CYCLES` | not programmed | 0.14 | not programmed | 0.14 |
| `LRZ_BUSY_CYCLES` | 543.67 = 79.9 % | 0.15 | 560.08 = 82.4 % | 0.16 |
| `TP_BUSY_CYCLES` | 6364.78 (530.4 per instance = 78.0 %) | 6364.75 = 100.000 % of it | 6536.32 | 6536.31 = 100.000 % |
| discard `1 - visible/input` | 71.85 % | - | 71.92 % | - |
| `VSC_BUSY_CYCLES` | 2.49 = 0.37 % | - | 2.55 = 0.38 % | - |
| `VSC_INPUT_TILES` (median) | 16/s in the steady window, 0/s in its pinned-clock ones (40.12) | - | 0/s | - |

p25 fps (60-90 s, `scripts/fps-window.py`): 15.22 (`bvbase`), 15.29 (`bvforce`), 15.21 (`bvforce2`),
15.15 (`bvforce3`), 15.27 (`bvforce4`), 15.18 (`bvforce5`).

Two notes on that table, both learned after it was cut and written up in 40.12. The percentages are over
every steady window, and `bvbase` is the one run of 22.11 whose core clock sagged: 22 of its 38 steady
windows are not within 1 % of the pinned 680 MHz (their median is 649 MHz, minimum 613), which is why its
`VPC_BUSY` reads 88.8 % where every other arm reads 91.6-91.7 %; on its 16 pinned-clock windows `bvbase`
reads 91.68 %, and those 16 are exactly the ones with no tiles. The tile count of `bvbase` sits in the
other 22 windows, so in that row the tile column and the duty-cycle column are not windows of the same
GPU state.

**Reading.**

* The BV banks are addressable and their value registers are separate: their own cycle counters count
  (`BV_VPC` busy 0.43-0.45 Mc/s, `VPC_WORKING` 0.16-0.17, `BV_TSE` busy 0.14, `BV_LRZ` busy 0.15-0.16,
  `BV_PC` busy 0.06), and slot 0 of `BV_TSE` reads 0 primitives/s where slot 0 of `TSE` reads 247 M/s in
  the same sample. What they do not count, in all four programmed arms, is primitives: `BV_PC`
  `PC_IA_PRIMITIVES`, `BV_TSE` `TSE_INPUT_PRIM` and `TSE_OUTPUT_VISIBLE_PRIM` read 0/s - 0.2/s in
  `bvbase`'s `BV_TSE` half, which against the 247 M/s of the ordinary half is none - and `BV_VPC`
  `VPCRAM_FULL`/`WIT_FULL` read 0.00 Mc/s. 40.12 shows what that is worth: none of these sessions had a
  binning pass that counted - `bvbase` fed about one tile per frame in its off-clock windows, every
  forced arm fed none.
* Forcing CB changes nothing in them: `BV_VPC` busy 0.43 against 0.44 Mc/s, every per-primitive counter
  still 0, and the ordinary-side anchors stayed where they belong (TSE input 247.28 against 254.00 M/s,
  discard 71.85 against 71.92 %). How much that is worth as a statement about the CB thread depends on
  whether these sessions binned at all, and 40.12 shows they did not: the `BV_*` zeros of 22.11 are the
  counters of a binning thread that was never started.
* `BV_TP` `TP_BUSY_CYCLES` is **not** a per-thread number, and this corrects the sentence of 40.8 that
  read "*the BV copy of `TP_BUSY_CYCLES` reads 6.5 G/s, i.e. 950-967 % of a one-second window of a 680
  MHz core. Either it is a sum over the 12 TP instances ... or the BV select was never programmed ...
  that is not decided here*". It is now decided, and both of the two offered explanations were the
  wrong pair: with `BV_TP` programmed deliberately, and also with its section removed (`bvforce4`,
  `bvforce5`), the BV copy reads 100.000 % of the ordinary copy (6364.75 against 6364.78 Mc/s). The TP
  print in the BV half mirrors the ordinary TP counter, whose 6.36 G/s is the sum over the 12 TP
  instances, i.e. 530 Mc/s per instance = 78 % of the core. There is no separate BV-TP measurement to
  make on this chip, and 950-967 % was never a duty cycle.
* The mirroring is not limited to TP, and that is the reason an unprogrammed `BV_*` half must not be
  read at all. In the 21.11 dumps, where no cfg named a BV group, whole groups of the BV half equal
  their ordinary twin: in `cbforce`, `BV_TP` 100.076 %, `BV_CP` 100.076 %, `BV_UCHE` 100.355 %,
  `BV_CCU` 101.278 %, `BV_RB` 100.668 % and the BV copies of `PC_IA_PRIMITIVES`, `TSE_INPUT_PRIM` and
  `TSE_OUTPUT_VISIBLE_PRIM` 100.5-100.6 % of the ordinary counters (`scripts/fdperf-bv-table.py` on
  `results/games/re4/tse3-cbforce/fdperf-raw.txt`). A select word that was never written carries the
  previous run's value or zero, and the BV value register then reports the same event as the ordinary
  one. So 40.8's "BV medians of 0.02-0.08 % of the core" measured nothing about the BV thread: those
  were groups whose BV select happened to name a nearly-idle counter.
* `TU_DEBUG` has no delivery line of its own and unknown keys are ignored (`u_debug.c`,
  `debug_parse_flags_option`), so a bogus key proves nothing and `GALLIUM_PRINT_OPTIONS=1` printed
  nothing in the game log (`bvforce2`). `TU_DEBUG=startup,<flag>` is the control to use: the driver logs
  the flag word itself (`tu_util.cc:135`). That is also what settles the `bvforce`/`bvforce3` difference
  below: CB really was forced, so the counter difference is in the cfg, not in the environment.

**The caveat this leaves, and 40.12 closes it.** In every forced arm of 22.11 - `cfg-bv` with
`TU_DEBUG=forcecb`, and `cfg-bv2` and `cfg-bv3` the same way - `PERF_VSC_INPUT_TILES` reads 0 in every
sample, where `cfg-tse3` on 21.11 fed tiles in 32 of its 40 steady windows with CB off and in all 88 with
`forcecb`. The unforced `cfg-bv` arm (`bvbase`) is in between: tiles in 22 of 38 steady windows at a
median of 16/s. `cfg-bv` and `cfg-tse3` hold an identical `VSC` section, so a `BV_*` section was the
suspect; dropping `BV_PC`/`BV_TP` (`bvforce4`) and then dropping `BV_TSE` too (`bvforce5`, only `BV_VPC`
left) did not bring the tiles back.

## 40.12 The VSC tile counter is a per-session switch, and that decides what 40.11 measured

**Why.** Three explanations were left for the dead tile counter: a `BV_*` section clobbers the VSC
counters, the `startup` flag added for the delivery line changed the driver, or the sessions differ.
Two more arms test the last two: `tse3cb2` (`cfg-tse3`, no BV section at all,
`TU_DEBUG=startup,forcecb`) and `tse3cb3` (`cfg-tse3`, plain `TU_DEBUG=forcecb`, the 21.11 arm repeated
tonight). Dumps `results/games/re4/tse3-{tse3cb2,tse3cb3}/`, plus `results/games/re4/bv-{bvforce4,bvforce5}/`
from 40.11.

**Tiles fed per second.** Two window rules, both printed, because the two kinds of counter need
different ones:

* *steady* = `t_rel` 20-105 s of the sample set, wrapped window deltas and `[invalid]` dropped;
* *pinned-clock* = the steady windows whose `CP_ALWAYS_COUNT` is within 1 % of the pinned 680 MHz. A
  duty cycle is meaningless in a window where the core ran at 649 MHz (it is diluted, see Correction 2);
  an event count like tiles/s is not clock-dependent, so it is cut over both sets.

`scripts/fdperf-tile-table.py` is the only place these numbers are cut, and it prints:

| run | date | cfg | `TU_DEBUG` | steady | pinned | tiles med / max /s, steady | windows with tiles, steady | tiles med / max /s, pinned | windows with tiles, pinned | VSC busy % (pinned) |
|---|---|---|---|---|---|---|---|---|---|---|
| `cbbase` | 21.11 | `cfg-tse3` | none (CB off) | 42 | 29 | 56 / 21,728 | 32 of 40 | 2 / 2,189 | 21 of 29 | 0.38 |
| `cbforce` | 21.11 | `cfg-tse3` | `forcecb` | 88 | 87 | 1,532 / 8,957 | 88 of 88 | 1,532 / 8,957 | 87 of 87 | 0.46 |
| `bvbase` | 22.11 | `cfg-bv` | none | 38 | 16 | 16 / 26 | 22 of 38 | 0 / 0 | 0 of 16 | 0.38 |
| `bvforce` | 22.11 | `cfg-bv` | `forcecb` | 41 | 40 | 0 / 3 | 1 of 41 | 0 / 0 | 0 of 40 | 0.38 |
| `bvforce3` | 22.11 | `cfg-bv` | `startup,forcecb` | 40 | 40 | 0 / 0 | 0 of 40 | 0 / 0 | 0 of 40 | 0.38 |
| `bvforce4` | 22.11 | `cfg-bv2` | `startup,forcecb` | 40 | 40 | 0 / 0 | 0 of 40 | 0 / 0 | 0 of 40 | 0.38 |
| `bvforce5` | 22.11 | `cfg-bv3` | `startup,forcecb` | 40 | 40 | 0 / 0 | 0 of 40 | 0 / 0 | 0 of 40 | 0.37 |
| `tse3cb2` | 22.11 | `cfg-tse3` | `startup,forcecb` | 41 | 41 | 0 / 0 | 0 of 41 | 0 / 0 | 0 of 41 | 0.38 |
| `tse3cb3` | 22.11 | `cfg-tse3` | `forcecb` | 39 | 39 | 0 / 0 | 0 of 39 | 0 / 0 | 0 of 39 | 0.37 |

p25 fps (60-90 s, `scripts/fps-window.py`): 15.26 (`tse3cb2`), 15.20 (`tse3cb3`).

**Reading.**

* No cfg of 22.11 kills the tile counter, and neither does `TU_DEBUG=startup`: `bvbase`, which carries
  all four `BV_*` sections, reads tiles in 22 of its 38 steady windows, and the 21.11 arm repeated
  verbatim tonight (`tse3cb3`) reads 0 like the rest. The difference is the session.
* The scale says how big that difference is. At the ~15 fps these runs hold (this 21.11 pair lost its
  fps CSVs, 40.10), `cbforce`'s 1,532 tiles/s is about 100 tiles per frame - a real binning pass - while
  `bvbase`'s 16 tiles/s is about one tile per frame, and every other 22.11 arm is at none, with the flag
  delivered and logged (`tse3cb2` carries `TU: info: TU_DEBUG=0x1000000001`) or without it.
* `VSC_INPUT_TILES` tracks neither the cfg nor the flag reliably across runs: the same cfg family and
  the same kind of scene read 56/s unforced and 1,532/s forced on 21.11, and 16/s unforced and 0/s
  forced on 22.11. Inside one run it does work - `cbforce` has tiles in 87 of its 87 pinned-clock
  windows, `cbbase` in 21 of 29 - so it is a per-session switch, and the "forcing CB feeds the VSC" step
  of 40.8 stands only as what that session showed.
* The one 22.11 arm that binned at all binned only while the core was below the pinned clock:
  `bvbase`'s 22 tile-windows have a median `CP_ALWAYS_COUNT` of 649 MHz and its 16 pinned-clock windows
  read 0 tiles. That is a hint for queue 21: the way to a run with a real binning pass may be a stretch
  where the geometry node is not saturated, and the first counter to check in such a run is the clock.
* So 40.11's per-primitive `BV_*` zeros are the counters of a binning thread that had no pass to run in
  those sessions. They say the BV banks are addressable and that a session without binning leaves them
  at ~0, and nothing more. The CB direction stays closed on 40.8's evidence (forcing it moved p25 by
  0.09 fps and the discard by 0.1 points), not by a direct BV reading, and queue 21 of
  `docs/plan-next-checks.md` asks for a run with a real binning pass before the BV thread can be read
  at work.

**Correction 1, 22.11: the tile row of 40.8.** That table read
"*`VSC_INPUT_TILES` | 0 (median) / 21,728 (max) | 775 / 8,957*". Those four numbers come from three
sample sets and none of them is a column of the table above. For `cbbase` the median is 56/s over the 40
tile values of the steady window, 2/s over its 29 pinned-clock ones, and 528/s over the whole raw file -
the published "0" was the median of all 68 tile values in the file, which is not a steady-window
statistic. For `cbforce` the median is 1,532/s in both window rules, and "775" was its minimum, not its
median. The paragraph's conclusion is unaffected: `cbbase` feeds tiles in 21 of 29 pinned-clock windows
and `forcecb` in 87 of 87, and the discard stays at 71.76 % and 71.86 %.

**Correction 2, 22.11: the duty cycles of this entry were cut over windows in which the core was not at
the pinned clock.** `scripts/fdperf-arm-table.py` now averages a duty cycle only over the pinned-clock
windows (`CP_ALWAYS_COUNT` within 1 % of 680 MHz), and prints how many windows it dropped and the dump's
median clock. The percentages published here were means over every sample of the run, so the difference
is the windows where DVFS had not reached 680 MHz:

| run | VPC busy as published here | every sample | steady window | pinned-clock windows | n, all / steady / pinned |
|---|---|---|---|---|---|
| `tse3-cbbase` | 68.9 % (40.10) | 77.24 % | 68.95 % | **91.73 %** | 70 / 42 / 29 |
| `tse3-cbforce` | 81.8 % (40.10) | 90.21 % | 91.61 % | **91.67 %** | 118 / 88 / 87 |
| `tse-tse1` | 91.6 % (40.8) | 91.56 % | 91.61 % | 91.61 % | 52 / 40 / 40 |
| `tse-forcecb` | 90.6 % (40.8) | 90.83 % | 90.60 % | **91.61 %** | 52 / 40 / 33 |
| `vpc3-vpc3base` | 91.70 % (40.9) | 91.67 % | 91.70 % | 91.75 % | 51 / 40 / 39 |
| `vpc3-attrbuf` | 90.86 % (40.9) | 90.78 % | 90.86 % | **91.63 %** | 50 / 39 / 35 |
| `bv-bvbase` | 88.8 % (40.11) | 89.13 % | 88.82 % | **91.68 %** | 49 / 38 / 16 |
| `vpc-vpcbase1` | 90.5 % (40.10) | 77.16 % | 90.51 % | **91.49 %** | 51 / 40 / 38 |
| `vpc-vpcbase2` | 91.0 % (40.6) | 90.59 % | 90.96 % | **91.57 %** | 50 / 39 / 29 |
| `vpc-hp50` | 88.4 % (40.6) | 89.00 % | 88.43 % | **91.45 %** | 50 / 39 / 31 |
| `vpc-hp40` | 62.7 % (40.6) | 60.92 % | 62.71 % | none - median clock 585 MHz | 43 / 39 / 0 |
| `tse-algo-prefer_gmem`, `tse2`, `vpc2b`, `nopref`, `fl111`, `fl121`, `cb1`, `lrz2`, `hpbase2`, `mesa27` | as published | within 0.7 points | as published | within 0.3 points | - |

What that changes in the entry's own wording:

* 40.10's "*the `cbbase`/`cbforce` pair is its own again on the counter side (VPC busy 68.9 % and
  91.6 %)*" and its other bullet's "*VPC busy 68.9 % (`cbbase`) and 81.8 % (`cbforce`)*" are both wrong on
  the counter side: on pinned-clock windows that pair is 91.73 % and 91.67 %, the same VPC pressure as
  every other arm, and the two published numbers were not even cut the same way - 81.8 % is a mean over
  all 118 samples of `cbforce`, 68.9 % a mean over the steady window of `cbbase`. What still separates
  that pair from the rest of 21.11 is its primitive rate (TSE input 244.8 M/s against 255 M/s) and its
  DRAM (15.27 GB/s against 15.7).
* 40.9's "*VPC busy within 0.8 points*" for the attribute-buffer pair holds as the numbers were cut, and
  on pinned-clock windows the gap is 0.12 points (`vpc3base` 91.75 %, `attrbuf` 91.63 %). Same verdict,
  stronger.
* 40.6's `hp40` row is not a 680 MHz number at all: none of its 39 steady windows is pinned-clock
  (median `CP_ALWAYS_COUNT` 585 MHz), so its 62.7 % says the core was throttled, not that the VPC had
  slack. The arm table prints that row's duty cycles as `-` with the clock named.
* `bvbase`'s 88.8 % of 40.11 is the same artifact, and it matters there because `bvbase` is also the arm
  whose tiles were read: its tile-windows and its pinned-clock windows are disjoint sets, so the tiles
  column and the duty-cycle column of that row are not windows of the same GPU state. Its VPC busy on
  pinned-clock windows is 91.68 %.

## 40.13 What the 22.11 additions do not show

* Whether the BV thread shades primitives when CB actually runs. Every forced arm of 22.11 ran without a
  binning pass (`tse3cb3` proves it is not the cfg), so the question is open and queue 21 states how to
  close it: find a session with tiles > 0, then read `BV_TSE` and `BV_PC` in it.
* Why the sessions differ. The 21.11 arms reached a binned stretch and the 22.11 arms did not; nothing in
  the logs of 22.11 says what the driver decided (`cb_disable_reason` is not logged), and the two nights'
  `cbbase`-equivalents differ by 11 M primitives/s of TSE input, which is within the content spread this
  entry already reports. The one pattern in the dumps is the clock: the only 22.11 windows with tiles are
  the off-clock ones (`bvbase`, median 649 MHz), and 21.11's `cbbase` fed tiles in 21 of its 29
  pinned-clock windows while its other counters say those windows are indistinguishable from its
  tile-free ones (VPC busy 91.70 % against 91.84 %, TSE input 244.8 M/s in both). So the correlation with
  the clock is real in one run and absent in the other, and it is not an explanation.
* Whether the wall's duty cycles differ between arms at all. With the pinned-clock window rule of
  Correction 2, `VPC_BUSY` is 91.45-91.75 % in every arm of `cfg-vpc`, `cfg-vpc2`, `cfg-vpc3`, `cfg-tse`,
  `cfg-tse2`, `cfg-tse3` and `cfg-bv` - 25 of the 27 arms in that band - with only the two
  autotune-target arms outside it (91.81 % and 92.40 %) and the two `mesa27` runs of the unpatched driver
  below it (90.21 % and 90.53 %). Differences of the size this entry has been reporting, 0.1 to 0.9 points, are within what the
  choice of windows alone moves, so no lever measured here is credited with a duty-cycle change; only
  `algo-prefer_gmem` (92.40 % busy, 26.23 % visible, 13.72 fps) stands outside the band on both counters.
  `scripts/fdperf-arm-table.py` prints that table.
* `vpc-hp40` has no usable duty-cycle number at all: all 39 of its steady windows are off-clock (median
  585 MHz), so whatever heap-pressure percent it was set to, the run is not comparable on any percentage.
  Its p25 (11.81) and its per-second counters still stand.
* `BV_VFD`, `BV_SP`, `BV_UFC`, `BV_RAS`, `BV_HLSQ`, `BV_CP` were left unprogrammed in `cfg-bv`, and the
  BV groups whose selects are shared with the ordinary group (`BV_TSE` and friends, no `select_offset`)
  were programmed with the same counters as their twin: a cfg that asks the BV bank for *different*
  counters than the ordinary bank has not been run, so "the BV half is a separate measurement" is shown
  only by the label check and the value-register difference in `bvbase`, not by a counter the ordinary
  group could not have produced.
* Nothing here changed the ship stack: `build/out` is still `4c3cdb210082`, no file in `patches/` was
  touched, and every 22.11 arm is the released driver with an environment variable.

## 40.14 The varyings counters were programmed on 21.11, and they close the payload half of that branch (queue 15)

**Why.** Queue 15 of `docs/plan-next-checks.md` pre-registered a reading for the last open vertex
question - "is the VPC saturated because of varyings?" - and named the counters that can answer it:
`VPC_PS_BUSY_CYCLES`, `VPC_SP_COMPONENTS`, `VPC_NUM_VPCRAM_WRITE`, `VPC_LM_FULL_WAIT_FOR_INTP_END`,
`PC_VERTEX_HITS` and the per-client write-request side of UCHE. `tools/fdperf/fdperf.cfg-vpc` carries all
of them inside the hw budgets, and the ten 21.11 arms run with it (`vpcbase1`, `vpcbase2`, `hpbase2`,
`hp50`, `lrz2`, `cb1`, `fl111`, `fl121`, `nopref`, `hp40`) - but 40.6 quoted only the coupling ratios of
those dumps, so the varyings numbers sat unread in the committed dumps. Read here over the pinned-clock
windows of `scripts/fdperf-arm-table.py` (`t_rel` 20-105 s with `CP_ALWAYS_COUNT` within 1 % of 680 MHz);
`scripts/fdperf-vpc-ratios.py` prints the same columns per dump.

| arm | VPC busy | `VS_BUSY` | `PS_BUSY` | `LM_FULL_WAIT_FOR_INTP_END` | `NUM_VPCRAM_WRITE` per VS invocation | `SP_COMPONENTS` per VS invocation |
|---|---|---|---|---|---|---|
| `vpc-vpcbase2` | 91.57 % | 88.68 % | 84.11 % | 1.10 % | 2.62 | 0.89 |
| `vpc-fl111` | 91.58 % | 88.67 % | 84.19 % | 1.11 % | 2.63 | 0.89 |
| `vpc-fl121` | 91.60 % | 88.69 % | 84.20 % | 1.14 % | 2.62 | 0.89 |
| `vpc-cb1` | 91.61 % | 88.69 % | 84.17 % | 1.10 % | 2.62 | 0.89 |
| `vpc-nopref` | 91.53 % | 88.63 % | 84.24 % | 1.12 % | 2.62 | 0.89 |
| `vpc-lrz2` | 91.73 % | 86.73 % | 84.09 % | 1.06 % | 2.62 | 0.89 |
| `vpc-hpbase2` | 91.71 % | 86.51 % | 84.49 % | 1.07 % | 2.63 | 0.89 |
| `vpc-hp50` | 91.45 % | 87.61 % | 83.67 % | 1.05 % | 2.62 | 0.89 |
| `vpc-vpcbase1` | 91.49 % | 84.94 % | 84.23 % | 0.98 % | 2.62 | 0.89 |
| `vpc-hp40` | no pinned-clock window (40.12) | - | - | - | - | - |

Three more counters from the same dumps: `PC_VERTEX_HITS` 470-501 M/s, i.e. 0.65 of `PC_IA_VERTICES`
(718-765 M/s); `UCHE_WRITE_REQUESTS_VPC` reads **0.0 M/s** in every arm while `UCHE_WRITE_REQUESTS_SP`
reads 46.3-48.8 M/s; and `VFD_STALL_CYCLES_VPC_ALLOC / VFD_BUSY` is 12.4 % (12.5 % in the 17.11 vertex
run of queue 15, so the arm set did not move it).

**Reading, against the pre-registered rule.**

* The payload half of the branch closes. The VPC moves 2.62 `VPCRAM` writes and 0.89 `SP_COMPONENTS` per
  vertex-shader invocation, and `LM_FULL_WAIT_FOR_INTP_END` - the signature queue 15 named for "the
  interpolate side is waiting on the link map" - is 1.0-1.1 % of the core, about 1.2 % of `VPC_BUSY`.
  Whatever the VPC is doing 91.5 % of the time, it is not waiting on varyings to drain, and the per-vertex
  payload is the same in every arm. The knob queue 15 named for a varying-side fix,
  `tu6_vpc_varying_mode()` / `tu6_emit_vpc_varying_modes()` (`tu_pipeline.cc:677-730`, `734-776`), is
  therefore **not** justified by any number in this repository, and it has not been tried.
* `PS_BUSY` is *not* a small share: 83.7-84.5 % of the core in all nine usable arms. That is the one
  number the pre-registration did not expect, and it cannot be turned into a varying claim, because
  `VPC_BUSY` 91.5 % + `VS_BUSY` 88.7 % + `PS_BUSY` 84.1 % sum to well over one core - the three are not
  mutually exclusive phases of one pipe, and `a7xx_perfcntrs.xml` gives no description for any of them
  (40.7 already said the "packing varyings" gloss of `PS_BUSY` is an inference). So the honest sentence is
  that the VPC's sub-unit occupancy is high and undecoded, not that interpolation is the wall.
* The fetch side stays as journal 38 described it: `VFD_STALL_CYCLES_VPC_ALLOC` is 12.4 % of VFD busy
  unchanged across nine arms, and `PC_VERTEX_HITS` at 0.65 per IA vertex is the reuse behind the
  1.03 vertices per input primitive of 40.6.
* The zero of `UCHE_WRITE_REQUESTS_VPC` is recorded and not interpreted. The counter is programmed
  (`fdperf.cfg-vpc`, UCHE `counter11 = 16`), so this is a measured zero, but it sits next to a non-zero
  SP write-request counter and a `VPCRAM` write count of 2.62 per invocation, which cannot all three be
  "the VPC writes nothing to L2". What the client-side write counters wire up to on a7xx is not in the
  register description in this tree, so no claim is built on it.

**What this does not show.** Whether the VPC's 91.5 % is geometry math or varying packing - the two
counters that would separate them are `VPC_PS_BUSY` and `VPC_VS_BUSY`, and their semantics are not
described anywhere in the tree or the XML; asking the hardware by changing
`tu6_emit_vpc_varying_modes()` is a build and a measurement that this evidence does not motivate. And the
arms above are all 21.11 sessions, so their content spread is the one 40.10 describes; the columns that
move between them are `VS_BUSY` (84.9-88.7 %) and the primitive rate, not the per-invocation payload.

## 40.15 The render-mode decision is two functions, and its stated reason never reaches a log (queue 22)

**Question.** Which condition keeps RE4's render passes out of GMEM - and can a `TU_DEBUG`
level tell us? A code reading, no run; the runs are 40.16.

**Method.** `../mesa27-src` at `9845cfb` plus our eight modified files, as the tree stood
22.11; the line numbers below are that tree.

**The code.** `use_sysmem_rendering()` (`tu_cmd_buffer.cc:1418-1495`) decides the render
mode per pass and writes a `force_render_mode_reason` string; `use_hw_binning()` (1386-1416)
then decides the VSC path, where it is only `vsc->binning_possible && vsc->binning_useful`
(1415). The branches, in order: `TU_DEBUG(SYSMEM)` (1423), `!tiling->possible` = "Can't fit
attachments into gmem" (1430), empty render area (1439/1445), tessellation (1450),
`rp.disable_gmem` (1455, reasons set at 5606 / 8813 / 10688 / 10818), XFB (1462),
PRIMITIVES_GENERATED query (1472), `TU_DEBUG(GMEM)` returning *false* (1478),
"Too many tiles and HW binning is not possible" (1485), and the autotuner (1489, reasons at
`tu_autotune.cc:1820-1937`; with no history it returns `default_mode = SYSMEM`, 1840, with no
string at all). `binning_possible` is `is_hw_binning_possible()` (`tu_util.cc:359-367`,
`pipe0.width * pipe0.height <= 32`, tile search 287-343 under the GMEM budget of
`tu_pass.cc:854-888`); `binning_useful` is `tile_count.w * tile_count.h > 2` (`tu_util.cc:509`),
forced by `FORCEBIN` (511) / killed by `NOBIN` (513).

**Verdict.** The reason string reaches the Perfetto trace only
(`tu_cmd_buffer.cc:3103-3106`), never `mesa_log*`, so no debug level prints it. Two branches
log on their own (the feedback-loop sites 5603/8811, `perf_debug()`) and in the `dbg-perf`
session they printed **zero** times while other `perf_debug()` sites printed by the thousand
(`results/games/re4/dbg-flip-and-messages.txt`) - so the feedback-loop branch provably did not fire and
the rest are silent by construction. Closing this needs a counter, not a knob: a per-second
histogram of `force_render_mode_reason`, modelled on `tu_dbg_log_gmem_load_store_skips()`
(`tu_util.cc:593-642`, called from `tu_queue.cc:436-437`). Needs a build (queue 16/22).

**Does not show.** Which branch fires (NOT MEASURED); whether `tiling->possible` is true for
the game's passes (`TU_GMEM=` of `tu_knl_drm_msm.cc:1390` is the cheap probe, not run).

## 40.16 Forcing GMEM plus HW binning costs a third of the frame rate; the flip happens inside one session (queue 22)

**Question.** The operator's dichotomy: if forcing binning raises fps a heuristic is wrong,
if it lowers fps the driver chose rightly. Testable with no build - the overrides are
`TU_DEBUG` bits and `TU_DEBUG` can be changed at runtime through `TU_DEBUG_FILE`
(`tu_util.cc:93-120`, runtime subset 69-76).

**Method.** `scripts/run-game.sh patched`, ship stack `4c3cdb210082`, `/tmp/opencode/chain22.sh`
08:24-08:35 on 22.11 plus the `dbg-sysmem` control at 09:47; sampler
`tools/fdperf/fdperf.cfg-tse3`. Delivery proved by the driver's own line: `TU_DEBUG=0x30001`,
`0x31011`, `0x30009`, and `TU: info: Watching TU_DEBUG_FILE: /tmp/opencode/tu-dbg-file.txt`
under `0x1`. All four dumps report `max_freq=680000000`.

**Numbers.** `results/games/re4/dbg-flip-and-messages.txt` (generator `scripts/dbg-flip-table.py`,
reads `results/games/re4/dbg-{perf,file,gmem,sysmem}/fdperf-raw.txt` and
`results/games/re4/fps-dbg-*.csv`) has the per-arm fps windows, message counts and the flip rows. The
three numbers that decide it, p25 fps 95-150 s against `VSC_BUSY` % of the core and
`VSC_INPUT_TILES` median /s: default 15.34 / 0.38 % / 0; forced sysmem 15.18 / 0.38 % / 0;
forced GMEM+binning 10.27 / 12.51 % / 53,505,966.

**The flip, which is the measurement.** In `dbg-file` the content does not change, so it is
one A/B in one session: the flag file was written at chain+85 s and blanked at chain+175 s,
tiles go 0 -> 49.7 M/s on the next sample and stay 52-54 M/s, and the fps buckets move
15.2 -> 10.2 and back to 15.2 (MangoHud's clock runs ~35 s behind the chain's launch line;
one offset lands both edges on the two writes).

**Verdict.** Frame rate fell by a third. At whole-game granularity the driver's sysmem choice
is the better one, and loading the VSC buys nothing - so "A740 has no binning/binning is off"
is not a lever for this game and justifies no patch. The `sysmem` control adds that demanding
sysmem changes nothing at all (15.18 against 15.34, tiles 0 in all 51 pinned samples), which
is what it looks like when every pass is already in sysmem.

**Does not show.** Whether some *individual* pass would be faster in GMEM (the knob forces
every pass; a per-pass answer needs the histogram of 40.15). Which branch decided (40.15).
The `[GMEM] loads/stores total: 0` lines that every arm prints: they count *conditional*
load/store only (`tu_clear_blit.cc:5894-5935`, gated by `vsc->binning_possible &&
pass->has_cond_load_store && ...` at `tu_cmd_buffer.cc:6811-6813`), so they say the
skip-if-no-geometry optimization is not in play, not that GMEM is idle - and they stayed 0 in
`dbg-gmem`, where tiles were fed. The unit of `A7XX_PERF_VSC_INPUT_TILES` (selector 4, no
description in `a7xx_perfcntrs.xml`) is NOT VERIFIED: 53.5 M/s at 10.2 fps would be ~13 000
full-frame 96x96 tile visits per frame, so only the 0 -> 53.5 M/s step is quoted. fps columns
are within-session; 15.30/15.34/15.36 inside one arm is the noise floor.

## 40.17 UBWC carries 2 % of RE4's DRAM reads, and turning it off from the translation layer does not move the frame rate (queue 23)

**Question.** Open question 15: does the compressor actually write compressed bytes, or only
a metadata plane (journal 22.2 says the `+0x2000` allocation signature proves an allocation)?
And what is the price of compression in the real game?

**Method.** No Mesa build: the switch is on the translation layer. The shipped vkd3d-proton
(`files/lib/wine/vkd3d-proton/x86_64-windows/d3d12core.dll`, `vkd3d-1.1-5641-g44cf7c2`) takes
`disable_color_compression,disable_depth_compression` in `VKD3D_CONFIG`; upstream
`libs/vkd3d/resource.c` (upstream source, not committed here) turns those into
`VkImageCompressionControlEXT` with `VK_IMAGE_COMPRESSION_DISABLED_EXT`, which Turnip honors
by setting `ubwc_enabled = false` (`tu_image.cc:637-644`). `/tmp/opencode/chain23.sh`,
09:35-09:50 on 22.11, ship stack `4c3cdb210082`, sampler `tools/fdperf/fdperf.cfg-traffic`
(new: UCHE 57/58 `..._UBWC_READ/WRITE_BEATS`, 43/44 `..._READ_REQUESTS_TP_UBWC/NONUBWC`,
the CMPDECMP CCU counters, `PERF_CP_CACHE_FLUSH`).

**Numbers.** `results/games/re4/traffic-ubwc-ab.txt` (generator `scripts/fdperf-traffic-table.py`, reads
`results/games/re4/tr-{base,nocomp,noupload}/fdperf-raw.txt`); 16 B per UCHE VBIF beat. Key row:
`tr-base` 15.59 GB/s DRAM read, 317 MB/s UBWC reads, 37 MB/s UBWC writes, TP requests
48.4 M/s UBWC against 1.95 G/s non-UBWC; `tr-nocomp` UBWC 0.00 / 0.00 and TP UBWC 0 in 52 of
52 samples. Frame rate 15.26 -> 15.06 p25, DRAM read 15.59 -> 15.73 GB/s.

**Verdict.** Compressed bytes do move - 2.0 % of the read bytes, 12.7 % of the write bytes,
2.4 % of the texture client's requests - which answers open question 15 and retires the
"only a metadata plane" caveat for the game as such. The app-side switch provably reaches the
compressor (all four UBWC counters exactly zero), and taking compression off costs +0.9 %
DRAM read, +10 % DRAM write and no measurable frame rate. So compression is not where RE4's
time goes, and this is also the cheapest A/B queue 16 wanted for `0014` without a Mesa build.
`no_upload_hvv` moved no traffic counter (all columns within 1 % of `tr-base`).

**Does not show.** Which images the 317 MB/s belongs to - the counters are global, so whether
`0014`'s images are in that 2 % is queue 16. The driver-side per-image lines are absent in
these arms (`results/raw/game-patched-tr-*.log` contain no `TU:` lines at all: no `TU_DEBUG`
was set), which is why chain24 re-runs the pair with `TU_DEBUG=perf`. And the `tr-noupload`
session ran a light scene from t=100 (six 10 s buckets at 64-93 fps, 23 of 50 samples
off-clock), so its fps row is not comparable and the flag needs one more session; the
`tr-base`/`tr-nocomp` pair the verdict rests on is unaffected.

Correction 22.11 10:30: that third session has been run - `tr-noupload2` in 40.18 is clean (52 of 52
pinned, max 18.5 fps) and gives p25 15.19 against the baseline's 15.26, so `no_upload_hvv` is a zero on
frame rate as well; the 64-93 fps stretch was content.

## 40.18 The third render mode is also slower than sysmem, and depth is where RE4's compressed traffic lives (queues 22, 23)

**Question.** Two leftovers. (a) GMEM *without* forcing `binning_useful` - the third of the three
render modes, never run. (b) Which images carry the 317 MB/s of UBWC reads of 40.17.

**Method.** `/tmp/opencode/chain24.sh`, 10:15-10:27 on 22.11, ship stack `4c3cdb210082`, game
Resident Evil 4 Gold Edition (`re4.exe`, D3D12 -> vkd3d-proton 3.1.0, 2560x1440 - `results/games/README.md`).
Arms, each with its delta in `results/games/re4/<tag>/meta.txt`: `gmem-nobin`
(`TU_DEBUG=startup,gmem,perf,log_skip_gmem_ops`, log line `TU_DEBUG=0x31001`, `cfg-tse3`);
`tr-nocomp-perf` (`TU_DEBUG=startup,perf` + `VKD3D_CONFIG=disable_color_compression,disable_depth_compression`,
`cfg-traffic`); `tr-noupload2` (`VKD3D_CONFIG=no_upload_hvv`, `cfg-traffic`) - a clean re-run of 40.17's
third arm.

**Numbers.** `results/games/re4/dbg-flip-and-messages.txt` and `results/games/re4/traffic-ubwc-ab.txt`
(generators committed); fps from `results/games/re4/fps-*.csv`. Render-mode ladder, p25 95-150 s:
forced sysmem 15.18, default 15.34, GMEM without binning 13.74 (tiles 0, `VSC_BUSY` 0.08 % of the
core), GMEM + binning 10.27. `tr-nocomp-perf`: 177 `Disabling UBWC ... due to
VK_IMAGE_COMPRESSION_DISABLED_EXT` lines, **all** of them `PIPE_FORMAT_Z32_FLOAT` or
`Z32_FLOAT_S8X24_UINT` (0 colour formats), against 2495 `... due to mutable formats` lines for the
colour class; traffic identical to `tr-nocomp` (UBWC 0.00, TP UBWC 0 in 52/52). `tr-noupload2`: every
traffic column within 1 % of `tr-base`, p25 15.10 / 15.19, 52 of 52 samples pinned at 680 MHz.

**Verdict.** (a) The render-mode ladder has no rung above sysmem: GMEM without binning is ~10 %
slower than sysmem and feeds no tiles, so the whole GMEM/binning direction is closed for this game -
not just "forcing binning is bad" but "GMEM is worse in both of its forms". (b) The compressed traffic
is depth: in the shipped vkd3d-proton's RE4 profile the compression-control switch applies to depth
images only, turning the UBWC counters to exactly zero, while the colour images are already
uncompressed through their mutable-format lists. So the tiling class journals 21-24 are about (colour,
format lists) is outside the 2 % measured in 40.17. (c) `no_upload_hvv` is a zero on a session that is
not anomalous: the earlier 64-93 fps stretch of 40.17 was content, not the flag - today's re-run has no
frame above 18.5 and the same p25 as the baseline.

**Does not show.** Whether some individual depth pass benefits from compression (the counters are
global, the switch is per-image-class). Whether `disable_color_compression` alone changes anything at
all in this game: with depth compression on and colour off, the UBWC traffic would stay, so that arm is
pointless here. Which images *keep* UBWC and why - a per-image log line is one `perf_debug()` away but
needs a build, and the answer would not change any number measured so far.

## 40.19 With the game's own Shadow Cache on, the frame carries half the primitives and runs 74 % faster (chain25, chain26)

**Question.** The operator's two observations - about 15 fps in every part of the level, and resolution
barely mattering - say the frame is dominated by a cost that does not depend on what the camera sees.
Which cost is it, and is it inside anything this repository can change? The test was aimed at the
shadow pass, because the pass that a tiler cannot amortise and a player can switch off is the shadow
cascade redraw.

**Method.** Ship stack `4c3cdb210082`, no env, no driver change: the delta between arms is the game's
own `local_config.ini`, edited before launch and restored afterwards (`/tmp/opencode/local_config.re4.orig[.2]`,
and `diff` shows the file came back byte-identical). Game: Resident Evil 4 Gold Edition (`re4.exe`,
D3D12 through vkd3d-proton 3.1.0, 2560x1440 display mode), one 210 s session per arm through
`scripts/run-arm.sh`, sampler `tools/fdperf/fdperf.cfg-tse3`.

| arm | game setting | chain |
|---|---|---|
| `sh-c0` | `AppShadowQuality=1 AppShadowCache=0` - as this install ships | 26 |
| `sh-c1` | `AppShadowQuality=1 AppShadowCache=1` | 26 |
| `sh-q0` | `AppShadowQuality=0 AppShadowCache=1` | 25 |
| `sh-q3` | `AppShadowQuality=3 AppShadowCache=1` | 25 |

`/tmp/opencode/chain25.sh`, `/tmp/opencode/chain26.sh`. Chain25 turned the cache on in *both* of its
arms, so it measures the quality knob and nothing else; the cache itself is isolated by chain26.

**Numbers.** `results/games/re4/shadow-cache-ab.txt` (regenerate: `scripts/shadow-cache-table.py`),
raw dumps `results/games/re4/{sh-c0,sh-c1,sh-q0,sh-q3}/fdperf-raw.txt`, fps
`results/games/re4/fps-sh-*.csv`, per-arm settings `results/games/re4/<arm>/meta.txt`. In the
pinned-clock windows: cache off 15.26 p25 with 16.69 M primitives per frame, `VPC_BUSY` 91.68 % and
`PC_STALL_CYCLES_VPC/PC_BUSY` 68.82 %; cache on 26.57 p25 with 8.49 M primitives per frame,
`VPC_BUSY` 85.57 %, `PC` stall 57.21 %. DRAM read is where it was (15.66 -&gt; 15.19 GB/s). Chain25's two
arms, four minutes apart, give 24.36 and 24.37 p25 and 8.44 / 8.46 M primitives per frame - the scene
reproduces to 0.04 %, and the cache-off arm reproduces the 15.1-15.3 cluster of 40.16 to within 1 %,
so 15.26 -&gt; 26.57 is the setting and not the camera.

**Verdict.** The wall has a component that is neither the driver nor vkd3d: with the Shadow Cache off,
RE4 redraws the static shadow casters every frame, and that redraw is 49 % of the primitives the frame
submits. Turning the cache on removes it and buys +74 % frame rate on the same build with the same
environment - the largest single effect measured in this repository, and larger than every driver knob
tried in journals 38-40 combined. Shadow *quality* inside the cached state changes nothing: quality 0
and quality 3 differ by 0.01 fps and 0.02 M primitives per frame, so what costs is the per-frame
redraw, not the map resolution. No consequence for the shipped driver follows from this - the draws are
the application's, and a driver that skipped them would be rendering something else.

Two things follow for how the rest of this entry is read. Every driver A/B in journals 38-40 ran with
the cache off, so their absolute frame rates are the worst setting this game has; the comparisons
within those journals are unaffected, because every arm shared the setting. And the cost structure has
changed under the render-mode question: `VPC_BUSY` is 85.6 % and not 91.7 %, so the GMEM/binning ladder
of 40.16 and 40.18 was measured on the heavy frame and needs re-running on this one before its verdict
is quoted as general.

**Does not show.** Whether the cached shadows are correct in motion (stale or late shadows on moving
casters is a picture question, and nothing here looks at the picture). Why quality 1 runs 8 % faster
than quality 0 and 3 while submitting the same primitives per frame - between-chain variation is the
honest answer, which is why only the within-chain pairs are quoted. Whether some other block becomes
the wall at 24-27 fps (`gpu_load` is still 97-99 %, so the answer is "something", and it is again on
the geometry side). And one method note: the `shot-*.png` of these runs are byte-identical to each
other and show a black screen with a cursor - `scripts/shot.py` through the portal does not capture
this game on this compositor - so the content check in this entry is the counter reproduction, not a
screenshot.

**Correction, 22.11 21:20, of that screenshot note.** The wording above says the capture path "does not
capture this game on this compositor". It does capture: a screenshot taken on 21.11 with the same script
contains the desktop (11 654 distinct colours), and the black frames here were taken with the panel
powered off (`/sys/class/drm/card0-DP-1/dpms` = `Off`) - a capture in that state is pure black with no
cursor (1 distinct colour), and with a game presenting it is black plus the ~12x20 cursor sprite. While
the panel is off nothing else can capture either: `ffmpeg -f kmsgrab` fails with `No usable planes found`
because the compositor holds no framebuffer at all (`/dev/dri/card0`: `connectors=3 crtcs=3 fbs=0`). The
method conclusion stands - the content check is the counter reproduction - but for a different, cheaper
reason: leave the panel on and the screenshot is a content check again. `scripts/run-arm.sh` now records
the panel's dpms state and the shot's colour count in every `meta.txt`, and `docs/howto-measure.md` owns
the details.

## 40.20 The render-mode ladder measured on the light frame: the verdict survives, so the sysmem default is not tuned to the game's worst setting (queue 24, chain27)

**Question.** 40.16 and 40.18 settled the three render modes (forced sysmem, driver default, GMEM,
GMEM + forced binning) and 40.19 showed that all of it was measured with the game's Shadow Cache off,
that is, on a frame carrying 16.7 M primitives instead of 8.4 M and with `VPC_BUSY` at 91.7 % instead
of 85.6 %. If binning or GMEM won on the cheaper frame, the shipped sysmem default would be a
compromise made against the game's worst setting rather than against the game. What does the ladder
look like on the light frame?

**Method.** `/tmp/opencode/chain27.sh`, 20:33-20:49 on 22.11, ship stack `4c3cdb210082` in every arm,
game Resident Evil 4 Gold Edition (`re4.exe`, D3D12 -> vkd3d-proton 3.1.0, 2560x1440), sampler
`tools/fdperf/fdperf.cfg-tse3`, one 210 s session per arm. `AppShadowQuality=1 AppShadowCache=1` is
written into `local_config.ini` before each launch and the file is restored after the chain
(`/tmp/opencode/local_config.re4.orig3`), and the settings line is appended to each arm's `meta.txt`,
so the arms cannot be quoted without their game setting. Arms and the flag as the driver reported it:
`sc-default` (no `TU_DEBUG`), `sc-sysmem` (`TU_DEBUG=0x30009`), `sc-gmem` (`0x31001`), `sc-forcebin`
(`0x31011`).

**Numbers.** `results/games/re4/render-mode-two-frames.txt` - both ladders side by side, regenerate
with `scripts/render-mode-cache-table.py`; raw dumps `results/games/re4/sc-{default,sysmem,gmem,forcebin}/`,
fps `results/games/re4/fps-sc-*.csv`. On the light frame: default 26.73 p25 / 8.42 M prims per frame /
`VPC_BUSY` 85.47 %; forced sysmem 26.54 / 8.47 M / 85.59 %; GMEM without binning 22.89 / 9.63 M /
86.85 %; GMEM with forced binning 18.90 / 10.18 M / 87.47 %, with `VSC_INPUT_TILES` 33.51 M/s against
0.00 in the other three. Against the default arm, forced binning is -29.3 % on the light frame and
-33.1 % on the heavy one, GMEM without binning -14.4 % and -10.4 %; the primitives forced binning adds
over the default are 1.24x on both frames.

**Verdict.** The order does not change and neither does the size of the penalty: on a frame with half
the geometry, GMEM is still the slower mode and forced binning still costs about a third of the frame
rate. So the sysmem default is not an artefact of the game's worst shadow setting - it is right on
both frames, and no render-mode change follows from 40.19. The forced-sysmem arm again ties the
default (-0.7 % light, -1.0 % heavy), which is 40.16's "the game is already where sysmem puts it"
result reproduced a second time on a different frame.

**Does not show.** Whether the driver's own reason for refusing to bin is the *right* reason - the
histogram of `force_render_mode_reason` is still unmeasured (queue 22, and its patch still unrun), so
this entry says GMEM loses, not why the driver's choice to stay in sysmem cannot be improved by
binning a subset of passes. And the same caveat as 40.19 for the absolute numbers: these are the
game's cached-shadow frame, so 26.7 is not the 15.3 of journals 38-40 and the two sets are only
comparable within their own frame.

## 40.21 On the cached-shadow frame the vertex path is still the busiest block, with 6 points of slack it cannot use (queue 25, chain28)

[Index back to `docs/analysis.md`](../analysis.md)

**Question.** 40.19 removed 49 % of the frame's primitives and 40.20 showed the render-mode verdict
survives the change. Both left the same thing unasked: is the wall found in 38-40 still the wall? If
the vertex path was busy because of the shadow redraw, then with the cache on it should have gone quiet
and some other block should have taken its place as the limiter - and that other block is where a
driver-side lever would be.

**Method.** `/tmp/opencode/chain28.sh`, 21:29-21:33 on 22.11: one 210 s session, ship stack
`4c3cdb210082`, no environment delta, `AppShadowQuality=1 AppShadowCache=1` written into
`local_config.ini` before launch and restored after (`/tmp/opencode/local_config.re4.orig4`), sampler
`tools/fdperf/fdperf.cfg-vpc` (the same cfg as the cache-off arm, so the two are the same counters).
Arm `vpc-cacheon`; the control is the committed `vpc-vpcbase2` of 40.6 - same build, same scene, same
cfg, cache off (its re-read at the pinned clock is the `91.57 %` row of 40.12's table, and 40.14's
occupancy table is the same dump).

**Numbers.** `results/games/re4/occupancy-two-frames.txt` (regenerate:
`scripts/occupancy-two-frames.py > results/games/re4/occupancy-two-frames.txt`), raw dumps
`results/games/re4/{vpc-vpcbase2,vpc-cacheon}/fdperf-raw.txt`, fps `results/games/re4/fps-{vpcbase2,vpc-cacheon}.csv`.
Per cent of the pinned core clock: VPC busy 91.57 -&gt; 85.54, VS busy 88.68 -&gt; 80.65, PS busy
84.11 -&gt; 76.97, `PC_STALL_CYCLES_VPC` 65.46 -&gt; 52.72. TSE input 254.79 -&gt; 225.88 M prim/s. The two
counters that sum replicated sub-units barely move: SP busy 1135.14 -&gt; 1134.02, UCHE busy
181.74 -&gt; 179.60. p25 15.25 -&gt; 26.74, over 29 and 41 kept windows.

**Verdict.** The bottleneck does not move: with the lighter frame the vertex path is still the busiest
block in the core (85.5 %), and the vertex shader inside it still dominates it (80.7 %). What changes
is that slack appears where the stall was - the primitive collector waits on the vertex path 12.7
points less - and the frame rate converts that slack into the +11.5 fps of 40.19. In other words the
game's Shadow Cache did not move the wall, it moved the game's work away from it. No driver-side block
became visible as a new limiter: nothing in this cfg goes from idle to busy.

**Does not show.** Whether the surviving 8.4 M primitives are the ones a driver could still reject -
that is 40.22, which reads the TSE reason counters on this frame. Whether the shader side is free:
`PS busy` is 76.97 %, so the fragment path is busy too, and the two `SP`/`UCHE` rows cannot be read as
occupancy at all (their sub-unit divisor is not stated in `a7xx_perfcntrs.xml`, so they are quoted only
as ratios between arms - the same caveat as 40.6). And the window counts differ (29 against 41), so
small differences in the per-window means are not resolvable; the 6-point and 12-point moves are.

## 40.22 The primitives the cache removed were mostly ones that survive the rasterizer, and the discard reasons keep their shape (queue 18 continued, chain29)

[Index back to `docs/analysis.md`](../analysis.md)

**Question.** 40.2 split the death of the frame's primitives into reasons on the cache-off frame:
21.1 % trivially rejected, 17.7 % face-culled, 0.33 % zero-area, 0.14 % clipped, against a measured
drop of 71.9 % between TSE input and TSE visible. If the cached frame's survivors died for *different*
reasons, the remaining lever would be different too - a face-cull-heavy frame is a camera problem, a
zero-area-heavy frame is a tessellation or scale problem, a zero-pixel-heavy frame is an overdraw
problem. Which is it now?

**Method.** `/tmp/opencode/chain29.sh`, 21:43-21:47 on 22.11, one 210 s session, ship stack
`4c3cdb210082`, no environment delta, cache on (`local_config.re4.orig6`), arm `tse2-cacheon` with
`tools/fdperf/fdperf.cfg-tse2` - four reason counters plus `PERF_PC_IA_PRIMITIVES`, which is the TSE
group's budget of four plus an IA counter from outside that budget (40.1 is where that budget first
decided a cfg). The input/visible/zero-pixel trio
comes from `lrz-base` (40.23, same scene, `fdperf.cfg-lrz`), because 40.1 showed the two cannot be
sampled in one run; the script therefore prints both input columns so a reader sees the cross-session
gap.

**Numbers.** `results/games/re4/tse-reasons-two-frames.txt` (regenerate:
`scripts/tse-reasons-two-frames.py > results/games/re4/tse-reasons-two-frames.txt`), raw dumps
`results/games/re4/{tse2-tse2,tse2-cacheon,lrz-base}/fdperf-raw.txt`. Cache off -&gt; on, as a share of
that frame's IA input: trivially rejected 21.13 -&gt; 18.42 %, face-culled 17.71 -&gt; 17.10 %, zero-area
0.33 -&gt; 0.52 %, clipped 0.14 -&gt; 0.00 %. The four reasons sum to 39.30 -&gt; 36.05 % of the input, against
a measured drop of 71.92 -&gt; 79.90 %. Rates: input 255.27 -&gt; 224.85 M/s, TSE visible
71.62 -&gt; 45.43 M/s, TSE zero-pixel 68.94 -&gt; 82.62 M/s (27.0 -&gt; 36.7 % of input).

**Verdict.** The shape is preserved: the same two reasons carry the discard on both frames, within 2.7
points of each other, so the cached-away geometry was not a special class of primitives. What does move
is where the survivors go. The input fell 11.8 % while the visible count fell 36.6 % and the
zero-pixel count *rose* 19.9 % - the cache removes primitives that would have produced pixels, and what
is left over is proportionally more geometry that the rasterizer rejects for covering nothing. That is
the same direction as 40.21: the frame got cheaper in shading and in the vertex path, and the ratio of
"useful pixels to submitted geometry" is not something the driver chooses.

**Does not show.** Nothing about causes of the rejects: the reason counters are named from
`src/freedreno/registers/adreno/a7xx_perfcntrs.xml`, which carries no `<desc>` for them, so "trivially
rejected" is the counter's name and not an explanation (40.2's caveat, unchanged). Whether the reasons
and the shape trio are consistent within one session - they are two sessions, and their input columns
differ by 0.03 % here, which is why shares are taken against each arm's own input. And whether a reject
saves the vertex path any work: the two frames show only that `VPC_BUSY` fell 6.03 points when the input
fell 11.8 % (40.21) while the discard share *rose* 8 points, which is what a "the reject is not worth
vertex work" reading predicts but is not a measurement of pipeline order - 40.2's caveat about
`TSE_INPUT_PRIM` and `PC_IA_PRIMITIVES` being the same counter twice covers that ground.

## 40.23 Turning LRZ off changes nothing, and the counters that made it look expensive do not follow the switch (queues: the LRZ question, chains 30-34)

[Index back to `docs/analysis.md`](../analysis.md)

**Question.** The operator asked two things: does disabling LRZ buy anything here, and is LRZ's fast
clear faster than an ordinary clear. The framing came from this repository's own counters: on the
cached-shadow frame `PERF_LRZ_BUSY_CYCLES` is 74.8 % of the core clock and `RAS_STALL_CYCLES_LRZ` is
28.4 %, which reads like an expensive unit - while 40.22 says 36.5 % of the frame's primitives produce
no pixel, the exact class of work a depth reject before pixel shading is supposed to remove.

**Method.** Five chains, 22.11 evening into 23.11, all with the game's `AppShadowQuality=1
AppShadowCache=1`, ship stack `4c3cdb210082`, one 210 s session per arm (`/tmp/opencode/chain3{0,1,2,3,4}.sh`):
chain30 the driconf option `tu_disable_conservative_lrz` through `DRIRC_CONFIGDIR` (`lrz-base`,
`lrz-nocons`, delivery in `results/lrz-drirc-delivery.log`); chain31 two `TU_DEBUG` switches and a
repeat of the base - and chain31 failed, because it used the names `nolz` and `nolzfc`, which do not
exist in this tree (`tu_util.cc:31-32` names them `nolrz` and `nolrzfc`, bits 7 and 18 of
`tu_util.h:47`/`:58`); chain32 the corrected names (`lrz-nolrz`, `lrz-nolrzfc`); chain33 repeats of both;
chain34 the same fast-clear pair with the traffic sampler. Delivery is printed, not assumed: every
arm's `TU_DEBUG` mask is taken from the driver's own line in its run log (`0x81` for `nolrz`, `0x40001`
for `nolrzfc`, `0x1` for the two mis-spelled arms), and the hardware-side check is
`PERF_LRZ_PRIM_KILLED_BY_LRZ` itself.

**Numbers.** `results/games/re4/lrz-killed.txt` (regenerate: `scripts/lrz-table.py >
results/games/re4/lrz-killed.txt`), raw dumps under `results/games/re4/{lrz-*,tr-lrzfc-*}/`.
LRZ kills 1.16-1.25 M prim/s in the five arms where it is on = 0.51-0.56 % of the TSE input, and 0.00 in
both `nolrz` arms. Its busy counter does not move: 74.79 % (base), 74.82 % and 74.99 % (the two `nolrz`
arms), 74.89 % (`nolrzfc` repeat); `RAS_STALL_CYCLES_LRZ` 28.22-28.69 % in all nine arms;
`RB_STARVE_CYCLES_LRZ_TILE` 209-223 % in all nine. p25 fps: the six default-configured arms span
26.53-26.67, `lrz-nolrz` 26.63, `lrz-nolrz2` 26.68, `lrz-nocons` 27.13 over 14 kept windows. The traffic
pair, which is the tightest control in this entry (two arms, back to back, 41 and 40 windows): depth
writes 19.59 -&gt; 19.48 M/s (-0.54 %), DRAM write 0.50 -&gt; 0.51 GB/s (+0.11 %), DRAM read
15.18 -&gt; 15.23 GB/s (+0.35 %), UBWC write 64.37 -&gt; 64.38 MB/s, p25 26.62 -&gt; 26.67 (+0.20 %).

**Verdict.** Three answers. (1) Disabling LRZ is a zero: 26.63 and 26.68 against a same-configuration
cluster of 26.53-26.67, with the switch demonstrably delivered. So is turning off *conservative* LRZ,
which is what chain30 asked. (2) The three LRZ counters that motivated the question cannot be read as
the price of depth rejection, because they are unchanged in the arms where rejection is measurably off.
Either the unit keeps servicing the RB's depth interface when the driver stops using it for reject, or
`LRZ_BUSY` counts something else - this run does not decide, and the counters carry no description in
`a7xx_perfcntrs.xml` to decide it (the same position 40.2 took on `TSE_INPUT_PRIM` versus
`PC_IA_PRIMITIVES`). Any wording in this repository that quoted 74.8 % as "what LRZ costs the frame" is
withdrawn here. (3) LRZ fast clear is on for this chip already (`enable_lrz_fast_clear` in `a7xx_base`,
40.24), and taking it away moves no byte this game writes and no frame of its rate: +0.11 % DRAM write,
+0.20 % p25. So neither direction of the fast-clear question has anything in it, and the 36.5 % of
primitives that produce no pixel (40.22) are not being missed by LRZ - LRZ's entire kill count is
0.54 % of the input. The reading rule that follows from (2) is [ADR-0012](../decisions/ADR-0012-lrz-is-not-a-lever-and-its-busy-counter-is-not-a-cost.md).

**Does not show.** Whether LRZ matters in a title that draws overlapping opaque geometry: RE4's frame
rejects almost everything for other reasons, so this is an answer about this game. What
`LRZ_PRIM_KILLED_BY_LRZ` and `LRZ_TOTAL_PIXEL` mean as units - the XML gives a `sel` and no `<desc>`, so
the kill count is quoted as a count and `LRZ_TOTAL_PIXEL` (520-534 M/s in every arm, including the ones
with LRZ off, which is itself a reason not to convert it to anything) is not converted at all. The
traffic pair has no LRZ counters in its cfg, so its delivery evidence is the mask line only. And one
method note worth keeping: an unknown `TU_DEBUG` name is skipped without a word - chain31 cost four
sessions to learn what `TU_FORCE_PROPS` would have said out loud (`mesa_logw`, `tu_device.cc:1816`), so
from now on a `TU_DEBUG` arm is quoted together with the mask the driver printed, which
`scripts/lrz-table.py` now does by itself.

## 40.24 An outside list of features supposedly "locked behind a7xx_gen3" for A740: every A8XX gate in the tree is a register difference, and the one software candidate left is `has_alias_rt` (no run)

[Index back to `docs/analysis.md`](../analysis.md)

**Question.** Two outside analyses were forwarded to this repository on 22.11 with the same shape: A740
allegedly has hardware that Turnip cuts off "by inertia", specifically (a) `sparseResidencyImage3D` and
`sparseResidencyAliased` said to sit behind the same `ubwc_all_formats_compatible` lock that patch
`0004` removed for `sparseResidencyImage2D`; (b) raster and descriptor extensions
(`VK_EXT_descriptor_buffer`, `VK_KHR_fragment_shader_barycentric`, `VK_EXT_post_depth_coverage`,
`VK_EXT_attachment_feedback_loop_layout`) said to be switched on with a `gen >= 3` test because the
maintainers had A750 boards; (c) LRZ, fast clear and softfloat32 said to be reset more aggressively on
gen2 than the hardware needs; and (d) ray-tracing pipelines said to be withheld from a chip that has
the intersection unit. Our own open thread is the same question from the other side: is any behaviour
this A740 could use hidden behind a generation test?

**Method.** No build, no run: three passes over `../mesa27-src` as it stands (our patches applied, four
files uncommitted - `freedreno_devices.py`, `tu_cmd_buffer.cc`, `tu_clear_blit.cc`, `tu_device.cc` - none
of them at a site quoted here). (1) All 80 `CHIP >= A8XX`, `CHIP < A8XX`, `CHIP == A8XX` and
`CHIP > A7XX` sites in `src/freedreno/**.{c,cc,h}` (register XML excluded), each read together with the
register it guards, and "does A740 have that register" answered from the tree's own `variants=`
attributes in `registers/adreno/a6xx.xml` and `adreno_pm4.xml`. (2) The properties that only
`a7xx_gen3` or `a8xx_base` sets (`freedreno_devices.py:849-880`, `:1401`), and every site that reads
them. (3) What the device actually answers, `scripts/device-features-a740.sh` -&gt;
`results/device-features-a740.txt`: `vulkaninfo --show-all` twice, once with the distribution's driver
and once with the ship stack `4c3cdb210082`, so a row can be attributed to upstream or to one of our
patches.

**Numbers.** The 80 sites sort into: 74 register, bitfield, packet or descriptor-format differences,
with the XML as the witness (`tu_descriptor_set.h` contributes 20 of them, all the A8XX descriptor
re-encoding, first at `:267`; `tu_cmd_buffer.cc:455` picks `SUBPASS_SLICE_FENCE` 0x36 `variants="A8XX-"`
over `SUBPASS_FENCE` 0x35 `variants="A7XX-`; `tu_lrz.cc:131` and `:157` add
`GRAS_LRZ_BUFFER_SLICE_PITCH`, `variants="A8XX-"`, because gen8 splits LRZ per UCHE slice); 2
workarounds for A8XX-only bugs (`tu_cmd_buffer.cc:10193` needs a WFI before `CP_REG_RMW`,
`common/freedreno_gpu_event.h:135` is a separate event table); and 4 sites this pass could not classify
(`tu_cmd_buffer.cc:2296`, `tu_cmd_buffer.cc:8770` with `tu_device.h:523`, `tu_shader.cc:2164` - all four
are gen8 CP behaviour derived from the blob, with no register difference to point at). **Zero** sites
where an A8XX test hides a software improvement. The software-strategy differences are all property
gates, listed per property in [`docs/a7xx-gen-props.md`](../a7xx-gen-props.md); ten of them are
runtime-forceable through the fixed list at `tu_device.cc:1750-1770` and were swept in journals 15.7 and
34, and an unknown name there is *not* silent (`mesa_logw` at `tu_device.cc:1816`). Not forceable and
not gen2-relevant: `has_sw_fuse` (a raytracing fuse), `new_control_regs` (crashdec naming),
`subpass_fence_cleans_resolve` (a gen8 resolve-wait), `gs_vpc_adjacency_quirk` (an A750 hang). The one
exception is `has_alias_rt`: the gate is `ir3_alias.c:768`, the pass "replace[s] const and immediate
components of the RT sources of end with alias.rt instructions in the preamble"
(`ir3_alias.c:762-764`), and the driver side already programs `SP_PS_OUTPUT_CONST_CNTL` and
`SP_PS_OUTPUT_CONST_MASK` for any A7XX (`tu_shader.cc:2890`), both registers `variants="A7XX-"`
(`a6xx.xml:4242`, `:4245`) - so the gate is a per-chip blob observation, not a missing register. That is
queue 26. On the claims: `sparseResidencyImage3D` is `false` in both runs of the artifact and the name
does not occur in `src/freedreno/` at all (`sparseResidencyStandard3DBlockShape = false`,
`tu_device.cc:1349`), so no generation is being locked out; `sparseResidencyAliased` is `true` in both
runs and comes from `has_sparse_prr` (`tu_device.cc:495-509`), not from UBWC;
`VK_EXT_descriptor_buffer` and `VK_EXT_attachment_feedback_loop_layout` are exposed on this device
already; barycentric and post-depth-coverage are absent in both runs because the driver carries no
extension-table entry for them, and `grep -rn "gen >= 3\|a7xx_gen3" src/freedreno/vulkan/` returns two
lines, a comment at `tu_lrz.cc:60` and the force-props table - there is no generation test in the
driver to remove. `VK_KHR_ray_tracing_pipeline` is absent while `VK_KHR_ray_query` and
`VK_KHR_acceleration_structure` are present, behind `props.has_ray_intersection` (`tu_device.cc:214-216`)
- queue 28. Fast clear has no generation gate at all: `fdl/freedreno_lrz_layout.h:252` and `:260` key it
on `props.enable_lrz_fast_clear`, which `a7xx_base` sets, so A740 runs the full A7XX FC path (1024-byte
flag RAM, two buffers, bidirectional: `common/freedreno_lrz.h:70-79`) - measured in 40.23. Softfloat32
is a driconf switch (`tu_device.cc:1059-1064`, "FP32 denorm preserve has to be emulated via soft-float")
and its price is journals 10 and 11, not this audit.

**Verdict.** "Written for A750, never looked at A740" is not the shape of this code. A `CHIP >= A8XX`
test in Turnip is a different register, packet or descriptor encoding, and the tree says so in its own
XML; the gen2-versus-gen3 gap is a *properties* gap, it is documented, ten of those properties have
already been swept at runtime on this chip, and of the rest only `alias.rt` is a feature A740 is
plausibly losing rather than a bug workaround or a naming change. For RE4's frame rate this entry finds
nothing: the wall in 40.21 is the volume of geometry the game submits, and none of the claimed locks is
on the path of that geometry.

**Does not show.** Whether `variants=` in the XML is complete for this chip revision - it is the tree's
own statement, not hardware documentation, and this repository has no Qualcomm register manual. Whether
`alias.rt` is *correct* on A740, which is what queue 26 exists to find out (a build plus a picture
check, and the panel has to be on for the picture). Anything about the proprietary driver's behaviour
(the "blob uses more prefetch", "aggressive WFI" and "RT pipeline works there" parts of the outside
notes): no artifact here can confirm or refute those, and the ship stack's own WFI and barrier behaviour
was measured in journals 38-40 as a zero. And what the game asks for: `results/device-features-a740.txt`
is one `vulkaninfo` instance from a shell, with no wine and no vkd3d-proton, so it says what the driver
offers and nothing about what RE4 requests.

## 40.25 The outside geometry plan, item by item: the VSC runs nothing on this frame, the VPC knobs are shared or already swept, and none of the three driver features it asks for is reachable from RE4 (queue 29, no run)

[Index back to `docs/analysis.md`](../analysis.md)

**Question.** A third outside analysis, forwarded 23.11, reads the 40.21 wall correctly as geometry and
then proposes four things to build: (1) audit what `a7xx_gen2` allegedly runs lower than `a7xx_gen3` in
the vertex/binning path (`num_vsc_pipes`, `VSC_BIN_SIZE`, `PRIM_ALLOC_THRESHOLD`, `VPC_RAST_STREAM_CNTL`,
"cull before VPC"); (2) finish `VK_EXT_device_generated_commands` so RE Engine's GPU culling stops
feeding the vertex path; (3) async compute on a second queue, "the RADV ACE layout", via
`tu_queue.cc` + `tu_knl_kgsl.cc`; (4) implement `VK_EXT_descriptor_heap`, "Adreno is ready and the common
NIR part is already written". Decided by inspection against the tree and against the binaries this stand
runs, with no build: each item is either already measured, or cannot be reached from this game.

**Method.** `grep` over `../mesa27-src/src/freedreno/`; the queue families of both drivers in
`results/queues-a740.txt` (`scripts/queues-a740.sh`, which also records the kernel nodes and the absence
of `/dev/kgsl-3d0`); the D3D12 layer's own binaries in `results/vkd3d-ext-strings.txt`
(`scripts/vkd3d-ext-strings.py`, a byte search for extension names); the counter table of 40.21 in
`results/games/re4/occupancy-two-frames.txt`.

**Numbers.** (1) *VSC*: the measured frame runs no binning or visibility pass at all - 40.12 has the VSC
at ~0.4 % of the core with the BV banks at 0 primitives/s, and 40.16 that forcing GMEM plus HW binning
takes the frame from 15.3 to 10.2 fps - so there is no stream to overflow; and `num_vsc_pipes = 32` in
all four A7XX device entries, FD740's own included (`freedreno_devices.py:1246`, `:1266`, `:1326`,
`:1348`), so there is no per-generation value to raise. *VPC*: the only VPC-named properties that differ
between the generations are `has_gmem_vpc_attr_buf` with `sysmem_vpc_attr_buf_size = 0x20000` and
`gmem_vpc_attr_buf_size = 0xc000` (`:854-856`), which are forceable through a special case in the force
table (`tu_device.cc:1799-1805`) and were measured twice: 15.2 gives vkmark noise of 0-4 %, and 40.9
gives RE4 "delivers, the driver logs the a750 sizes, moves nothing". `prim_alloc_threshold = 0x7` and
`has_pc_dgen_so_cntl` live in `a7xx_base` (`:751`, `:792`), so gen2 has them today. *PC/VFD registers*:
`PC_MODE_CNTL 0x1f1f`, `PC_DBG_ECO_CNTL 0x20080000`, `A7XX_PC_UNKNOWN_9E24 0x21fc7f00` and
`A7XX_VFD_DBG_ECO_CNTL 0` exist in exactly one table, `a730_raw_magic_regs` (`:885-905`), used by the
three A730 entries (`:1129`, `:1149`, `:1168`) and by no gen2 or gen3 part, and
`grep -rn "PC_MODE_CNTL\|PC_DBG_ECO\|VFD_DBG_ECO\|VPC_CNTL\|RB_VSC_CNTL" src/freedreno/vulkan/` returns
nothing - the driver writes no geometry tuning register, gated or otherwise. (2) *DGC*: defined in
`vk.xml` once, implemented in `src/amd/` (2 files) and `src/intel/` (1) and in `src/freedreno/` (0), and
the layer here knows the name - `lib/wine/vkd3d-proton/x86_64-windows/d3d12core.dll` carries
`VK_EXT_device_generated_commands` once, `VK_EXT_descriptor_buffer` twice,
`VK_EXT_mutable_descriptor_type` twice. (4) *descriptor_heap*: same picture in the tree (amd 4, intel 1,
freedreno 0), but the name occurs zero times in all 12 scanned binaries, including the `d3d12core.dll`
that carries the other three. (3) *queues*: both drivers expose two families with `queueCount = 1` each,
family 0 `GRAPHICS | COMPUTE | TRANSFER | SPARSE_BINDING`, family 1 `SPARSE_BINDING` only
(`results/queues-a740.txt`) - there is no compute-only family for a D3D12 compute queue to land on, and
`/dev/kgsl-3d0` is absent while `/dev/dri/renderD128` and `/dev/dri/card0` are present with driver name
`msm`, so `tu_knl_kgsl.cc` is not code this machine executes.

**Verdict.** Items (3) and (4) cannot reach RE4 on this stand: there is no second queue to hand out and
the shipped D3D12 layer never names `VK_EXT_descriptor_heap`. Item (2) is a real gap that both sides
would meet in - the layer names DGC, Turnip has no implementation - but it is CPU- and CP-side work,
while the limiter of this frame is geometry by the game's own measure: 16.69 M prims/frame at 15.26 fps
against 8.49 M at 26.57 fps (`results/games/re4/shadow-cache-ab.txt`), with `VPC_BUSY` 91.57 % and 85.54 %
and the primitive collector waiting on it 65.46 pp and 52.72 pp
(`results/games/re4/occupancy-two-frames.txt`). Item (1) is the one the 40.24 audit already
answered in general and this entry answers for the vertex path specifically: the gen2 table is not
missing a geometry limit - the values are shared in `a7xx_base` or identical across A7XX, and the single
property that does differ was measured as a zero twice. Nothing here changes the wall of 40.21 or the
queue 26 candidate.

**Does not show.** Whether a second queue would overlap with the graphics queue on this GPU: that is
scheduler and firmware behaviour, and `results/queues-a740.txt` records only what the driver offers an
application. Whether RE4 issues `ExecuteIndirect` at all - the binary scan shows that the layer knows the
DGC name, not that the game uses it. Whether the byte scan sees every name (a name kept only in a
compressed table would be missed); the three names found in `d3d12core.dll` show the method reaches that
file, which is why the fourth name's absence is quoted as a measurement. Nothing about how much CPU time
the frame leaves unused - the geometry dependence above names the limiter, it does not measure the CPU.
And whether RE4's shaders push
varyings the fragment stage never reads through the VPC - the one sub-point of the note with no artifact
either way, kept as open question 24.

## 40.26 On the ship frame the VPC's own RAM is 71 % of its busy time, and switching off the fp16 lowering of varyings moves nothing (chain35, question 24 continued, queue 28 closed)

[Index back to `docs/analysis.md`](../analysis.md)

**Question.** An outside note proposed cutting VPC pressure in two ways: stop sending varyings the
fragment stage never reads, and lower varyings to fp16. Both are about the one counter this repository
already found to dominate the block - `VPC_VPCRAM_FULL_CYCLES`, ~51 % of the VPC's busy time on the
shadow-cache-off frame (40.9) - and both were untested here. Two sub-questions, one measured and one
read: does the volume of attribute data behave like the constraint, and does the driver's mediump-to-fp16
lowering currently reduce that volume in this title? The same entry closes queue 28
(`VK_KHR_ray_tracing_pipeline`), which was the last inspection item on the queue.

**Method.** Three arms, ship stack `4c3cdb210082`, sampler `tools/fdperf/fdperf.cfg-vpc3` (the six-slot
VPC budget on `VPCRAM_FULL`/`WIT_FULL`/`STALL_VPCRAM_POS`/`STALL_LM_ACK`/`LM_REQ_HIT` + `BUSY`), one
second windows, counters over `t_rel` 20-105 s, p25 fps over 95-150 s; `/tmp/opencode/chain35.sh`,
curation in `results/games/re4/vr4-*/` with `meta.txt` per arm, table
`scripts/vpcram-fp16-table.py` -&gt; `results/games/re4/vpcram-fp16.txt`. Arms: `vr4-c0-base`
(`AppShadowCache=0`, the frame 40.9 measured, so its own reproduction control comes free),
`vr4-c0-nofp16` (same frame, `IR3_SHADER_DEBUG=nofp16` - the switch that *disables* the fp16 lowering of
mediump fragment inputs, `ir3_nir.c:1062`, named at `ir3_compiler.c:30`), `vr4-c1-base`
(`AppShadowCache=1`, the ship frame, first `cfg-vpc3` run on it).

**Numbers.** The control holds: `VPC_BUSY` 623.3 Mc/s = 91.67 % against the 623.5 Mc/s = 91.70 % of
40.9's `vpc3base`. On that frame `VPCRAM_FULL` is 324.9 Mc/s = 47.78 % of the core = 52.12 % of busy
(40.9: 317.0 / 46.62 % / 50.84 %), and turning the fp16 lowering off moves it to 322.0 Mc/s = 47.36 % =
51.74 % of busy with `VPC_BUSY` at 91.53 % - inside the spread of identical arms - and p25 fps 15.00
against 15.15. On the ship frame the picture is different in one respect worth naming: `VPC_BUSY` falls
to 566.3 Mc/s = 83.29 % (the Shadow Cache takes 8.4 points off the block, 40.21), while
`VPCRAM_FULL` rises to 403.2 Mc/s = 59.29 % of the core = **71.19 % of busy** - the largest share of a
block's own time this repository has measured - at p25 fps 26.54, inside the ship cluster of
26.53-26.68. `WIT_FULL` stays at 1.3-1.6 % of busy and `STALL_CYCLES_LM_ACK`/`NUM_LM_REQ_HIT` again read
exactly 0.0 in all 114 kept windows.

**Verdict.** The fp16 lever has nothing to bite on in RE4: the flag that switches fp16 varyings off
changes neither the VPC counters nor the frame rate, which is what the translation layer predicts -
RE4's shaders come from DXBC/DXIL, where there is no medium-precision qualifier to turn into
`RelaxedPrecision`, so the lowering at `ir3_nir.c:1062` has no varying to lower. The dead-varying idea
is aimed at the wrong side of the same block: this driver sizes the interpolator setup from what the
fragment stage *reads*, not from what the vertex stage writes - `tu6_emit_vpc_varying_modes()` walks
`ir3_next_varying(fs, i)` over `fs->inputs_count` (`tu_pipeline.cc:744`), takes the mode from
`fs->inputs[i].compmask` (`:683`), and the linkage is built by
`ir3_link_shaders(&linkage, last_shader, fs, true)` (`:802`) - so a VS output no FS input matches does
not get a slot, whatever the pipeline was linked from (GPL is on here: `.EXT_graphics_pipeline_library =
true` and `graphicsPipelineLibraryFastLinking = true`, `tu_device.cc:351`, `:1473`). What 40.26 does
establish is that the saturated thing inside the VPC is its own RAM accepting writes - 71.19 % of busy on
the ship frame, and 40.9 already showed it immune to the attribute-buffer size. The remaining quantity
that could connect that to the vertex path is attribute *width*, which is directly countable
(`VPC_SP_COMPONENTS` over `VFD_TOTAL_VERTICES`, both already in `fdperf.cfg-vpc`), and it is queue 30.
Queue 28 closes on the same day's inspection: `VK_KHR_ray_tracing_pipeline` occurs zero times in
`src/freedreno/`, while `KHR_acceleration_structure`/`KHR_ray_query` are gated on
`has_raytracing = props.has_ray_intersection && (!props.has_sw_fuse || kernel_fuse)`
(`tu_device.cc:214-216`), with `has_ray_intersection` set already for `a7xx_gen2`
(`freedreno_devices.py:825`) and `has_sw_fuse` only for `a7xx_gen3` (`:868`) - the driver's own comment
names our chip ("a device doesn't have a fuse (i.e. a740)", `:209-213`), and the device answers
`VK_KHR_acceleration_structure` rev 13 and `VK_KHR_ray_query` rev 1
(`results/device-features-a740.txt:13`, `:15`). Nothing is withheld from gen2 there: no generation gets
the pipeline extension.

**Does not show.** That `IR3_SHADER_DEBUG=nofp16` was read by the driver: no driver line proves it, only
`meta.txt`'s `# env:` row, so the arm is a measured zero whose delivery is unproven - a synthetic shader
with a real `RelaxedPrecision` varying, disassembled with and without the flag, is the control this
repository does not have. What the `VPCRAM_FULL` counter counts: `a7xx_perfcntrs.xml` gives it a select
and no `<desc>`, so "its own RAM could not take a write" stays a reading of the name, not a quote
(`docs/fdperf-a7xx.md`). Whether that counter is a cause of the wall or an artefact of a block that is
busy anyway - 40.9 says the same thing about its own pair, and 40.21's removal experiment is still the
only causal evidence. And how wide the attribute stream actually is per vertex, which is queue 30.

## 40.27 What one vertex costs is the same on both frames, so the VPC's RAM pressure is a volume problem and not a width problem (queue 30, no run)

[Index back to `docs/analysis.md`](../analysis.md)

**Question.** 40.26 left one vertex-side quantity that could still connect the wall to something a driver
could change. The VPC's own RAM refuses writes for 71.19 % of the block's busy time on the ship frame
(40.26), that share did not move when the attribute-buffer sizes were forced to the a750 values (40.9),
and it did not move when the fp16 lowering of varyings was switched off (40.26). What is left is neither
the buffer nor the encoding but the stream: how much attribute data one vertex brings with it. Queue 30
named the pair for it - `VPC_SP_COMPONENTS` over `VFD_TOTAL_VERTICES` - and both counters are programmed
by `tools/fdperf/fdperf.cfg-vpc`, which has already been run on both of this title's frames, so the
question was answerable from committed dumps without starting the game.

**Method.** No run. `scripts/fdperf-vpc-ratios.py` gained a `width` line (attribute bytes per vertex,
components per vertex, `NUM_VPCRAM_WRITE` per vertex, over `VFD_TOTAL_VERTICES`), and
`scripts/attr-width-table.py` -&gt; `results/games/re4/attribute-width.txt` pastes it with the fps window for
the three arms: `vpc-vpcbase1`, `vpc-vpcbase2` (`AppShadowCache=0`, the 21.11 pair of 40.14) and
`vpc-cacheon` (`AppShadowCache=1`, the ship frame of 40.21). Same ship stack `4c3cdb210082` in all three,
one-second windows, counters over `t_rel` 20-105 s with the core pinned at 680 MHz.

**Numbers.**

| arm | frame | p25 fps | `VFD_TOTAL_VERTICES` | attribute B/vertex | attributes/vertex | `SP_COMPONENTS`/vertex | `NUM_VPCRAM_WRITE`/vertex |
|---|---|---|---|---|---|---|---|
| `vpc-vpcbase1` | Shadow Cache off | 14.19 | 248.0 M/s | 31.81 | 5.02 | 0.89 | 2.62 |
| `vpc-vpcbase2` | Shadow Cache off | 15.25 | 262.0 M/s | 32.07 | 5.08 | 0.89 | 2.62 |
| `vpc-cacheon` | Shadow Cache on | 26.74 | 240.2 M/s | 33.03 | 5.29 | 1.03 | 2.98 |

The two candidate dividers are the same quantity on these windows: `PC_VS_INVOCATIONS` and
`VFD_TOTAL_VERTICES` print 248.0/248.0, 262.0/262.0 and 240.2/240.2 M/s, which is also what the line above
them says from the other side (`VFD_TOTAL_VERTICES / TSE_INPUT_PRIM` = 1.035 and 1.063, the 1.032-1.035 of
the 17.11 runs in journal 38), so it makes no difference which one a per-vertex figure is divided by.

**Verdict.** Per vertex, the two frames are the same workload: the attribute width differs by 3.8 %
between the slowest arm and the fastest (31.81 against 33.03), the attribute count by 5.4 % (5.02 against
5.29), while the frame rate differs by 74 % and the submitted primitive volume by a factor of two
(16.69 M against 8.49 M prims/frame, 40.19). The per-vertex payload is also the same in all eight other
`cfg-vpc` arms of 21.11 - 40.14 tabulates 2.62 writes and 0.89 components per invocation for every flag
combination tried there. So the "make each vertex cheaper in the VPC" family has no measured opening in
this title: the encoding is already fp16-capable and has nothing to lower (40.26), the interpolator setup
is sized from what the fragment stage reads (40.25, `tu_pipeline.cc:744`), and the width itself does not
distinguish a 15 fps frame from a 27 fps one. What the wall depends on is volume, which the game decides.

One caveat belongs to the reading rather than the verdict: `SP_COMPONENTS` per vertex is 0.89 and 1.03,
below one, for a counter whose name says components handed to the fragment stage. `a7xx_perfcntrs.xml`
gives it no `<desc>` (`docs/fdperf-a7xx.md`), so it cannot be a per-vertex count of varyings in the
literal sense, and no byte saving can be computed from it - the same reason 40.14 refused to turn
`PS_BUSY` into a varying claim. The two per-vertex figures used above as *width* are used only as ratios
between frames, where the unit cancels.

**Does not show.** That the two frames run the same shader programs - no shader identity was measured;
40.22 showing the rasterizer-discard shape unchanged across the cache switch is adjacent evidence, not
identity. Whether halving the attribute width would halve `VPCRAM_FULL`: this is an observation that
width does not differ between two frames of different speed, not a manipulation, and a manipulation would
need a driver that packs varyings, which this tree does not have. And what the 31.8-33.0 "bytes per
vertex" is in absolute terms - a ratio of a counter named `..._BYTES` over a vertex count, with no unit
and no per-format breakdown in the XML.

**Corrected 23.11 by journal 40.34, which this paragraph names.** The `SP_COMPONENTS` column of the table
above is withdrawn as a measure of what a vertex carries: `VPC_SP_COMPONENTS` (VPC selector 10) and
`SP_EXPORT_VPC_TRANS` (SP selector 48) are one signal, equal to the precision of 40.32's control pair in
every window of the 33 arms that program both, so the two names describe one count with no unit and 0.89 or
1.03 per vertex is neither components nor transactions-times-four. The verdict above rests on the two
VFD-side columns (31.81 against 33.03 bytes and 5.02 against 5.29 attributes per vertex), which are
untouched; what the varyings weigh per vertex is unmeasured and is queue 34.

## 40.28 The queue-16 builds exist, the build is reproducible, and that is what makes the ship-hash gap a fact (queue 16, builds)

[Index back to `docs/analysis.md`](../analysis.md)

**Question.** Queue 16 wants a driver identical to the ship stack except without patch 0014, and queue
26 wants `has_alias_rt` forceable at runtime; both need a build. The Mesa tree here is uncommitted by
design (`AGENTS.md`), so before trusting any build hash with a statement like "B = A minus 0014", the
mechanism has to be checked: does rebuilding the same tree twice still give the same sha256
(`docs/release.md` checklist item 2)?

**Method.** The shared `../mesa27-src` was not written to: both measurement trees are `cp -a` copies
of it (wrapper `/tmp/opencode/build36.sh`, container build `scripts/build-turnip-mesa27.sh`, `-j2`,
ccache in `/tmp`, ship `build/out` untouched). `../mesa27-src-ab` = copy, exp-24 render-mode rig
removed (`git apply -R`), exp-25 `TU_FORCE_PROPS` hook added, exp-14 inventory rig kept (queue 16's
acceptance is an inventory signature). `../mesa27-src-no0014` = the same, plus exp-26 by hand:
`mutable_views()` no longer feeds the layout predicates - `git apply -R patches/0014` cannot do this,
journal 39.7. A third copy, `../mesa27-src-verify` = shared tree minus both rigs, was built twice into
separate directories as the reproducibility control. Every tree is described by
`scripts/build-tree-stamp.sh` (new: HEAD, sha256 of `git diff`, hook knobs present, .so hash).

**Numbers.** `results/games/re4/0014ab/builds.txt`: verify built twice -> `f80d33ab2077` both times
(`/tmp/opencode/build36-verify.log`, `build36-verify2.log`); A = `88bab928c520` (`build/out-ab`),
B = `7ae5f008caa8` (`build/out-no0014`); `diff -rq` over the two trees names exactly one file,
`tu_formats.cc` - the exp-26 hunk.

**Verdict.** The build is reproducible, so a hash difference is a source difference. Two consequences,
both stronger than they were before this control: (1) `f80d33ab2077` != the ship `4c3cdb210082` means
the shared tree of 23.11, even with both experiment rigs removed, is **not** the source of the ship
stack - the drift 39.7 found in the 0014 text is not an artifact of the rigs (0004, 0005 and 0014
still do not reverse in the rig-free tree), and the exact ship stack cannot be recompiled from this
machine today. The queue-16 A/B is therefore anchored internally, A against B, and the ship `.so`
runs on the bench only as a control arm; (2) any measured difference between A and B belongs to the
single file exp-26 touches, i.e. to 0014's one semantic site.

**Does not show.** Which edit since 20.11 moved the ship hash (the drift was measured, not bisected);
whether A and B differ at runtime at all - that is chain37; and nothing about alias.rt, whose hook is
merely present in both trees and does nothing unless `TU_FORCE_PROPS` names it.
## 40.29 The 0014 A/B reproduces both inventory signatures on dedicated builds, and `has_alias_rt` moves no counter (queues 16 and 26, chain37)

[Index back to `docs/analysis.md`](../analysis.md)

**Question.** Queue 16 accepts patch 0014 by an inventory signature, not by a hash: the pre-0014
inventory has MUTABLE-without-list at 0 MiB tiled (`results/imginv-3variants.txt`, imginv4 row) and
the with-0014 one at 2450.3 MiB (imginv5 row). Do the two dedicated builds of 40.28 reproduce that
pair, and does the queue-26 candidate `has_alias_rt` move any counter on the same frame?

**Method.** `/tmp/opencode/chain37.sh`, four arms, `scripts/run-game.sh` with
`tools/fdperf/fdperf.cfg-vertex`, `HUDLOG=150`, `TIMEOUT=190`, the game's shadow cache as this
install has it. A = `build/out-ab` (`88bab928c520`), B = `build/out-no0014` (`7ae5f008caa8`), both
with `TU_IMG_INV=1`; the ship `.so` (`4c3cdb210082`) runs as a control that cannot show inventory
lines (the rig is not in its tree); the fourth arm is A with `TU_FORCE_PROPS=has_alias_rt`. Arms are
interleaved only by time, one run each. The inventory is read by `scripts/imginv-stats.py`, fps by
`scripts/fps-window.py ... 95 150`, counters by `scripts/arm-counters-table.py`.

**Numbers.** `results/games/re4/0014ab/imginv.txt`: A has 2474 MUTABLE-no-list creates, 4080.8 MiB,
**1450 tiled, 2450.3 MiB (60.0 %)**; B has 2475, 4063.0 MiB, **0 tiled, 0 MiB**. That is the
imginv5 and the imginv4 row to the tenth of a MiB on the tiled figure. `fps.txt`: p25 95-150 s is
A 26.12, B 25.62, ship 26.52, aliart 26.44. `counters.txt`: TSE in 220.38 / 215.37 / 224.20 / 224.37
M/s, VPC busy 85.63 / 84.58 / 85.64 / 85.58 %, PC stall on VPC 57.44 / 56.71 / 57.10 / 57.19 %; the
`TU_FORCE_PROPS: has_alias_rt` line is in the aliart run log, so the name was applied.

**Verdict.** The acceptance pair is reproduced: B is the pre-0014 inventory and A is the with-0014
one, so the one semantic site exp-26 turns off (40.28) is 0014 and nothing else. fps does not
separate the arms: A is 1.95 % above B, but the ship control is 1.5 % above A, i.e. the three sit
inside a band this frame has never resolved (0.6 % identical-arm spread, 40.21) - 0014 stays a
correctness/tiling patch, not a lever. `has_alias_rt` moves nothing: the largest counter difference
against A is 1.8 % on TSE input, VPC busy differs by 0.06 %, and fps by 1.2 %.

**Does not show.** Correctness of any arm - the operator's call for queue 26 was counters only, the
panel is off and the screenshot check is black by construction; whether the gen3 alias-RT pass did
not engage or merely is not on the critical path (counters cannot tell the two apart); whether the
1.95 % between A and B is real; DRAM and TSE-visibility columns, which `cfg-vertex` does not
program (printed as `n/a` in `counters.txt`).

**What the A arm actually carried.** Its 0014 is the one-decision text (`mutable_compat_class()` and
`mutable_views()` inside `tu6_mutable_format_list_forces_linear()`), not the text committed on 19.11
- the drift 39.7 measured, and the reason `git apply -R patches/0014` fails on these trees. The
operator's decision on 23.11: make that text the committed `0014` (same decision, one place instead
of two), with no further equivalence run - journals 33 and 36 already measured it equivalent to the
committed text (598 of 598 probe lines, 784 create signatures), and this run now carries it as the A
arm. Done on 23.11: `patches/0014-*.patch` is that text, and the p14 binary remains the
older text (`docs/release.md`, provenance).

## 40.30 A RE4 session can be made to bin, and it is a trickle of tiles at a sagged clock; the `BV_*` primitive halves are not counts (queue 21, chain38)

[Index back to `docs/analysis.md`](../analysis.md)

**Question.** Queue 21: every 22.11 arm read `VSC_INPUT_TILES` = 0, so the `BV_*` zeros of 40.11 were
never a measurement of a working BV thread - a binning pass had to be produced first. The queue asked
for a stretch where the tile counter is nonzero, then the `cfg-bv` halves read inside it, and fixed the
reading in advance: if during windows with tiles > 0 the `BV_TSE` `TSE_INPUT_PRIM` and `BV_PC`
`PC_IA_PRIMITIVES` stay 0, the BV thread provably never runs primitives; if they rise, journal 40.2's
discard has to be re-asked per thread. 40.12 left one hint about where to look - the only windows that
ever fed tiles were the ones whose `CP_ALWAYS_COUNT` was below the pinned clock.

**Method.** `/tmp/opencode/chain38.sh`, 08:53-09:04 on 23.11, ship stack `4c3cdb210082`, game
Resident Evil 4 Gold Edition (`re4.exe`, D3D12 -> vkd3d-proton 3.1.0, 2560x1440 - `results/games/README.md`),
`tools/fdperf/fdperf.cfg-bv`, `HUDLOG=150`, one run per arm, the game's `local_config.ini` written back
byte-identically after each. Two frames, the flag either on or off: `cb21-c0` / `cb21-c1`
(`AppShadowCache=1`, the 26 fps frame of 40.19/40.21) and `cb21-h0` / `cb21-h1` (`AppShadowCache=0`, the
ship frame of 40.10), with `TU_DEBUG=startup` against `TU_DEBUG=startup,forcecb`; `meta.txt` of each arm
records the setting and counts the delivered `TU_DEBUG=` line (bit 36 = `forcecb`).
`scripts/fdperf-bv-tilesplit.py` (new) cuts the two halves of one dump by window class - tiles > 0
against tiles = 0 - with the core clock per class, which is what 40.12 said to read in the same sample.

**Numbers.** `results/games/re4/cb21-{c0,c1,h0,h1}/fdperf-raw.txt` (cfg `cfg-bv`), read with
`scripts/fdperf-bv-tilesplit.py` over 40 steady windows per arm (`t_rel` 20-105 s of 51-52); the fps column
is `results/games/re4/cb21/fps.txt`, generated with `scripts/fps-window.py` over 95-150 s.

| arm | frame | `forcecb` | windows with tiles > 0 | tiles in them | core clock, those windows | p25 fps 95-150 s |
|---|---|---|---|---|---|---|
| `cb21-c0` | cache on | off | 0 of 40 | - | - | 26.23 |
| `cb21-c1` | cache on | on | 0 of 40 | - | - | 26.53 |
| `cb21-h0` | cache off | off | 0 of 40 | - | - | 15.14 |
| `cb21-h1` | cache off | on | **8 of 40** | 3, 4, 4, 7, 8, 9, 12, 14 | 662-678 MHz (680 elsewhere) | 15.18 |

The eight windows sit at `t_rel` 36.0, 38.1, 40.3, 42.5, 44.8, 46.9, 100.6, 104.8 s. In the `BV_*` half
of `cb21-h1` the primitive counters are nonzero in exactly those eight windows and zero in the other
32, with a ratio that does not change while the tile count runs from 3 to 14: `BV_PC` `PC_IA_PRIMITIVES`
is 2 x tiles and `BV_TSE` `TSE_INPUT_PRIM` is 14 x tiles in every one of them (t=36.0: 7 tiles, 14 and
98; t=46.9: 14 tiles, 28 and 196). In the same half, `BV_TP` `TP_BUSY_CYCLES` is 945 % of one core and
equals the ordinary `TP_BUSY` to four digits - 6,346,065,003 against 6,346,186,088 at t=36.0 - which is
the "not a busy fraction at all" signature 40.8 names in the header of `tools/fdperf/fdperf.cfg-bv`. The
ordinary halves of the same windows are unremarkable: TSE input 247-254 M/s, VPC busy 89.8-91.7 %.

**Verdict.** Three things, in the order the queue asked them.

1. A binning pass is reachable in this title without a build, but narrowly: tiles appear on the
   Shadow-Cache-off frame, only under `forcecb`, in 8 of 40 steady windows, at 3-14 tiles per ~2 s
   window, and only in windows where the core had sagged below the pinned 680 MHz. 40.12's clock hint
   is confirmed from the other side.
2. `forcecb` clears one gate and is not sufficient: the cache-on arm with the flag delivered (the
   `TU_DEBUG=startup,forcecb` line is in its run log) reads 0 tiles in all 40 windows. So
   `cb_disable_reason` keeps its decision on the frame where the flag works as firmly as on 22.11's.
3. The pre-registered trigger does not fire. The BV halves do rise, but a pair whose value is always
   14 x and 2 x the window's own tile counter is not two per-thread primitive counts - it is the tile
   number reaching the readback of selects that are addressed (the label test of the cfg passes: the
   `BV_TSE` line prints `INPUT_PRIM`, not the default `BUSY`) and not counting, and the half still
   carries 40.8's unprogrammed signature. Read at face value the pair is at most 196 primitives in a
   window whose ordinary pass carries 247-254 M/s, i.e. <= 8e-7, so the 71.9 % discard of 40.2 cannot
   move per thread by anything this rig could see. And the frame rate says the same thing without
   counters: 15.14 against 15.18 with the flag on (0.3 %), and 26.23 against 26.53 (1.1 %) in a pair
   where neither arm binned at all - so 1.1 % is the spread of two identical sessions here, and the
   eight trickle windows are inside it.

Queue 21 closes here, and with it the CB direction: 40.12 (no tiles in any 22.11 session), this entry
(tiles only as a trickle, at a sagged clock, worth no fps), and 40.18's ladder (GMEM is slower than
sysmem in both of its forms) leave nothing for a binning patch to win. Two rules come out of it: no
document in this repository may quote a `BV_*` primitive counter as a count of primitives, and no
further `cfg-bv` run is queued - the group answers when it is asked, it does not count per thread, and
answering again needs a kernel-side look at how the BV selects are written, which is not a game run.

**Does not show.** Whether the `BV_*` selects can be programmed at all from userspace on this kernel
(the labels say the section reached the group, the values say the values are not the group's own); what
the `force_render_mode_reason` string holds for the cache-on frame - queue 22's rig is in the tree and
unbuilt, so the reason stays unlogged; whether a longer or different-content session finds more tile
windows than 8 of 40 (the four arms are one session each, and 40.12 shows the tile counter is a
per-session property); and nothing about correctness - the panel is off, so the screenshot is black by
construction and the content check here is counter reproduction between arms.

## 40.31 The traffic half of queue 16's pre-registered reading was already on disk: 2450.3 MiB of linear-to-tiled moves no DRAM volume (queue 16, no run)

[Index back to `docs/analysis.md`](../analysis.md)

**Question.** Queue 16 wrote its reading in advance: "compare ratios inside one sample set, never
levels... The quantities: TP's GB/s and its share of DRAM reads, `UCHE` busy and its arbiter stall, the
TP starve counters, fps", and "if 2450.3 MiB of linear-to-tiled changes neither TP's 81 % share nor its
GB/s measurably, then the largest layout change in this stack is worth no traffic". 40.29 delivered the
inventory signatures and the fps, and printed `n/a` in the DRAM column, which reads as a missing
measurement. The question here is whether a session is needed to fill that column or whether chain37's
dumps already contain it.

**Method.** No run. The four chain37 dumps - `results/games/re4/{0014ab-a,0014ab-b,0014ab-ship,vr5-a-aliart}/fdperf-raw.txt`,
committed with 40.29 - carry the four client read counters `PERF_UCHE_VBIF_READ_BEATS_{TP,SP,VFD,PC}`,
the split journal 38 read. Cut as journal 38 read it: beats x 16 B (the conversion of
`results/games/re4/mesa27-vertex/steady-state.txt`, documented in `scripts/fdperf-vpc-ratios.py`), over
`t_rel` 20-105 s with the core at the pinned clock (median 680 MHz in every arm, 39-40 windows kept of
52, none dropped for wrapping), median per window.

**Numbers.**

| arm | 0014 | windows | DRAM read GB/s | of which TP | TP share |
|---|---|---|---|---|---|
| `0014ab-a` | with | 39 | 14.82 | 12.13 | 81.86 % |
| `0014ab-b` | without | 40 | 14.62 | 12.01 | 82.11 % |
| `0014ab-ship` | with (ship `.so`) | 40 | 15.08 | 12.34 | 81.85 % |
| `vr5-a-aliart` | with + inert prop | 40 | 15.12 | 12.40 | 81.97 % |

Two controls bracket the A/B difference, which is -1.33 %: `a` against `ship`, both with `0014`, differ
by 1.74 %, and `ship` against `aliart`, one build and a property measured inert in 40.29, by 0.27 %. The
absolute levels land on journal 38's baseline (TP 12.0 GB/s of 14.8, 81 % of reads), which is the check
that this cut is the same quantity, read the same way. The rasterizer columns of the same dumps move in
the same direction and by the same amount (`RB_Z_READ` 95.3 against 92.5 M/s, `RB_Z_WRITE` 19.3 against
18.2, `RB_C_WRITE` 17.6 against 17.2, A against B): a session-level drift, not a client-specific effect.

**Verdict.** The first branch queue 16 pre-registered came true. 2450.3 MiB moved out of linear changes
neither the client split (81.86 % against 82.11 % of reads on TP) nor the total read volume by more than
the spread between two sessions of the same build. The largest layout change in this stack is worth no
measured traffic, so ADR-0008 gains a second and much bigger instance than the driconf sweep of 40.23,
layout closes as a lever, and `0014` stays in the release because it is correct and free - which is what
queue 16's own status line already said; what is now measured is the "and the bandwidth behind it" half
of that sentence, and it is a zero. The `n/a` in `results/games/re4/0014ab/counters.txt` is a column
`scripts/arm-counters-table.py` does not map for `cfg-vertex`, not a hole in the data.

**Does not show.** Whether the compressed traffic moved - `fdperf.cfg-vertex` names the UBWC counters in
its header as deliberately left out ("UBWC is still unverified"), and 40.18 already puts RE4's
compressed traffic on depth images, outside the class `0014` touches, so that column belongs to a
different question. Whether the write side moved (the `VBIF_WRITE_BEATS` of `CP` and `UCHE` are not in
this cfg; `cfg-traffic` has them and was never run on these two builds). Anything about the two frames
of 40.30 - the chain37 arms ran the ship settings, `AppShadowCache=1`. And UCHE busy plus the TP starve
counters, the other two quantities queue 16 named: `cfg-vertex` programs the UCHE latency counters but
not `UCHE_BUSY` as a duty cycle, so that part of its reading stays unmeasured - nothing in the verdict
above depends on it, because both candidates for "where a layout change would show" - TP's volume and
TP's share - are measured.

## 40.32 `TSE_INPUT_PRIM` and `PC_IA_PRIMITIVES` are two readings, not one counter twice (queue 18(a), no run)

[Index back to `docs/analysis.md`](../analysis.md)

**Question.** Queue 18(a): in four dumps, `PERF_TSE_INPUT_PRIM` and `PERF_PC_IA_PRIMITIVES` are identical
to the sample (ratio 1.0000), and 40.2 kept both readings of that - "nothing is discarded between the
primitive collector and TSE", or the same counter exposed twice under two names. It asked for one run
with a cfg that samples only one of them and a known-different second one.

**Method.** No run. Compared the two names window by window in the five committed dumps that program
both - the four chain38 arms of 40.30 and `bv-bvbase` - 256 windows, through the same loader the ratio
scripts use (`scripts/fdperf_sections.py`, so the wrapped-window rows are already out).

**Numbers.** 0 of 256 windows print the two names equal. They agree to between 0.000006 % and 0.094 %:
the median window (`cb21-h0`) reads 253,011,436 into TSE against 253,004,969 from the collector, a gap
of 6,467 primitives, 2.6e-5.

**Verdict.** Two exposures of one counter return one register value and cannot differ; these differ in
every window of both cfgs and both frames. So the equality of 40.2 was a near-equality, and its first
reading is the right one: nothing is discarded between the primitive collector and TSE, and the whole
71.9 % discard belongs to TSE itself, which is what the reason breakdown of 40.2 already adds up to.
Queue 18(a) closes, and 40.2's "two readings, not decided" wording should be retired in favour of
"two readings that agree to 1e-5".

**Does not show.** What the residual gap is. Both counters are read across the same fdperf window, so
primitives in flight at the window boundary are the obvious candidate, and nothing here separates that
from a small population the collector counts and TSE does not accept; it is 4 orders below the quantity
it is compared against, which is also why journal 21.5's 1024/262144 residue and this gap are the same
kind of thing and neither owns a verdict.

## 40.33 The vertex-cache hit rate has never been measured: the cfgs carry `PC_VERTEX_HITS` without its denominator, and `tu_pipeline.cc` has no cache or restart state to check (no run)

[Index back to `docs/analysis.md`](../analysis.md)

**Question.** Asked by the operator on 23.11, as a check to be run: "post-transform vertex cache (VFD / PC) -
check in `tu_pipeline.cc` whether the vertex cache size or the `prim_restart`/topology mode gets reset by
something about vkd3d-proton, so that every vertex is recomputed instead of hitting the VPC/PC cache. Was
this checked?" It could not be answered from the documentation in one step, which is the second half of
the question this entry answers: three committed files make statements about a counter named "hits" and
none of them says what it is divided by.

**Method.** Three checks, no run. (1) Driver side, in `../mesa27-src`: `grep -niE
"vertex_cache|vcache|cache_size|restart|max_pc_dest_regs|topology" src/freedreno/vulkan/tu_pipeline.cc`
(5345 lines) and `grep -rn max_pc_dest_regs src/freedreno/vulkan/`. (2) Counter side: a cfg's selector id is
the `value="N"` attribute of `A7XX_PERF_<GROUP>_<name>` in
`../mesa27-src/src/freedreno/registers/adreno/a7xx_perfcntrs.xml`, read there for all 52 `PC_*` declarations
(0 busy, 10 starve-for-index, 17 dead-prim, 18 live-prim, 19 hits, 20 IA vertices, 21 IA primitives, 25 VS
invocations, 28 drawcalls, 39 tag-checked vertices); `desc=` occurs 0 times in that file, so a counter's name
is the whole documentation of it. The declarations are dense, so counting their lines gives the same numbers -
which is how the eight id comments of `tools/fdperf/fdperf.cfg-vpc` were derived, and both ways were checked
against the attribute. Then: which `PC_*`/`VPC_*` names the thirteen cfgs of
`tools/fdperf/` program. (3) Read the quotients that committed dumps already allow, with
`scripts/fdperf_sections.py`, over the three 21.11 `cfg-vpc` arms.

**Numbers.** The median of each counter over the same steady windows, divided;
`results/games/re4/{vpc-vpcbase1,vpc-vpcbase2,vpc-cacheon}/fdperf-raw.txt`:

| arm | `PC_VERTEX_HITS` | `VFD_TOTAL_VERTICES` | `PC_IA_VERTICES` | hits per delivered vertex | hits per IA vertex |
|---|---|---|---|---|---|
| `vpc-vpcbase1` | 463,810,084 | 244,663,537 | 708,641,707 | 1.896 | 0.654 |
| `vpc-vpcbase2` | 498,774,947 | 262,754,551 | 761,554,765 | 1.898 | 0.655 |
| `vpc-cacheon` | 437,511,780 | 240,032,199 | 677,593,461 | 1.823 | 0.646 |

Counter coverage, `grep` over `tools/fdperf/fdperf.cfg*` (thirteen cfgs as checked, fourteen with
`fdperf.cfg-vpc4` written for this entry): `PC_VERTEX_HITS` (id 19) is programmed by nine of the thirteen;
`PC_TAG_CHECKED_VERTICES` (id 39, the vertices whose tags were looked up - the denominator a hit rate needs)
by **none of the thirteen**, and it is absent from every committed dump; `PC_DEAD_PRIM` (17) and
`PC_LIVE_PRIM` (18), the dead/live primitive pair that would show degenerate topology, by **none** either.
Every cfg that carries hits uses all 8 of the PC group's hw slots (ids `{0,2,4,19,20,21,25,28}`), which is
why the partner never came along. On the post-transform side: `VPC_NUM_LM_REQ_HIT` is programmed by
`cfg-vpc2`/`cfg-vpc3` and reads 0 or 2.5 per window in all five dumps that carry it, with no request counter
in the same group to divide by.

**Verdict.** Four things.

1. The driver-side check the question names has nothing to check. `tu_pipeline.cc` contains no vertex-cache
   size, no cache mode, no restart and no topology state (0 matches in 5345 lines), and turnip never reads
   `max_pc_dest_regs` at all. The only related thing the driver writes is
   `PC_CNTL(CHIP, .primitive_restart = primitive_restart)` and `PC_RESTART_INDEX` at
   `tu_cmd_buffer.cc:8703-8725`, where `primitive_restart = primitive_restart_enabled && indexed` comes from
   the game's own dynamic IA state. So there is no driver-side door for "vkd3d-proton resets the vertex
   cache" to walk through: the question is a counter question, not a pipeline-state one.
2. The reuse this repository quotes (2.9:1, journal 38) is `PC_IA_VERTICES / VFD_TOTAL_VERTICES` - the app
   submits 3 vertices per primitive and ~1.03 reach the vertex shader. That is a property of the game's
   meshes and index order, an upper bound on what any cache could save; it is not a cache measurement.
3. The cache's own hit rate has never been measured here. It is hits over tag-checked vertices, ids 19/39,
   and no cfg in this repository or dump on this machine programs 39. Therefore the three places that read
   the hits counter as a reuse figure are corrected by this entry: `tools/fdperf/fdperf.cfg-vpc`'s header
   "PC_VERTEX_HITS (19, here) is what quantifies the reuse directly", and `docs/plan-next-checks.md` item 15's
   "`PC_VERTEX_HITS` 0.65 per IA vertex" and "`PC_VERTEX_HITS` (19) - the direct measure of the 2.9:1 reuse".
   The number is not a rate: the same reading is 1.82-1.90 per delivered vertex or 0.646-0.655 per IA vertex
   depending on which of two dividers is picked, and it exceeds the delivered vertex count in every window -
   a value larger than the number of vertices cannot be "a vertex that hit".
4. What closes the gap is a cfg edit, not a build and not a new idea: `tools/fdperf/fdperf.cfg-vpc4` (written
   with this entry, NOT RUN) is `fdperf.cfg-vpc` with two stall selectors and `PC_IA_PRIMITIVES` traded in the
   PC group for id 39 `PC_TAG_CHECKED_VERTICES`, id 17 `PC_DEAD_PRIM` and id 10 `PC_STARVE_CYCLES_FOR_INDEX`;
   the budget is 8/8 so something had to go, and `cfg-vpc` itself is left alone so the 21.11 arms stay
   reproducible against the header that describes them. Run it in the session queue 10 already owes: that
   gives the hit rate the operator asked about and, for the first time on this rig, a dead-primitive rate.
   Queued as item 31.

**Does not show.** What `PC_VERTEX_HITS` counts: `a7xx_perfcntrs.xml` carries no description for any counter
(0 `desc=` attributes, already noted in 40.7 and 40.11), so its semantics stay a name and only the arithmetic
above is measured. Whether RE4 enables primitive restart or what topologies it submits - no counter in any
committed dump speaks of restart, and there is no vkd3d-proton-side trace in this repository; id 17 is the
first evidence that would exist. Whether the post-transform cache is hit at all: `VPC_NUM_LM_REQ_HIT` reads
essentially zero with no partner in its group, which is the `UCHE_WRITE_REQUESTS_VPC` pattern of 40.15 (a
measured zero whose wiring is undescribed), so it is recorded and not used. Nothing about fps.

**Why the documentation was the obstacle.** The workload-side facts are in journal 38's table, the
counter-side facts were spread over item 15 of the queue and a cfg header comment, and no page said "the
vertex cache question: this part is measured, this part is not measurable with the cfgs that exist". Fixed
by this entry plus queue item 31, open question 25, and a rule line in `docs/fdperf-a7xx.md`.

## 40.34 The VPC spends half a core with its attribute RAM full on both frames, the two export counters are one signal, and the attribute-buffer size is not a knob on this chip (queues 30 and 31, no run)

**Question.** Four readings the 23.11 review asked for, none of which needed a session, plus two
source questions that came out of it. (1) Is the VPC computing or is it stalled - `fdperf.cfg-vertex`
samples `VPC_WORKING_CYCLES` and no entry ever divided it, and the reviewer's "stall UCHE ~0 % therefore
clean compute" inference rests on that division. (2) Does it need the divider that SP and TP get, i.e. is
the block multi-instance. (3) Is `VPC_VPCRAM_FULL_CYCLES` a spill into memory (then a bigger attribute
buffer helps) or a credit stall from below (then it does not) - the fork the reviewer proposed to decide
with `UCHE_WRITE_REQUESTS_VPC`. (4) Do `VPC_SP_COMPONENTS` (VPC selector 10) and `SP_EXPORT_VPC_TRANS`
(SP selector 48) measure two sides of the varyings traffic, as the cfg comments say - a "components per
vertex" of 0.89 is below one, and the reviewer read that as a unit error, a transaction carrying a vec4
where the document counted components. (5) Are `sysmem_vpc_attr_buf_size`/`gmem_vpc_attr_buf_size` being
absent from `a7xx_gen2` a missing value. (6) Does turnip run `nir_opt_varyings` at all, and if so with
which limits.

**Method.** No run, no build. `scripts/fdperf-vpc-state.py` (written for this entry) over every committed
dump, steady windows `t_rel` 20-105 s with the core pinned at >= 676 MHz, medians per counter and ratios of
medians; its output is `results/games/re4/vpc-state.txt` (71 arms). The divider question is answered per
window over all 72 dumps rather than per arm. Source read: `common/fd6_gmem_cache.h`,
`vulkan/tu_cmd_buffer.cc:649-660`, `common/freedreno_devices.py:736-860`, `common/freedreno_dev_info.py`
(the `FD_DEV_FEATURES` path), `vulkan/tu_shader.cc:3878`, `compiler/nir/nir.h:5832`,
`src/amd/vulkan/radv_pipeline_graphics.c:1257`.

**Numbers.** From `results/games/re4/vpc-state.txt`; per-arm columns are filled only where the cfg sampled
the counter.

| quantity | reading | arms |
|---|---|---|
| `VPC_WORKING / VPC_BUSY` | 0.630-0.687 | 23 (cfg-vertex, cfg-bv and the 0014 A/B arms carry it) |
| `VPC_VS_BUSY / VPC_BUSY` | 0.929-0.980 | 39 |
| `VPC_VPCRAM_FULL / VPC_BUSY` | 50.4-52.4 % on the 15 fps frame; 70.9-71.6 % on the 26 fps frame | 15, bimodal with no arm in between |
| `VPC_BUSY / CP_ALWAYS_COUNT` | 0.915-0.918 on the 15 fps frame, 0.856-0.857 on the 26 fps frame | same 15 |
| RAM-full time as a share of a core | 0.476-0.479 against 0.607-0.609 | same 15 |
| `VPC_WIT_FULL / VPC_BUSY` | 1.2-1.7 % | 5 |
| `UCHE_WRITE_REQUESTS_VPC` | 0.000 M/s, every window | 15 arms, both frames |
| `SP_BUSY / CP_ALWAYS_COUNT` | max 12.05 over all windows; medians 10.12-11.39 | 71 |
| max `VPC_BUSY / CP_ALWAYS_COUNT`, all windows of all dumps | 0.9345 (`dbg-file`) | 72 dumps |
| `VPC_SP_COMPONENTS / SP_EXPORT_VPC_TRANS` | 1.00000, 1176 of 1293 windows within 1e-4, largest gap 2.8e-02 in `tse3-cbbase` | 33 arms carry both |
| control `PC_IA_PRIMITIVES / TSE_INPUT_PRIM` | 0.99998, 1972 of 2088 windows within 1e-4, largest gap 2.8e-03 | 40.32's pair |

Per vertex (`VFD_TOTAL_VERTICES`), the shared export reading is 0.887-0.894 on the 15 fps frame,
1.034-1.037 on the 26 fps frame and 0.630 in `sc-forcebin`.

**Verdict.**
* The VPC is not a compute wall and journal 38's `STALL_CYCLES_UCHE` near zero never said it was: the block
  is busy 86-92 % of a core and *working* two thirds of that, and the third has a name - its attribute RAM
  is full for 0.48 of a core on the ship frame and 0.61 of a core on the Shadow-Cache frame. The 26 fps
  frame is the one more often full, at a lower busy share, so fullness does not follow vertex volume.
* No VPC counter needs a divider: the largest `VPC_BUSY / CP_ALWAYS_COUNT` anywhere in the repository is
  0.9345, while SP reaches 12.05 - the /12 the analysis applies to SP and TP is real, and the 85-92 % VPC
  numbers are per-core duty cycles as quoted.
* The spill-vs-credit fork cannot be decided with the counters that exist, and the reviewer's discriminator
  is the dead one: `UCHE_WRITE_REQUESTS_VPC` is 0.000 in every window of all 15 arms that program it, both
  frames - 40.15's zero generalises. What the dumps do give is the correlation instead of the mechanism:
  RAM-full grows on the frame with half the geometry and a flat SP side, which is the shape of "the buffer
  holds vertices because the consumer drains slowly" and not of "supply overruns the buffer". Recorded as a
  reading, not as a mechanism: no counter here measures credits.
* The pair `VPC_SP_COMPONENTS` / `SP_EXPORT_VPC_TRANS` is one signal, so the ×4 unit correction is not
  available and the per-vertex figure means nothing in either unit. Every cfg that programs selector 10 also
  programs selector 48, so this is a same-window comparison, and it is as tight as a control pair known to
  be two different quantities. The consequence for this repository is worse than the reviewer's: 40.14 and
  40.27 quote the two names as two facts and the cfg headers explain them as "components handed to the FS"
  and "the other side of the varyings traffic", and 0.63-1.04 per vertex is below one in a unit nobody has.
  The number of varyings per vertex has therefore never been measured here; queue 34 either gives the pair a
  unit with a known-interface probe or retires both names from the documents. Correction appended to 40.27.
* The attribute-buffer size is not a knob on this chip, which is a structural reason and stronger than the
  null result 15.2 and 40.9 recorded. `freedreno_devices.py` sets both sizes only in `a7xx_gen3` (0x20000 /
  0xc000, `:849-856`); `fd6_gmem_cache.h` labels the field "Vertex attrib cache (a750+)" and reads
  `vpc_attr_buf_size` on a7xx only inside `if (info->props.has_gmem_vpc_attr_buf)` (`:101-107`), the else
  branch never touching `vpc_attr_buf_*`; and `tu_cmd_buffer.cc:649` returns before `VPC_ATTR_BUF_GMEM_SIZE`,
  `_BASE` and `PC_ATTR_BUF_GMEM_SIZE` unless that same prop is set. `FD_DEV_FEATURES` reaches props
  (`freedreno_dev_info.py:275`), not the guard, so a `sysmem_vpc_attr_buf_size` sweep on a740 changes nothing
  by inspection - and the one variant that does reach the hardware, forcing `has_gmem_vpc_attr_buf` (which
  fills in both sizes, `tu_device.cc:1800-1806`), is already a measured zero twice, 50.84 % against 50.82 %
  of busy on the very column above. Absent sizes on gen2 are therefore not a bug: the register pair is not
  emitted on this generation and there is nothing for the number to size.
* `nir_opt_varyings` is not missing from turnip - `tu_shader.cc:3878` calls `nir_opt_varyings_bulk`, as do
  hk, kk and nvk - so the reviewer's exp-18 was a duplicate of existing code and is withdrawn. What is live
  is the opposite direction: those two `UINT32_MAX` arguments are `max_uniform_comps` and `max_ubos`
  (`nir.h:5832`), the varying-to-uniform promotion limits, and the API has no slot cap at all; RADV passes
  `0, 0` to the same parameters (`radv_pipeline_graphics.c:1257`) and so turns promotion off. Against a wall
  that 40.34 finds in the attribute RAM and the pixel side rather than in VPC arithmetic, promotion is a
  plausible cost, not a saving. One line, queued as 32, NOT BUILT.
* The BV control the reviewer asked for - `BV_*` rows at equal `tile_count` between two frames whose geometry
  differs by 2x - cannot be cut from committed dumps. Of the four `cfg-bv` arms, only `cb21-h1` binned at all
  (8 of 40 steady windows, 3-14 tiles, 40.30) and the other three have zero binned windows, so there is no
  tile-count overlap between frames. One session, recorded as a control for 40.30 and not as a measurement:
  queued as 33.

**Does not show.** The unit of any of these names: `a7xx_perfcntrs.xml` carries no `desc=` at all (40.7,
40.11), so "components", "transactions" and "requests" stay names and the equality of 10 and 48 says they
are one signal, not what it is. Whether `VPCRAM_FULL` would respond to a buffer size - untestable on this
generation, see above. Whether the flat SP side is the bottom of a stall: SP busy is the same 0.6 % band in
both frames, so nothing here separates "SP is busy because VPC feeds it" from "SP is busy because 1440p with
4x MSAA is busy". Whether promotion costs anything: no build was made. Nothing new about fps - the arms are
the ones 40.9, 40.14, 40.18 and 40.30 already measured.

## 40.35 The gen2 zeros are not hidden by inheritance, and the chip-variant list does not describe this tree (queue 35, no run)

**Question.** Queue 35 asks whether A740's `sysmem_vpc_attr_buf_size`/`gmem_vpc_attr_buf_size`
of 0 means "no such block in the silicon" or "nobody wrote the props". Before spending a session
on it, two cheaper questions had to be settled. (1) Could the 0 be an artefact of how this file is
read - the prop set once in a base block, applied to A740, and simply not repeated in the FD740
entry (the operator's reading, 23.11)? Inheritance here is real - `sysmem_per_ccu_depth_cache_size`
reaches FD740 from `a7xx_base` and the FD740 entry says nothing about it - so grep near the entry
cannot answer it. (2) The operator also brought a description of a variant with per-chip magic
register lists for chip ids `0x07010000` (A710), `0x43020000` (A720) and `0x43020100` (A722), said
to include hardware-tuned VPC attribute-buffer sizes and to be the only path those chip ids take,
"none of these chip IDs exist in Mesa main". Is that what this tree does?

**Method.** No run, no build. `scripts/props-for-chip.py` imports the props generator's own
catalog (`freedreno_devices.py` through `freedreno_dev_info.py`) and prints, per prop name, every
block that defines it plus the **merged** props of the chip ids in question - the same dict that
gets stringified into `freedreno_devices.h`. It runs in the build container, the only place with
mako, against `scripts/pystub/` (stubs for `mako`, `yaml`, and the meson-generated `a6xx` register
module this checkout lacks); the register proxy has to hand out a distinct value per name, because
a constant 0 makes `A6xxGPUInfo.__init__` abort with "duplicate raw magic reg". Raw output:
`results/props-a7xx-vpc-attr-buf.txt`. The second half was read in the source: the entries at
`freedreno_devices.py:1077`, `:1096`, `:1115` against the FD740 entry at `:1235`, and the
`UCHE_CACHE_WAYS` / `PC_DBG_ECO_CNTL` / `VPC_DBG_ECO_CNTL` lines of `a730_raw_magic_regs` (`:885`),
`a740_raw_magic_regs` (`:930`) and `a710_raw_magic_regs` (`:982`), `a720_raw_magic_regs` (`:1029`).
The upstream half is `curl` of `/-/raw/<ref>/src/freedreno/common/freedreno_devices.py` and
`/-/merge_requests/23217.patch` - the plain merge-request page is Anubis-protected, those two paths
answer, and the commands are in the artifact's header.

**Numbers.** First table: where the three names are defined, and what FD740 ends up with
(`results/props-a7xx-vpc-attr-buf.txt`); second: what the message claimed against this tree.

| prop | blocks that define it | FD740, merged |
|---|---|---|
| `has_gmem_vpc_attr_buf` | `a7xx_gen3` only | unset → 0 |
| `sysmem_vpc_attr_buf_size` | `a7xx_gen3`, `a8xx_gen1`, `a8xx_gen2` = 0x20000 | unset → 0 |
| `gmem_vpc_attr_buf_size` | `a7xx_gen3`, `a8xx_gen1`, `a8xx_gen2` = 0xc000 | unset → 0 |
| `sysmem_per_ccu_depth_cache_size` (control) | `a6xx_base`, `a7xx_base`, `a8xx_gen*` | 0x40000, inherited |
| `gmem_ccu_depth_cache_fraction` (control) | `a6xx_base` 2, `a7xx_base` 3, `a8xx_gen1/2` 0 | 3, inherited |

The flag is on for 15 catalog entries (FD750, Adreno 753, 810, 830/830v1, 829, 840, X2-85, X2-90)
and off for 73, which is every a6xx and every a7xx_gen1/gen2 chip.

| the message | this tree |
|---|---|
| "none of these chip IDs exist in Mesa main" | all three are in the catalog: `0x07010000` FD710 `:1077`, `0x43020000` FD720 `:1096`, `0x43020100` Adreno (TM) 722 `:1115` |
| `fd710_raw_magic_regs`, `fd720_722_magic_regs` | the names here are `a710_raw_magic_regs` and `a720_raw_magic_regs`; the 722 entry takes `a730_raw_magic_regs` |
| A710 num_ccu 3, tile align 32x16 | num_ccu 1, tile align 64x32 |
| A720 num_ccu 3, 64x32 | num_ccu 2, 64x32 |
| A722 num_ccu 4, 64x32 | num_ccu 2, 64x16 |
| A710 has different UCHE cache ways | `UCHE_CACHE_WAYS` 0x00040004 on a710, the same value a740 has; a730 is the one that differs (0x00840004) |
| A710 has a unique `PC_DBG_ECO_CNTL` | 0x20100000 on a710 - identical to a720's; a740 has 0x00100000, a730 0x20080000 |
| all three carry hardware-tuned VPC attribute buffer sizes | all three are `[a7xx_base, a7xx_gen1]`, where neither size is set; and no raw magic list contains `VPC_ATTR_BUF_*` |

A third check, from the same evening ("it seems it was there before and then got removed", pointing at
MR 23217): the same file at five upstream refs plus the enablement series itself, in
`results/upstream-vpc-attr-buf-history.txt`.

| upstream ref | where the name occurs | FD740's props chain |
|---|---|---|
| mesa-24.0.9 | nowhere (0 hits, the name does not exist) | `[a7xx_base, a7xx_740]` |
| mesa-24.2.8 | `a7xx_750` only (3 hits, 882-884) | `[a7xx_base, a7xx_740]`; the `a7xx_740` block is 8 lines, no cache size of any kind |
| mesa-25.0.7 / mesa-25.2.4 | `a7xx_gen3` only (3) | `[a7xx_base, a7xx_gen2]` |
| main | `a7xx_gen3` plus the three `a8xx_vpc_cache_{lg,med,sm}` presets (9, and 6 `vpc_pos_buf_size`) | `[a7xx_base, a7xx_gen2]` |

MR 23217 is the 25-patch a7xx enablement series that created the FD740 entry ("freedreno: Fully define
a730 and a740 device properties", "tu: Basic a7xx support"); the fetched series contains `vpc_attr_buf`
0 times and `ATTR_BUF` 0 times.

**Verdict.**
* The inheritance reading is false for these three names: no block of the a7xx family sets them
  before `a7xx_gen3`, while the two control rows show the same merge producing a real value where a
  base block does name a property. So 0 on A740 is "nothing ever named the property", not "a base
  block names it and the FD740 entry stays silent". That is the end of what source can say; the
  hardware half stays queue 35.
* Nothing was removed. The props appear in 24.2 attached to `a7xx_750` - the chip whose blob-derived
  props they are - and every ref since has kept them in the gen3/a8xx chains; 24.0.9 does not know the
  name at all, and the series that wrote the FD740 entry never mentions an attribute buffer. So
  "gen2 has 0 because someone deleted it" has no candidate: across the five refs, A740's chain has
  never been declared. What has grown since is the mechanism around it - main carries per-a8xx presets
  for the attr, pos and bv_pos sizes - i.e. the tuning is being done for a8xx and not for gen2.
* The variant description is not this Mesa - three chip ids that are in the catalog, two reg-list
  names that do not exist here, and three per-chip numbers that differ. Either it is another tree
  (a vendor fork) or a mixture of remembered values. Either way it cannot change what the driver
  writes on A740: the attribute-buffer registers appear only in the CS path behind
  `has_gmem_vpc_attr_buf` (`tu_cmd_buffer.cc:645-670`) and in no regtable, so a per-chip magic-reg
  variant leaves the question exactly where queue 35 has it. If a fork with those `num_ccu` and
  `tile_align` values is ever reachable, the interesting diff is those two fields - they move bin
  geometry - and not VPC.
* Nothing in 40.34's row 22 needs correcting: it already said the value is "never consulted", which
  this confirms at a different level (definition, not consumption).

**Does not show.** Any hardware behaviour - no counter, no session, no build. Whether forcing the
prop on gen2 would buy anything: 40.9 is still the only evidence and it says only "no fault, no
counter moved". The props printed here are those of `../mesa27-src`, the hand-patched tree the ship
stack is built from; the chip-id and history rows are checked against files fetched from upstream
(`/-/raw/<ref>`, in the artifact), so "not in Mesa main" is refuted for main and not just for this
tree. What was not read is the commits - the clone is shallow, no blame API - so a prop set and
removed *between* two of the five refs would be invisible here; the only window where that could hide
is 24.0.9 to 24.2.8, when the name did not exist yet. And no register value in the props output is
real: the `a6xx` module is stubbed, which is why this entry quotes only props and the literal `0x…`
values typed in the device file.
