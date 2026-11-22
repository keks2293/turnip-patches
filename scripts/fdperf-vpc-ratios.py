#!/usr/bin/env python3
"""Steady-window ratios of a cfg-vpc sample set (queue 15 of docs/plan-next-checks.md).

Why this script and not just fdperf-analyze.py: the analyze script averages every
sample in the file, and a sampler started during the fixed intro of the run mixes
that intro into the means.  This script selects samples by time relative to the
first sample in the file and prints the ratio set that queue 15 pre-registered, so
the same numbers can be re-cut after the fact and compared run to run.

Counter identity: names are the a7xx_perfcntrs.xml names as fdperf prints them, and only the
first section of a sample is used - fdperf prints the counters the cfg programmed first, then
the group's other counters, so the second section is NOT the cfg (cfg-vpc spends the six-slot
VPC budget on VS_BUSY/PS_BUSY/SP_COMPONENTS/NUM_VPCRAM_WRITE/LM_FULL_WAIT, which is why
VPC_WORKING is not available here; see the header of tools/fdperf/fdperf.cfg-vpc and
docs/fdperf-a7xx.md on hw budgets and silent-ignore).  Both that rule and the wrapped-window
rule live in scripts/fdperf_sections.py.  The XML lists these counters as <value name=...> with
no unit, so a "per vertex" figure is a ratio of two counters, not a decoded quantity.

DRAM bytes: VBIF beats x 16 B, the conversion used by results/games/re4/mesa27-vertex/
steady-state.txt (748 Mbeats/s = 12.0 GB/s there).

Usage:
    python3 scripts/fdperf-vpc-ratios.py results/games/re4/vpc-base/fdperf-raw.txt 20 105
"""
import sys
from statistics import mean

from fdperf_sections import load as _load, window


def main(path, lo, hi, period_s=1.0, freq_mhz=680.0):
    samples, unmeasured, dropped = _load(path)
    win = window(samples, lo, hi)
    if not win:
        print(f'{path}: no samples in t_rel {lo}-{hi}s')
        return 1
    names = {k for s in win for k in s if k != 't'}
    avg = {n: mean(s[n] for s in win if n in s) / period_s for n in names}

    def g(n):
        return avg.get(n)

    def r(a, b):
        x, y = g(a), g(b)
        return float('nan') if x is None or not y else 100.0 * x / y

    # A counter that the run's cfg did not program prints as `nan`, never as 0: a cfg can
    # only spend its group's hw budget, so absence is the normal case (see the headers of
    # tools/fdperf/fdperf.cfg-vpc, -vpc2, -vpc3).
    def m(n):
        v = g(n)
        return float('nan') if v is None else v / 1e6

    def q(a, b):
        x, y = g(a), g(b)
        return float('nan') if x is None or not y else x / y

    print(f'{path}: {len(win)} of {len(samples)} samples, t_rel {lo}-{hi}s, '
          f'period {period_s:g} s, freq {freq_mhz:.0f} MHz')
    side = sorted(n for n in unmeasured if n.startswith(('PERF_VPC_', 'PERF_PC_', 'PERF_VFD_')))
    if side:
        print('  only in the BV_* copy of the group (binning/visibility), so not the counter '
              'this cfg programmed: ' + ', '.join(n[5:] for n in side))
    for n, c in sorted(dropped.items()):
        print(f'  {n[5:]}: {c} window value(s) thrown away (u64 wraparound or [invalid])')
    # instance dividers as recorded in docs/fdperf-a7xx.md: SP/TP /12, RB /4
    inst = {'TP': 12, 'SP': 12, 'RB': 4}
    print('  busy vs %.0f MHz (divided by instances where the block has several):  ' % freq_mhz
          + '  '.join('%s %5.1f%%' % (b, 100 * (g('PERF_' + b + '_BUSY_CYCLES') or float('nan'))
                                      / (freq_mhz * 1e6 * inst.get(b, 1)))
                      for b in ('VPC', 'PC', 'TP', 'SP', 'RB')))
    print(f"  CP_BUSY {m('PERF_CP_BUSY_CYCLES'):7.1f} M/s   draws/s {g('PERF_PC_3D_DRAWCALLS'):8.0f}")
    print(f"  VPC       BUSY {m('PERF_VPC_BUSY_CYCLES'):7.1f}  VS_BUSY {m('PERF_VPC_VS_BUSY_CYCLES'):7.1f} "
          f" PS_BUSY {m('PERF_VPC_PS_BUSY_CYCLES'):7.1f}  LM_FULL_WAIT {m('PERF_VPC_LM_FULL_WAIT_FOR_INTP_END'):7.1f} M/s")
    print(f"  VS/BUSY {r('PERF_VPC_VS_BUSY_CYCLES','PERF_VPC_BUSY_CYCLES'):6.2f}%   "
          f"PS/BUSY {r('PERF_VPC_PS_BUSY_CYCLES','PERF_VPC_BUSY_CYCLES'):6.2f}%   "
          f"LM_FULL_WAIT/BUSY {r('PERF_VPC_LM_FULL_WAIT_FOR_INTP_END','PERF_VPC_BUSY_CYCLES'):6.2f}%   "
          f"STALL_UCHE/BUSY {r('PERF_VPC_STALL_CYCLES_UCHE','PERF_VPC_BUSY_CYCLES'):6.2f}%")
    vi = g('PERF_PC_VS_INVOCATIONS')
    print(f"  VS_INV {m('PERF_PC_VS_INVOCATIONS'):7.1f} M/s   SP_COMPONENTS {m('PERF_VPC_SP_COMPONENTS'):7.1f} M/s "
          f"= {q('PERF_VPC_SP_COMPONENTS','PERF_PC_VS_INVOCATIONS'):5.2f}/invocation   NUM_VPCRAM_WRITE {m('PERF_VPC_NUM_VPCRAM_WRITE'):7.1f} M/s "
          f"= {q('PERF_VPC_NUM_VPCRAM_WRITE','PERF_PC_VS_INVOCATIONS'):5.2f}/invocation")
    print(f"  SP_EXPORT_VPC_TRANS {m('PERF_SP_EXPORT_VPC_TRANS'):7.1f} M/s   SP_STALL_VPC/SP_BUSY "
          f"{r('PERF_SP_STALL_CYCLES_VPC','PERF_SP_BUSY_CYCLES'):5.2f}%")
    print(f"  PC      IA_PRIM {m('PERF_PC_IA_PRIMITIVES'):7.1f} M/s   VERTEX_HITS {m('PERF_PC_VERTEX_HITS'):7.1f} M/s "
          f"= {q('PERF_PC_VERTEX_HITS','PERF_PC_IA_PRIMITIVES'):5.2f}/prim   IA_VERTICES/IA_PRIM "
          f"{q('PERF_PC_IA_VERTICES','PERF_PC_IA_PRIMITIVES'):5.2f}")
    print(f"  VFD     TOTAL_VERTICES/TSE_INPUT_PRIM {q('PERF_VFD_TOTAL_VERTICES','PERF_TSE_INPUT_PRIM'):5.3f}   "
          f"NUM_ATTRIBUTES/TOTAL_VERTICES {q('PERF_VFD_NUM_ATTRIBUTES','PERF_VFD_TOTAL_VERTICES'):5.2f}   "
          f"DECODED_ATTRIBUTE_BYTES {(g('PERF_VFD_DECODED_ATTRIBUTE_BYTES') or float('nan'))/1e9:5.2f} GB/s")
    rd = (g('PERF_UCHE_VBIF_READ_BEATS_CH0') or 0) + (g('PERF_UCHE_VBIF_READ_BEATS_CH1') or 0)
    tp = g('PERF_UCHE_VBIF_READ_BEATS_TP')
    print(f"  DRAM    reads {rd*16/1e9:5.2f} GB/s   TP {(tp or float('nan'))*16/1e9:5.2f} GB/s "
          f"= {100*(tp or float('nan'))/rd if tp else float('nan'):5.1f}%   "
          f"SP {(g('PERF_UCHE_VBIF_READ_BEATS_SP') or float('nan'))*16/1e9:5.2f} GB/s")
    print(f"  UCHE    WRITE_REQUESTS_SP {m('PERF_UCHE_WRITE_REQUESTS_SP'):7.1f} M/s   "
          f"WRITE_REQUESTS_VPC {m('PERF_UCHE_WRITE_REQUESTS_VPC'):7.1f} M/s   "
          f"STALL_ARBITER/BUSY {r('PERF_UCHE_STALL_CYCLES_ARBITER','PERF_UCHE_BUSY_CYCLES'):6.2f}%")
    print(f"  starve  VFD_STARVE_UCHE/VFD_BUSY {r('PERF_VFD_STARVE_CYCLES_UCHE','PERF_VFD_BUSY_CYCLES'):6.2f}%   "
          f"VFD_STALL_VPC_ALLOC/VFD_BUSY {r('PERF_VFD_STALL_CYCLES_VPC_ALLOC','PERF_VFD_BUSY_CYCLES'):6.2f}%   "
          f"TP_STALL_UCHE/TP_BUSY {r('PERF_TP_STALL_CYCLES_UCHE','PERF_TP_BUSY_CYCLES'):6.2f}%")
    # The PC/VPC coupling: PC busy, and how much of that busy is PC waiting on VPC.
    # PC has its own counter budget, so this pair is in the same sample set as the VPC split.
    print(f"  PC      BUSY {m('PERF_PC_BUSY_CYCLES'):7.1f} M/s   STALL_VPC/PC_BUSY "
          f"{r('PERF_PC_STALL_CYCLES_VPC','PERF_PC_BUSY_CYCLES'):6.2f}%   STALL_VFD/PC_BUSY "
          f"{r('PERF_PC_STALL_CYCLES_VFD','PERF_PC_BUSY_CYCLES'):6.2f}%   STALL_UCHE/PC_BUSY "
          f"{r('PERF_PC_STALL_CYCLES_UCHE','PERF_PC_BUSY_CYCLES'):6.2f}%")
    # UCHE latency in cycles per access: the XML gives no unit, so the pair is the answer
    # (docs/fdperf-a7xx.md: read the counter semantics in the XML before quoting a number).
    lc, ls = g('PERF_UCHE_VBIF_LATENCY_CYCLES'), g('PERF_UCHE_VBIF_LATENCY_SAMPLES')
    print(f"  UCHE    BUSY {m('PERF_UCHE_BUSY_CYCLES'):7.1f} M/s   VBIF latency "
          f"{q('PERF_UCHE_VBIF_LATENCY_CYCLES','PERF_UCHE_VBIF_LATENCY_SAMPLES'):6.1f} cycles/access over "
          f"{(ls or float('nan'))/1e6:6.1f} M samples/s")
    return 0


if __name__ == '__main__':
    args = sys.argv[1:]
    if len(args) < 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(args[0], float(args[1]), float(args[2])))
