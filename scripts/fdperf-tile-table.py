#!/usr/bin/env python3
"""Every run that can say whether a binning pass ran: the VSC tile counter, two window rules.

Why: `PERF_VSC_INPUT_TILES` is the only counter in this repository that says "the driver binned in
this second", and journal 40.8 quoted it from three different sample sets at once (median of the whole
file, median of the steady window, minimum instead of median), which is how "0 (median) / 21,728 (max)"
ended up next to "775 / 8,957" in one table.  This script is the only place those numbers are cut, and
it prints both sample sets side by side so the difference is visible rather than remembered:

  * steady windows: t_rel LO-HI of the sample set, wrapped window deltas and [invalid] dropped;
  * pinned-clock windows: the steady windows whose CP_ALWAYS_COUNT is within 1 % of the pinned core
    clock.  Duty cycles need that second rule (a window at 613 MHz pulls a 91.7 % mean down to
    88.8 %, journal 40.12); an event count like tiles/s does not, which is why both are printed.

Reading fixed by journal 40.12: a nonzero tile rate says a binning pass ran in that window, and nothing
about the scene in another run.  The counter is programmed by the `VSC` cfg section; a run whose cfg has
no `VSC` section prints `-`, never a 0.

Usage:
    scripts/fdperf-tile-table.py [--lo 20 --hi 105] [dir-or-dump ...]
    # with no arguments, the runs of journal 40.12, in the order that entry prints them
"""
import glob
import os
import sys
from statistics import median

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdperf_sections import load, window  # noqa: E402

FREQ = 680e6          # core clock pinned for every run below (fdperf prints max_freq=680000000)

# Which dump answers which question of journal 40.12, and what its environment was.  Written down by
# hand: guessing which run had which flag is how 40.8's tile row went wrong.
RUNS = [
    ("cbbase", "results/games/re4/tse3-cbbase/fdperf-raw.txt", "21.11", "cfg-tse3", "none (CB off)"),
    ("cbforce", "results/games/re4/tse3-cbforce/fdperf-raw.txt", "21.11", "cfg-tse3", "forcecb"),
    ("bvbase", "results/games/re4/bv-bvbase/fdperf-raw.txt", "22.11", "cfg-bv", "none"),
    ("bvforce", "results/games/re4/bv-bvforce/fdperf-raw.txt", "22.11", "cfg-bv", "forcecb"),
    ("bvforce3", "results/games/re4/bv-bvforce3/fdperf-raw.txt", "22.11", "cfg-bv", "startup,forcecb"),
    ("bvforce4", "results/games/re4/bv-bvforce4/fdperf-raw.txt", "22.11", "cfg-bv2", "startup,forcecb"),
    ("bvforce5", "results/games/re4/bv-bvforce5/fdperf-raw.txt", "22.11", "cfg-bv3", "startup,forcecb"),
    ("tse3cb2", "results/games/re4/tse3-tse3cb2/fdperf-raw.txt", "22.11", "cfg-tse3", "startup,forcecb"),
    ("tse3cb3", "results/games/re4/tse3-tse3cb3/fdperf-raw.txt", "22.11", "cfg-tse3", "forcecb"),
]

TILES = "PERF_VSC_INPUT_TILES"
BUSY = "PERF_VSC_BUSY_CYCLES"


def fmt(vals):
    """median / max of one run's tile values, or `-` when the counter is not programmed."""
    if not vals:
        return "      - /      -", " 0 of  0"
    return f"{median(vals):6,.0f} / {max(vals):6,}", f"{sum(1 for v in vals if v):2} of {len(vals):2}"


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

    if args:
        runs = [(os.path.basename(os.path.dirname(p))[len("fdperf-"):] or os.path.basename(p),
                 p, "-", "-", "-") for p in args]
    else:
        runs = RUNS

    print(f"counter window t_rel {lo:.0f}-{hi:.0f} s (steady), pinned clock within 1 % of "
          f"{FREQ / 1e6:.0f} MHz; tiles/s is a per-second count, so its median is cut over both "
          "sample sets - the steady windows and the pinned-clock ones - while every duty cycle below "
          "uses only the pinned-clock ones (`-` = the cfg never programmed that counter)")
    print("| run | date | cfg | TU_DEBUG | steady windows | pinned-clock windows | "
          "tiles median / max /s, steady | windows with tiles, steady | "
          "tiles median / max /s, pinned | windows with tiles, pinned | VSC busy % (pinned) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for tag, path, day, cfg, env in runs:
        if not os.path.exists(path):
            print(f"| {tag:9} | {day} | {cfg} | {env} | missing: {path} |")
            continue
        samples, _unmeasured, _dropped = load(path)
        allw = window(samples, lo, hi)
        steady = [s for s in allw if TILES in s]
        pinned = [s for s in steady
                  if 0.99 * FREQ <= s.get("PERF_CP_ALWAYS_COUNT", 0) <= 1.01 * FREQ]
        steady_med, steady_n = fmt([s[TILES] for s in steady])
        pinned_med, pinned_n = fmt([s[TILES] for s in pinned])
        busy = [s[BUSY] for s in pinned if BUSY in s]
        busycell = f"{median(busy) / FREQ * 100:5.2f}" if busy else "    -"
        print(f"| {tag:9} | {day} | {cfg:8} | {env:15} | {len(allw):3} | {len(pinned):3} | "
              f"{steady_med} | {steady_n} | {pinned_med} | {pinned_n} | {busycell} |")


if __name__ == "__main__":
    main()
