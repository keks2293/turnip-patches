# 38. The two 17.11 fdperf runs already answer most of the vertex/VPC question (21.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md).

**Question.** The vertex path was proposed as the next place to look, with two specific claims: (a) ir3 may leave work in the *binning* vertex shader that does not affect `gl_Position`, so VFD and VPC pay for every mesh twice; (b) excess or unpacked varyings may be what saturates the VPC (91.1 % busy, PC waiting on it 63 % of the window), and the fix would be varying packing. Both were framed as needing a new game run with `fdperf.cfg-vertex`. Before spending a session: the two committed runs of 17.11 already carried `VPC_WORKING_CYCLES`, `VPC_VS_BUSY_CYCLES`,
`VPC_VS_WORKING_CYCLES` and `VPC_NUM_ATTR_REQ_LM` - the VPC group is 6 counters on a7xx and both cfgs filled it - and the raw dumps of both are in git.

**Method.** Re-parse the committed dumps with the repository's own parser, so the sample/window semantics are the analyzer's, not a new one:

```python
import importlib.util
spec = importlib.util.spec_from_file_location("an", "scripts/fdperf-analyze.py")
an = importlib.util.module_from_spec(spec); spec.loader.exec_module(an)
samples, window = an.parse("results/games/re4/mesa27/fdperf-raw.txt")   # or -vertex/
t0 = samples[0]["t"]
sel = [s["v"] for s in samples
       if s["v"].get("PERF_CP_ALWAYS_COUNT", 0) / window > 5e8 and s["t"] - t0 >= 35]
# then mean-per-counter of PERF_VPC_{BUSY,WORKING,VS_BUSY,VS_WORKING,STALL_CYCLES_UCHE,
# NUM_ATTR_REQ_LM}, PERF_VFD_TOTAL_VERTICES, PERF_PC_VS_INVOCATIONS, PERF_PC_IA_VERTICES,
# PERF_TSE_INPUT_PRIM; busy% = cycles / (680e6 * window)
```

`scripts/fdperf-analyze.py` is extended in the same commit so these counters are printed as
per-second rows instead of being visible only in the dump (`VPC_WORK`, `VPC_VS_BUSY`,
`VPC_PS_BUSY`, `VPC_SP_COMP`, `VPC_VPCRAM_WR`, `VPC_LM_WAIT`, `VPC_ATTR_LM`, `VERT_HITS`,
`PRIM_IA`, `SP_VPC_TRANS`, `UCHE_WR_REQ_SP`, `UCHE_WR_REQ_VPC`); a counter absent from a dump is
an empty cell, never a 0, which is the rule already documented in that script. The new
counters were checked against the committed dump of 17.11 for regression: same 46 rows, no
duplicate columns, `VPC_PS_BUSY_PER_S` empty there because that cfg line never existed.

**Which windows.** The predicate written in the header of `results/games/re4/mesa27/steady-state.txt`
(`CP_ALWAYS_COUNT > 5e8`, `t_rel >= 35`) selects 35 of 46 windows in the main run and 34 in the
vertex run, and gives VPC busy 88.8 % / 90.5 % against the recorded 91.1 % / 90.5 % - i.e. the
recorded "33 windows" filter is not exactly recoverable from that header. Absolute busy % is
therefore *not* re-derived here; every number used below is a **ratio inside one sample set**, and
those are stable: tightening the selection to the printed span (35-106 s, 36-106 s; 19 and 18
windows) moves each ratio by less than 1 % of its own value.

## 38.1 What the committed dumps already say

| quantity | main cfg (17.11 16:01) | cfg-vertex (17.11 18:01) | reading |
|---|---|---|---|
| `VPC_STALL_CYCLES_UCHE / VPC_BUSY` | 0.00 % | 0.00 % | the VPC is not waiting on L2; the recorded "stall UCHE ~0 % (чистое вычисление)" holds |
| `VPC_WORKING / VPC_BUSY` | 66.9 % | 69.3 % | about a third of "busy" is not "working" |
| `VPC_VS_BUSY / VPC_BUSY` | 92.8-93.5 % | 96.0-96.4 % | nearly all VPC busy time is on the VS side |
| VFD vertices / TSE `INPUT_PRIM` | 1.034-1.035 | 1.032-1.034 | ~1.03 vertices fetched per input primitive |
| `PC_IA_VERTICES` / VFD vertices | 2.900 | 2.903-2.907 | the app submits 3 vertices per primitive; the vertex path delivers ~1.03 |
| `PC_VS_INVOCATIONS` / VFD vertices | 1.000 | 1.000 | one invocation per fetched vertex (no instancing, no tessellation amplification) |
| `VPC_NUM_ATTR_REQ_LM` / VFD vertices | 0.498-0.503 | 0.497-0.502 | ~1 LM attribute request per 2 vertices |
| VFD decoded bytes per vertex (recorded in both artifacts) | 32.0 B = 5.00 attr x 6.3 B | 31.7 B = 5.00 attr x 6.3 B | the game's vertex declaration is ~5 attributes |

Four things follow, all of them for or against the two claims:

1. **"VFD re-fetches every triangle" is not what the counters show.** `PC_IA_VERTICES` says 785 M
   vertices/s and the fetcher delivers 271 M/s: the 3:1 unroll of primitives into vertices is
   already collapsed to ~1.03 per primitive, i.e. reuse of about 2.9:1. What is *not* measured in
   either run is `PERF_PC_VERTEX_HITS` (selector 19), which is the direct quantity behind that
   reuse. Claim (b) therefore cannot lean on vertex volume per primitive: the fetch side is at
   ~1 vertex per primitive with 5 attributes.
2. **The LM counter cannot be read as "interpolators per vertex".** `NUM_ATTR_REQ_LM` is ~0.5 per
   vertex while `VFD_NUM_ATTRIBUTES`/`DECODED_ATTRIBUTE_BYTES` say ~5 attributes per vertex, so the
   counter counts something coarser than one request per attribute per vertex. The XML is not help:
   `src/freedreno/registers/adreno/a7xx_perfcntrs.xml` declares counters as bare `<value name=...>`
   and contains no `<desc>` element at all (count 0), so no counter in this file carries a
   definition. The honest consequence is that the varying question must be asked with counters
   whose names are quantities - `VPC_SP_COMPONENTS` (10), `VPC_NUM_VPCRAM_WRITE` (25),
   `VPC_LM_FULL_WAIT_FOR_INTP_END` (24) - not by interpreting LM requests. None of the three has
   ever been measured here.
3. **The VS/PS split is one-sided so far.** `VPC_VS_BUSY` is 93-96 % of `VPC_BUSY`, but
   `VPC_PS_BUSY` (17) was in neither cfg, and nothing in the tree says the two partition `BUSY`.
   So "the varying/interpolate side is idle" is *not* supported: it is unmeasured. That single
   counter is what turns claim (b) from an opinion into a measurement, and it is the reason
   `tools/fdperf/fdperf.cfg-vpc` exists (see `docs/artifacts.md`).
4. **The 30-point BUSY/WORKING gap is a question, not a finding.** `WORKING` has no definition in
   the repository, so a lower `WORKING/BUSY` may mean idling inside a busy window or a different
   counting domain. Recorded so nobody quotes it as utilisation.

## 38.2 The binning half is closed by the compiler source, not by counters

Claim (a) is about what the binning variant of the vertex shader computes, and the tree answers it
directly. `ir3_nir.c` deletes, in the binning variant, every output the binner does not need:

```c
static bool
output_slot_used_for_binning(gl_varying_slot slot)
{
   return slot == VARYING_SLOT_POS || slot == VARYING_SLOT_PSIZ ||
          slot == VARYING_SLOT_CLIP_DIST0 || slot == VARYING_SLOT_CLIP_DIST1 ||
          slot == VARYING_SLOT_VIEWPORT || slot == VARYING_SLOT_LAYER;
}
```
(`src/freedreno/ir3/ir3_nir.c:1204-1211`, used by `remove_nonbinning_output()` at 1212-1226 and
applied by `lower_binning()` at 1228-1233 from the `if (so->binning_pass)` block, which re-runs
`nir_shader_gather_info()` afterwards, `ir3_nir.c:1589-1597`).

So the binning VS does **not** export - and after DCE does not compute - the FS varyings: the half
of claim (a) that concerns varyings is already done upstream. What the binning pass *does* keep is
the attribute loads, deliberately:

```c
      /* for a6xx+, binning and draw pass VS use same VBO state, so we
       * need to make sure not to remove any inputs that are used by
       * the nonbinning VS.
       */
      if (ctx->compiler->gen >= 6 && so->binning_pass &&
          so->type == MESA_SHADER_VERTEX) {
         ...
            /* be sure to keep inputs, even if only used in VS */
            if (so->nonbinning->inputs[n].compmask & (1 << c))
               array_insert(in->block, in->block->keeps, in);
```
(`src/freedreno/ir3/ir3_compiler_nir.c:6007-6030`)

- that is, the residue of double vertex work is fetch-side (VBO/attribute state shared with the
  draw-pass VS), not varying math, which is the opposite half from the one claim (a) names.

**And no counter here can separate the two passes.** There is no a7xx perf counter whose name
mentions binning - `grep -o 'A7XX_PERF_[A-Z0-9_]*BINN[A-Z0-9_]*' src/freedreno/registers/adreno/*.xml`
returns nothing - so `PC_VS_INVOCATIONS` and `VFD_TOTAL_VERTICES` count whichever passes the
hardware ran, and their 1.000 ratio must not be read as "the VS runs once per vertex across the
frame". The only per-pass mechanism in the tree is the binning-pass timestamp pair described in
`tu_autotune.cc:429-432` ("Binning pass timestamps, only written for GMEM with HW binning... Added
to (ts_end - ts_start) to get the true total GMEM cost"), which is driver-side tuning input and is
not wired into fdperf.

## 38.3 One perf claim in the same proposal is contradicted by a committed artifact

The proposal also expected the 64-bit no-list UBWC grant (journal 37) to reduce TP -> UCHE misses and
so relieve the L2 arbiter. The committed per-client split says this cannot be where the mass is:
`results/games/re4/mesa27-vertex/steady-state.txt` measures DRAM reads per client as TP 12.0 GB/s
(81 %), VFD 2.3 (16 %), PC 0.4 (3 %), **SP 0.05 GB/s (0.3 %)**. Journal 37 established that
`R64_*` has no texture entry and its only reader is a storage image, i.e. an SP-side client, so a
grant in that class addresses the client that is 0.3 % of reads, not the 81 %. Journal 37 said the
fps value of the class was unmeasured; this narrows the sentence: on the measured client split there
is no room for it in this workload. Per-client *write* beats were never measured (only
`UCHE_VBIF_READ_BEATS_*`), which is why the new cfg carries `UCHE_WRITE_REQUESTS_SP` (15) and
`UCHE_WRITE_REQUESTS_VPC` (16).

## 38.4 What this does not show

* Absolute busy % is not re-derived (see "Which windows"); only ratios within one sample set are used.
* The two runs are different game content (13.7-15.7 fps against mean 23.5, recorded in the two
  artifacts), so their agreement is about structure, not about levels.
* Nothing measured here says whether the game's varyings are excessive: `SP_COMPONENTS`,
  `NUM_VPCRAM_WRITE` and `LM_FULL_WAIT_FOR_INTP_END` have never been run, and `PS_BUSY` has not
  either. That is `tools/fdperf/fdperf.cfg-vpc` plus a game session - queue 15.
* Nothing here concerns DX11/DXVK: no DX11 run of this game exists on this machine (journal 11.2
  records the one attempt, which failed because `local_config.ini` is an output key). Queue 14.
* Semantics of `WORKING` and of `NUM_ATTR_REQ_LM` are not defined anywhere in the repository; the
  statements above are about magnitudes and internal consistency, not about hardware definitions.
