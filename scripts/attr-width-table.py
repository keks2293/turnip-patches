#!/usr/bin/env python3
"""Table for queue 30: what one vertex costs, on the two measured frames.

    scripts/attr-width-table.py > results/games/re4/attribute-width.txt

Journal 40.26 left one quantity that could connect `VPC_VPCRAM_FULL_CYCLES` (71.19 % of the block's own
busy time on the ship frame) to the vertex path: not how many vertices per second - that dependence is
already measured, 16.69 M prims/frame at 15.26 fps against 8.49 M at 26.57 fps
(results/games/re4/shadow-cache-ab.txt) - but how wide the stream per vertex is.  Queue 30 named the
counters, `VPC_SP_COMPONENTS` over `VFD_TOTAL_VERTICES`; both are programmed by
tools/fdperf/fdperf.cfg-vpc, which was run on both frames on 21.11 and 22.11, so the queue is answered
from committed dumps and no new run was needed.

Arms (the frame each one is, is in its meta.txt where meta.txt exists):
  vpc-vpcbase1, vpc-vpcbase2   AppShadowCache=0, 14.19 and 15.25 fps p25 - the 21.11 pair of journal 40.14
  vpc-cacheon                  AppShadowCache=1, 26.74 fps p25 - the ship frame

Like scripts/vpcram-fp16-table.py, this script owns no arithmetic.  It runs the two committed tools that
own the numbers and pastes their output under one heading per arm: `scripts/fdperf-vpc-ratios.py <dump>
20 105` (its `width` line is the per-vertex column set, and it prints a counter the cfg did not program
as `nan`, never as 0) and `scripts/fps-window.py <csv> 95 150` for p25 fps.
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "results/games/re4")
# (arm directory, csv stem, frame, env, when measured).  The csv stem differs from the directory name for
# the 21.11 arms: their counters live in results/games/re4/vpc-vpcbase1/ while their MangoHud log is
# results/games/re4/fps-vpcbase1.csv, so the two names are given separately rather than derived.
ARMS = [
    ("vpc-vpcbase1", "vpcbase1", "AppShadowCache=0", "no env", "21.11, journal 40.14"),
    ("vpc-vpcbase2", "vpcbase2", "AppShadowCache=0", "no env", "21.11, journal 40.14"),
    ("vpc-cacheon", "vpc-cacheon", "AppShadowCache=1", "no env", "22.11, journal 40.21"),
]


def run(argv):
    p = subprocess.run(argv, cwd=REPO, capture_output=True, text=True)
    text = (p.stdout + p.stderr).rstrip()
    return text if text else "    (no output)"


def main() -> int:
    print("# What one vertex costs, on the two measured frames (Resident Evil 4, re4.exe, D3D12 via")
    print("# vkd3d-proton 3.1.0, 2560x1440; ship stack sha256 4c3cdb210082 in all three arms).")
    print("# regenerate: scripts/attr-width-table.py > results/games/re4/attribute-width.txt")
    print("# sampler tools/fdperf/fdperf.cfg-vpc; counters over t_rel 20-105 s, fps p25 over elapsed 95-150 s")
    print("# ownership: the counter reading is scripts/fdperf-vpc-ratios.py (its `width` line), the fps")
    print("#       window is scripts/fps-window.py; this file runs both and pastes the result.")
    print("# the other eight cfg-vpc arms of 21.11 are driver-flag variants of the cache-off frame")
    print("#       (fl111, fl121, cb1, nopref, lrz2, hpbase2, hp50, hp40): 40.14 tabulates their")
    print("#       per-invocation figures, all 2.62 NUM_VPCRAM_WRITE and 0.89 SP_COMPONENTS.")

    for tag, stem, game, env, when in ARMS:
        dump = os.path.join(OUT, tag, "fdperf-raw.txt")
        csv = os.path.join(OUT, f"fps-{stem}.csv")
        print(f"\n=== {tag}   ({game}; {env}; {when})")
        for path, label in ((dump, "counters"), (csv, "fps")):
            if not os.path.exists(path):
                print(f"    {label}: {os.path.relpath(path, REPO)} NOT PRESENT (arm did not run?)")
        if os.path.exists(dump):
            print(run([sys.executable, "scripts/fdperf-vpc-ratios.py",
                       os.path.relpath(dump, REPO), "20", "105"]))
        if os.path.exists(csv):
            print(run([sys.executable, "scripts/fps-window.py",
                       os.path.relpath(csv, REPO), "95", "150"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
