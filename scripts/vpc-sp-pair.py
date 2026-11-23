#!/usr/bin/env python3
"""Do `VPC_SP_COMPONENTS` (VPC selector 10) and `SP_EXPORT_VPC_TRANS` (SP selector 48) count one thing,
and can a dump already in git give either of them a unit (queue 34 of docs/plan-next-checks.md).

Why this script and not the ratio it re-cuts. journal 40.34 says the pair is "one signal" from a ratio of
medians over each arm's steady windows (1.00000, 1176 of 1293 windows within 1e-4). A ratio of medians
cannot say what the other 117 windows are, and the reviewer's mechanism - "SP and VPC exchange one
component per vertex" - is a statement about a per-vertex value that the same entry refuses to quote
because there is no per-vertex denominator in a unit anybody has. So this script prints the two raw window
deltas side by side, per window, their difference, and every candidate denominator the same cfg happens to
program, so that

  * "equal" is measured as equality - the same integer - not as a ratio inside a tolerance;
  * the difference is tested for what kind of thing it is: a constant small offset (one counter, sampled
    at a window boundary) is a signed difference with a non-zero median and one sign, while noise in the
    last significant digits is a signed difference that crosses zero inside every arm;
  * each candidate denominator sits in the same row as the counter, so a quotient that holds still while
    its denominator moves 2x is visible without re-cutting anything.

Reading rules, all of them `scripts/fdperf_sections.py`'s, whose docstring owns the reasoning:
  * only the ordinary group's half of a sample is read; a name that appears only in the `BV_*` half is
    reported as never programmed in the ordinary group, not as that block's own counter;
  * a window delta that came back wrapped (>= 2**63) or `[invalid]` is dropped and counted;
  * a counter the dump does not carry prints `MISSING` and a window whose value was dropped prints
    `DROPPED`. Neither is ever arithmetic on a zero: a selector is absent because its group's hw budget is
    spent elsewhere (VPC 6, SP 24, PC 8 - docs/fdperf-a7xx.md), not because the block counted nothing;
  * every value is a window delta from `fdperf -r 1000 -d`. `delta / 1e6` is Mc/s only while
    `CP_ALWAYS_COUNT` is one second of the pinned clock (680 MHz here), which is why the table prints the
    measured `CP_ALWAYS_COUNT / 1e6` as `clk MHz` in the same row: at 558 MHz that window is 1.22 s long
    and its event counts are 1.22x what a pinned window's would be.

What this table cannot decide, said before the numbers: every committed dump is the same build of the same
title (Resident Evil 4 - `results/games/README.md`), so no arm in git changes the number of vertex-shader
outputs, which is the variable queue 34's probe changes. The arms here differ in render mode, cache mode,
clock and frame rate. So nothing below separates "components" from "transactions" from "vec4-shaped
transactions". What it does settle is whether `id 10 / vertex` behaves like a property of a shader
interface at all, whether the pair is bit-identical, and whether PC selector 19 is dead or idle.

Usage:
    scripts/vpc-sp-pair.py                          # every fdperf dump under results/
    scripts/vpc-sp-pair.py --arms dbg-file,sc-gmem
    scripts/vpc-sp-pair.py --lo 20 --hi 105         # journal 40's steady windows only
    scripts/vpc-sp-pair.py --no-rows                # summaries without the per-window table
"""
import argparse
import glob
import os
import statistics as st
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdperf_sections import load  # noqa: E402

ID10 = "PERF_VPC_SP_COMPONENTS"            # VPC group, selector 10
ID48 = "PERF_SP_EXPORT_VPC_TRANS"          # SP group, selector 48
VERT = "PERF_VFD_TOTAL_VERTICES"
ATTR = "PERF_VFD_NUM_ATTRIBUTES"
BYTES = "PERF_VFD_DECODED_ATTRIBUTE_BYTES"
VPCRAM = "PERF_VPC_NUM_VPCRAM_WRITE"
WORK = "PERF_VPC_WORKING_CYCLES"
BUSY = "PERF_VPC_BUSY_CYCLES"
CLK = "PERF_CP_ALWAYS_COUNT"
TILES = "PERF_VSC_INPUT_TILES"
MODES = ("binned", "low rate", "zero", "value dropped", "not sampled")
BIN_TILES = 1_000_000   # the floor for a binned window: one 2560x1440 frame is thousands of
                      # bins, so one second of binned frames is a rate far above this; see
                      # print_render_mode for why the value is not read as a tile count
SP_BUSY = "PERF_SP_BUSY_CYCLES"
HITS = "PERF_PC_VERTEX_HITS"               # PC selector 19
TAGGED = "PERF_PC_TAG_CHECKED_VERTICES"    # PC selector 39, the denominator 40.33 says nobody programmed

DENOMS = [(ATTR, "attrM"), (BYTES, "byteM"), (VERT, "vertM"),
          (VPCRAM, "vpcramM"), (WORK, "workM"), (BUSY, "busyM")]

MISSING = "MISSING"
DROPPED = "DROPPED"


# --- one window's value, or a word saying why there is none -----------------------------------------

def value(win, name, present):
    if name in win:
        return win[name]
    return DROPPED if name in present else MISSING


def isnum(v):
    """A value a window actually carried (every raw window delta is an int)."""
    return isinstance(v, int)


def isreal(v):
    """A number, int or float: medians of an even number of window deltas come back as floats."""
    return isinstance(v, (int, float))


def cnt(v, width):
    """A raw window delta, with separators: this is the column exact equality is read from."""
    return f"{v:{width},d}" if isnum(v) else f"{str(v):>{width}s}"


def mil(v, width):
    """A window delta in millions of counts (Mc/s at a pinned 1 s window, counts x1e6 otherwise)."""
    return f"{v / 1e6:{width}.1f}" if isnum(v) else f"{str(v):>{width}s}"


def div(a, b, width, spec=".4f"):
    """A quotient of two values, or the word that says why there is none. A missing side never becomes
    a zero: a ratio of a counter the cfg did not program is not a zero, it is an unanswered question."""
    if not (isreal(a) and isreal(b)):
        bad = DROPPED if DROPPED in (a, b) else MISSING
        return f"{bad:>{width}s}"
    if b == 0:
        return f"{'DIV0':>{width}s}"
    return f"{a / b:{width}{spec}}"


def q(a, b):
    """The float form of `div`, for the summary blocks: None when either side is missing or b is 0."""
    if not (isreal(a) and isreal(b)) or b == 0:
        return None
    return a / b


def median(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return st.median(vals) if vals else None


def pct(vals, p):
    vals = sorted(v for v in vals if isinstance(v, (int, float)))
    return vals[min(len(vals) - 1, int(p * len(vals)))] if vals else None


def fnum(v, width, spec=".1f", sign=""):
    """A number right-aligned in `width`, or the word MISSING: an absent counter never prints 0."""
    if not isinstance(v, (int, float)):
        return f"{MISSING:>{width}s}"
    return f"{v:{sign}{width}{spec}}"


# --- reading the dumps -------------------------------------------------------------------------------

class Dump:
    def __init__(self, path):
        self.path = path
        self.tag = tag_for(path)
        self.samples, self.unmeasured, self.dropped = load(path)
        self.present = {k for w in self.samples for k in w}
        self.t0 = self.samples[0]["t"] if self.samples else 0.0

    def windows(self, lo, hi):
        out = []
        for i, w in enumerate(self.samples):
            t = w["t"] - self.t0
            if lo is not None and t < lo:
                continue
            if hi is not None and t > hi:
                continue
            out.append((i + 1, t, w))
        return out


def tag_for(path):
    """`results/games/<title>/<arm>/fdperf-raw.txt` is the arm `results/games/re4/README.md` names;
    anything else is named by the directory and file that hold it, so two dumps cannot share a row."""
    parts = path.split(os.sep)
    if "games" in parts and len(parts) - parts.index("games") >= 4:
        return parts[parts.index("games") + 2]
    return f"{parts[-2]}/{os.path.splitext(parts[-1])[0]}"


def is_scratch(path):
    """A path with a `raw` directory component is the gitignored scratch of a run (AGENTS.md: "raw logs
    stay in results/raw/ (gitignored) - a curated file is what git sees and what a claim may cite"), and
    those copies are not committed, so they are not the corpus this queue item asks about. The committed
    dumps are named fdperf-raw.txt, which is a file name and not a directory, so this test cannot catch
    them by accident."""
    return "raw" in path.split(os.sep)[:-1]


def find_dumps(pattern, include_scratch=False):
    """Every file under `pattern` whose header says it is an fdperf dump - found by content, not name,
    so a future synthetic arm under results/synthetics/ is picked up without editing this script.
    Returns (dumps, skipped_scratch)."""
    found, skipped = [], 0
    for path in sorted(glob.glob(pattern, recursive=True)):
        try:
            with open(path, errors="replace") as f:
                head = f.read(4096)
        except OSError:
            continue
        if "=== sample" not in head:
            continue
        if not include_scratch and is_scratch(path):
            skipped += 1
            continue
        found.append(path)
    return found, skipped


# --- sections ----------------------------------------------------------------------------------------

def say(text, indent="# ", width=100):
    """Print one prose line of the artifact, wrapped, so no line of a committed table is 400 columns."""
    for line in textwrap.wrap(text, width=width, initial_indent=indent, break_on_hyphens=False,
                              subsequent_indent=indent + " " * 3):
        print(line)


def print_scope(dmps, both, only_one, neither, pattern, skipped):
    dirs = sorted({os.path.dirname(d.path) for d in dmps})
    print("# Scope: every fdperf dump committed under the scanned pattern, read offline; nothing here")
    print("# samples the GPU. One dump is one `fdperf -r 1000 -d` session of one arm of one game run.")
    say(f"scanned {len(dmps)} dumps in {len(dirs)} director"
        f"{'y' if len(dirs) == 1 else 'ies'} under {pattern!r}"
        + (f"; {skipped} more dumps sit under a gitignored raw/ directory and were not read: they are "
           "the pre-curation copies of the same runs and no claim cites them" if skipped else ""))
    parents = sorted({os.path.dirname(d) for d in dirs})
    for p in parents:
        sub = [d for d in dirs if os.path.dirname(d) == p]
        print(f"#   under {p}: {len(sub)} dump director"
              f"{'y' if len(sub) == 1 else 'ies'}, "
              f"{sum(1 for x in dmps if os.path.dirname(os.path.dirname(x.path)) == p)} dumps")
    say(f"carries both id 10 and id 48: {len(both)} arms - " + (", ".join(both) or "none"))
    say(f"carries exactly one of the two: {len(only_one)} arms - " + (", ".join(only_one) or "none"))
    say(f"carries neither: {len(neither)} arms - " + (", ".join(neither) or "none"))


def print_rows(dmps, both, lo, hi, no_rows):
    """The per-window table: one row per window of every arm that carries both selectors."""
    rows = []
    head = (f"{'arm':22s} {'win':>3s} {'t_rel':>5s} {'id10':>14s} {'id48':>14s} {'id10-id48':>12s} "
            f"{'diff %':>8s} " + " ".join(f"{h:>8s}" for _, h in DENOMS)
            + f" {'clk MHz':>8s} {'id10/vert':>9s} {'id48/vert':>9s}")
    for d in dmps:
        if d.tag not in both:
            continue
        for i, t, w in d.windows(lo, hi):
            a, b = value(w, ID10, d.present), value(w, ID48, d.present)
            diff = a - b if (isnum(a) and isnum(b)) else MISSING
            vert = value(w, VERT, d.present)
            cells = {n: value(w, n, d.present) for n, _ in DENOMS}
            clk = value(w, CLK, d.present)
            rows.append({"arm": d.tag, "win": i, "t": t, "id10": a, "id48": b, "diff": diff,
                         "vert": vert, "clk": clk, "tiles": value(w, TILES, d.present),
                         "spbusy": value(w, SP_BUSY, d.present), **cells})
    if not no_rows:
        print()
        print("# Every window of every arm that carries both selectors. `id10`/`id48` are raw window")
        print("# deltas; `diff %` is (id10-id48)/id10 in percent; the volume columns are the same deltas")
        print("# in millions of counts; `clk MHz` is CP_ALWAYS_COUNT/1e6, i.e. the window's own length at")
        print("# the pinned 680 MHz. MISSING = the cfg never programmed that selector; DROPPED = this")
        print("# window's value was thrown away as a wrapped or [invalid] delta.")
        print(head)
        print("-" * len(head))
        for r in rows:
            dv = 100.0 * r["diff"] / r["id10"] if (isnum(r["diff"]) and r["id10"]) else None
            print(f"{r['arm']:22s} {r['win']:3d} {r['t']:5.1f} {cnt(r['id10'], 14)} {cnt(r['id48'], 14)} "
                  f"{cnt(r['diff'], 12)} {fnum(dv, 8, '.4f')} "
                  + " ".join(mil(r[n], 8) for n, _ in DENOMS)
                  + f" {fnum(r['clk'] / 1e6 if isnum(r['clk']) else None, 8, '.1f')}"
                  + f" {div(r['id10'], r['vert'], 9)} {div(r['id48'], r['vert'], 9)}")
    return rows


def cadence(d):
    """Blocks per second of wall time and the smallest gap between sample labels. The repository's own
    note on the sampler says one `=== sample` block is one fresh fdperf process and that the process lives
    ~2.2-2.3 s (docs/fdperf-a7xx.md, "Windows"), so 49-53 blocks over ~108 s is the expected shape; a dump
    with sub-second gaps is a run whose windows were not that shape."""
    ts = [w["t"] for w in d.samples]
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    return len(ts), (st.median(gaps) if gaps else None), (min(gaps) if gaps else None)


def print_equality(rows, dmps):
    pairs = [r for r in rows if isnum(r["diff"])]
    lost = [r for r in rows if not isnum(r["diff"])]
    print("\nIs the pair equal, or only close?  Raw window deltas, so no tolerance is involved.")
    print(f"  windows carrying both values: {len(pairs)} of {len(rows)} printed windows, "
          f"in {len({r['arm'] for r in pairs})} arms")
    if lost:
        print(f"  windows that could NOT be compared: {len(lost)} - " + "; ".join(
            f"{r['arm']} window {r['win']} at t_rel {r['t']:.1f} s (id10 {r['id10']}, id48 {r['id48']})"
            for r in lost))
        print("  DROPPED means the loader threw that one window's delta away as a u64 wraparound or "
              "[invalid]; it is not a zero and is not counted in any statistic below.")
    if not pairs:
        print("  no window carries the pair")
        return
    eq = [r for r in pairs if r["diff"] == 0]
    diffs = [r["diff"] for r in pairs]
    adiff = [abs(d) for d in diffs]
    by_arm0 = {}
    for r in pairs:
        by_arm0.setdefault(r["arm"], []).append(r["diff"])
    both_signs = sum(1 for v in by_arm0.values() if any(x > 0 for x in v) and any(x < 0 for x in v))
    rel = [(100.0 * abs(r["diff"]) / r["id10"], r["arm"], r["t"]) for r in pairs if r["id10"]]
    worst = max(pairs, key=lambda r: abs(r["diff"]))
    wrel = max(rel)
    say(f"bit-identical (id10 == id48): {len(eq)} windows ({100 * len(eq) / len(pairs):.2f} %), in "
        f"{len({r['arm'] for r in eq})} arms of {len(by_arm0)}: "
        + (", ".join(sorted({r['arm'] for r in eq})) or "none"), "  ")
    say(f"signed id10-id48: positive in {sum(1 for d in diffs if d > 0)} windows, negative in "
        f"{sum(1 for d in diffs if d < 0)}, zero in {len(eq)}; {both_signs} of {len(by_arm0)} arms contain "
        "both signs, so no arm behaves like the two counters are one signal carrying a fixed offset.", "  ")
    say(f"|difference| in counts: median {median(adiff):,.0f}, p90 {pct(adiff, .9):,.0f}, "
        f"p99 {pct(adiff, .99):,.0f}, p99.9 {pct(adiff, .999):,.0f}, max {max(adiff):,}", "  ")
    clk_txt = f"{worst['clk']:,}" if isnum(worst["clk"]) else str(worst["clk"])
    say(f"largest absolute difference: {abs(worst['diff']):,} counts, {worst['arm']} window "
        f"{worst['win']} at t_rel {worst['t']:.1f} s, where id10 read {worst['id10']:,} and id48 read "
        f"{worst['id48']:,} over a window of clk {clk_txt} counts", "  ")
    print(f"  largest relative difference: {wrel[0]:.4f} % of id10, {wrel[1]} at t_rel {wrel[2]:.1f} s")
    print(f"  windows over 0.1 % apart: {sum(1 for x, *_ in rel if x > 0.1)}; over 1 %: "
          f"{sum(1 for x, *_ in rel if x > 1.0)}; over 5 %: {sum(1 for x, *_ in rel if x > 5.0)}")
    print("  Splitting the same windows by their own CP_ALWAYS_COUNT, because a difference of 81 counts is")
    print("  0.00004 % of a loaded window and 8 % of a window in which the core was gated and both counters")
    print("  read about a thousand counts:")
    for label, g in (("  clk > 500 MHz (1 s window under load)",
                      [r for r in pairs if isnum(r["clk"]) and r["clk"] > 5e8]),
                     ("  clk <= 500 MHz (core gated)",
                      [r for r in pairs if isnum(r["clk"]) and r["clk"] <= 5e8])):
        if not g:
            continue
        rs = [100.0 * abs(r["diff"]) / r["id10"] for r in g if r["id10"]]
        say(f"{label.strip()}: {len(g)} windows, max |difference| "
            f"{max(abs(r['diff']) for r in g):,} counts, median {st.median(rs):.5f} % of id10, "
            f"max {max(rs):.4f} %", "  ")
    far = {}
    for r in pairs:
        if r["id10"] and 100 * abs(r["diff"]) / r["id10"] > 1.0:
            far.setdefault(r["arm"], []).append(r)
    by_tag = {d.tag: d for d in dmps}
    print(f"  the {len(far)} arms that hold every window over 1 % apart, and the shape of their dumps:")
    for arm in sorted(far):
        d = by_tag[arm]
        n, mg, mn = cadence(d)
        drop = sum(c for nn, c in d.dropped.items() if nn in (ID10, ID48))
        loaded = sum(1 for r in far[arm] if isnum(r["clk"]) and r["clk"] > 5e8)
        say(f"{arm}: {len(far[arm])} windows over 1 % apart, {loaded} of them with the core loaded; "
            f"that dump has {n} blocks with a median gap of {mg:.2f} s and a smallest gap of {mn:.2f} s, "
            f"and {drop} window values of the pair were thrown away as wrapped", "    ")
    print("  docs/fdperf-a7xx.md, section Windows: one block is one fresh fdperf process living ~2.2-2.3 s,")
    print("  and a window read right after a dead process carries a negative delta imaged as unsigned. Only")
    print("  the dumps named above depart from that shape, and they are the only ones whose loaded windows")
    print("  put the two counters more than 1 % apart.")
    per = {}
    for r in pairs:
        per.setdefault(r["arm"], []).append(r["diff"])
    med_per = {t: median(v) for t, v in per.items()}
    max_per = {t: max(abs(x) for x in v) for t, v in per.items()}
    lo_t, hi_t = min(med_per, key=med_per.get), max(med_per, key=med_per.get)
    say(f"per arm, median signed difference: {med_per[lo_t]:+,} counts in {lo_t} to {med_per[hi_t]:+,} "
        f"counts in {hi_t}; the largest |difference| within an arm runs from {min(max_per.values()):,} "
        f"counts to {max(max_per.values()):,} counts over the {len(per)} arms", "  ")
    print(f"  arms whose printed windows are ALL bit-identical: "
          + (", ".join(t for t in sorted(per) if all(x == 0 for x in per[t])) or "none"))
    print(f"  arms with at least one bit-identical window: {len({r['arm'] for r in eq})} of {len(per)}; "
          f"arms where no window is bit-identical: {len(per) - len({r['arm'] for r in eq})}")


def print_per_arm(dmps, rows):
    print("\nPer arm, medians over the printed windows. A quotient is only a candidate unit if it holds")
    print("still across arms whose denominator moves; `MISSING` means no window of that arm sampled it.")
    head = (f"{'arm':22s} {'win':>3s} {'clk':>4s} {'bin':>4s} {'id10 Mc/s':>9s} {'id48 Mc/s':>9s} "
            f"{'med diff':>9s} {'id10/vert':>9s} {'id48/vert':>9s} {'attr/vert':>9s} {'B/vert':>7s} "
            f"{'vpcram/vert':>11s} {'id10/attr':>9s} {'id10/B':>9s} {'id10/vpcram':>11s} {'busy/clk':>8s}")
    print(head)
    print("-" * len(head))
    by_arm = {}
    for r in rows:
        by_arm.setdefault(r["arm"], []).append(r)
    for arm in sorted(by_arm):
        rs = by_arm[arm]
        a, b = median([r["id10"] for r in rs]), median([r["id48"] for r in rs])
        md, clk = median([r["diff"] for r in rs]), median([r["clk"] for r in rs])
        d = {n: median([r[n] for r in rs]) for n, _ in DENOMS}
        vert = d[VERT]
        binned = sum(1 for r in rs if isnum(r["tiles"]) and r["tiles"] > 0)
        bin_txt = f"{binned:4d}" if any(isnum(r["tiles"]) for r in rs) else f"{'n/s':>4s}"
        print(f"{arm:22s} {len(rs):3d} {fnum(clk / 1e6 if clk else None, 4, '.0f')} {bin_txt} "
              f"{fnum(a / 1e6 if isreal(a) else None, 9, '.1f')} "
              f"{fnum(b / 1e6 if isreal(b) else None, 9, '.1f')} "
              f"{fnum(md, 9, '.0f', '+')} "
              f"{div(a, vert, 9)} {div(b, vert, 9)} {div(d[ATTR], vert, 9)} {div(d[BYTES], vert, 7)} "
              f"{div(d[VPCRAM], vert, 11)} {div(a, d[ATTR], 9)} {div(a, d[BYTES], 9, '.5f')} "
              f"{div(a, d[VPCRAM], 11)} {div(d[BUSY], clk, 8, '.3f')}")

    names = [n for n, _ in DENOMS] + [CLK, TILES, SP_BUSY]
    by_dump = {d.tag: d for d in dmps}
    absent = {n[5:]: [arm for arm in sorted(by_arm) if n not in by_dump[arm].present] for n in names}
    carries = sorted(k for k, v in absent.items() if not v)
    print(f"  columns every arm in this set carries: {', '.join(carries) or 'none'}")
    for k, v in sorted(absent.items()):
        if v:
            say(f"{k} MISSING in {len(v)} of {len(by_arm)} arms: " + ", ".join(v), "  ")
    for d in sorted((x for x in dmps if x.tag in by_arm), key=lambda x: x.tag):
        bad = {n[5:]: c for n, c in d.dropped.items() if n in (ID10, ID48)}
        if bad:
            print(f"  {d.tag}: windows of the pair dropped as a wrapped or [invalid] delta: "
                  + ", ".join(f"{k} x{c}" for k, c in sorted(bad.items())))
        if d.unmeasured & {ID10, ID48}:
            print(f"  {d.tag}: {', '.join(sorted(n[5:] for n in d.unmeasured if n in (ID10, ID48)))} "
                  "appears only in the BV_* half of the dump, so the ordinary group never sampled it")


def print_denominators(rows):
    """Which candidate denominator holds still, per window and per arm, when the others move."""
    print("\nCandidate denominators: the same quotient per window and per arm-of-medians, with max/min as")
    print("the spread. A quotient that is flat while its denominator moves 2x points at that denominator.")
    cands = [
        (f"id10 / {VERT[5:]:26s}", lambda r: q(r["id10"], r[VERT])),
        (f"id10 / {VPCRAM[5:]:26s}", lambda r: q(r["id10"], r[VPCRAM])),
        (f"id10 / {ATTR[5:]:26s}", lambda r: q(r["id10"], r[ATTR])),
        (f"id10 / {BYTES[5:]:26s}", lambda r: q(r["id10"], r[BYTES])),
        (f"{ATTR[5:]:26s} / vert", lambda r: q(r[ATTR], r[VERT])),
        (f"{BYTES[5:]:26s} / vert", lambda r: q(r[BYTES], r[VERT])),
        (f"{VPCRAM[5:]:26s} / vert", lambda r: q(r[VPCRAM], r[VERT])),
    ]
    by_arm = {}
    for r in rows:
        by_arm.setdefault(r["arm"], []).append(r)
    for label, fn in cands:
        vals = [fn(r) for r in rows]
        vals = [v for v in vals if v is not None]
        if not vals:
            print(f"  {label}: MISSING in every printed window - no arm in git carries this pair")
            continue
        arms = {}
        for arm, rs in by_arm.items():
            m = median([fn(r) for r in rs])
            if m is not None:
                arms[arm] = m
        line = (f"{label.strip()}: over the {len(vals)} windows that carry both sides, "
                f"{min(vals):.5f} to {max(vals):.5f} (max/min {max(vals) / min(vals):.2f}x), median "
                f"{median(vals):.5f}")
        if arms:
            lo, hi = min(arms.values()), max(arms.values())
            line += (f"; over the {len(arms)} arm medians, {lo:.5f} to {hi:.5f} "
                     f"(max/min {hi / lo:.2f}x)")
        say(line, "  ")
        if arms and len(arms) > 2:
            lo_a = min(arms, key=arms.get)
            hi_a = max(arms, key=arms.get)
            say(f"{lo_a} is lowest at {arms[lo_a]:.5f} and {hi_a} highest at {arms[hi_a]:.5f}", "      ")


def print_pixel_cost(rows):
    """Does id10/vertex move when the pixel side moves and the shaders cannot have? Inside one arm the
    binary, both shaders and the geometry are fixed, so anything the quotient does across that arm's own
    windows is not the interface: it is the mode the frame was drawn in."""
    print("\nSame binary, same shaders, same session, so only the pixel cost and the render mode move:")
    print("  spbusy - windows split at the median SP_BUSY_CYCLES / CP_ALWAYS_COUNT of the arm, i.e. the")
    print("           half that spends a larger share of the core on the pixel side; `key` columns give the")
    print("           median quotient of each half, so the size of the pixel-side move is visible. The")
    print("           quotient sits near 10.4 because the SP domain is 12-wide (docs/howto-measure.md")
    print("           quotes the SP divider /12); only the relative split is used here.")
    print("  tiles  - windows with VSC_INPUT_TILES > 0 against windows with 0, inside one session; the")
    print("           `key` columns are the median tile count of each half")
    head = (f"{'arm':22s} {'split':>7s} {'n lo':>5s} {'n hi':>5s} {'key lo':>7s} {'key hi':>7s} "
            f"{'id10/vert lo':>13s} {'id10/vert hi':>13s} {'hi/lo':>7s} "
            f"{'id48/vert lo':>13s} {'id48/vert hi':>13s}")
    print(head)
    print("-" * len(head))
    by_arm = {}
    for r in rows:
        by_arm.setdefault(r["arm"], []).append(r)
    shown = 0
    res = {}

    def share(r):
        return q(r["spbusy"], r["clk"])

    def tiles(r):
        return r["tiles"] if isnum(r["tiles"]) else None

    for arm in sorted(by_arm):
        base = [r for r in by_arm[arm] if isnum(r["id10"]) and isnum(r["id48"])
                and isnum(r[VERT]) and r[VERT]]
        for label, key in (("spbusy", share), ("tiles", tiles)):
            keep = [r for r in base if key(r) is not None]
            if len(keep) < 6:
                continue
            if label == "spbusy":
                cut = st.median([key(r) for r in keep])
                lo = [r for r in keep if key(r) <= cut]
                hi = [r for r in keep if key(r) > cut]
            else:
                lo = [r for r in keep if key(r) == 0]
                hi = [r for r in keep if key(r) > 0]
                if len(lo) < 5 or len(hi) < 5:
                    continue
            ql = median([r["id10"] / r[VERT] for r in lo])
            qh = median([r["id10"] / r[VERT] for r in hi])
            pl = median([r["id48"] / r[VERT] for r in lo])
            ph = median([r["id48"] / r[VERT] for r in hi])
            kl, kh = median([key(r) for r in lo]), median([key(r) for r in hi])
            if not ql or qh is None:
                continue
            shown += 1
            print(f"{arm:22s} {label:>7s} {len(lo):5d} {len(hi):5d} {kl:7.3f} {kh:7.3f} "
                  f"{ql:13.4f} {qh:13.4f} {qh / ql:7.3f} {pl:13.4f} {ph:13.4f}")
            res.setdefault(label, []).append((arm, qh / ql, kl, kh))
    if not shown:
        print("  no arm in this set contains both sides of either split")
    for label in ("spbusy", "tiles"):
        mv = res.get(label) or []
        if not mv:
            continue
        qr = sorted(mv, key=lambda x: abs(x[1] - 1.0))
        kl, kh = sorted(x[2] for x in mv), sorted(x[3] for x in mv)
        print(f"  {label}: {len(mv)} arms. The key reads {kl[len(kl) // 2]:,.3f} in the lower half against "
              f"{kh[len(kh) // 2]:,.3f} in the upper, at the median of the arms.")
        print(f"  {label}: id10/vert then differs between the halves by "
              f"{abs(qr[len(qr) // 2][1] - 1) * 100:.2f} % at that median and "
              f"{abs(qr[-1][1] - 1) * 100:.1f} % at most, in {qr[-1][0]}.")
    tiles = res.get("tiles", [])
    real = [x for x in tiles if x[3] >= 1e6]
    weak = [x for x in tiles if x[3] < 1e6]
    print("  VSC_INPUT_TILES is the binning test the repository already uses: `> 0` means a binning pass")
    print("  ran (tools/fdperf/fdperf.cfg-bv line 44 says the flag's run 'never started a binning pass")
    print("  (VSC_INPUT_TILES 0 in every window)'). So only an arm whose upper half is a real tile rate is")
    print("  a render-mode contrast:")
    for arm, ratio, kl, kh in sorted(real):
        print(f"    {arm:22s} bins {kh:,.0f} tiles in the upper half against {kl:,.0f} in the lower, "
              f"id10/vert {ratio:.4f}x")
    if weak:
        print("    not a mode contrast (the upper half is a handful of tiles): "
              + ", ".join(f"{a} {k:,.0f}" for a, _, _, k in sorted(weak)))
    print("  The spbusy split moves the pixel side by well under one percent, so on its own it only shows")
    print("  that id10/vert does not chase small pixel-load wiggles. The render-mode split above, where an")
    print("  arm really changes between binned and direct windows, is the one that moves it.")




def window_mode(r):
    """A window's render mode, read off VSC_INPUT_TILES: `binned` above BIN_TILES, `low rate` for a non-zero
    reading too small to be frames of bins, `zero` for the reading the repository calls 'never started a
    binning pass', `value dropped` for a window whose VSC delta was thrown away, `not sampled` where the cfg
    carried no VSC selector at all."""
    t = r["tiles"]
    if isnum(t):
        return "binned" if t >= BIN_TILES else ("low rate" if t > 0 else "zero")
    return "value dropped" if t == DROPPED else "not sampled"


def print_render_mode(rows):
    """The same window set split by render mode instead of by arm. Inside one arm the binary, both shaders
    and the geometry are fixed, so a quotient that moves between that arm's own binned and unbinned windows
    is not a property of a shader interface, whatever else it is a property of."""
    print("\nRender mode, not arm. VSC_INPUT_TILES is the repository's own test for a binning pass:")
    print("  tools/fdperf/fdperf.cfg-bv line 44 calls a run whose VSC_INPUT_TILES is 0 in every window one")
    print("  that 'never started a binning pass', so a window is read the same way here. The counter's own")
    print("  scale cannot be compared between dumps: the same selector 4 of the VSC group reads 5.4e7 per")
    print("  second in dbg-file and 1.5e3 in tse3-cbforce, one title, one resolution, one frame. Only the")
    print("  gap inside the data is used to class a window, and a rate a 2560x1440 frame could not produce")
    print("  is named for what it is instead of being read as a tile count:")
    classes = {}
    for r in rows:
        if not (isnum(r["id10"]) and isnum(r["id48"]) and isnum(r[VERT]) and r[VERT]):
            continue
        classes.setdefault(window_mode(r), []).append(r)
    for mode in MODES:
        rs = classes.get(mode)
        if not rs:
            continue
        vals = sorted(r["tiles"] for r in rs if isnum(r["tiles"]))
        note = {"binned": "  <- a rate only a binning pass at frame rate produces",
                "low rate": "  <- a non-zero rate no 2560x1440 frame can produce as bins",
                "zero": "  <- the test the repository uses for 'no binning pass started'",
                "value dropped": "  <- this window's VSC delta was a u64 wraparound",
                "not sampled": "  <- the cfg carried no VSC selector"}.get(mode, "")
        if vals:
            print(f"  {mode:11s}: {len(rs):4d} windows, the counter between {vals[0]:,} and {vals[-1]:,}"
                  + note)
        else:
            print(f"  {mode:11s}: {len(rs):4d} windows, no VSC reading to class" + note)
    head = (f"  {'arm':22s} {'mode':>11s} {'win':>4s} {'tiles':>12s} {'id10/vert':>10s} {'id48/vert':>10s} "
            f"{'attr/vert':>10s} {'B/vert':>8s} {'vpcram/vert':>12s} {'id10/vpcram':>12s}")
    print(head)
    print("  " + "-" * (len(head) - 2))
    by = {}
    for r in rows:
        if not (isnum(r["id10"]) and isnum(r["id48"]) and isnum(r[VERT]) and r[VERT]):
            continue
        by.setdefault((r["arm"], window_mode(r)), []).append(r)
    for (arm, mode) in sorted(by):
        rs = by[(arm, mode)]
        d = {n: median([r[n] for r in rs]) for n, _ in DENOMS}
        a = median([r["id10"] for r in rs])
        b = median([r["id48"] for r in rs])
        print(f"  {arm:22s} {mode:>11s} {len(rs):4d} {fnum(median([r['tiles'] for r in rs]), 12, ',.0f')} "
              f"{div(a, d[VERT], 10)} {div(b, d[VERT], 10)} {div(d[ATTR], d[VERT], 10)} "
              f"{div(d[BYTES], d[VERT], 8)} {div(d[VPCRAM], d[VERT], 12)} {div(a, d[VPCRAM], 12)}")
    for mode in ("binned", "low rate", "zero", "not sampled"):
        # a cell of two or three windows is one odd frame, not a mode: only cells with 5 windows count here
        arms = sorted(a for a, m in by if m == mode and len(by[(a, m)]) >= 5)
        if not arms:
            continue
        vals = sorted(median([r["id10"] / r[VERT] for r in by[(a, mode)]]) for a in arms)
        skipped = len({a for a, m in by if m == mode}) - len(arms)
        print(f"  {mode:11s}: {len(arms):2d} arms show that mode in at least 5 windows, id10/vert "
              f"{vals[0]:.4f} to {vals[-1]:.4f} ({vals[-1] / vals[0]:.2f}x)"
              + (f"; {skipped} arm(s) with fewer windows in that mode are left out" if skipped else ""))
    def quot(ws, num, den):
        return median([r[num] for r in ws]) / median([r[den] for r in ws])

    mixed = [a for a in sorted({x[0] for x in by})
             if (a, "binned") in by and any(m != "binned" for x, m in by if x == a)]
    if not mixed:
        print("  no arm carries both a binned and an unbinned window, so the mode cannot be separated from")
        print("  the arm inside one session here.")
    for arm in mixed:
        b = by[(arm, "binned")]
        for m in sorted({m for x, m in by if x == arm and m != "binned"}):
            dr = by[(arm, m)]
            print(f"  {arm} is one session, one binary, one pair of shaders, and it carries both modes:")
            print(f"  {' ' * len(arm)}id10/vert {quot(b, "id10", VERT):.4f} over its {len(b)} binned windows "
                  f"against {quot(dr, "id10", VERT):.4f} over its {len(dr)} {m} ones,")
            print(f"  {' ' * len(arm)}a factor {quot(b, "id10", VERT) / quot(dr, "id10", VERT):.3f}, while "
                  f"attr/vert goes {quot(b, ATTR, VERT):.4f} -> {quot(dr, ATTR, VERT):.4f} and")
            print(f"  {' ' * len(arm)}decoded bytes per vertex "
                  f"{quot(b, BYTES, VERT):.2f} -> {quot(dr, BYTES, VERT):.2f}: the interface the shaders "
                  "declare did not change.")
    print("  So the per-vertex reading of id 10 is not a property of the shader interface. Where one session")
    print("  contains both render modes, and the binary and both shaders cannot have changed, the counter")
    print("  per vertex moves by the factor printed above while the interface quotients do not move.")


def print_pc_group(dmps):
    print("\nPC group over every dump scanned: dead selector or idle workload?  id 19 is PC_VERTEX_HITS and")
    print("id 39 is PC_TAG_CHECKED_VERTICES (a7xx_perfcntrs.xml). `other PC counter` is any PERF_PC_* name")
    print("in the same window except id 19 itself. `win w/ 19` counts windows where the selector printed.")
    head = (f"{'arm':22s} {'win':>4s} {'id19':>6s} {'id39':>6s} {'win w/ 19':>9s} {'id19==0':>8s} "
            f"{'id19>0':>7s} {'max id19':>13s} {'19==0 & other!=0':>17s} {'19>0 & others==0':>17s} "
            f"{'PC names':>8s}")
    print(head)
    print("-" * len(head))
    tot = dict.fromkeys(("d19", "d39", "w19", "zero", "nz", "zother", "nnone"), 0)
    seen = {}
    for d in dmps:
        w19 = [w for w in d.samples if HITS in w]
        zero = [w for w in w19 if w[HITS] == 0]
        nz = [w for w in w19 if w[HITS]]
        zother = [w for w in zero if any(v for k, v in w.items()
                                         if k.startswith("PERF_PC_") and k != HITS)]
        nnone = [w for w in nz if not any(v for k, v in w.items()
                                          if k.startswith("PERF_PC_") and k != HITS)]
        names = sorted(k[5:] for k in d.present if k.startswith("PERF_PC_"))
        for n in names:
            seen[n] = seen.get(n, 0) + 1
        tot["d19"] += bool(w19)
        tot["d39"] += TAGGED in d.present
        tot["w19"] += len(w19)
        tot["zero"] += len(zero)
        tot["nz"] += len(nz)
        tot["zother"] += len(zother)
        tot["nnone"] += len(nnone)
        print(f"{d.tag:22s} {len(d.samples):4d} {('yes' if w19 else 'no'):>6s} "
              f"{('yes' if TAGGED in d.present else 'no'):>6s} {len(w19):9d} {len(zero):8d} "
              f"{len(nz):7d} {(f'{max(w[HITS] for w in w19):,}' if w19 else MISSING):>13s} "
              f"{len(zother):17d} {len(nnone):17d} {len(names):8d}")
    print(f"  dumps scanned {len(dmps)}; id 19 present in {tot['d19']}; id 39 present in {tot['d39']}")
    print(f"  windows carrying id 19: {tot['w19']}; reading 0: {tot['zero']}; reading > 0: {tot['nz']}; "
          f"of the zero windows another PC counter was non-zero in {tot['zother']}; of the non-zero "
          f"windows every other PC counter was zero in {tot['nnone']}")
    per_name = {}
    for d in dmps:
        for w in d.samples:
            for k, v in w.items():
                if k.startswith("PERF_PC_"):
                    a = per_name.setdefault(k, [set(), 0, 0, 0, 0])
                    a[0].add(d.tag)
                    a[1] += 1
                    a[2] += v == 0
                    a[3] += v > 0
                    a[4] = max(a[4], v)
    print("\n  Every PERF_PC_* selector a committed dump prints, and whether it ever counts. A selector that")
    print("  is non-zero somewhere is wired on a740, so a window of it reading 0 is the workload, not the")
    print("  selector. A name missing from this list was programmed by no cfg in tools/fdperf/ and no dump")
    print("  can answer anything about it.")
    head = f"  {'selector':30s} {'dumps':>5s} {'windows':>8s} {'== 0':>6s} {'> 0':>6s} {'max':>14s}"
    print(head)
    print("  " + "-" * (len(head) - 2))
    for k in sorted(per_name):
        tags, nw, n0, nz_n, mx = per_name[k]
        print(f"  {k[5:]:30s} {len(tags):5d} {nw:8d} {n0:6d} {nz_n:6d} {mx:14,}")
    reasons = {"PC_RESERVED": "the XML calls this selector a reserved slot, so it counts nothing defined",
               "PC_STALL_CYCLES_TESS": "RE4 draws no tessellated primitive, so there is nothing to stall on"}
    for k in sorted(per_name):
        tags, nw, n0, nz_n, mx = per_name[k]
        if n0 > nw / 2 and mx > 0:
            name = k[5:]
            print(f"  {name} reads 0 in {n0} of its {nw} windows and never above {mx:,} counts: printed, so")
            print(f"  it is wired, but {reasons.get(name, 'this workload leaves it near zero')}.")
    print("  PC names anywhere (dumps carrying the name): "
          + ", ".join(f"{k} x{v}" for k, v in sorted(seen.items())))
    print("  Absent from every dump = no cfg in tools/fdperf/ ever programmed it (40.33), so the kernel")
    print("  was never asked and nothing can be said about it. Present and non-zero = wired and counting,")
    print("  so a zero window of it is the workload being idle, not the selector being dead.")


def print_header():
    """The file header the repository convention puts on a generated artifact: what the table is,
    the command that regenerates it, and the reading rules a quote from it must carry."""
    print("# What the VPC/SP exchange counters add up to, window by window, over the dumps already in git")
    print("#       (Resident Evil 4, re4.exe, D3D12 via vkd3d-proton 3.1.0, 2560x1440. The arms differ in")
    print("#       render mode, cache mode, clock and frame rate - never in the build, so no arm changes")
    print("#       the number of vertex-shader outputs; `results/games/README.md` is the registry of arms).")
    print("# regenerate: scripts/vpc-sp-pair.py --dumps 'results/games/**/*.txt' \\")
    print("#                 > results/games/re4/vpc-sp-pair.txt")
    print("# reads: committed dumps, found by their own header rather than by file name. The corpus is the")
    print("#       game runs, because the question is about the game; the count, the per-title breakdown and")
    print("#       how many dumps carry the pair are in the `# scanned` and `# carries both` blocks below,")
    print("#       which are derived - do not quote a count from prose. The default glob also picks up")
    print("#       results/synthetics/, whose probe runs carry neither selector: journal 40.36 cites that run")
    print("#       separately, for the two PC columns. Every window goes through scripts/fdperf_sections.py.")
    print("#       Nothing here samples the GPU: the script reads files. A dump under a gitignored raw/")
    print("#       directory is skipped - the pre-curation copy of a run, which no claim cites (AGENTS.md).")
    print("# ids: the value= attributes of A7XX_PERF_<GROUP>_<name> in")
    print("#       ../mesa27-src/src/freedreno/registers/adreno/a7xx_perfcntrs.xml, so VPC 10 is")
    print("#       A7XX_PERF_VPC_SP_COMPONENTS, SP 48 is A7XX_PERF_SP_EXPORT_VPC_TRANS, PC 19 is")
    print("#       A7XX_PERF_PC_VERTEX_HITS and PC 39 is A7XX_PERF_PC_TAG_CHECKED_VERTICES. The XML")
    print("#       gives no desc= attribute for any of them, so no column below is a decoded quantity")
    print("#       (journal 40.7, 40.11, 40.33): each is a ratio of two counters. Queue 34's")
    print("#       \"PC_TAG_CHECKED_VERTICES (id 19)\" conflates the last two ids.")
    print("# re-cuts: journal 40.34's row for this pair called the two counters one signal from a ratio")
    print("#       of per-arm medians (1.00000) over the windows of t_rel 20-105 s at CP_ALWAYS_COUNT")
    print("#       >= 676 MHz (1176 of 1293 windows in 33 arms, results/games/re4/vpc-state.txt). This file")
    print("#       prints every window of every arm that carries the pair, the two raw deltas and their")
    print("#       difference as an integer, so \"equal\" is read as equality and not as a quotient inside a")
    print("#       tolerance. That clock filter is why vpc-state lists 33 arms and not 34: vpc-hp40 has no")
    print("#       window at >= 676 MHz, and its one all-idle window is where both selectors read exactly 0.")
    print("# values are window deltas from `fdperf -r 1000 -d` (docs/fdperf-a7xx.md, section Windows). The")
    print("#       `*M/s` columns are delta/1e6 and are millions of counts per second only while `clk MHz`")
    print("#       says the window really was one second of the pinned clock; `clk MHz` is that window's own")
    print("#       CP_ALWAYS_COUNT/1e6.")
    print("# MISSING means no cfg in tools/fdperf/ programmed that selector, so it is an unanswered question")
    print("#       and never a zero. DROPPED means this window's delta was thrown away as a u64 wraparound")
    print("#       or [invalid] by scripts/fdperf_sections.py and is kept out of every statistic below.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dumps", default="results/**/*.txt",
                    help="glob to scan for dumps (default: every .txt under results/)")
    ap.add_argument("--arms", help="comma-separated arm names, default every arm that carries both")
    ap.add_argument("--lo", type=float, help="first t_rel in seconds (default: the file's first sample)")
    ap.add_argument("--hi", type=float, help="last t_rel in seconds (default: the file's last sample)")
    ap.add_argument("--no-rows", action="store_true", help="summaries only, no per-window table")
    ap.add_argument("--include-scratch", action="store_true",
                    help="also read the dumps under a gitignored raw/ directory (they are copies of the "
                         "same runs and their arm names collide with the committed ones)")
    args = ap.parse_args()

    paths, skipped = find_dumps(args.dumps, args.include_scratch)
    if not paths:
        sys.exit(f"no fdperf dump found under {args.dumps!r}")
    dmps = []
    for p in paths:
        try:
            dmps.append(Dump(p))
        except Exception as exc:                                        # noqa: BLE001
            print(f"# {p}: unreadable: {exc}")

    both = [d.tag for d in dmps if ID10 in d.present and ID48 in d.present]
    only_one = [d.tag for d in dmps if (ID10 in d.present) != (ID48 in d.present)]
    neither = [d.tag for d in dmps if ID10 not in d.present and ID48 not in d.present]
    if args.arms:
        want = set(args.arms.split(","))
        both = [t for t in both if t in want]

    print_header()
    print_scope(dmps, both, only_one, neither, args.dumps, skipped)
    print(f"# dumps read: {len(dmps)}, samples read: {sum(len(d.samples) for d in dmps)}")
    rows = print_rows(dmps, both, args.lo, args.hi, args.no_rows)
    print_equality(rows, dmps)
    print_per_arm(dmps, rows)
    print_denominators(rows)
    print_pixel_cost(rows)
    print_render_mode(rows)
    print_pc_group(dmps)
    print(f"\nWindows read: {len(rows)} over {len({r['arm'] for r in rows})} arms"
          + (" (the table above)." if not args.no_rows else "."))
    print("No unit is derived here. The XML gives none (40.7, 40.11, 40.33), and no arm in git changes the")
    print("number of vertex-shader outputs, so queue 34's known-interface probe stays the only measurement")
    print("that can name one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
