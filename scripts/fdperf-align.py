#!/usr/bin/env python3
"""fdperf-align.py - overlay the fdperf windows onto the MangoHud CSV and the cur_freq trace.

Input:
  fdperf-align.py <tsv> <freq-trace> <csv> <csv-start-epoch>
                  [--offset sec=1.65] [--freq-fallback MHz=680]
                  [--analyzer-freq MHz=680]

  <tsv>            per-window TSV from fdperf-analyze.py (column t = start of
                   the fdperf process; the busy% values are normalised to
                   analyzer-freq, see below)
  <freq-trace>     "epoch_hz_hertz" lines from /sys/class/devfreq/*/cur_freq
                   (5-50 Hz, any interval)
  <csv>            MangoHud CSV: 3 header lines, then fps (column 0),
                   gpu_core_clock MHz (column 7), elapsed in ns (the last one);
                   csv-start-epoch = the moment MangoHud started (about the
                   time in the file name).
  <csv-start-epoch> epoch (float) of the CSV start.

Window model: the t label in the TSV is the start of the fdperf process
(sudo + PERFCNTR_CONFIG); the first core window starts after ~period, and the
delta of the last two windows is printed (see
tools/fdperf/fdperf-windowed-delta.patch).  So the "middle" of the counter
window is about t + offset (1.65 s by default with period 1 s), and the
frequency is averaged over the trace on [t+offset-0.65, t+offset+0.65].

For every window we print:
  * fps and the core frequency from the CSV (the closest row by elapsed);
  * block busy% normalised from analyzer-freq to the actual window frequency
    and with the multi-instance divisors: SP/TP /12 (usptp = num_sp_cores*2),
    UCHE /2, CCU /6 (num_ccu), RB /4 - see docs/fdperf-a7xx.md;
  * UCHE read beats, VS invocations, pixels (M/s).
"""
import csv
import sys

# multi-instance divisors (a740; derivation in docs/fdperf-a7xx.md)
DIV = {'SP': 12, 'TP': 12, 'UCHE': 2, 'CCU': 6, 'RB': 4}


def main():
    args = sys.argv[1:]
    opts = {'offset': 1.65, 'freq-fallback': 680.0, 'analyzer-freq': 680.0}
    while args and args[0].startswith('--'):
        key = args[0][2:]
        if key in opts:
            opts[key] = float(args[1])
            del args[:2]
        else:
            sys.exit(f'unknown flag: {args[0]}')
    if len(args) != 4:
        print(__doc__)
        sys.exit(1)
    tsv_path, freq_path, csv_path = args[:3]
    csv_start = float(args[3])
    offset = opts['offset']
    f_fallback = opts['freq-fallback']
    f_base = opts['analyzer-freq']

    # freq trace: [(t, hz)]
    freq = []
    for line in open(freq_path):
        parts = line.split()
        if len(parts) >= 2:
            freq.append((float(parts[0]), int(parts[1])))

    # csv: (elapsed_s, fps, gpu_core_clock_MHz) - elapsed in ns
    fps_rows = []
    with open(csv_path, newline='') as f:
        r = list(csv.reader(f))
    for row in r[3:]:
        try:
            fps = float(row[0])
            el = float(row[-1]) / 1e9
            clk = float(row[7])
            fps_rows.append((el, fps, clk))
        except (ValueError, IndexError):
            pass

    def freq_at(t0, t1):
        xs = [f for t, f in freq if t0 <= t <= t1]
        return sum(xs) / len(xs) / 1e6 if xs else None

    def fps_at(el):
        best = min(fps_rows, key=lambda x: abs(x[0] - el), default=None)
        if not best:
            return None, None
        return best[1], best[2]

    hdr = open(tsv_path).readline().split('\t')
    rows = []
    with open(tsv_path) as f:
        next(f)
        for line in f:
            vals = line.rstrip('\n').split('\t')
            rows.append(dict(zip(hdr, vals)))

    print(f"# offset {offset:.2f} s, freq-fallback {f_fallback:.0f} MHz, "
          f"analyzer-freq {f_base:.0f} MHz, csv-start {csv_start:.0f}")
    print(f"{'t_rel':>8} {'freq':>6} {'fps':>6} | "
          f"{'PC':>5} {'VFD':>5} {'VPC':>5} {'TSE':>5} {'RAS':>5} | "
          f"{'SP':>5} {'TP':>5} {'RB':>5} {'CCU':>5} {'LRZ':>5} {'UFC':>5} | "
          f"{'UCHE':>5} {'HLSQ':>5} {'CP*':>5} | "
          f"{'UCHErd/s':>9} {'VSinv/s':>9} {'PIX/s':>9}")
    print('-' * 130)
    for r in rows:
        t = float(r['t'])
        tmid = t + offset  # middle of the counter window
        el = tmid - csv_start
        f = freq_at(tmid - 0.65, tmid + 0.65)
        if f is None:
            f = f_fallback
        fps, clk = fps_at(el)
        if clk is not None and clk >= 100:
            f = clk  # the CSV frequency is more precise than the trace (same field, per frame)
        f = max(f, 100.0)

        def cell(name):
            v = r.get(name, '')
            return float(v) if v != '' else None  # '' = not measured

        def pct(name):
            v = cell(name)
            if v is None:
                return '   -'
            # normalise from analyzer-freq to f + the multi-instance divisor:
            return f"{v * f_base / f / DIV.get(name, 1):5.0f}"

        # UCHE read: total CH0+CH1; if the cfg lacks it (cfg-vertex has
        # per-client instead of total) - the sum of per-client VFD+TP+SP+PC
        # (without HLSQ/LRZ, negligible clients):
        uche_rd = cell('UCHE_RD_BEATS_PER_S')
        if uche_rd is None:
            parts = [cell(k) for k in
                     ('UCHE_RD_VFD_PER_S', 'UCHE_RD_TP_PER_S',
                      'UCHE_RD_SP_PER_S', 'UCHE_RD_PC_PER_S')]
            if any(p is not None for p in parts):
                uche_rd = sum(p for p in parts if p is not None)
        vsinv = cell('VS_INV_PER_S')
        pix = cell('PIXELS_PER_S')
        print(f"{el:8.1f} {f:6.0f} {fps or 0:6.1f} | "
              + ' '.join(pct(n) for n in ['PC', 'VFD', 'VPC', 'TSE', 'RAS'])
              + ' | '
              + ' '.join(pct(n) for n in ['SP', 'TP', 'RB', 'CCU', 'LRZ', 'UFC'])
              + ' | '
              + ' '.join(pct(n) for n in ['UCHE', 'HLSQ', 'CP'])
              + f" | {uche_rd / 1e6 if uche_rd is not None else float('nan'):9.0f} "
              + f"{vsinv / 1e6 if vsinv is not None else float('nan'):9.0f} "
              + f"{pix / 1e6 if pix is not None else float('nan'):9.0f}")


if __name__ == '__main__':
    main()
