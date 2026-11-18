#!/usr/bin/env python3
"""fdperf-analyze.py - turn fdperf samples into per-block load.

Input: a sampler file from scripts/fdperf-sample.sh ("=== sample <t> ==="
blocks + "NAME: value" / "NAME: value NN.NN%" lines) plus arguments:
  fdperf-analyze.py <file> [tsv-out] [--freq <MHz>]

A note on windows: fdperf (with the windowed-delta patch, see
docs/fdperf-a7xx.md) reads two core samples per run and prints the delta
between them - the window is the period from "fdperf -r <ms>" (appears in the
file header as "period_ms=").  Between the "=== sample" marks there is about
2*period (process start + waiting for two samples) - that is NOT the counter
window; use period_ms for normalisation.

What it computes:
  * block busy% = BUSY_CYCLES_block / (freq * window) * 100.
    freq is the actual core frequency, --freq (680 MHz by default = the max
    of Adreno 740; in saturated RE4 windows ondemand holds about max).  It is
    cross-checked via the CP_ALWAYS_MHZ column (CP_ALWAYS_COUNT/window) and
    the cur_freq trace.
  * IMPORTANT (verified on a740, see docs/fdperf-a7xx.md): RBBM_ALWAYS_ON and
    RBBM_*_BUSY are NOT in the core-frequency domain (at 220 and 680 MHz they
    yield 0.3-0.8 "MHz" and do not divide by core-freq - duty would come out
    above 100%).  They are printed in a separate block in cycles/s, without
    percentages.  CP_BUSY is also counted in its own (CP/bus) domain - busy%
    by core-freq only approximates it.
  * latencies (VBIF UCHE, TP, SP GM/TEXTURE, UFC, CMP) in cycles per access;
  * traffic (beats/req per second) and events (draws, VS invocations,
    vertices, pixels).

Duplicate names inside a sample (BV groups count the countable by default)
are resolved by "first occurrence".

A counter missing from the dump (a cfg line beyond the group hw budget -
fdperf SILENTLY ignores extra lines, see docs/fdperf-a7xx.md) -> None: an
empty cell in the TSV, skipped in the summaries.  A false 0 is never printed.
"""
import re
import sys

SAMPLE_RE = re.compile(r'^=== sample (\S+) ===$')
LINE_RE = re.compile(r'^([A-Z][A-Z0-9_]+):\s+(\d+)(?:\s+\S+)?$')
HDR_RE = re.compile(r'^# period_ms=(\d+)')

# core-domain blocks (divided by the core frequency):
BUSY = {
    'PC': 'PERF_PC_BUSY_CYCLES',
    'VFD': 'PERF_VFD_BUSY_CYCLES',
    'HLSQ': 'PERF_HLSQ_BUSY_CYCLES',
    'VPC': 'PERF_VPC_BUSY_CYCLES',
    'TSE': 'PERF_TSE_BUSY_CYCLES',
    'RAS': 'PERF_RAS_BUSY_CYCLES',
    'UCHE': 'PERF_UCHE_BUSY_CYCLES',
    'TP': 'PERF_TP_BUSY_CYCLES',
    'SP': 'PERF_SP_BUSY_CYCLES',
    'RB': 'PERF_RB_BUSY_CYCLES',
    'VSC': 'PERF_VSC_BUSY_CYCLES',
    'CCU': 'PERF_CCU_BUSY_CYCLES',
    'LRZ': 'PERF_LRZ_BUSY_CYCLES',
    'UFC': 'PERF_UFC_BUSY_CYCLES',
}
# CP - its own domain (CP/bus clocks), approximate:
CP_BUSY = 'PERF_CP_BUSY_CYCLES'
# RBBM (GMU) - not the core domain, printed in cycles/s:
RBBM_RAW = {
    'RBBM_ALWAYS_ON': 'PERF_RBBM_ALWAYS_ON',
    'RBBM_VBIF': 'PERF_RBBM_VBIF_BUSY',
    'RBBM_UCHE': 'PERF_RBBM_UCHE_BUSY',
    'RBBM_HLSQ': 'PERF_RBBM_HLSQ_BUSY',
    'RBBM_PCDC': 'PERF_RBBM_PC_DCALL_BUSY',
    'RBBM_PCVSD': 'PERF_RBBM_PC_VSD_BUSY',
}

LATENCY = [
    ('UCHE_VBIF', 'PERF_UCHE_VBIF_LATENCY_CYCLES', 'PERF_UCHE_VBIF_LATENCY_SAMPLES'),
    ('TP', 'PERF_TP_LATENCY_CYCLES', 'PERF_TP_LATENCY_TRANS'),
    ('SP_GM', 'PERF_SP_GM_LOAD_LATENCY_CYCLES', 'PERF_SP_GM_LOAD_LATENCY_SAMPLES'),
    ('SP_TEX', 'PERF_SP_TEXTURE_FETCH_LATENCY_CYCLES', 'PERF_SP_TEXTURE_FETCH_LATENCY_SAMPLES'),
    ('UFC', 'PERF_UFC_MISS_LATENCY_CYCLES', 'PERF_UFC_MISS_LATENCY_SAMPLES'),
    ('CMP_VBIF', 'PERF_CMPDECMP_VBIF_LATENCY_CYCLES', 'PERF_CMPDECMP_VBIF_LATENCY_SAMPLES'),
]
TRAFFIC = [
    ('UCHE_RD_BEATS', 'PERF_UCHE_VBIF_READ_BEATS_CH0', 'PERF_UCHE_VBIF_READ_BEATS_CH1'),
    ('UCHE_WR_BEATS', 'PERF_UCHE_VBIF_WRITE_BEATS_CH0', 'PERF_UCHE_VBIF_WRITE_BEATS_CH1'),
    ('UCHE_RD_REQ', 'PERF_UCHE_RAM_READ_REQ', None),
    ('UCHE_WR_REQ', 'PERF_UCHE_RAM_WRITE_REQ', None),
    # per-client UCHE (only in cfg-vertex, fdperf.cfg-vertex):
    ('UCHE_RD_VFD', 'PERF_UCHE_VBIF_READ_BEATS_VFD', None),
    ('UCHE_RD_TP', 'PERF_UCHE_VBIF_READ_BEATS_TP', None),
    ('UCHE_RD_SP', 'PERF_UCHE_VBIF_READ_BEATS_SP', None),
    ('UCHE_RD_PC', 'PERF_UCHE_VBIF_READ_BEATS_PC', None),
    ('UCHE_REQ_VFD', 'PERF_UCHE_READ_REQUESTS_VFD', None),
    ('UCHE_REQ_TP', 'PERF_UCHE_READ_REQUESTS_TP', None),
    ('UCHE_REQ_SP', 'PERF_UCHE_READ_REQUESTS_SP', None),
    ('UCHE_REQ_PC', 'PERF_UCHE_READ_REQUESTS_PC', None),
    ('UCHE_GMEM_RD', 'PERF_UCHE_GMEM_READ_BEATS', None),
    ('UCHE_GMEM_WR', 'PERF_UCHE_GMEM_WRITE_BEATS', None),
    ('UBWC_RD', 'PERF_UCHE_UBWC_READ_BEATS', None),
    ('UBWC_WR', 'PERF_UCHE_UBWC_WRITE_BEATS', None),
    ('CCU_GMEM_RD', 'PERF_CCU_GMEM_READ', None),
    ('CCU_GMEM_WR', 'PERF_CCU_GMEM_WRITE', None),
    ('DRAW', 'PERF_CP_SQE_DRAW_EXEC', None),
    ('VS_INV', 'PERF_PC_VS_INVOCATIONS', None),
    ('VERTS', 'PERF_VFD_TOTAL_VERTICES', None),
    ('PIXELS', 'PERF_SP_PIXELS', None),
    ('FS_INSTR', 'PERF_SP_FS_INSTRUCTIONS', None),
    ('PRIM_IN', 'PERF_TSE_INPUT_PRIM', None),
]


def parse(path):
    samples = []
    cur = None
    period_ms = None
    for line in open(path, encoding='utf-8', errors='replace'):
        m = HDR_RE.match(line)
        if m:
            period_ms = int(m.group(1))
            continue
        m = SAMPLE_RE.match(line)
        if m:
            cur = {'t': float(m.group(1)), 'v': {}}
            samples.append(cur)
            continue
        if cur is None:
            continue
        m = LINE_RE.match(line.strip())
        if m and m.group(1) not in cur['v']:
            cur['v'][m.group(1)] = int(m.group(2))
    return samples, (period_ms or 1000) / 1000.0


def stats(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, None
    return sum(vals) / len(vals), max(vals)


def main():
    args = sys.argv[1:]
    freq_mhz = 680.0
    if '--freq' in args:
        i = args.index('--freq')
        freq_mhz = float(args[i + 1])
        del args[i:i + 2]
    if not args:
        print(__doc__)
        sys.exit(1)
    samples, window = parse(args[0])
    if not samples:
        print('no samples')
        sys.exit(1)
    freq_hz = freq_mhz * 1e6

    # per-sample rows (window - the core window from period_ms, NOT the mark
    # interval).  The counter is absent from the dump (beyond the group hw
    # budget - fdperf silently ignores extra cfg lines) => None, not 0.
    rows = []
    for s in samples:
        v = s['v']
        row = {'t': s['t']}
        for name, key in BUSY.items():
            x = v.get(key)
            row[name] = (x * 100.0 / (freq_hz * window)
                         if x is not None else None)
        x = v.get(CP_BUSY)
        row['CP'] = (x * 100.0 / (freq_hz * window)
                     if x is not None else None)
        for name, key in RBBM_RAW.items():
            x = v.get(key)
            row[name] = x / window if x is not None else None
        row['CP_ALWAYS_MHZ'] = v.get('PERF_CP_ALWAYS_COUNT', 0) / window / 1e6
        for name, cyc, sam in LATENCY:
            c, m = v.get(cyc), v.get(sam)
            row[name + '_CYC'] = (c / m if (c is not None and
                                            m is not None and m > 100)
                                  else None)
        for name, a, b in TRAFFIC:
            xa = v.get(a)
            xb = v.get(b) if b else None
            # both keys must be in the dump, otherwise the sum is incomplete => None
            x = None if (xa is None or (b is not None and xb is None)) \
                else xa + (xb if b else 0)
            row[name + '_PER_S'] = x / window if x is not None else None
        rows.append(row)

    # Keep every sample: loading/transitions carry information too (upload
    # load shows up in UCHE/CP).  The scene is overlaid from the CSV by time
    # separately.
    def col(name):
        return [r.get(name) for r in rows]

    print(f"# {len(rows)} samples, window {window*1000:.0f} ms, freq {freq_mhz:.0f} MHz")
    print(f"### core-block busy% = BUSY/(freq*window) (mean / max):")
    print(f"{'block':12} {'mean%':>8} {'max%':>8}")
    order = ['PC', 'VFD', 'HLSQ', 'VPC', 'TSE', 'RAS', 'UCHE', 'TP',
             'SP', 'RB', 'CCU', 'LRZ', 'UFC', 'VSC']
    for b in order:
        m, mx = stats(col(b))
        if m is None:
            continue
        print(f"{b:12} {m:8.1f} {mx:8.1f}")
    m, mx = stats(col('CP'))
    print(f"{'CP*':12} {m:8.1f} {mx:8.1f}")
    print("  (* CP - its own domain, approximate)")

    print("\n### RBBM (GMU domain, cycles/s - do NOT divide by core-freq):")
    print(f"{'name':16} {'mean/s':>14} {'max/s':>14}")
    for b in RBBM_RAW:
        m, mx = stats(col(b))
        if m is None:
            continue
        print(f"{b:16} {m:14.0f} {mx:14.0f}")

    fm, fx = stats(col('CP_ALWAYS_MHZ'))
    print(f"\nCP_ALWAYS_COUNT/window: mean {fm:.1f} MHz, max {fx:.1f} MHz "
          f"(CP domain diagnostics; cross-check against cur_freq)")

    print("\n### latency (cycles per access, mean / max):")
    print(f"{'name':10} {'mean':>10} {'max':>10}")
    for name, _, _ in LATENCY:
        m, mx = stats(col(name + '_CYC'))
        if m is not None:
            print(f"{name:10} {m:10.1f} {mx:10.1f}")

    print("\n### traffic / events (per second, mean / max):")
    print(f"{'name':12} {'mean':>14} {'max':>14}")
    for name, _, _ in TRAFFIC:
        m, mx = stats(col(name + '_PER_S'))
        if m is not None:
            print(f"{name:12} {m:14.0f} {mx:14.0f}")

    # per-sample dump (for cross-checking against the CSV)
    if len(args) > 1:
        out = args[1]
        keys = ['t', 'CP_ALWAYS_MHZ'] + order + ['CP'] + list(RBBM_RAW) + \
               [n + '_CYC' for n, _, _ in LATENCY] + \
               [n + '_PER_S' for n, _, _ in TRAFFIC]
        with open(out, 'w', encoding='utf-8') as f:
            f.write('\t'.join(keys) + '\n')
            for r in rows:
                cells = []
                for k in keys:
                    if k == 't':
                        cells.append(f"{r['t']:.3f}")
                        continue
                    val = r.get(k)
                    # None - not measured (beyond the hw budget), not 0:
                    cells.append('' if val is None else f"{val:.4g}")
                f.write('\t'.join(cells) + '\n')
        print(f"\nper-sample TSV: {out}")


if __name__ == '__main__':
    main()
