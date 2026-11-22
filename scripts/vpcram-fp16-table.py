#!/usr/bin/env python3
"""Table for chain35: the VPC's own RAM pressure with and without the mediump-to-fp16 lowering.

    scripts/vpcram-fp16-table.py > results/games/re4/vpcram-fp16.txt

The chain (see /tmp/opencode/chain35.sh, recorded in each arm's meta.txt) asks whether the volume of
per-vertex attribute data explains `VPC_VPCRAM_FULL_CYCLES` sitting at ~51 % of the VPC's busy time
(journal 40.5), by turning off the one driver switch that changes what a varying costs - the fp16
lowering of mediump fragment inputs, on by default for gen >= 6 (`ir3_nir.c:1062`), off with
`IR3_SHADER_DEBUG=nofp16` (`ir3_compiler.c:30`).

This script owns no arithmetic. It runs the two committed tools that own the numbers and pastes their
output under one heading per arm:

  * `scripts/fdperf-vpcram-ratios.py <dump> 20 105` for the counters (it reads only the first section
    of the dump and prints a counter it cannot see as `-`; the semantics caveat - the a7xx XML names
    these counters without any `<desc>` - is owned by that script and by docs/fdperf-a7xx.md);
  * `scripts/fps-window.py <csv> 95 150` for p25 fps in the standard 95-150 s window.

So a correction to the counter reading or to the fps window lands in those scripts and this table
regenerates; nothing here has to be re-checked by hand.
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "results/games/re4")
ARMS = [
    ("vr4-c0-base", "AppShadowCache=0", "no env"),
    ("vr4-c0-nofp16", "AppShadowCache=0", "IR3_SHADER_DEBUG=nofp16"),
    ("vr4-c1-base", "AppShadowCache=1", "no env"),
]


def run(argv):
    p = subprocess.run(argv, cwd=REPO, capture_output=True, text=True)
    text = (p.stdout + p.stderr).rstrip()
    return text if text else "    (no output)"


def main() -> int:
    print("# The VPC's own RAM, with and without the mediump-to-fp16 lowering (Resident Evil 4, re4.exe,")
    print("# D3D12 via vkd3d-proton 3.1.0, 2560x1440; driver sha256 4c3cdb210082 in all three arms).")
    print("# regenerate: scripts/vpcram-fp16-table.py > results/games/re4/vpcram-fp16.txt")
    print("# chain: /tmp/opencode/chain35.sh; sampler tools/fdperf/fdperf.cfg-vpc3;")
    print("#       counters over t_rel 20-105 s, fps p25 over elapsed 95-150 s")
    print("# ownership: the counter reading is scripts/fdperf-vpcram-ratios.py, the fps window is")
    print("#       scripts/fps-window.py; this file runs both and pastes the result.")

    for tag, game, env in ARMS:
        dump = os.path.join(OUT, tag, "fdperf-raw.txt")
        csv = os.path.join(OUT, f"fps-{tag}.csv")
        print(f"\n=== {tag}   ({game}; {env})")
        for path, label in ((dump, "counters"), (csv, "fps")):
            if not os.path.exists(path):
                print(f"    {label}: {os.path.relpath(path, REPO)} NOT PRESENT (arm did not run?)")
        if os.path.exists(dump):
            print(run([sys.executable, "scripts/fdperf-vpcram-ratios.py",
                       os.path.relpath(dump, REPO), "20", "105"]))
        if os.path.exists(csv):
            print(run([sys.executable, "scripts/fps-window.py",
                       os.path.relpath(csv, REPO), "95", "150"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
