#!/usr/bin/env python3
"""Vertex-path occupancy of the same game scene at the game's two shadow settings.

    scripts/occupancy-two-frames.py > results/games/re4/occupancy-two-frames.txt

Journal 40.19 measured the game's Shadow Cache as worth 49 % of the frame's primitives (+74 % fps),
which means every block-occupancy number in journals 38-40 describes the *uncached* frame. This table
repeats the 40.14 measurement on the cached one (arm `vpc-cacheon`, chain28) so the "what is the wall
now" question has a number instead of an assumption carried over.

Both arms were sampled with `tools/fdperf/fdperf.cfg-vpc`, the set 40.14's table is built from, on the
ship stack, no environment delta: the difference between them is one line of the game's
`local_config.ini`.  Duty cycles over 1 s windows within `t_rel` 20-105 s whose
`PERF_CP_ALWAYS_COUNT` is within 1 % of the pinned 680 MHz; fps is p25 of MangoHud's `elapsed` over
95-150 s.  `SP_BUSY_CYCLES` and `UCHE_BUSY_CYCLES` are sums over sub-units and therefore exceed 100 %;
they are printed for their ratio between the arms, not as occupancy.
"""
import csv
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdperf_sections import load, window

PIN = 680e6
LO, HI = 20, 105
BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results/games/re4")

# (arm, the game's setting as recorded in its meta.txt, fps csv - the 21.11 tags name the file after
# the tag without the directory prefix, so the path cannot always be derived)
ARMS = [
    ("vpc-vpcbase2", "AppShadowCache=0 (the frame journals 38-40 describe)", "fps-vpcbase2.csv"),
    ("vpc-cacheon",  "AppShadowCache=1 (chain28, queue 25)", "fps-vpc-cacheon.csv"),
]
COUNTERS = [
    ("VPC busy", "PERF_VPC_BUSY_CYCLES"),
    ("VS busy", "PERF_VPC_VS_BUSY_CYCLES"),
    ("PS busy", "PERF_VPC_PS_BUSY_CYCLES"),
    ("PC stall on VPC", "PERF_PC_STALL_CYCLES_VPC"),
    ("TSE input prim/s", "PERF_TSE_INPUT_PRIM"),
    ("SP busy (sum of sub-units)", "PERF_SP_BUSY_CYCLES"),
    ("UCHE busy (sum of sub-units)", "PERF_UCHE_BUSY_CYCLES"),
]


def arm_rows(arm, fps_csv):
    samples, _u, _d = load(os.path.join(BASE, arm, "fdperf-raw.txt"))
    win = [s for s in window(samples, LO, HI)
           if s.get("PERF_CP_ALWAYS_COUNT") and abs(s["PERF_CP_ALWAYS_COUNT"] - PIN) / PIN < 0.01]

    def mean(key):
        v = [s[key] for s in win if isinstance(s.get(key), (int, float))]
        return statistics.mean(v) if v else None

    rows = open(os.path.join(BASE, fps_csv)).read().splitlines()[2:]
    fps = []
    for r in csv.DictReader(rows):
        try:
            t, f = float(r["elapsed"]) / 1e9, float(r["fps"])
        except (KeyError, TypeError, ValueError):
            continue
        if 95 <= t < 150 and 0.5 < f < 1000:
            fps.append(f)
    p25 = sorted(fps)[len(fps) // 4] if fps else None
    return win, mean, p25


def main():
    print("# Vertex-path occupancy of Resident Evil 4 Gold Edition at its two shadow settings")
    print("#       (re4.exe, D3D12 via vkd3d-proton 3.1.0, 2560x1440).  Registry: results/games/README.md")
    print("# driver: build/out/libvulkan_freedreno.so sha256 4c3cdb210082 (ship stack) in both arms,")
    print("#       no environment delta - the difference is one key of the game's local_config.ini")
    print("# sampler: tools/fdperf/fdperf.cfg-vpc; counter window t_rel 20-105 s at the pinned clock;")
    print("#       fps = p25 over MangoHud elapsed 95-150 s")
    print("# regenerate: scripts/occupancy-two-frames.py > results/games/re4/occupancy-two-frames.txt")
    print()
    cols = []
    for arm, setting, fps_csv in ARMS:
        win, mean, p25 = arm_rows(arm, fps_csv)
        cols.append((arm, setting, len(win), p25, mean))

    print("| counter | " + " | ".join(f"{arm} |" for arm, *_ in cols) + " delta |")
    print("|---|" + "---|" * (len(cols) + 1))
    for label, key in COUNTERS:
        vals = []
        for arm, setting, n, p25, mean in cols:
            m = mean(key)
            vals.append(None if m is None else (100.0 * m / PIN if "prim" not in label else m / 1e6))

        def fmt(v):
            if v is None:
                return "  n/a"
            return f"{v:6.2f} M/s" if "prim" in label else f"{v:6.2f} %"

        d = ""
        if vals[0] is not None and vals[1] is not None:
            d = f"{vals[1] - vals[0]:+6.2f}" + (" M/s" if "prim" in label else " pp")
        print(f"| {label} | {fmt(vals[0])} | {fmt(vals[1])} | {d} |")
    print("| p25 fps |" + "".join(f" {c[3]:7.2f} |" for c in cols) + f" {cols[1][3] - cols[0][3]:+6.2f} |")
    print("| 1 s windows kept |" + "".join(f" {c[2]:11d} |" for c in cols) + "  |")
    print()
    for arm, setting, n, p25, mean in cols:
        print(f"`{arm}` - {setting}")
    print("`fps-vpcbase2.csv` is the 21.11 tag (the csv is named after the tag, the directory after")
    print("the cfg family); both files are committed and their `meta.txt` names the counter cfg.")


if __name__ == "__main__":
    sys.exit(main())
