#!/usr/bin/env python3
"""One loader for `fdperf -r <period> -d` dumps, with the two dump defects filtered out.

Shared by scripts/fdperf-vpc-ratios.py, scripts/fdperf-tse-ratios.py and
scripts/fdperf-vpcram-ratios.py; those three print different ratio tables over the same
samples, so the parsing rules must not be three separate copies.

What the dump actually looks like (see also docs/fdperf-a7xx.md, "Requirements and
pitfalls").  One `fdperf -r 1000 -d` call prints the groups of the device in order: the
ordinary groups first, then the binning/visibility ones.  The group list is
`src/freedreno/registers/adreno/a7xx_perfcntrs.json`, which defines `BV_CP`, `BV_PC`,
`BV_VFD`, `BV_VPC` (num 6, `select_offset` 6), `BV_TP`, `BV_SP`, `BV_UFC`, `BV_TSE` (num 4),
`BV_RAS`, `BV_LRZ`, `BV_HLSQ` after the ordinary groups, and each BV group's countable list is
the *same* enum as its ordinary twin (`"type": "a7xx_vpc_perfcounter_select"` for both `VPC`
and `BV_VPC`).  That is why a dump carries the same name twice.  Both rules below came out of
the 21.11 runs:

1. **A name that appears only in the BV section is not a counter of the group the cfg
   programmed.**  In `results/raw/fdperf-vpc3base.txt` the ordinary `PERF_VPC_BUSY_CYCLES` is
   621,619,685 (91.41 %) and the BV copy of the same name reads 458,806 (0.07 %);
   `PERF_VPC_WORKING_CYCLES`, which that cfg does not program in the ordinary VPC group,
   appears only in the BV section at 0.03 % - quoting it as "the VPC's working cycles" would be
   quoting the BV thread.  `load()` keeps the ordinary value and reports such names in
   `unmeasured`, which the ratio scripts print as "not sampled by this cfg".  The BV copies are
   readable in their own right (their medians are in journal 40.8), just not as the ordinary
   block's numbers.
2. **A window delta can wrap.**  `results/raw/fdperf-cbbase.txt` has one sample of 70 with
   `PERF_VSC_INPUT_TILES: 18446744073709551290` = 2**64 - 82, the two's-complement image of a
   negative delta.  Averaged as printed, it turned a counter that reads 528 tiles/s into
   "449,920,587,163 Mc/s", which was then written up as a broken selector.  Values >= 2**63
   are dropped and counted in `dropped`.

The section split is positional: a line belongs to the second section when it repeats a name
seen more than `section_gap` lines earlier (default 32).  The plain distance rule is needed
because the first section legitimately repeats two CP names within 5 lines (`PERF_CP_MODE_SWITCH`,
`PERF_CP_CONTEXT_DONE`), which is not a section boundary.
"""
import re

ROW = re.compile(r"^(PERF_\w+):\s+(\S+)")

WRAP_LIMIT = 1 << 63


def clean(name, raw, dropped):
    """One printed value, filtered.  Returns an int or None; None also records why in `dropped`."""
    if not raw.isdigit():
        dropped[name] = dropped.get(name, 0) + 1
        return None
    val = int(raw)
    if val >= WRAP_LIMIT:
        dropped[name] = dropped.get(name, 0) + 1
        return None
    return val


def load_sections(path, section_gap=32):
    """Returns (samples, bv_samples, unmeasured, dropped, bv_dropped).

    samples      list of dicts for the ordinary groups: {'t': s after the first sample, name: value}
    bv_samples   list of dicts for the `BV_*` half of the same samples, same order and same 't'
    unmeasured   names seen only in the BV half (so never programmed in the ordinary group)
    dropped      {name: values thrown away as wrapped or [invalid]}, ordinary half
    bv_dropped   the same for the BV half

    `load()` is this function with the BV half discarded, and is what the ratio tables use;
    scripts/fdperf-bv-table.py is the one reader that wants both halves (journal 40.8, queue 20).
    """
    samples, bv_samples = [], []
    cur, curbv = None, None
    unmeasured, dropped, bv_dropped = set(), {}, {}
    first, split = {}, None
    pos = -1

    with open(path, errors="replace") as f:
        for line in f:
            if line.startswith("=== sample"):
                t = float(line.split()[2])
                cur, curbv = {"t": t}, {"t": t}
                samples.append(cur)
                bv_samples.append(curbv)
                first, split, pos = {}, None, -1
                continue
            if cur is None:
                continue
            m = ROW.match(line)
            if not m:
                continue
            name, raw = m.group(1), m.group(2)
            pos += 1
            if name in first and pos - first[name] > section_gap:
                split = pos
            if split is not None and pos >= split:
                if name not in first:
                    unmeasured.add(name)
                if name not in curbv:
                    val = clean(name, raw, bv_dropped)
                    if val is not None:
                        curbv[name] = val
                continue
            first.setdefault(name, pos)
            if name in cur:
                continue
            val = clean(name, raw, dropped)
            if val is not None:
                cur[name] = val
    return samples, bv_samples, unmeasured, dropped, bv_dropped


def load(path, section_gap=32):
    """Returns (samples, unmeasured, dropped) - the ordinary groups only, see load_sections."""
    samples, _bv, unmeasured, dropped, _bvd = load_sections(path, section_gap)
    return samples, unmeasured, dropped


def window(samples, lo, hi):
    t0 = samples[0]["t"] if samples else 0.0
    out = []
    for s in samples:
        if lo <= s["t"] - t0 <= hi:
            s = dict(s)
            s["t"] -= t0
            out.append(s)
    return out
