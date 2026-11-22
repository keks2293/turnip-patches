#!/usr/bin/env python3
"""One row per run: the wall's four coupling ratios, the geometry count and the frame rate.

Why: every question this repository asks is "did this lever move the wall?", and the wall is
described by a handful of numbers measured in the same one-second samples - VPC busy, PC waiting on
VPC, the UCHE arbiter stall, how much the vertex fetch and the sampler starve on UCHE, primitives
per second - plus p25 fps.  Reading them run by run out of three different ratio scripts is how
comparisons end up being made from memory, so this script prints the whole table from the committed
dumps, one line per run, with the counters a cfg did not program shown as `-` rather than as 0.

Rules this script follows, all of them learned the hard way (docs/fdperf-a7xx.md, journal 40):
  * every ratio is inside one block, because counters of different groups share their group's
    clocking and a percentage across groups is not a thing here;
  * only the ordinary group's half of the dump is read (scripts/fdperf_sections.py separates the
    BV_* twins), wrapped window deltas and `[invalid]` are dropped, and an event counter is printed
    per second, never as a share of the core;
  * the counter window is t_rel 20-105 s of the sample set (journal 40's steady stretch) and the
    fps window is 60-90 s of the MangoHud CSV (the window journal 40's p25 numbers use) - both
    printed in the header, because a table without its windows is not a measurement;
  * which fps CSV belongs to which run is written down by hand below, never guessed.

Usage:
    scripts/fdperf-arm-table.py [--lo 20 --hi 105] [dir-or-dump ...]
    # with no arguments, every results/games/re4/*/fdperf-raw.txt in the repository
"""
import csv
import glob
import os
import sys
from statistics import mean, median

from fdperf_sections import load, window

FREQ = 680e6          # core clock pinned in every 21.11 run (fdperf prints max_freq=680000000)
BEAT = 16             # bytes per VBIF read beat, docs/fdperf-a7xx.md

# label, numerator(s), denominator, scale.  numerator None means "read this counter directly".
# `per instance` counters (TP, SP have 12 instances) divide by the instance count where
# docs/fdperf-a7xx.md records it.
COLS = [
    ("VPC busy %",      "PERF_VPC_BUSY_CYCLES",                     None,            100.0 / FREQ),
    ("PC stall VPC %",  "PERF_PC_STALL_CYCLES_VPC",                 "PERF_PC_BUSY_CYCLES", 100.0),
    ("UCHE arb %",      "PERF_UCHE_STALL_CYCLES_ARBITER",           "PERF_UCHE_BUSY_CYCLES", 100.0),
    ("VFD starve UCHE %", "PERF_VFD_STARVE_CYCLES_UCHE",            "PERF_VFD_BUSY_CYCLES", 100.0),
    ("TP stall UCHE %", "PERF_TP_STALL_CYCLES_UCHE",                "PERF_TP_BUSY_CYCLES", 100.0),
    ("TP busy %",       "PERF_TP_BUSY_CYCLES",                      None,            100.0 / (12 * FREQ)),
    ("TSE in M/s",      "PERF_TSE_INPUT_PRIM",                      None,            1e-6),
    ("TSE vis %",       "PERF_TSE_OUTPUT_VISIBLE_PRIM",             "PERF_TSE_INPUT_PRIM", 100.0),
    ("DRAM GB/s",       ("PERF_UCHE_VBIF_READ_BEATS_CH0", "PERF_UCHE_VBIF_READ_BEATS_CH1"), None, 1e-9 * BEAT),
]

# Which MangoHud CSV belongs to which run, maintained by hand: the run directory is
# fdperf-<cfg-family>-<tag> while the CSV is fps-<tag>, and some 21.11 tags use `_` inside
# (`algo-prefer_gmem`), so guessing is how a comparison gets made against the wrong session.
# None means the run has no CSV at all - `tse1` lost its CSV to the runner bug (journal 40.7) and
# `cbforce` was a counter-only arm.
FPS = {
    "sh-c0":             "results/games/re4/fps-sh-c0.csv",
    "sh-c1":             "results/games/re4/fps-sh-c1.csv",
    "sh-q0":             "results/games/re4/fps-sh-q0.csv",
    "sh-q3":             "results/games/re4/fps-sh-q3.csv",
    "dbg-perf":          "results/games/re4/fps-dbg-perf.csv",
    "dbg-file":          "results/games/re4/fps-dbg-file.csv",
    "dbg-gmem":          "results/games/re4/fps-dbg-gmem.csv",
    "dbg-sysmem":        "results/games/re4/fps-dbg-sysmem.csv",
    "tr-base":           "results/games/re4/fps-tr-base.csv",
    "tr-nocomp":         "results/games/re4/fps-tr-nocomp.csv",
    "tr-nocomp-perf":    "results/games/re4/fps-tr-nocomp-perf.csv",
    "tr-noupload2":      "results/games/re4/fps-tr-noupload2.csv",
    "gmem-nobin":        "results/games/re4/fps-gmem-nobin.csv",
    "mesa27":            "results/games/re4/mesa27/fps.csv",
    "mesa27-vertex":     "results/games/re4/mesa27-vertex/fps.csv",
    "tse-algo-bandwidth":    "results/games/re4/fps-algo-bandwidth.csv",
    "tse-algo-prefer-gmem":  "results/games/re4/fps-algo-prefer_gmem.csv",
    "tse-forcecb":       "results/games/re4/fps-forcecb.csv",
    "tse-tse1":          None,
    "tse2-tse2":         "results/games/re4/fps-tse2.csv",
    "tse3-cbbase":       "results/games/re4/fps-cbbase.csv",
    "tse3-cbforce":      None,
    "vpc-cb1":           "results/games/re4/fps-cb1.csv",
    "vpc-fl111":         "results/games/re4/fps-fl111.csv",
    "vpc-fl121":         "results/games/re4/fps-fl121.csv",
    "vpc-hp40":          "results/games/re4/fps-hp40.csv",
    "vpc-hp50":          "results/games/re4/fps-hp50.csv",
    "vpc-hpbase2":       "results/games/re4/fps-hpbase2.csv",
    "vpc-lrz2":          "results/games/re4/fps-lrz2.csv",
    "vpc-nopref":        "results/games/re4/fps-nopref.csv",
    "vpc-vpcbase1":      "results/games/re4/fps-vpcbase1.csv",
    "vpc-vpcbase2":      "results/games/re4/fps-vpcbase2.csv",
    "vpc2-vpc2b":        "results/games/re4/fps-vpc2b.csv",
    "vpc3-attrbuf":      "results/games/re4/fps-attrbuf.csv",
    "vpc3-vpc3base":     "results/games/re4/fps-vpc3base.csv",
    "bv-bvbase":         "results/games/re4/fps-bvbase.csv",
    "bv-bvforce":        "results/games/re4/fps-bvforce.csv",
    "bv-bvforce2":       "results/games/re4/fps-bvforce2.csv",
    "bv-bvforce3":       "results/games/re4/fps-bvforce3.csv",
    "bv-bvforce4":       "results/games/re4/fps-bvforce4.csv",
    "bv-bvforce5":       "results/games/re4/fps-bvforce5.csv",
    "tse3-tse3cb2":      "results/games/re4/fps-tse3cb2.csv",
    "tse3-tse3cb3":      "results/games/re4/fps-tse3cb3.csv",
}


def fps_p25(csv_path, lo=60.0, hi=90.0):
    """p25 of fps, parsed the way scripts/fps-window.py (which owns the rule) does: two metadata rows
    before the header, `elapsed` in nanoseconds in this MangoHud build, sanity bound
    0.5 < fps < 1000 (startup rows report ~1e-05), and the 25th percentile as `sorted[n//4]`.
    Window defaults to 60-90 s, the window every p25 of journal 40 was quoted on; docs/analysis.md
    13.0's 40-50 s window is the older protocol and gives numbers about 0.5 fps higher, so a table
    and a journal paragraph can only be compared when they name the same window."""
    if not csv_path or not os.path.exists(csv_path):
        return None
    with open(csv_path) as f:
        lines = f.read().splitlines()
    vals = []
    for r in csv.DictReader(lines[2:]):
        try:
            t = float(r["elapsed"]) / 1e9
            fps = float(r["fps"])
        except (KeyError, TypeError, ValueError):
            continue
        if lo <= t < hi and 0.5 < fps < 1000:
            vals.append(fps)
    if not vals:
        return None
    vals.sort()
    return vals[max(0, int(0.25 * len(vals)))]


def row_for(path, lo, hi):
    name = os.path.basename(os.path.dirname(path)) or os.path.basename(path)
    tag = name[len("fdperf-"):] if name.startswith("fdperf-") else name
    samples, _unmeasured, dropped = load(path)
    win = window(samples, lo, hi)
    if not win:
        return None
    # docs/fdperf-a7xx.md ("Healthy vs degenerate window"): a 1 s window in which CP did not run at
    # the pinned core clock is not a window of the workload - the counters are sampled while the GPU
    # was ramping, and every duty cycle in it is diluted.  Reported, never silently kept.  The cut is
    # +/-1 % of the pinned clock, not the 0.9 x "degenerate" line: a window at 613 MHz passes 0.9 and
    # still pulls a 91.7 % duty cycle down to 88.8 % (journal 40.12, run `bvbase`).
    bad = [i for i, s in enumerate(win)
           if not 0.99 * FREQ <= s.get("PERF_CP_ALWAYS_COUNT", FREQ) <= 1.01 * FREQ]
    off = len(bad)
    deg = sum(1 for i in bad
              if win[i].get("PERF_CP_ALWAYS_COUNT", FREQ) < 0.9 * FREQ)
    win = [s for i, s in enumerate(win) if i not in set(bad)]
    avg = {}
    for n in {k for s in win for k in s if k != "t"}:
        vals = [s[n] for s in win if n in s]
        if vals:
            avg[n] = mean(vals)

    cells = []
    for label, num, den, scale in COLS:
        if isinstance(num, tuple):
            parts = [avg.get(n) for n in num]
            val = sum(p for p in parts if p) if any(parts) else None
        else:
            val = avg.get(num)
        if val is not None and den is not None:
            d = avg.get(den)
            val = val / d if d else None
        cells.append(f"{val * scale:8.2f}" if val is not None else "       -")

    fps = fps_p25(FPS.get(tag))
    fps_cell = f"{fps:6.2f}" if fps else "NOT MEASURED"
    notes = []
    clocks = sorted(s.get("PERF_CP_ALWAYS_COUNT") for s in window(samples, lo, hi)
                    if s.get("PERF_CP_ALWAYS_COUNT"))
    if off:
        med = median(clocks) / 1e6 if clocks else 0.0
        extra = f", {deg} of them below 0.9 x, the \"degenerate\" line of docs/fdperf-a7xx.md" if deg else ""
        notes.append(f"{off} of {len(win) + off} windows dropped: CP_ALWAYS_COUNT not within 1 % of the "
                     f"pinned {FREQ / 1e6:.0f} MHz (this dump's median is {med:.0f} MHz{extra}). Duty "
                     "cycles in a window where the core was below the pinned clock are diluted, so they "
                     "are not averaged together with the on-clock ones")
    if dropped:
        notes.append("window values dropped as wrapped/[invalid]: "
                     + ", ".join(f"{k[5:]} x{v}" for k, v in sorted(dropped.items())))
    if tag not in FPS:
        notes.append("no fps mapping written down for this run - add it to FPS in this script "
                     "rather than guessing a CSV")
    elif not FPS[tag]:
        notes.append("no MangoHud CSV for this run")
    medclock = f"{clocks[len(clocks) // 2] / 1e6:6.1f}" if clocks else "     -"
    return (tag, f"| {tag:22} | " + " | ".join(cells) + f" | {fps_cell} | {len(win)} | {medclock} |", notes)


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
    paths = sorted(glob.glob("results/games/re4/*/fdperf-raw.txt")) if not args else [
        os.path.join(a, "fdperf-raw.txt") if os.path.isdir(a) else a for a in args
    ]
    head = [c[0] for c in COLS]
    print(f"counter window t_rel {lo:.0f}-{hi:.0f} s, fps window 60-90 s (scripts/fps-window.py); "
          "`-` = not programmed by that cfg, never 0; `windows` counts only windows whose "
          "CP_ALWAYS_COUNT is at the pinned clock, and the median clock of the whole dump is shown "
          "so an off-clock run cannot be read as a 680 MHz one")
    print("| run | " + " | ".join(head) + " | p25 fps | windows | median clock MHz |")
    print("|---" * (len(head) + 3) + "|")
    notes_all = []
    for p in paths:
        r = row_for(p, lo, hi)
        if not r:
            continue
        tag, line, notes = r
        print(line)
        notes_all += [f"{tag}: {x}" for x in notes]
    if notes_all:
        print()
        for x in notes_all:
            print("note:", x)
    return 0


if __name__ == "__main__":
    sys.exit(main())
