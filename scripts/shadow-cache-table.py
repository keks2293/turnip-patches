#!/usr/bin/env python3
"""Curated evidence table for the in-game Shadow Cache A/B (journal 40.19, chain25/chain26).

    scripts/shadow-cache-table.py > results/games/re4/shadow-cache-ab.txt

The question this table answers: the 15 fps cluster of journals 38-40 was measured with the game's
`AppShadowCache=0` (the value in this install's `local_config.ini`), and chain25 changed the shadow
keys along with the cache.  Four arms separate the two: the cache is the only key that moves anything.

Reads only committed files: `results/games/re4/<arm>/fdperf-raw.txt`, `results/games/re4/fps-<arm>.csv`
and the `# game settings:` line that the chain appended to `<arm>/meta.txt` - the settings column is
read from the artifact, so the table cannot claim a setting the run did not have.

Rules (docs/fdperf-a7xx.md, journal 40):
  * counter columns are means over 1 s windows whose `PERF_CP_ALWAYS_COUNT` is within 1 % of the
    pinned 680 MHz; the number of windows kept and dropped is printed, an off-clock window would
    dilute every duty cycle in the row;
  * fps is p25 of MangoHud's `elapsed` in two fixed windows; MangoHud's clock runs ~35 s behind the
    chain's launch line, so 95-150 s is the steady stretch of a 210 s session;
  * `prims/frame` divides the per-second primitive rate by the p25 of the same arm - it is the only
    column that compares work across arms of different frame rates, and it is a quotient of two
    measured numbers, not a counter;
  * the drop counters of `cfg-tse3` are 3 of the 4 TSE slots (budget 4), so the reason for the drop
    is not in this table - see journal 40.2.
"""
import csv
import os
import statistics
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from fdperf_sections import load, window

ARMS = ["sh-c0", "sh-c1", "sh-q0", "sh-q3"]
PIN = 680e6
FPS_WINDOWS = [(70, 84), (95, 150)]
LO, HI = 20, 105


def settings(arm):
    """The `# game settings:` line the chain appended to meta.txt, or `NOT RECORDED`."""
    path = f"results/games/re4/{arm}/meta.txt"
    if not os.path.exists(path):
        return "NOT RECORDED"
    for line in open(path):
        if line.startswith("# game settings:"):
            return line.split(":", 1)[1].strip()
    return "NOT RECORDED"


def fps_p25(path, lo, hi):
    if not os.path.exists(path):
        return None, 0
    lines = open(path).read().splitlines()
    v = []
    for r in csv.DictReader(lines[2:]):
        try:
            t, f = float(r["elapsed"]) / 1e9, float(r["fps"])
        except (KeyError, TypeError, ValueError):
            continue
        if lo <= t < hi and 0.5 < f < 1000:
            v.append(f)
    if not v:
        return None, 0
    return sorted(v)[len(v) // 4], len(v)


def counters(arm):
    samples, _un, _dr = load(f"results/games/re4/{arm}/fdperf-raw.txt")
    span = window(samples, LO, HI)          # t_rel = s["t"] - samples[0]["t"], scripts/fdperf_sections.py
    win = [s for s in span
           if s.get("PERF_CP_ALWAYS_COUNT")
           and abs(s["PERF_CP_ALWAYS_COUNT"] - PIN) / PIN < 0.01]
    dropped = len(span) - len(win)

    def mean(key):
        v = [s[key] for s in win if isinstance(s.get(key), (int, float))]
        return statistics.mean(v) if v else None

    return {
        "windows": (len(win), dropped),
        "tse_in": mean("PERF_TSE_INPUT_PRIM"),
        "tse_vis": mean("PERF_TSE_OUTPUT_VISIBLE_PRIM"),
        "tse_0px": mean("PERF_TSE_ZERO_PIXEL_PRIM"),
        "vpc_busy": mean("PERF_VPC_BUSY_CYCLES"),
        "pc_stall_vpc": mean("PERF_PC_STALL_CYCLES_VPC"),
        "pc_busy": mean("PERF_PC_BUSY_CYCLES"),
        "vbif_ch0": mean("PERF_UCHE_VBIF_READ_BEATS_CH0"),
        "vbif_ch1": mean("PERF_UCHE_VBIF_READ_BEATS_CH1"),
    }


def main():
    print("# Shadow Cache A/B in Resident Evil 4 Gold Edition (re4.exe), D3D12 via vkd3d-proton 3.1.0,")
    print("#       2560x1440 display mode; proton-cachyos-11.0-arm64.  Registry: results/games/README.md")
    print("# driver: build/out/libvulkan_freedreno.so sha256 4c3cdb210082 (ship stack) in all four arms;")
    print("#       the delta between arms is the game's own local_config.ini, not the driver or the env")
    print("# sampler: tools/fdperf/fdperf.cfg-tse3, counter window t_rel 20-105 s at the pinned clock")
    print("# chains: /tmp/opencode/chain25.sh (sh-q0, sh-q3), /tmp/opencode/chain26.sh (sh-c0, sh-c1)")
    print("# regenerate: scripts/shadow-cache-table.py > results/games/re4/shadow-cache-ab.txt")
    print("")
    print("| arm | game settings | p25 fps 70-84s | p25 fps 95-150s | prims/frame (TSE in / p25) |"
          " TSE in M/s | TSE vis % | TSE 0-pixel M/s | VPC busy % | PC stall on VPC % | DRAM read GB/s |"
          " windows kept/dropped |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")

    for arm in ARMS:
        c = counters(arm)
        p70, n70 = fps_p25(f"results/games/re4/fps-{arm}.csv", *FPS_WINDOWS[0])
        p95, n95 = fps_p25(f"results/games/re4/fps-{arm}.csv", *FPS_WINDOWS[1])

        def num(v, fmt="%8.2f"):
            return fmt % v if v is not None else "      n/a"

        prims_frame = c["tse_in"] / p95 / 1e6 if c["tse_in"] and p95 else None
        vis = (100.0 * c["tse_vis"] / c["tse_in"]) if c["tse_vis"] and c["tse_in"] else None
        dram = (c["vbif_ch0"] + c["vbif_ch1"]) * 16 / 1e9 if c["vbif_ch0"] is not None else None
        vpc = 100.0 * c["vpc_busy"] / PIN if c["vpc_busy"] else None
        pc = (100.0 * c["pc_stall_vpc"] / c["pc_busy"]) if c["pc_stall_vpc"] and c["pc_busy"] else None

        print(f"| {arm} | {settings(arm)} | {num(p70, '%6.2f')} (n={n70}) | {num(p95, '%6.2f')} (n={n95}) |"
              f" {num(prims_frame, '%6.2f')} M | {num(c['tse_in'] / 1e6 if c['tse_in'] else None)} |"
              f" {num(vis, '%7.2f')} | {num(c['tse_0px'] / 1e6 if c['tse_0px'] else None)} |"
              f" {num(vpc, '%6.2f')} | {num(pc, '%6.2f')} | {num(dram, '%8.2f')} |"
              f" {c['windows'][0]} / {c['windows'][1]} |")

    print("")
    print("prims/frame is a quotient (per-second TSE input over p25 fps of the same arm), not a counter;")
    print("it is the column that compares two arms whose frame rates differ.")


if __name__ == "__main__":
    main()
