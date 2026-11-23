#!/usr/bin/env python3
"""Give `VPC_SP_COMPONENTS` (VPC 10) and `SP_EXPORT_VPC_TRANS` (SP 48) a unit, from the interface sweep.

    scripts/varyings-table.py                                  # every arm under results/synthetics
    scripts/varyings-table.py results/synthetics/varyings/varyings*/
    scripts/varyings-table.py --lo 5 --hi 40                   # steady windows only
    scripts/varyings-table.py --per-window varyings16           # one window per row

Why these arms can answer what the game dumps could not.  Journal 40.36 settled, from 26 in-game
windows, that id 10 and id 48 are not one signal window by window (44 of 1823 pairs bit-identical,
2.41 %; the sign of the difference flips in all 34 arms), and that nothing in those dumps gives
either of them a unit: the number of vec4 varyings crossing the VS/FS interface is not known for any
committed title.  `tests/vpc-attrbuf.c --varyings=N` knows.  All five arms draw the same 24576 x 8
mesh into the same 768x768 target with the same vertex buffer, and differ in one thing, the interface
width N - which the driver's disassembly confirms before the run (scripts/check-varyings-arms.py,
results/synthetics/varyings/interface-check.txt), because two of the three ways the rig was built
compiled to an interface that was not N (journal 42.1).

What each arm predicts, so the table is a test and not a look.  The mesh is 8192 independent
triangles per instance and shares no vertices, so one delivered vertex is one vertex-shader
invocation and belongs to exactly one primitive.  The VPC therefore ships each vertex once, and the
state it ships is `VPC_VS_CNTL.STRIDE_IN_VPC` = 4N + 4 components wide (the N vec4 plus position):

  | if id 10 counts            | id 10 per delivered vertex, arm N | x stride |
  |----------------------------|-----------------------------------|----------|
  | components (one per)       | 4N + 4              (8 .. 68)      | 1.000    |
  | 64-bit (2-component) units | (4N + 4) / 2        (4 .. 34)      | 0.500    |
  | 128-bit (4-component)      | (4N + 4) / 4        (2 .. 17)      | 0.250    |
  | 256-bit (8-component)      | (4N + 4) / 8        (1 .. 8.5)     | 0.125    |
  | whole vertices             | ~1, or 2 with position separate    | ~0.015   |

The `x stride` column divides the measured per-vertex value by 4N + 4, so it names the candidate
without arithmetic in the reader's head.  The first four are all linear in N, so "it scales with the
interface" was never going to decide anything - only this column can, and the measured value is
0.1250 in every arm.
`SP_EXPORT_VPC_TRANS` is the pixel side's export, one FS invocation per pixel whatever N is, so
`id 48 / SP_PIXELS` should sit at one transaction per pixel in every arm; if it steps with N instead,
`trans` is per component or per bundle and the two counters are the same traffic read from opposite
ends.  `SP 42` (FS bary instructions) and `SP 115` (the fp32 subset) are the FS's own count of the
same fetches: 42 per pixel is what the interface says the FS must fetch, and 115 equal to 42 says
nothing was packed to 16 bits.

The controls are printed before the tested columns, because an arm whose geometry differs measures
nothing: `VFD_TOTAL_VERTICES`, `TSE_INPUT_PRIM`, `SP_PIXELS` and `CCU_COLOR_BLOCKS` must agree
between arms, and `VSC_INPUT_TILES` says whether the pass was sysmem or binned (40.35: 0 in 11 of 11
windows of this probe).

Reading rules are `scripts/fdperf_sections.py`'s (its docstring owns the reasoning): only the
ordinary group's half of a sample, wrapped or `[invalid]` deltas dropped and counted, a counter the
dump does not carry printed as `MISSING` rather than as a zero.  Values are medians of the per-second
window deltas; `clk` is `CP_ALWAYS_COUNT / 1e6` printed next to them, because an event count is a
rate only while the clock is what the divisor assumes (the governor's ceiling here is 680 MHz and the
probe is not clock-pinned, so a window below --min-clk is dropped and counted).

What this cannot show: the FS's own work changes with N (N `bary.f` and N more adds), so the pixel
side is the limiter in the wide arms - fps is printed, and `SP 43`/`SP 44` show each side's
instructions.  That is the quantity under test, not a confound to remove, but it means "id 10 per
second" across arms is meaningless and only the per-vertex and per-pixel columns are comparable.
"""
import argparse
import glob
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdperf_sections import load  # noqa: E402

ID10 = "PERF_VPC_SP_COMPONENTS"
ID48 = "PERF_SP_EXPORT_VPC_TRANS"
CLK = "PERF_CP_ALWAYS_COUNT"

# Everything that must be EQUAL across arms for the rest of the table to mean anything, printed per
# frame below.  The three PC names are there because the cfg programs them and a sampled counter nobody
# prints is a wasted slot: PC 21 is the vertex-shader invocation count, which equals the vertex count only
# while nothing is reused, and PC 16 is what the VPC itself says it shipped primitives for.  (The cfg's
# PC 0 is `PERF_PC_RESERVED` - a slot spent on nothing, which docs/plan-next-checks.md queues.)
CONTROLS = [("PERF_VFD_TOTAL_VERTICES", "vert"),
            ("PERF_PC_IA_VERTICES", "ia_vert"),
            ("PERF_PC_VS_INVOCATIONS", "vs_inv"),
            ("PERF_TSE_INPUT_PRIM", "in_prim"),
            ("PERF_TSE_OUTPUT_VISIBLE_PRIM", "vis_prim"),
            ("PERF_PC_VPC_PRIMITIVES", "vpc_prim"),
            ("PERF_SP_PIXELS", "pix"),
            ("PERF_CCU_COLOR_BLOCKS", "cblk"),
            ("PERF_VSC_INPUT_TILES", "tiles")]

MISSING, DROPPED = "MISSING", "DROPPED"


def arm_name(path):
    """`varyings<N>` from the curated directory name; the arm's N is in its own meta.txt too."""
    base = os.path.basename(os.path.normpath(path))
    return base


def n_of(name, path):
    """The interface width of an arm: from the directory name, checked against meta.txt.

    `attrbuf` is the rig's own default pair (tests/vpc_attrbuf.{vert,frag}): sixteen vec4 wide since
    journal 42.1 corrected its fragment shader, and its name carries no digit to read."""
    digits = "".join(c for c in name if c.isdigit())
    n = int(digits) if digits else (16 if name == "attrbuf" else None)
    meta = os.path.join(path, "meta.txt")
    if n is not None and os.path.exists(meta):
        with open(meta, errors="replace") as f:
            head = f.read(400)
        claimed = [line for line in head.splitlines() if line.startswith("arm:")]
        if claimed and str(n) not in claimed[0]:
            print("%s: directory says N=%d, meta says %r - trusting the directory"
                  % (name, n, claimed[0]), file=sys.stderr)
    return n


def med(samples, name, min_clk):
    """Median of one counter's window deltas, in millions per second; plus what was thrown away."""
    vals, bad_clk = [], 0
    for s in samples:
        v = s.get(name)
        if v is None:
            continue
        clk = s.get(CLK)
        if clk is not None and clk < min_clk * 1e6:
            bad_clk += 1
            continue
        vals.append(v)
    if not vals:
        return MISSING, 0, 0
    return st.median(vals) / 1e6, len(vals), bad_clk


def ratio(samples, num, den, min_clk):
    """Median of a per-window quotient, with the denominator in the same window (never med/med)."""
    vals, bad_clk = [], 0
    for s in samples:
        a, b, clk = s.get(num), s.get(den), s.get(CLK)
        if a is None or b is None or not b:
            continue
        if clk is not None and clk < min_clk * 1e6:
            bad_clk += 1
            continue
        vals.append(a / b)
    if not vals:
        return MISSING, 0, 0
    return st.median(vals), len(vals), bad_clk


def stride_from_vpcram(path):
    """The stride the VPC's own RAM counter implies, for a directory with fdperf-raw.txt + run.txt.

    42.2 calibrates `VPC_NUM_VPCRAM_WRITE` at one write per 4 components - the id10/VPCRAM ratio is
    0.5001-0.5006 in all five arms - so VPC RAM writes per delivered vertex times 4 is the stride the
    block ships, and (stride - 4) / 4 the vec4 varyings it carries.  The vertex rate comes from the
    probe's own `verts_per_s` line, because the cfgs that programmed VPCRAM did not program
    VFD_TOTAL_VERTICES; that is also what lets this read directories sampled before this cfg existed.
    """
    raw, run = os.path.join(path, "fdperf-raw.txt"), os.path.join(path, "run.txt")
    if not (os.path.exists(raw) and os.path.exists(run)):
        return MISSING, MISSING, MISSING
    rate = None
    for line in open(run, errors="replace"):
        if line.startswith("verts_per_s "):
            rate = float(line.split()[1]) * 1e6
    if not rate:
        return MISSING, MISSING, MISSING
    samples, _u, _d = load(raw)
    v = [s["PERF_VPC_NUM_VPCRAM_WRITE"] for s in samples
         if s.get("PERF_VPC_NUM_VPCRAM_WRITE") is not None]
    if not v:
        return MISSING, MISSING, MISSING
    per_vertex = st.median(v) / rate
    return rate / 1e6, per_vertex, 4 * per_vertex


def fps_of(path):
    run = os.path.join(path, "run.txt")
    if not os.path.exists(run):
        return MISSING
    for line in open(run, errors="replace"):
        if line.startswith("fps "):
            return line.split()[1]
    return MISSING


def fmt(v, digits=3):
    if isinstance(v, str):
        return v
    if v >= 1000:
        return "%.0f" % v
    return "%.*f" % (digits, v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arms", nargs="*", default=None,
                    help="curated arm directories (default: results/synthetics/varyings/*/)")
    ap.add_argument("--lo", type=int, default=0)
    ap.add_argument("--hi", type=int, default=10_000)
    ap.add_argument("--min-clk", type=float, default=0.0,
                    help="optionally drop windows below this MHz; the default keeps them all, "
                         "see the note on clocks in the header")
    ap.add_argument("--per-window", metavar="ARM", default=None)
    args = ap.parse_args()

    # `varyings<N>` and the rig's own `attrbuf` pair are both arms of this sweep
    dirs = args.arms or sorted(glob.glob("results/synthetics/varyings/*/"))
    dirs = [d for d in dirs if os.path.exists(os.path.join(d, "fdperf-raw.txt"))]
    if not dirs:
        print("no curated arms under results/synthetics/varyings/ - run scripts/run-varyings-sweep.sh")
        return 1
    dirs.sort(key=lambda d: n_of(arm_name(d), d) or 0)

    print("# What the two export counters count: the interface sweep of tests/vpc-attrbuf.c --varyings=N")
    print("# regenerate: scripts/varyings-table.py | tee results/synthetics/varyings/arms.txt")
    print("# arms:       %s" % ", ".join(arm_name(d) for d in dirs))
    print("# values:     medians of per-second window deltas, millions per second, unless the column")
    print("#               says otherwise.  n = windows kept of the sample.")
    print("# clocks:     the arms ran at the governor's own clock (the printed clk column is")
    print("#               CP_ALWAYS_COUNT / 1e6, 625-680 MHz here).  Nothing is filtered for it:")
    print("#               an event counter over `fdperf -r 1000` is per wall second whatever the")
    print("#               clock, and a duty column divides by that window's own ALWAYS_COUNT, so")
    print("#               every column below is clock-free.  --min-clk exists if a reader wants")
    print("#               the pinned subset (680 MHz is the ceiling of this part).")
    if args.min_clk:
        print("# min-clk:    %.0f MHz, so some windows are deliberately dropped" % args.min_clk)
    print("# window:     --lo %d --hi %d s from each arm's first sample" % (args.lo, args.hi))
    print("# read with:  the rules of scripts/fdperf_sections.py (BV half discarded, wrapped deltas")
    print("#               dropped); MISSING = the cfg did not program it, DROPPED = no usable window")
    print("# expect:     VPC_SP_COMPONENTS / vertex ~ 4N+4 / k where k is the number of components")
    print("#               per event; the `x stride` column is that measured over 4N+4, so 1.000")
    print("#               says one per component, 0.500 two, 0.250 four, 0.125 eight; and")
    print("#               SP_EXPORT_VPC_TRANS / pixel ~ flat across arms if it counts transactions,")
    print("#               and equal to id 10 in every window if the two are the same traffic;")
    print("# SP_PIXELS:  is per pixel INVOCATION and this mesh overdraws the 768x768 target")
    print("#               thousands of times (32 G/s at 10.9 fps against 0.59 M pixels in the")
    print("#               target), so a per-pixel export ratio is ~1e-4 and that is expected -")
    print("#               what matters is whether it moves with N.")
    print()

    loaded = []
    for d in dirs:
        samples, _unmeasured, dropped = load(os.path.join(d, "fdperf-raw.txt"))
        t0 = samples[0]["t"] if samples else 0.0
        kept = [s for s in samples if args.lo <= s["t"] - t0 <= args.hi]
        loaded.append((arm_name(d), n_of(arm_name(d), d), d, kept, dropped))

    if args.per_window:
        for name, n, d, kept, _dr in loaded:
            if name != args.per_window:
                continue
            names = [c for c, _ in CONTROLS] + [CLK, ID10, ID48, "PERF_VPC_NUM_VPCRAM_WRITE",
                                                "PERF_SP_FS_STAGE_BARY_INSTRUCTIONS"]
            print("%-11s %-8s %s" % ("t s", "clk MHz", " ".join("%12s" % h[5:] for h in names)))
            for s in kept:
                print("%-11.1f %-8.1f %s"
                      % (s["t"] - t0, s.get(CLK, 0) / 1e6,
                         " ".join("%12s" % ("-" if s.get(h) is None else "%.3f" % (s[h] / 1e6))
                                  for h in names)))
            return 0

    # ---- the controls: are the five arms the same workload at all? --------------------------------
    # Per FRAME, not per second: the arms run at 0.9 to 10.9 fps, so a rate is not comparable
    # between them, and the check that they drew the same picture is a per-frame one.  The divisor is
    # the probe's own fps from its run.txt, measured over the whole run including the sampler's
    # warm-up, so it is a rate over the same interval the sampler's windows come from.
    print("controls - per FRAME (the arm's rate over its own fps), in millions, which must be equal")
    print("across arms or nothing else here is comparable.  `spread` is max/min over the arms:")
    print("1.00 is equality.  (The render-target hash cannot do this job: from N=4 up the colour")
    print("saturates the UNORM target, so arms 4, 8 and 16 print one hash for different sums.)")
    hdr = "%-11s %-5s %-8s %-7s" % ("arm", "N", "fps", "clk")
    for _c, short in CONTROLS:
        hdr += " %10s" % short
    print(hdr + "  n")
    per_frame = {}
    for name, n, d, kept, _dr in loaded:
        f = fps_of(d)
        f = float(f) if f.replace(".", "", 1).isdigit() else None
        line = "%-11s %-5s %-8s %-7s" % (name, n if n is not None else "?", f or MISSING,
                                         fmt(med(kept, CLK, 0)[0], 1))
        for c, _short in CONTROLS:
            v = med(kept, c, args.min_clk)[0]
            pv = v if isinstance(v, str) or not f else v / f
            per_frame.setdefault(_short, []).append(pv)
            line += " %10s" % fmt(pv, 2)
        print(line + "  %d" % med(kept, ID10, args.min_clk)[1])
    line = "%-11s %-5s %-8s %-7s" % ("spread", "", "", "")
    for _c, short in CONTROLS:
        nums = [v for v in per_frame[short] if not isinstance(v, str)]
        if len(nums) < 2:
            spread = MISSING
        elif min(nums) == 0:
            spread = "all 0" if max(nums) == 0 else "0 seen"
        else:
            spread = "%.2f" % (max(nums) / min(nums))
        line += " %10s" % spread
    print(line)

    # ---- the tested columns -----------------------------------------------------------------------
    print()
    print("the two counters, per unit of work the same dump measures")
    print("%-11s %-5s %-9s %-9s %-9s %-9s %-9s %-9s %-11s %-11s"
          % ("arm", "N", "id10 M/s", "/vertex", "stride", "x stride", "/vpcram",
             "id48 M/s", "/pixel", "id10 == id48"))
    print("%-11s %-5s %-9s %-9s %-9s %-9s %-9s %-9s %-11s %-11s"
          % ("", "", "", "", "(4N+4)", "(meas/exp)", "", "", "x 1e-6", "windows"))
    print("-" * 108)
    for name, n, d, kept, _dr in loaded:
        stride = 4 * n + 4 if n else None
        m10 = med(kept, ID10, args.min_clk)[0]
        m48 = med(kept, ID48, args.min_clk)[0]
        pv = ratio(kept, ID10, "PERF_VFD_TOTAL_VERTICES", args.min_clk)[0]
        xr = (pv / stride) if (stride and not isinstance(pv, str)) else MISSING
        vr = ratio(kept, ID10, "PERF_VPC_NUM_VPCRAM_WRITE", args.min_clk)[0]
        pp = ratio(kept, ID48, "PERF_SP_PIXELS", args.min_clk)[0]
        both = [(s.get(ID10), s.get(ID48)) for s in kept]
        both = [(a, b) for a, b in both if a is not None and b is not None]
        eq = ("%d/%d" % (sum(1 for a, b in both if a == b), len(both))) if both else MISSING
        print("%-11s %-5s %-9s %-9s %-9s %-9s %-9s %-9s %-11s %-11s"
              % (name, n if n is not None else "?", fmt(m10), fmt(pv, 4),
                 stride if stride else MISSING, fmt(xr, 4), fmt(vr, 4), fmt(m48), fmt(pp, 6), eq))

    print()
    print("the interface as the two ends of it see it - FS bary instructions per pixel, and the")
    print("fp32 share of them (115 = 42 would mean nothing was packed to 16 bits)")
    print("Read the two left columns only.  `SP instr/s` and `FS instr/s` are printed for")
    print("completeness and are NOT interpreted: at 680 MHz they read 7 Mc/cycle-core (VS) and")
    print("143 (FS), which cannot be instructions, so those selectors count per thread, per quad")
    print("or per some wider group (docs/fdperf-a7xx.md gives no unit for them), and the FS/VS")
    print("column is the ratio of two numbers whose unit is unknown.")
    print("%-11s %-5s %-11s %-11s %-11s %-11s %-11s %-11s"
          % ("arm", "N", "SP42/pixel", "SP115/pixel", "115/42", "VS instr/s", "FS instr/s",
             "FS/VS"))
    print("-" * 100)
    for name, n, d, kept, _dr in loaded:
        b = ratio(kept, "PERF_SP_FS_STAGE_BARY_INSTRUCTIONS", "PERF_SP_PIXELS", args.min_clk)[0]
        f = ratio(kept, "PERF_SP_BARY_FP32_INSTRUCTIONS", "PERF_SP_PIXELS", args.min_clk)[0]
        r = ratio(kept, "PERF_SP_BARY_FP32_INSTRUCTIONS",
                  "PERF_SP_FS_STAGE_BARY_INSTRUCTIONS", args.min_clk)[0]
        vs = med(kept, "PERF_SP_VS_INSTRUCTIONS", args.min_clk)[0]
        fs = med(kept, "PERF_SP_FS_INSTRUCTIONS", args.min_clk)[0]
        print("%-11s %-5s %-11s %-11s %-11s %-11s %-11s %-11s"
              % (name, n if n is not None else "?", fmt(b, 3), fmt(f, 3), fmt(r, 3),
                 fmt(vs), fmt(fs), fmt(fs / vs, 3) if not isinstance(vs, str)
                 and not isinstance(fs, str) and vs else MISSING))

    print()
    print("the pair window by window - 40.36's question, asked where the interface is known: how")
    print("often are the two counters the same integer, and how far apart are they when they are not")
    print("(`d > 0.1 %` counts the windows further apart than that, the same cut")
    print("`results/games/re4/vpc-sp-pair.txt` applies to its 1823 windows, where the median skew of")
    print("two counters reading the same quantity shows up as 0.00295 % of id10)")
    print("%-11s %-5s %-7s %-9s %-11s %-11s %-11s %-11s %-11s"
          % ("arm", "N", "windows", "identical", "median |d|", "max |d|", "med |d|/id10",
             "d > 0.1 %", "sign of d"))
    print("-" * 100)
    for name, n, d, kept, _dr in loaded:
        diffs = [s[ID10] - s[ID48] for s in kept
                 if s.get(ID10) is not None and s.get(ID48) is not None]
        if not diffs:
            print("%-11s %-5s %s" % (name, n, MISSING))
            continue
        ad = [abs(x) for x in diffs]
        pos = sum(1 for x in diffs if x > 0)
        neg = sum(1 for x in diffs if x < 0)
        med10 = st.median([s[ID10] for s in kept if s.get(ID10)])
        wide = sum(1 for a, b in both if a and abs(a - b) / a > 0.001)
        print("%-11s %-5s %-7d %-9s %-11s %-11s %-11s %-11s %-11s"
              % (name, n, len(diffs), "%d/%d" % (sum(1 for x in diffs if x == 0), len(diffs)),
                 fmt(st.median(ad), 1), fmt(max(ad), 1),
                 "%.5f" % (100.0 * st.median(ad) / med10), "%d/%d" % (wide, len(diffs)),
                 "%d+ %d-" % (pos, neg)))

    print()
    print("the two exports per pixel: id 48 (to VPC) against id 49 (to RB, the colour side, which")
    print("is one per pixel whatever N is) - if 48 moves with N and 49 does not, the movement in 48")
    print("is the interface and not the export mechanism")
    print("`id49 per quad` is the same constant expressed against quads, which is the unit the")
    print("export is plausibly in; the point of the whole table is the column's flatness, not its value")
    print("%-11s %-5s %-12s %-12s %-11s %-11s %-11s %-11s"
          % ("arm", "N", "id48/pixel", "id49/pixel", "id49/quad", "id49 M/s", "pix M/s",
             "quads M/s"))
    print("-" * 89)
    for name, n, d, kept, _dr in loaded:
        print("%-11s %-5s %-12s %-12s %-11s %-11s %-11s %-11s"
              % (name, n if n is not None else "?",
                 fmt(ratio(kept, ID48, "PERF_SP_PIXELS", args.min_clk)[0], 6),
                 fmt(ratio(kept, "PERF_SP_EXPORT_RB_TRANS", "PERF_SP_PIXELS", args.min_clk)[0], 6),
                 fmt(ratio(kept, "PERF_SP_EXPORT_RB_TRANS", "PERF_SP_QUADS", args.min_clk)[0], 4),
                 fmt(med(kept, "PERF_SP_EXPORT_RB_TRANS", args.min_clk)[0]),
                 fmt(med(kept, "PERF_SP_PIXELS", args.min_clk)[0], 0),
                 fmt(med(kept, "PERF_SP_QUADS", args.min_clk)[0])))

    print()
    print("who waits for whom, and whether the pass was ever binned.  `VPC busy %` is printed here")
    print("as a finding, not as a load measure: it sits at 100 % in every arm although the arms span")
    print("12x in frame rate and 8.5x in payload per vertex, and `SP stall VPC` Mc/s over the same")
    print("windows is 0.000-0.019 of a 680 Mc/s clock - the pixel pipe is never held up by the VPC,")
    print("so a busy counter pinned at full cannot be read as saturation.  What the arms do disagree")
    print("on is VPC_WORKING/BUSY, which falls as the interface widens.")
    print("%-11s %-5s %-11s %-11s %-11s %-11s %-11s"
          % ("arm", "N", "VPC busy %", "VPC work %", "SP stall VPC", "VSC tiles", "SP busy %"))
    print("-" * 80)
    for name, n, d, kept, _dr in loaded:
        def duty(c):
            v = med(kept, c, args.min_clk)[0]
            k = med(kept, CLK, 0)[0]
            return MISSING if isinstance(v, str) or isinstance(k, str) or not k else "%.2f" % (
                100.0 * v / k)
        print("%-11s %-5s %-11s %-11s %-11s %-11s %-11s"
              % (name, n if n is not None else "?",
                 duty("PERF_VPC_BUSY_CYCLES"), duty("PERF_VPC_WORKING_CYCLES"),
                 fmt(med(kept, "PERF_SP_STALL_CYCLES_VPC", args.min_clk)[0]),
                 fmt(med(kept, "PERF_VSC_INPUT_TILES", args.min_clk)[0]),
                 duty("PERF_SP_BUSY_CYCLES")))

    # ---- the VPC's own RAM counter, read back as a stride ------------------------------------------
    print()
    print("the stride as the VPC's own RAM counter reports it: writes per delivered vertex x 4.")
    print("Calibrated here, not assumed - `x stride` above puts id 10 at one event per 8 components")
    print("and id10/VPCRAM is 0.5001-0.5006 in every arm, so VPCRAM is one write per 4 components")
    print("(one 128-bit word), and 4 x writes-per-vertex is the stride.  The vertex rate is the")
    print("probe's own `verts_per_s`, which is also why this reads directories sampled before this")
    print("cfg existed: `smoke` is the attribute-buffer probe's 23.11 run, whose compiled interface")
    print("is the open question of 42.1.")
    print("%-20s %-11s %-11s %-14s" % ("directory", "vtx M/s", "VPCRAM/vtx", "implied stride"))
    print("-" * 58)
    others = [d for d in sorted(glob.glob("results/synthetics/attrbuf/*"))
              if d not in {x[2] for x in loaded}]
    for d in [x[2] for x in loaded] + others:
        rate, pv, sd = stride_from_vpcram(d)
        print("%-20s %-11s %-11s %-14s"
              % (os.path.basename(os.path.normpath(d)), fmt(rate, 3), fmt(pv, 3), fmt(sd, 2)))

    any_drop = {name: dr for name, _n, _d, _k, dr in loaded if dr}
    if any_drop:
        print()
        print("deltas thrown away as wrapped or [invalid] (scripts/fdperf_sections.py):")
        for name, dr in any_drop.items():
            print("  %-11s %s" % (name, ", ".join("%s=%d" % kv for kv in sorted(dr.items()))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
