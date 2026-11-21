#!/usr/bin/env python3
"""Steady-window table for the VPC's own memory system (tools/fdperf/fdperf.cfg-vpc3).

Why a separate script and not fdperf-vpc-ratios.py: the VPC group's hardware budget is 6
(docs/fdperf-a7xx.md, "hw counter budgets"), and cfg-vpc spends those six slots on one reading of
the block (VS_BUSY/PS_BUSY/SP_COMPONENTS/NUM_VPCRAM_WRITE/LM_FULL_WAIT) while cfg-vpc3 spends them
on the other (VPCRAM_FULL, WIT_FULL, STALL_CYCLES_VPCRAM_POS, STALL_CYCLES_LM_ACK,
NUM_LM_REQ_HIT, plus BUSY as counter0). One dump therefore never contains both sets, and a script
that prints one set cannot be pointed at the other.  Like scripts/fdperf-tse-ratios.py, this one
prints a counter it cannot see as `-` instead of 0 or a crash.

What each line is.  Busy percentages are against the core frequency the run was pinned to (680 MHz
here).  The stall counters are divided by VPC_BUSY_CYCLES, which is what "how much of the block's
time went to this wait" means when the block is nearly saturated; the same-numbering caveat from
docs/fdperf-a7xx.md applies - counters of different groups counted in the same window share their
group's clocking, so every ratio printed here is inside the VPC group except where a line says
otherwise.

Semantics warning, owned by docs/fdperf-a7xx.md: a7xx_perfcntrs.xml contains no desc=
attributes, so "VPCRAM_FULL = the VPC's own RAM could not accept a write" is a reading of the
counter name, not a quote.  The dump-parsing rules (first section only, wrapped window deltas
thrown away) live in scripts/fdperf_sections.py.

Usage: fdperf-vpcram-ratios.py <fdperf-dump> [lo_s] [hi_s]
"""
import sys
from statistics import mean

from fdperf_sections import load, window

# (name, what the line says it is)
COUNTERS = [
    ("PERF_VPC_BUSY_CYCLES", "busy of the block"),
    ("PERF_VPC_WORKING_CYCLES", "working (not stalled) part of busy"),
    ("PERF_VPC_VPCRAM_FULL_CYCLES", "VPC's own RAM could not take a write"),
    ("PERF_VPC_WIT_FULL_CYCLES", "write/completion table full"),
    ("PERF_VPC_STALL_CYCLES_VPCRAM_POS", "waiting for a position slot in VPCRAM"),
    ("PERF_VPC_STALL_CYCLES_LM_ACK", "waiting for an acknowledge from LM"),
]
HITRATE = ("PERF_VPC_NUM_LM_REQ_HIT", "LM request hits")
REQS = ("PERF_VPC_NUM_ATTR_REQ_LM", "attribute requests to LM")


def main(path, lo, hi):
    samples, unmeasured, dropped = load(path)
    win = window(samples, lo, hi)
    if not win:
        print(f"{path}: no samples in t_rel {lo}-{hi}s")
        return 1
    names = {k for s in win for k in s if k != "t"}
    avg = {n: mean(s[n] for s in win if n in s) for n in names}
    freq = 680e6

    def g(n):
        return avg.get(n)

    def m(n):
        v = g(n)
        return float("nan") if v is None else v / 1e6

    def r(a, b):
        x, y = g(a), g(b)
        return float("nan") if x is None or not y else 100.0 * x / y

    print(f"{path}: {len(win)} of {len(samples)} samples, t_rel {lo}-{hi}s")
    if not any(n in names for n, _ in COUNTERS):
        print("  no VPC-memory counter in this dump - it is not a fdperf.cfg-vpc3 run")
        return 1
    side = sorted(n for n in unmeasured if n.startswith("PERF_VPC_"))
    if side:
        print("  only in the BV_* copy of the group (binning/visibility), so not the counter "
              "this cfg programmed: " + ", ".join(n[5:] for n in side))
    for n, c in sorted(dropped.items()):
        if n.startswith("PERF_VPC_"):
            print(f"  {n[5:]}: {c} window value(s) thrown away (u64 wraparound or [invalid])")
    print(f"  {'counter':32} {'M/s':>8}  {'/680MHz':>8}  {'%BUSY':>7}   meaning (a reading, not a quote)")
    for n, what in COUNTERS:
        if n not in names:
            print(f"  {n[5:]:32} {'-':>8}{'':>19}   not sampled by this cfg")
            continue
        print(f"  {n[5:]:32} {m(n):8.1f}  {100*g(n)/freq:7.2f}%  {r(n,'PERF_VPC_BUSY_CYCLES'):6.2f}%   {what}")
    for n, what in (HITRATE, REQS):
        if n in names:
            print(f"  {n[5:]:32} {m(n):8.1f}{'':>20}   {what}")
    hit, req = g(HITRATE[0]), g(REQS[0])
    if hit is not None and req:
        print(f"  LM request hit rate             {100*hit/req:7.2f}%")
    busy = g("PERF_VPC_BUSY_CYCLES")
    work = g("PERF_VPC_WORKING_CYCLES")
    if busy and work:
        print(f"  VPC_BUSY - VPC_WORKING          {m('PERF_VPC_BUSY_CYCLES') - m('PERF_VPC_WORKING_CYCLES'):8.1f} M/s"
              f" = {100*(busy-work)/busy:5.2f}% of busy unaccounted by WORKING")
    print(f"  anchor (must stay where the cfg-vpc runs put it): VPC busy "
          f"{100*busy/freq if busy else float('nan'):5.1f}%")
    return 0


if __name__ == "__main__":
    lo = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
    hi = float(sys.argv[3]) if len(sys.argv) > 3 else 105.0
    sys.exit(main(sys.argv[1], lo, hi))
