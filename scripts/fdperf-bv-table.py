#!/usr/bin/env python3
"""The two halves of a dump side by side: what the ordinary group counted and what its `BV_*` twin counted.

Why: an a7xx dump carries every block twice - the ordinary counter group and the `BV_*`
(binning/visibility, i.e. the CB thread) twin of the same group, whose countable list is the *same*
enum (`a7xx_perfcntrs.json`: `BV_VPC` num 6 `select_offset` 6, `BV_TSE` num 4, ...).  Until 22.11 the
BV half had only ever been read as noise: the cfgs of this repository program the ordinary groups and
never name a `BV_*` section, so the BV selects keep their defaults and the printed numbers cannot be
attributed (journal 40.8: medians of 0.02-0.08 % of the core for VPC/TSE/LRZ, and `BV_TP` BUSY at
950-967 % of a one-second window, which is not a busy fraction at all).  `tools/fdperf/fdperf.cfg-bv`
programs them on purpose; this script is how its two arms are read.

Reading rules (the same ones scripts/fdperf_sections.py owns):
  * a name that appears in only one half was programmed in only one half, and "-" is printed for the
    other half, never 0;
  * window deltas that came back wrapped (>= 2**63) or `[invalid]` are dropped and counted;
  * cycle counters are shown both as Mc/s and as a share of the pinned 680 MHz core, because that is
    the only comparison that means anything across a group boundary;
  * a percentage between the two halves is a ratio of two counters of *different* groups (the ordinary
    group and the BV group are separate hardware groups), so it is printed as a scale check, not as a
    duty cycle.

Usage:
    scripts/fdperf-bv-table.py [--lo 20] [--hi 105] <dump> [dump ...]
"""
import sys
from statistics import mean

from fdperf_sections import load_sections, window

FREQ = 680e6


def avg_of(samples):
    names = {k for s in samples for k in s if k != "t"}
    return {n: mean(s[n] for s in samples if n in s) for n in names}


def cell(name, v):
    """A cycle counter is a share of the core; an event counter (PRIM, TILES, TRANS, REQUESTS,
    SAMPLES) is a rate per second.  fdperf itself makes this split when it prints `%.2f%%` for a
    label containing CYCLE/BUSY/IDLE and a bare number for the rest (fdperf.c, dump_counters), so a
    table that shows tiles in Mc/s prints 0.00 for 1,532 tiles/s - which is how an event counter
    looks dead."""
    if v is None:
        return "              -"
    if any(k in name for k in ("CYCLES", "BUSY", "IDLE", "STALL", "STARVE")):
        txt = f"{v / 1e6:8.2f} Mc/s"
        if v > 10 * FREQ:   # > 1000 % of one core: a sum over instances, or a mirror
            txt += " *"
        return f"{txt:>16}"
    return f"{v / 1e3:11.1f} k/s"


def report(path, lo, hi):
    samples, bv_samples, unmeasured, dropped, bv_dropped = load_sections(path)
    win, winbv = window(samples, lo, hi), window(bv_samples, lo, hi)
    print(f"### {path}: {len(win)} of {len(samples)} samples, t_rel {lo:.0f}-{hi:.0f} s")
    if not win:
        print("  no samples in the window")
        return
    a, b = avg_of(win), avg_of(winbv)
    names = sorted(set(a) | set(b))
    print(f"  {'counter':38} {'ordinary group':17} {'BV_* group':17}  BV/ordinary")
    for n in names:
        va, vb = a.get(n), b.get(n)
        rel = f"{100 * vb / va:8.3f} %" if (va and vb) else "         -"
        print(f"  {n[5:]:38} {cell(n, va)} {cell(n, vb)}  {rel}")
    for label, d in (("ordinary", dropped), ("BV", bv_dropped)):
        if d:
            print(f"  dropped values ({label}): "
                  + ", ".join(f"{k[5:]} x{v}" for k, v in sorted(d.items())))
    if unmeasured:
        print("  only in the BV half (this cfg never programmed it in the ordinary group): "
              + ", ".join(sorted(n[5:] for n in unmeasured)))


def main():
    args = sys.argv[1:]
    lo, hi = 20.0, 105.0
    while args and args[0].startswith("--"):
        key, val = args[0][2:], float(args[1])
        if key == "lo":
            lo = val
        elif key == "hi":
            hi = val
        else:
            sys.exit(f"unknown option --{key}")
        args = args[2:]
    if not args:
        sys.exit(__doc__)
    for path in args:
        report(path, lo, hi)
    print("\n`*` = more than 1000 % of one 680 MHz core: either a sum over the block's instances\n"
          "(TP and SP have 12) or a select that was never programmed. Not a busy fraction either way.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
