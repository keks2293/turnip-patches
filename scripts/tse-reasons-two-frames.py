#!/usr/bin/env python3
"""Why the frame's primitives are discarded, at the game's two shadow settings.

    scripts/tse-reasons-two-frames.py > results/games/re4/tse-reasons-two-frames.txt

Journal 40.2 split the discard of the *uncached* frame into reasons (21.1 % trivially rejected,
17.7 % face-culled, 0.33 % zero-area, 0.14 % clipped). Journal 40.19 then found the game's own Shadow
Cache, which removes half the frame's primitives, so the split has to be re-measured on the frame the
game actually wants to run (arm `tse2-cacheon`, chain29): if the surviving primitives are discarded
for different reasons, the remaining lever is different too.

The TSE counter budget is 4 (`docs/fdperf-a7xx.md`, "hw counter budgets"), so the four reason
counters and the input/visible/zero-pixel counters cannot be sampled in one run. Each frame therefore
uses two arms, both named in the footer: the `tse2` arms give the reasons and `PERF_PC_IA_PRIMITIVES`
(the input, an IA counter that is not in the TSE budget), the `cfg-lrz`/`cfg-tse3` shape arms give
input, visible and zero-pixel. Shares are therefore computed across sessions, and the two sessions of
one frame differ by run-to-run noise, which is why the input column is printed for both.

Duty cycles and rates over 1 s windows within `t_rel` 20-105 s whose `PERF_CP_ALWAYS_COUNT` is within
1 % of the pinned 680 MHz; fps is p25 of MangoHud's `elapsed` over 95-150 s.
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

# frame -> (arm with the reason counters, arm with input/visible/zero-pixel, fps csv of the first)
FRAMES = [
    ("Shadow Cache off", "tse2-tse2", "tse-tse1", "fps-tse2.csv"),
    ("Shadow Cache on", "tse2-cacheon", "lrz-base", "fps-tse2-cacheon.csv"),
]
REASONS = [
    ("trivially rejected", "PERF_TSE_TRIVAL_REJ_PRIM"),
    ("face-culled", "PERF_TSE_FACENESS_CULLED_PRIM"),
    ("zero area", "PERF_TSE_ZERO_AREA_PRIM"),
    ("clipped", "PERF_TSE_CLIPPED_PRIM"),
]
SHAPE = [
    ("IA input (reason arm)", "PERF_PC_IA_PRIMITIVES", "reasons"),
    ("TSE input", "PERF_TSE_INPUT_PRIM", "shape"),
    ("TSE visible", "PERF_TSE_OUTPUT_VISIBLE_PRIM", "shape"),
    ("TSE zero-pixel", "PERF_TSE_ZERO_PIXEL_PRIM", "shape"),
]


def means(arm):
    samples, _u, _d = load(os.path.join(BASE, arm, "fdperf-raw.txt"))
    win = [s for s in window(samples, LO, HI)
           if s.get("PERF_CP_ALWAYS_COUNT") and abs(s["PERF_CP_ALWAYS_COUNT"] - PIN) / PIN < 0.01]

    def mean(key):
        v = [s[key] for s in win if isinstance(s.get(key), (int, float))]
        return statistics.mean(v) if v else None

    return win, mean


def p25(fps_csv):
    path = os.path.join(BASE, fps_csv)
    if not os.path.exists(path):
        return None
    fps = []
    for r in csv.DictReader(open(path).read().splitlines()[2:]):
        try:
            t, f = float(r["elapsed"]) / 1e9, float(r["fps"])
        except (KeyError, TypeError, ValueError):
            continue
        if 95 <= t < 150 and 0.5 < f < 1000:
            fps.append(f)
    return sorted(fps)[len(fps) // 4] if fps else None


def main():
    print("# Why Resident Evil 4 Gold Edition's primitives are discarded, at its two shadow settings")
    print("#       (re4.exe, D3D12 via vkd3d-proton 3.1.0, 2560x1440).  Registry: results/games/README.md")
    print("# driver: build/out/libvulkan_freedreno.so sha256 4c3cdb210082 (ship stack) in every arm, no")
    print("#       environment delta - the difference is one key of the game's local_config.ini")
    print("# samplers: tools/fdperf/fdperf.cfg-tse2 (reasons + PC_IA_PRIMITIVES) and")
    print("#       tools/fdperf/fdperf.cfg-lrz (input/visible/zero-pixel + LRZ); 1 s windows, t_rel")
    print("#       20-105 s, pinned clock; fps = p25 over MangoHud elapsed 95-150 s")
    print("# regenerate: scripts/tse-reasons-two-frames.py > results/games/re4/tse-reasons-two-frames.txt")
    print()

    cols = []
    for label, rarm, sarm, fps_csv in FRAMES:
        rwin, rmean = means(rarm)
        swin, smean = means(sarm)
        cols.append((label, rarm, sarm, rwin, rmean, smean, p25(fps_csv)))

    # four columns: the two frames, each as a rate and as a share of that frame's IA input
    print("| counter | " + " | ".join(f"{c[0]}: M/s | {c[0]}: % of input |" for c in cols))
    print("|---|" + "---|" * (2 * len(cols)))

    def row(label, vals, dens, rate_fmt="{:7.2f} M/s", per_frame_blank_share=False):
        cells = []
        for v, d in zip(vals, dens):
            cells.append("     n/a" if v is None else rate_fmt.format(v / 1e6))
            if per_frame_blank_share or v is None or not d:
                cells.append("")
            else:
                cells.append(f"{100.0 * v / d:5.2f} %")
        print(f"| {label} | " + " | ".join(cells) + " |")

    for label, key, which in SHAPE:
        vals = [((rmean if which == "reasons" else smean)(key))
                for _l, _r, _s, _w, rmean, smean, _f in cols]
        row(label, vals, [None] * len(cols), per_frame_blank_share=True)

    # the denominator every share uses: the IA input of the arm that sampled the reasons
    dens = [rmean("PERF_PC_IA_PRIMITIVES") for _l, _r, _s, _w, rmean, _sm, _f in cols]
    for label, key in REASONS:
        vals = [rmean(key) for _l, _r, _s, _w, rmean, _sm, _f in cols]
        row(label, vals, dens)

    # how much of the input the reasons explain, against the measured drop
    sums = [sum((rmean(k) or 0) for _lb, k in REASONS)
            for _l, _r, _s, _w, rmean, _sm, _f in cols]
    row("sum of the four reasons", sums, dens)
    drops = []
    for _l, _r, _s, _w, _rmean, smean, _f in cols:
        inp, vis = smean("PERF_TSE_INPUT_PRIM"), smean("PERF_TSE_OUTPUT_VISIBLE_PRIM")
        drops.append(None if inp is None or vis is None else inp - vis)
    row("drop = input - visible (shape arm)", drops, dens)
    print("| p25 fps (reason arm) |" +
          "".join(f" {c[6]:15.2f} |  |" if c[6] else "            n/a |  |" for c in cols))
    print("| 1 s windows kept |" +
          "".join(f" {len(c[3]):15d} |  |" for c in cols))
    print()
    for label, rarm, sarm, _w, _r, _s, _f in cols:
        print(f"`{label}` - reasons and input from `{rarm}`, visible/zero-pixel from `{sarm}`;")
        print(f"    the two are different sessions of the same scene, hence the input column above.")
    print("Semantics: the reason counter names are read from")
    print("`src/freedreno/registers/adreno/a7xx_perfcntrs.xml` (singular `ZERO_AREA_PRIM`,")
    print("`CLIPPED_PRIM`, `TRIVAL_REJ_PRIM`, `FACENESS_CULLED_PRIM`); the XML carries no descriptions,")
    print("so a reason is named, not explained (journal 40.2, same caveat).")


if __name__ == "__main__":
    sys.exit(main())
