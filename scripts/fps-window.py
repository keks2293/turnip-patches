#!/usr/bin/env python3
"""p25 of fps over the standard window of a MangoHud CSV (docs/analysis.md 13.0).

Window: elapsed 40-50 s from launch (40 s intro + 10 s of the 3D menu). The
`elapsed` column is in NANOSECONDS in this MangoHud build: filtering it as
seconds silently yields an empty window.

Comparisons are only valid window-to-window with the same driver build
(sha256 of build/out/libvulkan_freedreno.so) - 13.0.

Usage: scripts/fps-window.py <csv> [lo_s] [hi_s]
"""
import csv
import statistics
import sys


def main() -> int:
    path = sys.argv[1]
    lo = float(sys.argv[2]) if len(sys.argv) > 2 else 40.0
    hi = float(sys.argv[3]) if len(sys.argv) > 3 else 50.0

    with open(path) as f:
        lines = f.read().splitlines()
    # MangoHud CSV layout: two metadata rows, then the header, then data.
    rows = list(csv.DictReader(lines[2:]))

    data = []
    for r in rows:
        try:
            t = float(r["elapsed"]) / 1e9
            fps = float(r["fps"])
            ft = float(r["frametime"])
        except (KeyError, TypeError, ValueError):
            continue
        # garbage rows at startup report fps ~1e-05; the sanity bound is not
        # the old "fps < 30" filter, the window already excludes menus/loading
        if 0.5 < fps < 1000:
            data.append((t, fps, ft, r))
    if not data:
        print(f"{path}: no usable samples", file=sys.stderr)
        return 1

    sel = [d for d in data if lo <= d[0] < hi]
    span = f"{data[0][0]:.1f}..{data[-1][0]:.1f}s"
    if not sel:
        print(f"{path}: window {lo:g}-{hi:g}s EMPTY (data span {span})", file=sys.stderr)
        return 1

    fps = sorted(d[1] for d in sel)
    p25 = fps[len(fps) // 4]
    clocks = sorted({round(float(d[3]["gpu_core_clock"])) for d in sel if d[3].get("gpu_core_clock")})
    gpu_load = statistics.mean(float(d[3]["gpu_load"]) for d in sel if d[3].get("gpu_load"))
    swap = statistics.mean(float(d[3]["swap_used"]) / 1024 for d in sel if d[3].get("swap_used"))

    name = path.rsplit("/", 1)[-1]
    print(f"{name}: span {span}, window {lo:g}-{hi:g}s")
    print(f"  n={len(sel)} p25={p25:.2f} mean={statistics.mean(fps):.2f} "
          f"min={fps[0]:.1f} max={fps[-1]:.1f}")
    print(f"  frametime={statistics.mean(d[2] for d in sel):.1f}ms "
          f"clocks={clocks} gpu_load={gpu_load:.0f}% swap={swap:.2f}GiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
