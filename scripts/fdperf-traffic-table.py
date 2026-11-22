#!/usr/bin/env python3
"""DRAM/UBWC traffic table for the arms sampled with fdperf.cfg-traffic (journal 40.17).

Prints, per dump and per arm: the pinned-clock window count and median frequency, DRAM read
and write GB/s (UCHE VBIF beats x 16 B, the conversion docs/fdperf-a7xx.md uses), the UBWC
beat totals, the texture-client request split (TP_UBWC vs TP_NONUBWC), and the CCU path
through CMPDECMP.  Values are medians over the samples whose CP_ALWAYS_COUNT is within 1 %
of 680 MHz - the window rule of journal 40.13 (Correction 2), because an off-clock window
moves every per-second number.

    scripts/fdperf-traffic-table.py <dump.txt ...>

Counter semantics were read in ../mesa27-src/src/freedreno/registers/adreno/a7xx_perfcntrs.xml
(UCHE selectors 27/28/52/53 read/write beats, 57/58 UBWC read/write beats, 43/44 TP request
split; CMP 3/4/5/6 the CCU path).  What a "beat" is on CMPDECMP is not described there, so
CMP columns are printed raw and not converted.
"""
import statistics
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from fdperf_sections import load

PIN = 680e6
PAIR = [
    ("DRAM read GB/s", ["PERF_UCHE_VBIF_READ_BEATS_CH0", "PERF_UCHE_VBIF_READ_BEATS_CH1"], 16e-9),
    ("DRAM write GB/s", ["PERF_UCHE_VBIF_WRITE_BEATS_CH0", "PERF_UCHE_VBIF_WRITE_BEATS_CH1"], 16e-9),
    ("UBWC read MB/s", ["PERF_UCHE_UBWC_READ_BEATS"], 16e-6),
    ("UBWC write MB/s", ["PERF_UCHE_UBWC_WRITE_BEATS"], 16e-6),
]
RAW = [
    ("TP req UBWC /s", "PERF_UCHE_READ_REQUESTS_TP_UBWC"),
    ("TP req nonUBWC /s", "PERF_UCHE_READ_REQUESTS_TP_NONUBWC"),
    ("CMP rd data", "PERF_CMPDECMP_VBIF_READ_DATA_CCU"),
    ("CMP wr data", "PERF_CMPDECMP_VBIF_WRITE_DATA_CCU"),
    ("CMP rd req", "PERF_CMPDECMP_VBIF_READ_REQUEST"),
    ("RB Z write", "PERF_RB_Z_WRITE"),
    ("RB C write", "PERF_RB_C_WRITE"),
    ("CP cache flush /s", "PERF_CP_CACHE_FLUSH"),
]


def main() -> int:
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        return 2

    hdr = ["arm", "pinned", "MHz"] + [n for n, _, _ in PAIR] + [n for n, _ in RAW]
    rows = []
    for path in paths:
        samples, _un, _dr = load(path)
        pin = [s for s in samples if "PERF_CP_ALWAYS_COUNT" in s
               and abs(s["PERF_CP_ALWAYS_COUNT"] - PIN) <= 0.01 * PIN]
        use = pin or samples

        def med(names, scale=1.0):
            vals = []
            for n in names:
                v = [s[n] for s in use if n in s]
                if not v:
                    return None
                vals.append(statistics.median(v))
            return sum(vals) * scale

        row = [path.split("/")[-2] if "/" in path else path,
               f"{len(pin)}/{len(samples)}",
               f"{statistics.median([s['PERF_CP_ALWAYS_COUNT'] for s in samples])/1e6:.0f}"]
        for _n, names, scale in PAIR:
            v = med(names, scale)
            row.append("-" if v is None else f"{v:8.2f}")
        for _n, name in RAW:
            v = med([name])
            row.append("-" if v is None else f"{v:14,.0f}")
        rows.append(row)

    print("| " + " | ".join(hdr) + " |")
    print("|" + "---|" * len(hdr))
    for r in rows:
        print("| " + " | ".join(r) + " |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
