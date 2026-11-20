# Direction: RE4 frame rate

**State: closed - no driver-side lever (ADR-0008).** The direction did not die, it
changed subject: what is left is memory shape, which lives in
`streams/mutable-lazy-deposition.md`.

Believed, with the evidence:

- the game is bound by L2 demand and latency, not by geometry or by driver choices:
  UCHE 90 % busy with 39 % arbitration, ~220 ns UCHE->VBIF, DRAM ~30 % of peak with
  texture reads at 81 % of it - `docs/fdperf-a7xx.md`, `analysis` 13-17;
- stock and patched drivers give the same ~13-15 fps; softfloat, FL 11_1, GMEM,
  resolution, shadows, blur, governor, `TU_FORCE_PROPS`, autotune and preempt were each
  measured and moved nothing (`analysis` 13-15);
- the numbers people compare are often artefacts: the environment classes are
  `analysis` 29 and `streams/measurement-tooling.md`;
- "UBWC would halve the traffic" is not confirmed for this workload: the measured UBWC
  share moves by 0.2 points between a 0014 stack and the crude prop, and the classes the
  prop adds are ones where tiling may be harmful (`analysis` 27, ADR-0001).

Open: fps A/B for mode 7 (`0013`) was never run; the expectation, given a latency bound,
is small, and the correctness case for `0013` does not depend on it.

Decisions: ADR-0008, ADR-0001, ADR-0004. Artifacts: `docs/fdperf-a7xx.md`,
`results/fdperf-mesa27*/steady-state.txt`, `results/fps-*.csv`,
`tools/fdperf/fdperf-windowed-delta.patch`.
