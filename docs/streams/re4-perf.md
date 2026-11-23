# Direction: RE4 frame rate

**State: closed - no driver-side lever (ADR-0008).** The direction did not die, it
changed subject: what is left is memory shape, which lives in
`streams/mutable-lazy-deposition.md`.

Believed, with the evidence:

- the game is bound by L2 demand and latency, not by geometry or by driver choices:
  UCHE 90 % busy with 39 % arbitration, ~220 ns UCHE->VBIF, DRAM ~30 % of peak with
  texture reads at 81 % of it - `docs/fdperf-a7xx.md`, journal 13-17;
- stock and patched drivers give the same ~13-15 fps; softfloat, FL 11_1, GMEM,
  resolution, shadows, blur, governor, `TU_FORCE_PROPS`, autotune and preempt were each
  measured and moved nothing (journal 13-15);
- the numbers people compare are often artefacts: the environment classes are
  journal 29 and `streams/measurement-tooling.md`;
- "UBWC would halve the traffic" is not confirmed for this workload: the measured UBWC
  share moves by 0.2 points between a 0014 stack and the crude prop, and the classes the
  prop adds are ones where tiling may be harmful (journal 27, ADR-0001).

Open, and smaller than a lever: three 23.11 readings are in the queue, not here - the last
driver change standing in the vertex tract (the varying-to-uniform promotion limits, queue 32),
the control journal 40.30 needs for its `BV_*` verdict (queue 33), and a unit for the two export
counters now that they are known to be one signal (queue 34). What moves those from curiosity to
queue line is journal 40.34: the VPC is not computing, it is holding its own attribute RAM full,
so promotion is worth asking about as a cost and not as a saving, and no attribute-buffer size on
this generation is programmable to try the other way.

Open: fps A/B for mode 7 (`0013`) was never run; the expectation, given a latency bound,
is small, and the correctness case for `0013` does not depend on it.

Open, and narrower than "find a lever": two of Turnip's own driconf perf options change
the command stream, were never enabled for this device, and were never asked of it - the
props search of journal 15 could not see them, because they are not device properties.
They are listed with what each one costs in queue 12, and journal 34 says which fourth one
is unreachable on a740 without a build. No fps has been taken for either: both act in a
renderpass, and the rig has none. Journal 35 removed the third from that list before it was
run: the FDM option needs an image with the density-map usage bit, and the game's
inventories contain none, so in the inventoried scenes it cannot fire at all. What is left
is concurrent binning and conservative LRZ, plus queue 13's report-side question below.

Closed, and worth knowing it is closed: the shading-rate (VRS) path. Journal 35 measures
that this stack declares 22 `R8_UINT` shading-rate images (12.0 MiB, tiled, no UBWC), that
the extension is exposed for every a7xx, and that the driver's only involvement is four
register groups and a cache invalidate per subpass - there is no driver-side knob, so no
A/B, and the rates belong to the application. What is not measured is whether any of those
images is ever attached; the check is one driver log line and a game run, blocked on memory
with the rig.

Open in the same surface but a different kind - the report rather than the command stream:
what the game does when the driver tells it there is less memory than the heap it reports
today. The report is measured (journal 34.4); the behaviour is queue 13. This is the only
unasked driver-side question here that points at the bound in ADR-0008 instead of around it.

Decisions: ADR-0008, ADR-0001, ADR-0004. Artifacts: `docs/fdperf-a7xx.md`,
`results/games/re4/mesa27*/steady-state.txt`, `results/games/re4/fps-*.csv`,
`results/test-perfprops-rig.log`, `tools/fdperf/fdperf-windowed-delta.patch`.
