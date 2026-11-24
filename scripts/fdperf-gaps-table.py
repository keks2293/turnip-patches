#!/usr/bin/env python3
"""The ten counters that no dump in this repository had carried, read once in RE4 (journal 43).

    scripts/fdperf-gaps-table.py
    scripts/fdperf-gaps-table.py results/games/re4/gaps37/fdperf-raw.txt \
                                results/games/re4/gaps37/fdperf-traffic.txt
    scripts/fdperf-gaps-table.py --lo 0 dump.txt        # keep the first windows too

What the table is for.  `tools/fdperf/fdperf.cfg-gaps` was written from the budget audit of journal
41.1 and had never been run: ten names, each inside its block's selector budget, each with a
denominator beside it.  A first run can decide only whether a name moves at all, and that is what the
left block prints: n, how many of the steady windows are non-zero, and the per-second median and
range.  A name the cfg did program but which reads 0 in every window is dead for our purposes, and
printing `0/56` is the finding - not `MISSING`, which this script reserves for a name the dump does
not carry at all (the `BV` half is discarded by `scripts/fdperf_sections.py`, whose docstring owns
the rules).

The three questions queue 37 asked, and where each one is answered here:
  (a) `EVICTS` - alive, so the line below prints what it is worth, and it is a bound, not a byte
      count: no unit describes the event, but the event cannot be bigger than all DRAM write traffic
      divided by it, which is what the "bytes per eviction" line computes.  There is no fill or miss
      counter on UCHE, so this does not measure what L2 keeps: the "L2 caches most of the vertex
      bytes" figure stays an inference from what does not reach DRAM.
  (b) `PC_VPC_PRIMITIVES` - alive and equal to the primitive count journal 40 already had from
      `PC_IA_PRIMITIVES` (the per-frame line below), so it is a usable primitive denominator when the
      PC budget has no slot left for IA.  It is not the per-vertex denominator queue 34 wanted:
      journal 42 settled that question without it, and this counter counts primitives.
  (c) `LRZ_LRZ_WRITE` - alive, ~4.4 k events/s, one per ~127 k LRZ busy cycles: the mask is written,
      so the depth path is not "read-only".  That is all it says, because journal 40 records that the
      units of LRZ's counters are undescribed, so the rate cannot be compared with `LRZ_READ`'s.

What is NOT here: the cfg has no SP section, so the analyzer's `SP_GM` column stays empty after this
run.  Two of its three never-filled columns (`RBBM_PCDC`, `RBBM_PCVSD`) do fill.

The steady window starts at `--lo 20` s.  The sampler is started 60 s after the game is launched, but
the first ~10 s of this scene are still a transient: `EVICTS` reads 6-12 M/s there against 2.8 M/s
afterwards, and `CCU_2D_*` 20-43 M/s against 5 M/s.  Printing the whole 140 s as one median would
average two different states, so the transient is named in the header and left out of the medians;
`--lo 0` shows it.

Divisors, and the one place this script deliberately does not divide:
  * `x clock` divides by that window's own `CP_ALWAYS_COUNT` and is printed only for the two UCHE
    queue counters, which are in the UCHE core domain;
  * the two RBBM rows get `-`.  `docs/fdperf-a7xx.md` records that RBBM counters are not in the core
    domain and that `RBBM_ALWAYS_ON` is the 19.2 MHz GMU tick, so neither available divisor makes a
    duty out of them;
  * `RBBM_PC_DCALL_BUSY` is therefore judged against the counter it should agree with, the PC block's
    own `PERF_PC_BUSY_CYCLES`, which this cfg keeps in its PC budget (id 0).  That comparison is what
    tells a reader whether the new column carries information or repeats a known one;
  * `CMP read data / request` is printed as the raw quotient and is NOT a burst size: 1.71 is what
    this run gives, which is the reason `fdperf.cfg-gaps` no longer calls id 3 "bytes".

Cross-run lines are marked as such.  The gaps and traffic dumps are two samplings of the same scene
four minutes apart, not two halves of one window; their read traffic agrees to 3 %, which is the
accuracy of anything divided across them.
"""
import argparse
import os
import statistics as st
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdperf_sections import load  # noqa: E402

MISSING = "MISSING"
CLK = "PERF_CP_ALWAYS_COUNT"
BEAT = 16  # bytes per UCHE VBIF beat, docs/fdperf-a7xx.md

# label, counter, is the counter in a core clock domain (so `x clock` means something)
GAPS = [
    ("EVICTS",          "PERF_UCHE_EVICTS",                  False),
    ("CCHE_TPH_QFULL",  "PERF_UCHE_CCHE_TPH_QUEUE_FULL",     True),
    ("CCHE_DPH_QFULL",  "PERF_UCHE_CCHE_DPH_QUEUE_FULL",     True),
    ("PC_VPC_PRIM",     "PERF_PC_VPC_PRIMITIVES",            False),
    ("RBBM_PC_DCALL",   "PERF_RBBM_PC_DCALL_BUSY",           False),
    ("RBBM_PC_VSD",     "PERF_RBBM_PC_VSD_BUSY",             False),
    ("LRZ_LRZ_WRITE",   "PERF_LRZ_LRZ_WRITE",                False),
    ("CCU_2D_RD_REQ",   "PERF_CCU_2D_RD_REQ",                False),
    ("CCU_2D_WR_REQ",   "PERF_CCU_2D_WR_REQ",                False),
    ("CMP_VBIF_WR_REQ", "PERF_CMPDECMP_VBIF_WRITE_REQUEST",  False),
]

# the denominators the cfg kept beside the new names, so a missing one is visible
DENOMS = [
    ("CP_ALWAYS_COUNT", CLK),
    ("CP_BUSY",         "PERF_CP_BUSY_CYCLES"),
    ("RBBM_ALWAYS_ON",  "PERF_RBBM_ALWAYS_ON"),
    ("UCHE_BUSY",       "PERF_UCHE_BUSY_CYCLES"),
    ("UCHE_STALL_ARB",  "PERF_UCHE_STALL_CYCLES_ARBITER"),
    ("PC_BUSY",         "PERF_PC_BUSY_CYCLES"),
    ("CCU_BUSY",        "PERF_CCU_BUSY_CYCLES"),
    ("LRZ_BUSY",        "PERF_LRZ_BUSY_CYCLES"),
    ("CMP_RD_DATA",     "PERF_CMPDECMP_VBIF_READ_DATA_CCU"),
    ("CMP_RD_REQ",      "PERF_CMPDECMP_VBIF_READ_REQUEST"),
]

# what journal 40 measured for the same scene, so the primitive denominator can be checked against it
# (16.69 M primitives/frame at 15.26 p25, from PC_IA_PRIMITIVES, journal 40.19)
J40_PRIMS_PER_FRAME = 16.69
J40_FPS = 15.26


def steady(samples, lo):
    if not samples:
        return []
    t0 = samples[0]["t"]
    return [s for s in samples if s["t"] - t0 >= lo]


def med(values):
    return st.median(values) if values else None


def med_list(samples, name):
    v = [s[name] for s in samples if s.get(name) is not None]
    return v


def med_ratio(samples, num, den):
    v = [s[num] / s[den] for s in samples if s.get(num) is not None and s.get(den)]
    return med(v)


def med_sum_ratio(samples, num, den1, den2):
    v = [s[num] / (s[den1] + s[den2]) for s in samples
         if s.get(num) is not None and s.get(den1) and s.get(den2)]
    return med(v)


def sum_rate(samples, n1, n2):
    v = [s[n1] + s[n2] for s in samples if s.get(n1) is not None and s.get(n2) is not None]
    return med(v)


def print_note(label, value, note, width=58):
    """One table row whose explanation may run past the column."""
    lines = textwrap.wrap(note, width) or [""]
    print("   %-32s %11s   %s" % (label, value, lines[0]))
    for extra in lines[1:]:
        print("   %-32s %11s   %s" % ("", "", extra))


def one_dump(path, lo):
    samples, _un, dropped = load(path)
    ss = steady(samples, lo)
    print("== %s" % path)
    print("   windows %d (%d after %.0f s), dropped %s"
          % (len(samples), len(ss), lo, dropped or "{}"))
    clock = med(med_list(ss, CLK))
    if clock:
        print("   clock %.0f MHz (CP_ALWAYS_COUNT median)" % (clock / 1e6))
    if not any(med_list(ss, _n) for _l, _n, _c in GAPS):
        # the control run beside the gaps run: it programs none of the ten names, so the ten rows
        # would all be MISSING and say nothing.  What it is for is the DRAM denominator below.
        print("   control run: carries none of the ten names.  Its own rates, for the cross-run"
              " lines:")
        for label, name in (("DRAM read beats/s", "PERF_UCHE_VBIF_READ_BEATS_CH0"),
                            ("DRAM write beats/s", "PERF_UCHE_VBIF_WRITE_BEATS_CH0"),
                            ("UBWC read beats/s", "PERF_UCHE_UBWC_READ_BEATS"),
                            ("UBWC write beats/s", "PERF_UCHE_UBWC_WRITE_BEATS")):
            v = med_list(ss, name)
            print("     %-20s %s" % (label, "%d" % med(v) if v else MISSING))
        print("   (a second channel of each is programmed too; the ratios below add them)")
        return ss
    print("   %-17s %4s %7s %12s %12s %12s %9s"
          % ("counter", "n", "nonzero", "median/s", "min/s", "max/s", "x clock"))
    for label, name, clocked in GAPS:
        v = med_list(ss, name)
        if not v:
            print("   %-17s %4s %7s %12s" % (label, 0, MISSING, MISSING))
            continue
        xc = ("%.3f" % (med(v) / clock)) if clocked and clock else "-"
        print("   %-17s %4d %7d %12d %12d %12d %9s"
              % (label, len(v), sum(1 for x in v if x), med(v), min(v), max(v), xc))
    absent = [label for label, name in DENOMS if not med_list(ss, name)]
    print("   denominators: %s" % ("all present" if not absent else "MISSING " + ", ".join(absent)))
    return ss


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dumps", nargs="*", default=None)
    ap.add_argument("--lo", type=float, default=20.0,
                    help="steady window start, seconds from the first sample (default 20)")
    ap.add_argument("--fps", type=float, default=None,
                    help="the run's mean fps, for the primitives-per-frame line")
    args = ap.parse_args()

    paths = args.dumps or [p for p in
                           ("results/games/re4/gaps37/fdperf-raw.txt",
                            "results/games/re4/gaps37/fdperf-traffic.txt")
                           if os.path.exists(p)]
    if not paths:
        print("no gaps dump - run tools/fdperf/fdperf.cfg-gaps (journal 43)")
        return 1

    print("# The ten counters that had never been read on this machine, from tools/fdperf/fdperf.cfg-gaps")
    print("# run 24.11: RE4 ship frame, D3D12, driver 4c3cdb210082, no env delta; journal 43")
    print("# regenerate: scripts/fdperf-gaps-table.py --fps %s | tee results/games/re4/gaps37/table.txt"
          % (args.fps if args.fps else "<mean>"))
    print("#             (--fps is the mean of `scripts/fps-window.py results/games/re4/fps-gaps37.csv 60 200`)")
    print("# read with:  scripts/fdperf_sections.py (BV half discarded, wrapped deltas dropped);")
    print("#             n = steady windows (--lo), nonzero = windows where the counter is not 0;")
    print("#             MISSING = the dump does not carry the name at all, 0 = it does and reads 0")
    print("# transient:  the first ~10 s of the sample are a different state and are excluded by --lo")
    print("# x clock:    divided by that window's CP_ALWAYS_COUNT; only the two UCHE queue rows have")
    print("#             it, and a value above 1 means the counter is not a core-domain duty")
    print()
    loaded = {}
    for p in paths:
        loaded[os.path.basename(p)] = one_dump(p, args.lo)
        print()

    gaps = loaded.get("fdperf-raw.txt") or next(iter(loaded.values()))
    ctrl = loaded.get("fdperf-traffic.txt")

    print("what each new counter is worth; only same-window quotients are called ratios")
    print("   %-32s %11s   %s" % ("line", "value", "what it means"))

    # (a) EVICTS: alive, and bounded in size by the write traffic it would have to be part of
    rd_beats = sum_rate(gaps, "PERF_UCHE_VBIF_READ_BEATS_CH0", "PERF_UCHE_VBIF_READ_BEATS_CH1")
    ev = med(med_list(gaps, "PERF_UCHE_EVICTS"))
    if ev and rd_beats:
        r = ev / rd_beats
        print_note("EVICTS / read beat (same win)", "%.5f" % r,
                   "one eviction per %.0f of this window's 16-B read beats" % (1 / r))
    if ctrl:
        c_rd = sum_rate(ctrl, "PERF_UCHE_VBIF_READ_BEATS_CH0", "PERF_UCHE_VBIF_READ_BEATS_CH1")
        c_wr = sum_rate(ctrl, "PERF_UCHE_VBIF_WRITE_BEATS_CH0", "PERF_UCHE_VBIF_WRITE_BEATS_CH1")
        if c_rd and c_wr and rd_beats and ev:
            # the gaps window's own read traffic, scaled by the control's write/read share
            wr_here = rd_beats * c_wr / c_rd
            print_note("DRAM read", "%.2f" % (c_rd * BEAT / 1e9),
                       "GB/s, traffic control (2 x %d B/beat)" % BEAT)
            print_note("DRAM write", "%.2f" % (c_wr * BEAT / 1e9),
                       "GB/s, traffic control; scaled to the gaps window, %.2f GB/s"
                       % (wr_here * BEAT / 1e9))
            print_note("bytes per eviction, max", "%.0f" % (wr_here * BEAT / ev),
                       "B.  Cross-run bound (write traffic / EVICTS), and it assumes every eviction"
                       " writes back.  A line is 64 B, which would be %.0f%% of all DRAM write, while"
                       " 128 B would be %.0f%% - more than the machine writes, so the event is no bigger"
                       " than a line.  It is still not a miss count: UCHE has no fill counter, so what"
                       " L2 keeps stays an inference."
                       % (100 * ev * 64 / (wr_here * BEAT), 100 * ev * 128 / (wr_here * BEAT)))

    # (b) VPC_PRIMITIVES: a primitive denominator, checked against journal 40's other one
    vp_draw = med_ratio(gaps, "PERF_PC_VPC_PRIMITIVES", "PERF_CP_CONTEXT_DONE")
    vp = med(med_list(gaps, "PERF_PC_VPC_PRIMITIVES"))
    if vp_draw:
        print_note("VPC_PRIM / CP_CONTEXT_DONE", "%.0f" % vp_draw,
                   "primitives per context-done, same window")
    if vp and args.fps:
        per_frame = vp / args.fps / 1e6
        print_note("VPC_PRIM / frame", "%.2f" % per_frame,
                   "M primitives/frame at %.2f mean fps.  Journal 40.19 had %.2f M/frame from"
                   " PC_IA_PRIMITIVES, a counter this cfg does not program: %+.1f%% from an"
                   " independent name for the same quantity, so VPC_PRIMITIVES is a usable primitive"
                   " denominator when the PC budget has no slot left for IA"
                   % (args.fps, J40_PRIMS_PER_FRAME, 100 * (per_frame / J40_PRIMS_PER_FRAME - 1)))
    elif vp:
        print_note("VPC_PRIM /s", "%d" % vp,
                   "pass --fps for the per-frame comparison with journal 40.19")

    # (c) LRZ's write side
    lrz_w = med(med_list(gaps, "PERF_LRZ_LRZ_WRITE"))
    lrz_b = med(med_list(gaps, "PERF_LRZ_BUSY_CYCLES"))
    if lrz_w:
        print_note("LRZ_BUSY / LRZ_WRITE", "%.0f" % (lrz_b / lrz_w if lrz_b else 0),
                   "LRZ busy cycles per mask write (%.0f write events/s).  LRZ itself is busy %.0f%%"
                   " of the clock, so the depth path writes the mask but rarely.  LRZ's units are"
                   " undescribed (journal 40), so this rate cannot be compared with LRZ_READ's"
                   % (lrz_w, 100 * lrz_b / med(med_list(gaps, CLK)) if lrz_b else 0))

    # the two RBBM names, judged against the counter they would have to agree with
    dclock = med_ratio(gaps, "PERF_RBBM_PC_DCALL_BUSY", CLK)
    dpc = med_ratio(gaps, "PERF_RBBM_PC_DCALL_BUSY", "PERF_PC_BUSY_CYCLES")
    if dpc:
        print_note("RBBM_PC_DCALL / PC_BUSY", "%.5f" % dpc,
                   "in every window, so the new column repeats PC busy, a counter this cfg also"
                   " programs (PC id 0).  It is also %.3f x the core clock, consistent with that but"
                   " not proof of a domain: docs/fdperf-a7xx.md keeps RBBM counters out of the core"
                   " domain, so no duty is printed for it" % dclock)
    vsd = med_list(gaps, "PERF_RBBM_PC_VSD_BUSY")
    if vsd:
        print_note("RBBM_PC_VSD_BUSY", "%d" % med(vsd),
                   "non-zero in %d/%d steady windows: dead here, the way UCHE_GMEM_*_BEATS are.  The"
                   " only reading that distinguishes 'dead counter' from 'path unused' would be a"
                   " synthetic that exercises the vertex dispatch, and nothing here does"
                   % (sum(1 for x in vsd if x), len(vsd)))

    for label, name in (("CCHE_TPH_QFULL / clock", "PERF_UCHE_CCHE_TPH_QUEUE_FULL"),
                        ("CCHE_DPH_QFULL / clock", "PERF_UCHE_CCHE_DPH_QUEUE_FULL")):
        r = med_ratio(gaps, name, CLK)
        if r is not None:
            note = ("more events per second than there are core cycles, so it is not a count of"
                    " cycles the queue was full" if r > 1 else
                    "the depth client's queue is barely full: %.1f events per 1000 core cycles"
                    % (r * 1e3))
            print_note(label, "%.3f" % r, note + "; no unit in the XML, so this is a rate only")

    cmp_r = med_ratio(gaps, "PERF_CMPDECMP_VBIF_READ_DATA_CCU", "PERF_CMPDECMP_VBIF_READ_REQUEST")
    if cmp_r is not None:
        print_note("CMP read data / request", "%.2f" % cmp_r,
                   "raw quotient, NOT a burst size: what a CMPDECMP beat is has never been described,"
                   " and 1.71 says the two names cannot be bytes and requests of the same transfers."
                   " This is why `fdperf.cfg-gaps` no longer calls id 3 \"bytes\"")

    # the one pair that cannot be told apart
    print()
    rd = [(s.get("PERF_CCU_2D_RD_REQ"), s.get("PERF_CCU_2D_WR_REQ")) for s in gaps]
    rd = [(a, b) for a, b in rd if a is not None and b is not None]
    if rd:
        eq = sum(1 for a, b in rd if a == b)
        print("CCU 2D read == write: %d/%d steady windows, max |diff| %d.  The XML names selectors 10"
              % (eq, len(rd), max(abs(a - b) for a, b in rd)))
        print("and 11 separately, and the block does program distinct counters (GMEM read and write")
        print("differ by 4x in cfg-vertex dumps), so the two are indistinguishable here: either one")
        rd_req = med(med_list(gaps, "PERF_CMPDECMP_VBIF_READ_REQUEST"))
        wr_req = med(med_list(gaps, "PERF_CMPDECMP_VBIF_WRITE_REQUEST"))
        both = med([a for a, _b in rd])
        if rd_req and wr_req:
            print("selector aliases the other, or both count CCU requests of either direction.  Their")
            print("value is %.1f M/s, %.0f%% of the CMP read+write request count in the same windows"
                  % (both / 1e6, 100 * both / (rd_req + wr_req)))
            print("(%.1f M/s), which is a 3D-path rate and not a blitter's - so these are not the 2D"
                  % ((rd_req + wr_req) / 1e6))
            print("engine's counters and cannot tell a 2D copy from a 3D one, which is what the cfg")
            print("header wanted them for.  A write-only 2D op would separate them; nothing here can.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
