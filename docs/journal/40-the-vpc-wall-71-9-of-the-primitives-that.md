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
71.9 %, the VSC at ~0.4 % of the core and the `BV_*` copies of VPC/TSE/LRZ at 0.02-0.08 %), and the VPC
attribute buffer (`TU_FORCE_PROPS=has_gmem_vpc_attr_buf` delivers - the driver logs the a750 sizes - and
moves nothing, 40.9). What stays open is the wall itself: `VPC_BUSY` 91 %, of whose time
`VPC_VPCRAM_FULL_CYCLES` accounts for ~51 % - the largest single named component measured so far.

## 40.1 What was run

| run | driver state | sampler cfg | dump (committed) |
|---|---|---|---|
| `tse1` | ship stack `4c3cdb210082`, no env | `tools/fdperf/fdperf.cfg-tse` | `results/fdperf-tse-tse1/fdperf-raw.txt` |
| `tse2` | ship stack, no env | `tools/fdperf/fdperf.cfg-tse2` | `results/fdperf-tse2-tse2/fdperf-raw.txt` |
| `algo-prefer_gmem` | + `TU_AUTOTUNE_ALGO=prefer_gmem` | `fdperf.cfg-tse` | `results/fdperf-tse-algo-prefer-gmem/fdperf-raw.txt` |
| `algo-bandwidth` | + `TU_AUTOTUNE_ALGO=bandwidth` | `fdperf.cfg-tse` | `results/fdperf-tse-algo-bandwidth/fdperf-raw.txt` |
| `forcecb` | + `TU_DEBUG=forcecb` | `fdperf.cfg-tse` | `results/fdperf-tse-forcecb/fdperf-raw.txt` |
| `cbbase`, `cbforce` | none, and + `TU_DEBUG=forcecb` | `fdperf.cfg-tse3` | `results/fdperf-tse3-cbbase/`, `results/fdperf-tse3-cbforce/` |
| `vpc3base`, `attrbuf` | none, and + `TU_FORCE_PROPS=has_gmem_vpc_attr_buf` | `fdperf.cfg-vpc3` | `results/fdperf-vpc3-vpc3base/`, `results/fdperf-vpc3-attrbuf/` |

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
the 79.6 % figure in `results/fdperf-mesa27/steady-state.txt` (17.11, a different cfg and a different
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

What it does answer, from the committed 17.11 runs (`results/fdperf-mesa27/fdperf-raw.txt`,
`results/fdperf-mesa27-vertex/fdperf-raw.txt`, windows >= 35 s) and from `tse1`/`tse2`: `VSC_BUSY` is
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
`results/game-patched-algopg.log` and `results/game-patched-algobogus.log`:

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
override does happen - verbatim, from `results/game-patched-fl111w.log` with `VKD3D_DEBUG=warn`:

```
warn:vkd3d-proton:d3d12_device_caps_override: Overriding feature level: 0xb100.
```

and the negative control, `results/game-patched-flbogusw.log`:

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
(`results/game-patched-dx11dx11.log`, `…-dx11forceDX11.log`, `…-d3doff.log`).

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
   `results/fps-forcecb.csv`) had no fps table. The runner now takes the newest non-`_summary` CSV. The
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
read 0-21,728 into the number quoted above. The same class of defect was already written up in
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
(`scripts/fdperf-vpc-ratios.py`, `results/fdperf-vpc-vpcbase1/fdperf-raw.txt`). What is *not* established
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

Delivery is proved from the game log, 9 lines each in `results/raw/game-patched-attrbuf.log`, 0 in the
control:

```
TU: info: TU_FORCE_PROPS: has_gmem_vpc_attr_buf
TU: info: TU_FORCE_PROPS: vpc_attr_buf_size sysmem=0x20000 gmem=0xc000
```

The numbers (`scripts/fdperf-vpcram-ratios.py results/fdperf-vpc3-*/fdperf-raw.txt 20 105`, 40 and 39
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
* `VPC_STALL_CYCLES_LM_ACK` and `VPC_NUM_LM_REQ_HIT` read exactly 0 in both arms of 40.9, so the LM hit
  rate is `NOT MEASURED`, not 0 %.
* The `vpc3base`/`attrbuf` pair is its own content cluster on p25 (14.71/14.73 against the day's
  15.15-15.24), and the `cbbase`/`cbforce` pair is its own again on the counter side (VPC busy 68.9 % and
  91.6 %). Within-pair comparisons in this entry are sound; cross-pair absolute values are not.
