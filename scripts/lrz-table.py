#!/usr/bin/env python3
"""What LRZ kills in Resident Evil 4, and whether Turnip's conservative LRZ is the reason.

    scripts/lrz-table.py > results/games/re4/lrz-killed.txt

The question comes from journal 40.2's split of the frame, re-read on the cached-shadow frame by 40.22:
about 80 % of the submitted primitives produce no pixel, and most of them are not culled at all - they
reach the rasterizer and come back as `TSE_ZERO_PIXEL_PRIM`. Depth rejection before pixel shading is
LRZ's job, and its counter (`LRZ_PRIM_KILLED_BY_LRZ`, LRZ select 12) had never been programmed on a
game run in this repository. The second arm flips the one driver knob that decides how LRZ is used:
`tu_lrz.cc:1524`/`:1533` take the conservative path (an upper-bound depth range) unless driconf's
`tu_disable_conservative_lrz` is set, delivered here through `$DRIRC_CONFIGDIR`
(`results/lrz-drirc-delivery.log` records how delivery was proved, and its limits).

The name spelling matters and cost one chain: the accepted names in this tree are `nolrz` and
`nolrzfc` (`src/freedreno/vulkan/tu_util.cc:31-32`, bits 7 and 18 of `tu_util.h:47`/`:58`). Chain31
ran `nolz`/`nolzfc`, which do not exist, and an unknown TU_DEBUG name is skipped silently - those two
arms print `TU_DEBUG=0x1` and are kept here as the control for what a typo looks like.

Semantics warning, read from the register description rather than assumed: `a7xx_perfcntrs.xml`
names LRZ counters and gives them a select value, and nothing else - there is no `<desc>` for
`LRZ_PRIM_KILLED_BY_LRZ` or `LRZ_TOTAL_PIXEL` anywhere in the tree. So the killed count is quoted per
second and as a share of `TSE_INPUT_PRIM`, both of which are counts of primitives like the input
counter, and `LRZ_TOTAL_PIXEL` is not converted to any unit. Cycle counters are % of the core clock.

Rules as elsewhere here: counter means over 1 s windows within `t_rel` 20-105 s whose
`PERF_CP_ALWAYS_COUNT` is within 1 % of the pinned 680 MHz (the dump's median clock is printed); fps
is p25 of MangoHud's `elapsed` over 95-150 s. Only the ordinary counter half of each dump is read
(`scripts/fdperf_sections.py`).
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

# An arm whose dump is absent prints `n/a`: the arms ran in three chains (30 = the driconf option,
# 31 = the two mis-spelled switches, 32 = the two real ones), so one table covers all of them.
ARMS = [
    ("lrz-base", "chain30, no env: LRZ and its fast clear as the driver configures them"),
    ("lrz-nocons", "chain30, DRIRC_CONFIGDIR with tu_disable_conservative_lrz=true"),
    ("lrz-base2", "chain31, no env again - the repeat that puts a number on the session spread"),
    ("lrz-nolz", "chain31, TU_DEBUG=startup,nolz - the name does not exist, mask stayed 0x1"),
    ("lrz-nolzfc", "chain31, TU_DEBUG=startup,nolzfc - the name does not exist, mask stayed 0x1"),
    ("lrz-nolrz", "chain32, TU_DEBUG=startup,nolrz (mask 0x81): LRZ off for the device, tu_device.cc:3388"),
    ("lrz-nolrzfc", "chain32, TU_DEBUG=startup,nolrzfc (mask 0x40001): LRZ on, fast clear off, tu_lrz.cc:291-292"),
    ("lrz-nolrz2", "chain33, repeat of nolrz - the second observation of the kill counter at zero"),
    ("lrz-nolrzfc2", "chain33, repeat of nolrzfc - the arm with a full set of pinned-clock windows"),
]

CYCLES = [
    # `% of the core` is counter cycles / 680 MHz.  A value above 100 % is not an error and not an
    # occupancy: the counter accumulates over replicated sub-units.  How many sub-units the RB group
    # has is not stated in `a7xx_perfcntrs.xml`, so those rows are quoted for their ratio between the
    # arms only, never as "x % of the RB units".
    ("LRZ busy", "PERF_LRZ_BUSY_CYCLES"),
    ("RAS busy", "PERF_RAS_BUSY_CYCLES"),
    ("RAS stall on LRZ", "PERF_RAS_STALL_CYCLES_LRZ"),
    ("LRZ intf working (RAS)", "PERF_RAS_LRZ_INTF_WORKING_CYCLES"),
    ("RB busy (sums sub-units)", "PERF_RB_BUSY_CYCLES"),
    ("RB starve on LRZ tile (sums sub-units)", "PERF_RB_STARVE_CYCLES_LRZ_TILE"),
    ("RB stall on HLSQ (sums sub-units)", "PERF_RB_STALL_CYCLES_HLSQ"),
    ("CCU stall on depth return (sums sub-units)", "PERF_CCU_STALL_CYCLES_RB_DEPTH_RETURN"),
    ("VPC busy", "PERF_VPC_BUSY_CYCLES"),
    ("TSE busy", "PERF_TSE_BUSY_CYCLES"),
]
EVENTS = [
    ("TSE input prim", "PERF_TSE_INPUT_PRIM"),
    ("TSE visible prim", "PERF_TSE_OUTPUT_VISIBLE_PRIM"),
    ("TSE zero-pixel prim", "PERF_TSE_ZERO_PIXEL_PRIM"),
    ("LRZ killed prim", "PERF_LRZ_PRIM_KILLED_BY_LRZ"),
    ("LRZ total pixel", "PERF_LRZ_TOTAL_PIXEL"),
]


def mask(arm):
    """The flag mask the driver itself printed in this arm's run log, or ''.

    `TU_DEBUG=startup` makes Turnip log the parsed mask (`tu_util.cc:135`), so this is the delivery
    evidence for a `TU_DEBUG` arm: an unknown name is skipped silently and the mask then shows only
    the `startup` bit.  For arms with no `TU_DEBUG` the run log carries no such line, which is itself
    the answer - those arms differ by game setting or driconf, not by debug flags.
    """
    path = os.path.join(BASE, f"game-patched-{arm}.log")
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as fh:
        for line in fh:
            found = line.find(b"TU_DEBUG=0x")
            if found >= 0:
                token = line[found + len(b"TU_DEBUG="):].split()[0]
                return token.decode(errors="replace").strip()
    return ""


def read(arm):
    path = os.path.join(BASE, arm, "fdperf-raw.txt")
    if not os.path.exists(path):
        return [], 0.0, (lambda _key: None), None
    samples, _u, _d = load(path)
    win = [s for s in window(samples, LO, HI)
           if s.get("PERF_CP_ALWAYS_COUNT") and abs(s["PERF_CP_ALWAYS_COUNT"] - PIN) / PIN < 0.01]
    clock = statistics.median([s["PERF_CP_ALWAYS_COUNT"] for s in win]) if win else 0

    def mean(key):
        v = [s[key] for s in win if isinstance(s.get(key), (int, float))]
        return statistics.mean(v) if v else None

    path = os.path.join(BASE, f"fps-{arm}.csv")
    p25 = None
    if os.path.exists(path):
        fps = []
        for r in csv.DictReader(open(path).read().splitlines()[2:]):
            try:
                t, f = float(r["elapsed"]) / 1e9, float(r["fps"])
            except (KeyError, TypeError, ValueError):
                continue
            if 95 <= t < 150 and 0.5 < f < 1000:
                fps.append(f)
        p25 = sorted(fps)[len(fps) // 4] if fps else None
    return win, clock, mean, p25


TRAFFIC_ARMS = [
    ("tr-lrzfc-on", "chain34, no env: LRZ fast clear on, as `a7xx_base` programs it"),
    ("tr-lrzfc-off", "chain34, TU_DEBUG=startup,nolrzfc: fast clear off, LRZ itself still on"),
]

# Beats x 16 B, the conversion `docs/fdperf-a7xx.md` owns (same as `scripts/fdperf-traffic-table.py`).
# A fast clear replaces a pixel write with a metadata write, so the counters that would move are the
# RB depth writes and the DRAM write beats, not any of the cycle counters above.
TRAFFIC = [
    ("depth writes (RB)", ["PERF_RB_Z_WRITE"], 1e-6, "M/s"),
    ("depth reads (RB)", ["PERF_RB_Z_READ"], 1e-6, "M/s"),
    ("colour writes (RB)", ["PERF_RB_C_WRITE"], 1e-6, "M/s"),
    ("colour reads (RB)", ["PERF_RB_C_READ"], 1e-6, "M/s"),
    ("DRAM read GB/s", ["PERF_UCHE_VBIF_READ_BEATS_CH0", "PERF_UCHE_VBIF_READ_BEATS_CH1"], 16e-9, ""),
    ("DRAM write GB/s", ["PERF_UCHE_VBIF_WRITE_BEATS_CH0", "PERF_UCHE_VBIF_WRITE_BEATS_CH1"], 16e-9, ""),
    ("UBWC read MB/s", ["PERF_UCHE_UBWC_READ_BEATS"], 16e-6, ""),
    ("UBWC write MB/s", ["PERF_UCHE_UBWC_WRITE_BEATS"], 16e-6, ""),
]


def main():
    print("# Does LRZ kill primitives in Resident Evil 4 Gold Edition, and does conservative LRZ stop it")
    print("#       (re4.exe, D3D12 via vkd3d-proton 3.1.0, 2560x1440, game's Shadow Cache on in every arm)")
    print("# driver: build/out/libvulkan_freedreno.so sha256 4c3cdb210082 (ship stack) in every arm.")
    print("#       `lrz-nocons` differs by DRIRC_CONFIGDIR only (delivery and its limits:")
    print("#       results/lrz-drirc-delivery.log); every other non-base arm differs by TU_DEBUG, and the")
    print("#       mask the driver printed is the first row of each table")
    print("# sampler: tools/fdperf/fdperf.cfg-lrz for the first table,")
    print("#       tools/fdperf/fdperf.cfg-traffic for the second; counter window t_rel 20-105 s at the")
    print("#       pinned clock; fps = p25 over MangoHud elapsed 95-150 s")
    print("# regenerate: scripts/lrz-table.py > results/games/re4/lrz-killed.txt")
    print()
    data = {arm: read(arm) for arm, _ in ARMS}

    masks = {arm: mask(arm) for arm, _ in ARMS}
    print("| counter | " + " | ".join(arm for arm, _ in ARMS) + " |")
    print("|---|" + "---|" * len(ARMS))
    print("| `TU_DEBUG` mask in the run log | " +
          " | ".join(f"`{masks[arm]}`" if masks[arm] else "     none" for arm, _ in ARMS) + " |")
    for label, key in CYCLES:
        cells = []
        for arm, _ in ARMS:
            _win, _clk, mean, _p25 = data[arm]
            m = mean(key)
            cells.append(f"{100.0 * m / PIN:7.2f} %" if m is not None else "     n/a")
        print(f"| {label}, % of the core | " + " | ".join(cells) + " |")
    for label, key in EVENTS:
        cells = []
        for arm, _ in ARMS:
            _win, _clk, mean, _p25 = data[arm]
            m = mean(key)
            cells.append(f"{m / 1e6:7.2f} M/s" if m is not None else "     n/a")
        print(f"| {label} | " + " | ".join(cells) + " |")
    for label, num, den in (("visible share of input", "PERF_TSE_OUTPUT_VISIBLE_PRIM", "PERF_TSE_INPUT_PRIM"),
                            ("zero-pixel share of input", "PERF_TSE_ZERO_PIXEL_PRIM", "PERF_TSE_INPUT_PRIM"),
                            ("LRZ-killed share of input", "PERF_LRZ_PRIM_KILLED_BY_LRZ", "PERF_TSE_INPUT_PRIM")):
        cells = []
        for arm, _ in ARMS:
            _win, _clk, mean, _p25 = data[arm]
            n, d = mean(num), mean(den)
            cells.append(f"{100.0 * n / d:7.2f} %" if n is not None and d else "     n/a")
        print(f"| {label} | " + " | ".join(cells) + " |")
    cells = [f"{data[arm][3]:8.2f}" if data[arm][3] else "     n/a" for arm, _ in ARMS]
    print("| p25 fps | " + " | ".join(cells) + " |")
    cells = [f"{len(data[arm][0]):11d}" for arm, _ in ARMS]
    print("| 1 s windows kept | " + " | ".join(cells) + " |")
    cells = [f"{data[arm][1] / 1e6:8.0f} MHz" for arm, _ in ARMS]
    print("| dump median clock | " + " | ".join(cells) + " |")
    print()
    for arm, what in ARMS:
        print(f"`{arm}` - {what}")

    print()
    print("## The fast clear needs the traffic sampler, because a fast clear is a bus event (chain34)")
    print()
    print("None of the counters above can see the fast clear: it replaces a pixel write with a metadata")
    print("write, so its price is on the bus and in the RB's write counters, not in a cycle counter.")
    print("`tools/fdperf/fdperf.cfg-traffic` programs those (`RB_Z_WRITE`, the UBWC beats, both VBIF")
    print("channels).  Same window and clock rules as the table above; beats are converted at 16 B per")
    print("`docs/fdperf-a7xx.md`, the same conversion `scripts/fdperf-traffic-table.py` uses.")
    print()
    tdata = {arm: read(arm) for arm, _ in TRAFFIC_ARMS}
    tmasks = {arm: mask(arm) for arm, _ in TRAFFIC_ARMS}
    print("| counter | " + " | ".join(arm for arm, _ in TRAFFIC_ARMS) + " | off against on |")
    print("|---|" + "---|" * (len(TRAFFIC_ARMS) + 1))
    print("| `TU_DEBUG` mask in the run log | " +
          " | ".join(f"`{tmasks[arm]}`" if tmasks[arm] else "     none" for arm, _ in TRAFFIC_ARMS) +
          " |  |")
    for label, names, scale, unit in TRAFFIC:
        vals = []
        for arm, _ in TRAFFIC_ARMS:
            _win, _clk, mean, _p25 = tdata[arm]
            picked = [mean(n) for n in names]
            vals.append(None if any(x is None for x in picked) else sum(picked) * scale)
        cells = ["     n/a" if v is None else f"{v:8.2f}{unit}" for v in vals]
        delta = ("     n/a" if any(v is None for v in vals) or not vals[0]
                 else f"{100.0 * (vals[1] - vals[0]) / vals[0]:+7.2f} %")
        print(f"| {label} | " + " | ".join(cells) + f" | {delta} |")
    p = [tdata[arm][3] for arm, _ in TRAFFIC_ARMS]
    pdelta = f"{100.0 * (p[1] - p[0]) / p[0]:+7.2f} %" if all(p) and p[0] else "     n/a"
    print("| p25 fps | " + " | ".join(f"{v:11.2f}" if v else "         n/a" for v in p) +
          f" | {pdelta} |")
    print("| 1 s windows kept | " +
          " | ".join(f"{len(tdata[arm][0]):11d}" for arm, _ in TRAFFIC_ARMS) + " |  |")
    print("| dump median clock | " +
          " | ".join(f"{tdata[arm][1] / 1e6:8.0f} MHz" for arm, _ in TRAFFIC_ARMS) + " |  |")


if __name__ == "__main__":
    main()
