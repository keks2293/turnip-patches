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
