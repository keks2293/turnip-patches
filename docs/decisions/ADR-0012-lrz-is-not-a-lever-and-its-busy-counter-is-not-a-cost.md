# ADR-0012: LRZ is not an RE4 lever, and `LRZ_BUSY`-style counters are not a cost meter

Date: 2026-11-23 (measured 22-23.11)
Status: accepted

## Context

`PERF_LRZ_BUSY_CYCLES` reads 74.8 % of the core clock on this game's cached-shadow frame and
`PERF_RAS_STALL_CYCLES_LRZ` 28.4 %, which looks like a unit worth arguing about, and the operator asked
whether turning LRZ off - or taking away its fast clear - wins anything. Three switches reach LRZ
without a build: the driconf `tu_disable_conservative_lrz`, `TU_DEBUG=nolrz` (device-level,
`tu_device.cc:3388`) and `TU_DEBUG=nolrzfc` (keeps LRZ, drops the flag-RAM fast clear,
`tu_lrz.cc:291-292`). LRZ fast clear is already enabled for this chip (`enable_lrz_fast_clear` in
`a7xx_base`), so the only measurable direction is the negative one.

## Decision

Close LRZ as a performance direction for this game, and stop quoting the LRZ cycle counters as a cost.
If LRZ is ever reopened, it needs a workload where the kill counter moves between arms, not another RE4
session.

## Consequences

- no driver change, no driconf change, no shipped knob moves: LRZ off is 26.63 and 26.68 p25 against a
  same-configuration cluster of 26.53-26.67, and the fast-clear pair is +0.11 % DRAM write and +0.20 %
  p25 with the sampler that can see writes at all;
- the reason the question looked open is withdrawn: `LRZ_BUSY`, `RAS_STALL_CYCLES_LRZ` and
  `RB_STARVE_CYCLES_LRZ_TILE` are unchanged in arms where the kill counter is demonstrably 0, so they
  are not a meter for depth rejection. Nothing in this repository may quote them as "what LRZ costs";
  open question 22 owns what it would take to learn what they are;
- what LRZ does on this title is small and counted: 0.51-0.56 % of the frame's input primitives, while
  36.5 % of them produce no pixel for reasons downstream of it;
- the method consequence is general: a `TU_DEBUG` arm is quoted with the mask the driver printed, and
  with a counter that must respond, because an unknown `TU_DEBUG` name is skipped silently (one chain
  was spent on `nolz`/`nolzfc`, which do not exist; `TU_FORCE_PROPS` at least warns).

## Evidence

journal 40.23; `results/games/re4/lrz-killed.txt` (regenerate `scripts/lrz-table.py`), raw dumps
`results/games/re4/{lrz-*,tr-lrzfc-*}/`, delivery `results/lrz-drirc-delivery.log`; fast clear's lack of
a generation gate is journal 40.24.
