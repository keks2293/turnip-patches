#!/usr/bin/env python3
"""One `cfg-bv` dump split by whether a binning pass ran in the window, ordinary half against `BV_*` half.

    scripts/fdperf-bv-tilesplit.py [--lo 20] [--hi 105] <dump> [dump ...]

Why (queue 21 of `docs/plan-next-checks.md`).  Journals 40.11 and 40.12 read the `BV_*` primitive
counters at 0/s, but those sessions never started a binning pass (`VSC_INPUT_TILES` 0 in every
window), so the zero was not a binning/visibility thread at work - it was a thread with no pass to
run.  The question is therefore per window and not per run: take the windows in which the VSC was fed
tiles and read the `BV_*` half of *the same dump* in those same windows.  If `BV_TSE`
`TSE_INPUT_PRIM` and `BV_PC` `PC_IA_PRIMITIVES` stay 0 there, the BV thread provably never runs
primitives; if they rise, the discard ratio of journal 40.2 has to be re-asked per thread.

Rules (`scripts/fdperf_sections.py` owns the parsing, the same ones `fdperf-bv-table.py` uses):

  * the class of a window is `PERF_VSC_INPUT_TILES > 0` in that window's own sample;
  * the core clock is printed per class and never assumed: 40.12 found that `bvbase`'s tile windows
    are exactly the windows where the core sagged below the pinned 680 MHz, so a duty cycle read in
    a tile window is diluted by the clock and the reader has to see both in one line;
  * `-` means the name is not in that half of that dump, `0.00` means it was programmed and counted
    nothing.  The two are never conflated - an unprogrammed `BV_*` half is not a measurement (40.11);
  * both halves come from one dump over one `t_rel` window, so no comparison in this table mixes
    runs, days or cfgs.
"""
import sys
from statistics import mean

from fdperf_sections import load_sections, window

FREQ = 680e6
NAMES = [
    "PERF_VSC_INPUT_TILES",
    "PERF_VSC_BUSY_CYCLES",
    "PERF_TSE_INPUT_PRIM",
    "PERF_TSE_OUTPUT_VISIBLE_PRIM",
    "PERF_PC_IA_PRIMITIVES",
    "PERF_VPC_BUSY_CYCLES",
    "PERF_LRZ_BUSY_CYCLES",
    "PERF_TP_BUSY_CYCLES",
]
IS_CYCLE = lambda n: any(k in n for k in ("CYCLES", "BUSY", "IDLE", "STALL", "STARVE"))


def cell(name, v):
    if v is None:
        return "            -"
    if IS_CYCLE(name):
        pct = f" ({100 * v / FREQ:5.2f} %)" if v <= 10 * FREQ else "  *"
        return f"{v / 1e6:8.2f} Mc/s{pct}"
    if v < 1000:      # 17 tiles/s is not zero: it must not print as 0.0
        return f"{v / 1e3:10.3f} k/s"
    return f"{v / 1e3:10.1f} k/s"


def means(samples, bv_by_t, name):
    """(ordinary half, BV half) means of one counter; None when the half does not carry it."""
    o = [s[name] for s in samples if isinstance(s.get(name), (int, float))]
    b = []
    for s in samples:
        v = bv_by_t.get(s["t"], {}).get(name)
        if isinstance(v, (int, float)):
            b.append(v)
    return (mean(o) if o else None, mean(b) if b else None)


def report(path, lo, hi):
    samples, bv_samples, _un, _d, _bd = load_sections(path)
    win = window(samples, lo, hi)
    bv_by_t = {s["t"]: s for s in window(bv_samples, lo, hi)}
    on = [s for s in win if isinstance(s.get("PERF_VSC_INPUT_TILES"), (int, float))
          and s["PERF_VSC_INPUT_TILES"] > 0]
    off = [s for s in win if not (isinstance(s.get("PERF_VSC_INPUT_TILES"), (int, float))
                                  and s["PERF_VSC_INPUT_TILES"] > 0)]
    print(f"### {path}: {len(win)} steady windows in t_rel {lo:.0f}-{hi:.0f} s, "
          f"{len(on)} of them with tiles > 0")
    if not win:
        print("  no samples in the window")
        return

    def clk(cls):
        v = [s["PERF_CP_ALWAYS_COUNT"] for s in cls
             if isinstance(s.get("PERF_CP_ALWAYS_COUNT"), (int, float))]
        return f"{mean(v) / 1e6:6.1f} MHz" if v else "     -"

    print(f"  core clock (CP_ALWAYS_COUNT)     tiles>0 {clk(on)}   tiles=0 {clk(off)}")
    print(f"  {'counter':34} {'ordinary, tiles>0':19} {'BV_*, tiles>0':19} "
          f"{'ordinary, tiles=0':19} {'BV_*, tiles=0':19}")
    for n in NAMES:
        oo, bo = means(on, bv_by_t, n)
        of, bf = means(off, bv_by_t, n)
        print(f"  {n[5:]:34} {cell(n, oo)} {cell(n, bo)} {cell(n, of)} {cell(n, bf)}")
    print("  `*` = over 1000 % of one core: a sum over the block's instances, or a select that was\n"
          "      never programmed (40.8).  `-` = not in that half of this dump, which is not a zero.\n"
          "      An event counter below 1000/s keeps three decimals, because the trickle of tiles this\n"
          "      table is looking for is not zero (40.12: `bvbase` ran 16 tiles/s in 22 of 38 windows).")


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
    return 0


if __name__ == "__main__":
    sys.exit(main())
