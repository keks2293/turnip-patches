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

Open: fps A/B for mode 7 (`0013`) was never run; the expectation, given a latency bound,
is small, and the correctness case for `0013` does not depend on it.

Open, and narrower than "find a lever": three of Turnip's own driconf perf options change
the command stream, were never enabled for this device, and were never asked of it - the
props search of journal 15 could not see them, because they are not device properties.
They are listed with what each one costs in queue 12, and journal 34 says which fourth one
is unreachable on a740 without a build. No fps has been taken for any of them: all three
act in a renderpass, and the rig has none.

Open in the same surface but a different kind - the report rather than the command stream:
what the game does when the driver tells it there is less memory than the heap it reports
today. The report is measured (journal 34.4); the behaviour is queue 13. This is the only
unasked driver-side question here that points at the bound in ADR-0008 instead of around it.

Decisions: ADR-0008, ADR-0001, ADR-0004. Artifacts: `docs/fdperf-a7xx.md`,
`results/fdperf-mesa27*/steady-state.txt`, `results/fps-*.csv`,
`results/test-perfprops-rig.log`, `tools/fdperf/fdperf-windowed-delta.patch`.
