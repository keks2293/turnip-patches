#!/usr/bin/env python3
"""Steady-window table for the TSE drop question (tools/fdperf/fdperf.cfg-tse, -tse2).

Why a separate script: the headline of the drop measurement is a ratio of two counters of
the same group taken from the same sample (`TSE_OUTPUT_VISIBLE_PRIM / TSE_INPUT_PRIM`), and
the TSE budget is 4 (docs/fdperf-a7xx.md, "hw counter budgets"), so the size of the drop and
the reason for it live in different runs.  This script prints both kinds and marks whichever
is absent as such instead of printing 0.

The window rule is the one used by scripts/fdperf-vpc-ratios.py: 1 s windows, by default
20-105 s after the first sample, mean over the window set.  Busy percentages are against the
core frequency fdperf reports for that run.  Multi-instance dividers are NOT applied here
(docs/fdperf-a7xx.md lists them; every percentage printed here is a ratio inside one block,
where the divider cancels).

The XML gives no descriptions for these counters (`desc=' appears 0 times in
src/freedreno/registers/adreno/a7xx_perfcntrs.xml), so "TRIVAL_REJ = rejected outside the
viewport" is a reading of the name, not a quote.

Parsing (the second section of the dump, the wrapped window delta) is in
scripts/fdperf_sections.py, which owns those two rules for all three ratio scripts.

Usage: fdperf-tse-ratios.py <fdperf-dump> [lo_s] [hi_s]
"""
import sys
from collections import Counter
from statistics import mean

from fdperf_sections import load, window


def main() -> int:
    path = sys.argv[1]
    lo = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
    hi = float(sys.argv[3]) if len(sys.argv) > 3 else 105.0

    s, unmeasured, dropped = load(path)
    win = window(s, lo, hi)
    if not win:
        print(f"{path}: no samples in {lo}-{hi}s", file=sys.stderr)
        return 1
    names = {k for x in win for k in x if k != "t"}
    counts = Counter(k for x in win for k in x if k != "t")
    avg = {n: mean(x[n] for x in win if n in x) for n in names}

    # The frequency line of the run: "frequency <n> MHz" is not in the dump, and the clock
    # is pinned during these runs, so 680 MHz is stated in the cfg header and used here.
    freq = 680e6

    def has(n):
        return n in avg

    def g(n):
        return avg.get(n, 0.0)

    def pct(n):
        return 100 * g(n) / freq

    def r(a, b):
        return 100 * g(a) / g(b) if g(a) and g(b) else float("nan")

    print(f"{path}: {len(win)} of {len(s)} samples, t_rel {lo}-{hi}s")
    side = sorted(n for n in unmeasured if n.startswith(("PERF_TSE_", "PERF_VSC_")))
    if side:
        print("  only in the BV_* copy of the group (binning/visibility), so not the counter "
              "this cfg programmed: " + ", ".join(n[5:] for n in side))
    for n, c in sorted(dropped.items()):
        if n.startswith(("PERF_TSE_", "PERF_VSC_")):
            print(f"  {n[5:]}: {c} window value(s) thrown away (u64 wraparound or [invalid])")
    tse = [n for n in ("PERF_TSE_BUSY_CYCLES", "PERF_TSE_INPUT_PRIM",
                       "PERF_TSE_OUTPUT_VISIBLE_PRIM", "PERF_TSE_ZERO_PIXEL_PRIM",
                       "PERF_TSE_TRIVAL_REJ_PRIM", "PERF_TSE_ZERO_AREA_PRIM",
                       "PERF_TSE_FACENESS_CULLED_PRIM", "PERF_TSE_CLIPPED_PRIM") if has(n)]
    for n in tse:
        print(f"  {n[5:]:32} {g(n)/1e6:8.2f} M/s   /680MHz {pct(n):6.2f}%")
    if not tse:
        print("  no TSE counter in this dump")
    if has("PERF_TSE_INPUT_PRIM") and has("PERF_TSE_OUTPUT_VISIBLE_PRIM"):
        drop = g("PERF_TSE_INPUT_PRIM") - g("PERF_TSE_OUTPUT_VISIBLE_PRIM")
        print(f"  drop = INPUT - OUTPUT_VISIBLE   {drop/1e6:8.2f} M/s = {100*drop/g('PERF_TSE_INPUT_PRIM'):5.1f}% of input")
    if has("PERF_TSE_TRIVAL_REJ_PRIM") and has("PERF_TSE_ZERO_AREA_PRIM"):
        reasons = (g("PERF_TSE_TRIVAL_REJ_PRIM") + g("PERF_TSE_ZERO_AREA_PRIM")
                   + g("PERF_TSE_FACENESS_CULLED_PRIM") + g("PERF_TSE_CLIPPED_PRIM"))
        print(f"  reason counters sum             {reasons/1e6:8.2f} M/s")
    for n in ("PERF_VSC_BUSY_CYCLES", "PERF_VSC_STALL_CYCLES_UCHE"):
        if has(n):
            print(f"  {n[5:]:32} {g(n)/1e6:8.2f} M/s   /680MHz {pct(n):6.2f}%")
    # EOT_NUM and INPUT_TILES count events, not cycles: they are printed per second.
    for n in ("PERF_VSC_EOT_NUM", "PERF_VSC_INPUT_TILES"):
        if has(n):
            note = f"   [{counts[n]} windows used, {dropped[n]} values dropped as wrapped]" if dropped.get(n) else ""
            print(f"  {n[5:]:32} {g(n):11.1f} per s{note}")
    if has("PERF_VSC_STALL_CYCLES_UCHE") and g("PERF_VSC_BUSY_CYCLES"):
        print(f"  VSC stall UCHE / VSC busy      {r('PERF_VSC_STALL_CYCLES_UCHE','PERF_VSC_BUSY_CYCLES'):6.2f}%")
    print("  anchors (must not move when only the TSE/VSC slots change):")
    if has("PERF_VPC_BUSY_CYCLES"):
        print(f"    VPC busy {pct('PERF_VPC_BUSY_CYCLES'):5.1f}%   VS/BUSY {r('PERF_VPC_VS_BUSY_CYCLES','PERF_VPC_BUSY_CYCLES'):5.2f}%   "
              f"PS/BUSY {r('PERF_VPC_PS_BUSY_CYCLES','PERF_VPC_BUSY_CYCLES'):5.2f}%")
    if has("PERF_PC_BUSY_CYCLES"):
        print(f"    PC busy {pct('PERF_PC_BUSY_CYCLES'):5.1f}%   STALL_VPC/PC_BUSY {r('PERF_PC_STALL_CYCLES_VPC','PERF_PC_BUSY_CYCLES'):6.2f}%")
    if has("PERF_UCHE_BUSY_CYCLES"):
        print(f"    UCHE stall arbiter/busy {r('PERF_UCHE_STALL_CYCLES_ARBITER','PERF_UCHE_BUSY_CYCLES'):6.2f}%")
    if has("PERF_VFD_BUSY_CYCLES"):
        print(f"    VFD starve UCHE/busy {r('PERF_VFD_STARVE_CYCLES_UCHE','PERF_VFD_BUSY_CYCLES'):6.2f}%")
    if has("PERF_UCHE_VBIF_READ_BEATS_CH0"):
        rd = (g("PERF_UCHE_VBIF_READ_BEATS_CH0") + g("PERF_UCHE_VBIF_READ_BEATS_CH1")) * 16
        print(f"    DRAM read {rd/1e9:5.2f} GB/s   TP {g('PERF_UCHE_VBIF_READ_BEATS_TP')*16/1e9:5.2f} GB/s")
    if has("PERF_CP_DEAD_DRAWS_IN_BIN_RENDER"):
        print(f"    CP dead draws in bin render {g('PERF_CP_DEAD_DRAWS_IN_BIN_RENDER'):8.1f}/s   "
              f"predicated kills {g('PERF_CP_PREDICATED_DRAWS_KILLED'):6.1f}/s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
