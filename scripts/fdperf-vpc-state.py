#!/usr/bin/env python3
"""What the VPC is doing with its time, and what the two export counters agree on.

    scripts/fdperf-vpc-state.py                      # every committed dump
    scripts/fdperf-vpc-state.py --arms cb21-h0,vpc-vpcbase1
    scripts/fdperf-vpc-state.py --any-clock          # drop the 676 MHz pin filter

Three questions, all of them readings of files already in git (journal 40.34):

1. Is the VPC computing, or is it busy and stalled? `VPC_WORKING_CYCLES / VPC_BUSY_CYCLES`
   answers that, and `VPC_VPCRAM_FULL_CYCLES` / `VPC_WIT_FULL_CYCLES` name the stall when it
   is one. `fdperf.cfg-vertex` programs WORKING, `fdperf.cfg-bv` and `fdperf.cfg-vpc3` program
   the two stall selectors, so the columns are filled by different arms and each is read only
   where it was sampled.
2. Does a VPC counter need the divider that SP and TP get? It does not if no VPC reading ever
   exceeds the core clock, so the script prints the largest `VPC_BUSY_CYCLES / CP_ALWAYS_COUNT`
   found in any window of any dump (and SP, which does exceed it, as the contrast).
3. Do `VPC_SP_COMPONENTS` (VPC selector 10) and `SP_EXPORT_VPC_TRANS` (SP selector 48) describe
   two sides of one stream, as the cfg comments say? Every cfg that has one has the other, so
   the two can be compared inside the same window; the script prints their ratio per arm and the
   agreement over all windows, against a control pair of known-different counters
   (`PC_IA_PRIMITIVES` / `TSE_INPUT_PRIM`, which 40.32 showed to agree to 1e-5 and to be two
   different quantities).

Counters come from `scripts/fdperf_sections.py`, which keeps the ordinary group's value when a
name also appears in the BV section and reports the BV-only names as unmeasured - so nothing in
this table is a BV-thread mirror (its rule 1). Per-vertex figures use `VFD_TOTAL_VERTICES`,
falling back to `PC_VS_INVOCATIONS`; on these windows the two are the same number (40.27).

Output is a table plus three footer blocks. Nothing here is a verdict; journal 40.34 reads it.
"""
import argparse
import glob
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdperf_sections import load  # noqa: E402

WINDOW = (20, 105)          # steady window, seconds from the first sample (journal 40's convention)
PIN_MHZ = 676               # a window counts as pinned-clock at or above this CP_ALWAYS_COUNT

COLUMNS = [
    ("VPC_BUSY_CYCLES", "busy/clk"),
    ("VPC_WORKING_CYCLES", "work/busy"),
    ("VPC_VS_BUSY_CYCLES", "vsbusy/busy"),
    ("VPC_VPCRAM_FULL_CYCLES", "RAMfull"),
    ("VPC_WIT_FULL_CYCLES", "WITfull"),
    ("UCHE_WRITE_REQUESTS_VPC", "wreqM/s"),
    ("SP_BUSY_CYCLES", "sp/clk"),
    ("VPC_SP_COMPONENTS", "comp/vert"),
    ("SP_EXPORT_VPC_TRANS", "trans/vert"),
]


def med(samples, name):
    v = [w["PERF_" + name] for w in samples if w.get("PERF_" + name) is not None]
    return st.median(v) if v else None


def windows(samples, any_clock):
    t0 = samples[0]["t"]
    out = []
    for w in samples:
        if not WINDOW[0] <= w["t"] - t0 <= WINDOW[1]:
            continue
        clk = w.get("PERF_CP_ALWAYS_COUNT") or 0
        if not any_clock and clk / 1e6 < PIN_MHZ:
            continue
        out.append(w)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", help="comma-separated arm names, default every dump under results/games/re4")
    ap.add_argument("--any-clock", action="store_true", help=f"keep windows below {PIN_MHZ} MHz")
    args = ap.parse_args()

    if args.arms:
        tags = args.arms.split(",")
    else:
        tags = sorted(f.split("/")[-2] for f in glob.glob("results/games/re4/*/fdperf-raw.txt"))

    head = f"{'arm':22s} {'win':>3s} {'clk':>4s} {'bin':>3s} " + " ".join(f"{n:>10s}" for _, n in COLUMNS)
    print(head)
    print("-" * len(head))

    ratio_all = []
    ctrl_all = []
    max_vpc = (0.0, None)
    max_sp = (0.0, None)

    for tag in tags:
        path = f"results/games/re4/{tag}/fdperf-raw.txt"
        if not os.path.exists(path):
            continue
        try:
            samples, _unmeasured, _dropped = load(path)
        except Exception as exc:                                    # noqa: BLE001
            print(f"{tag:22s} unreadable: {exc}")
            continue
        for w in samples:
            clk = w.get("PERF_CP_ALWAYS_COUNT")
            if not clk:
                continue
            vpc, sp = w.get("PERF_VPC_BUSY_CYCLES"), w.get("PERF_SP_BUSY_CYCLES")
            if vpc and (vpc / clk,) and (vpc / clk) > max_vpc[0]:
                max_vpc = (vpc / clk, tag)
            if sp and (sp / clk) > max_sp[0]:
                max_sp = (sp / clk, tag)

        rows = windows(samples, args.any_clock)
        if not rows:
            print(f"{tag:22s} {0:3d} no window passes the filter ({len(samples)} samples)")
            continue
        m = {name: med(rows, name) for name, _ in COLUMNS}
        clk = med(rows, "CP_ALWAYS_COUNT")
        vert = med(rows, "VFD_TOTAL_VERTICES") or med(rows, "PC_VS_INVOCATIONS")
        binned = sum(1 for w in rows if (w.get("PERF_VSC_INPUT_TILES") or 0) > 0)

        cells = []
        for name, _ in COLUMNS:
            v = m[name]
            if v is None or not clk:
                cells.append(f"{'-':>10s}")
            elif name == "VPC_BUSY_CYCLES":
                cells.append(f"{v / clk:10.3f}")
            elif name == "VPC_WORKING_CYCLES":
                busy = m["VPC_BUSY_CYCLES"]
                cells.append(f"{v / busy:10.3f}" if busy else f"{'-':>10s}")
            elif name == "VPC_VS_BUSY_CYCLES":
                busy = m["VPC_BUSY_CYCLES"]
                cells.append(f"{v / busy:10.3f}" if busy else f"{'-':>10s}")
            elif name in ("VPC_VPCRAM_FULL_CYCLES", "VPC_WIT_FULL_CYCLES"):
                busy = m["VPC_BUSY_CYCLES"]
                cells.append(f"{100 * v / busy:9.1f}%" if busy else f"{'-':>10s}")
            elif name in ("VPC_SP_COMPONENTS", "SP_EXPORT_VPC_TRANS"):
                cells.append(f"{v / vert:10.3f}" if vert else f"{'-':>10s}")
            elif name == "UCHE_WRITE_REQUESTS_VPC":
                cells.append(f"{v / 1e6:10.3f}")
            else:
                cells.append(f"{v / clk:10.3f}")
        print(f"{tag:22s} {len(rows):3d} {clk / 1e6:4.0f} {binned:3d} " + " ".join(cells))

        for w in rows:
            a, b = w.get("PERF_VPC_SP_COMPONENTS"), w.get("PERF_SP_EXPORT_VPC_TRANS")
            if a and b:
                ratio_all.append(a / b)
            c, d = w.get("PERF_PC_IA_PRIMITIVES"), w.get("PERF_TSE_INPUT_PRIM")
            if c and d:
                ctrl_all.append(c / d)

    def agree(vals, label):
        if not vals:
            print(f"  {label}: no window carries the pair")
            return
        s = sorted(vals)
        q = lambda p: s[min(len(s) - 1, int(p * len(s)))]  # noqa: E731
        tight = sum(1 for v in vals if abs(v - 1.0) <= 1e-4)
        worst = max(abs(v - 1.0) for v in vals)
        print(f"  {label}: {len(vals)} windows, median {q(0.5):.5f}, p10 {q(0.1):.5f}, p90 {q(0.9):.5f}, "
              f"within 1e-4 of 1.0: {tight} ({100 * tight / len(vals):.1f} %), largest gap {worst:.1e}")

    print("\nDivider check, every window of every dump read (a multi-instance block exceeds the clock):")
    print(f"  max VPC_BUSY_CYCLES / CP_ALWAYS_COUNT = {max_vpc[0]:.4f}  ({max_vpc[1]})")
    print(f"  max SP_BUSY_CYCLES  / CP_ALWAYS_COUNT = {max_sp[0]:.4f}  ({max_sp[1]})  <- SP is 12-wide, /12")

    print("\nDo the two export counters agree?")
    agree(ratio_all, "VPC_SP_COMPONENTS / SP_EXPORT_VPC_TRANS")
    agree(ctrl_all, "control PC_IA_PRIMITIVES / TSE_INPUT_PRIM")
    print("  A ratio pinned at 1.0 to the control pair's precision means one signal, not two sides.")


if __name__ == "__main__":
    main()
