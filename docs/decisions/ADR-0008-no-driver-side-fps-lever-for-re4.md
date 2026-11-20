# ADR-0008: no driver-side change raises RE4 fps on this device

Date: 2026-11-20 (recorded; measured 30.09-17.11)
Status: accepted

## Context

Stock and patched drivers give the same ~13-15 fps, so the search was for a lever.
fdperf on the steady state says why none was found: UCHE 90 % busy (39 % of it
arbitration), latency UCHE->VBIF ~220 ns, DRAM 15.1 GB/s (~30 % of peak), texture reads
12.0 GB/s (81 % of DRAM reads), vertices 8.5 GB/s of L2 demand but only 2.3 GB/s of
DRAM.

## Decision

Stop looking for an fps lever inside the driver for this game. Reduce bytes instead:
UBWC and tiling of texture traffic, or MSAA/resolution - the latter changes the numbers,
not the nature of the bound.

## Consequences

- the following were each measured and gave nothing: softfloat, FL 11_1, GMEM size,
  resolution, shadows, blur, CPU governor, `TU_FORCE_PROPS`, autotune, preempt settings;
- governor comparisons are noise unless pinned; windowed fdperf is the only honest way to
  read counters here (`tools/fdperf/fdperf-windowed-delta.patch`);
- the remaining work is memory-shape work: `docs/streams/mutable-lazy-deposition.md`.

## Evidence

journal 13-17; `docs/fdperf-a7xx.md` (steady state, vertex run,
conclusion); `results/fdperf-mesa27*/steady-state.txt`, `results/fps-gov-*.csv`,
`results/fps-ctrl100{,b}.csv`.
