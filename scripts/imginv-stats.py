#!/usr/bin/env python3
"""Statistics for the TU_IMG_INV=1 inventory (experiments/exp-14-image-inventory.patch).

  scripts/imginv-stats.py results/raw/game-patched-imginv5.log [second.log ...]

Prints, per log: how many images were created and how many MiB, how much of that
is tiled and UBWC, and the breakdown of MUTABLE images by "base format -> list"
(the list is what decides UBWC through the compat table).  With two or more logs
the last table is printed side by side, which is how the flag experiment is
compared against the reference inventory.
"""
import re
import sys
from collections import defaultdict

FIELDS = re.compile(r'(\w+)=(\S+)')
MiB = 1024.0 * 1024.0


def parse(path):
    rows = []
    broken = 0
    for line in open(path, errors='replace'):
        if 'TU_IMG_INV ' not in line:
            continue
        d = dict(FIELDS.findall(line))
        # stderr of wine/vkd3d is interleaved with the driver's, so a few lines are
        # cut in the middle; they are counted and skipped, not guessed at.
        if not {'fmt', 'size', 'listn', 'ubwc', 'mutable', 'tile'} <= set(d):
            broken += 1
            continue
        d['size'] = int(d['size'])
        d['listn'] = int(d['listn'])
        d['ubwc'] = int(d['ubwc'])
        # the app's VK_IMAGE_CREATE_MUTABLE_FORMAT bit comes from the client, so it is
        # read out of flags (0x8); the `mutable=` field of the log is the driver's own
        # verdict and its meaning changed between inventory revisions
        d['flags'] = int(d['flags'], 16)
        d['mutable'] = 1 if d['flags'] & 0x8 else 0
        d['dims'] = re.search(r' \d+x\d+x\d+ ', line).group().strip()
        rows.append(d)
    if broken:
        print(f'  ({path}: {broken} inventory lines cut by foreign stderr, not counted)')
    return rows


def summarize(rows):
    total = sum(r['size'] for r in rows) / MiB
    tiled = [r for r in rows if r['tile'] == 'tiled']
    ubwc = [r for r in rows if r['ubwc']]
    mut_list = [r for r in rows if r['mutable'] and r['listn'] > 0]
    mut_nolist = [r for r in rows if r['mutable'] and r['listn'] == 0]
    plain = [r for r in rows if not r['mutable']]
    out = [('all creates', len(rows), total),
           ('  tile=tiled', len(tiled), sum(r['size'] for r in tiled) / MiB),
           ('  ubwc=1', len(ubwc), sum(r['size'] for r in ubwc) / MiB),
           ('MUTABLE with list', len(mut_list), sum(r['size'] for r in mut_list) / MiB),
           ('  of them ubwc', len([r for r in mut_list if r['ubwc']]),
            sum(r['size'] for r in mut_list if r['ubwc']) / MiB),
           ('MUTABLE no list', len(mut_nolist), sum(r['size'] for r in mut_nolist) / MiB),
           ('  of them tiled', len([r for r in mut_nolist if r['tile'] == 'tiled']),
            sum(r['size'] for r in mut_nolist if r['tile'] == 'tiled') / MiB),
           ('  of them ubwc', len([r for r in mut_nolist if r['ubwc']]),
            sum(r['size'] for r in mut_nolist if r['ubwc']) / MiB),
           ('without MUTABLE', len(plain), sum(r['size'] for r in plain) / MiB),
           ('  of them ubwc', len([r for r in plain if r['ubwc']]),
            sum(r['size'] for r in plain if r['ubwc']) / MiB)]
    return out


def combos(rows):
    """(base fmt, list) -> (creates, MiB, MiB with ubwc, MiB tiled)."""
    c = defaultdict(lambda: [0, 0.0, 0.0, 0.0])
    for r in rows:
        if not r['mutable'] or r['listn'] == 0:
            continue
        key = (r['fmt'], r['list'])
        e = c[key]
        e[0] += 1
        e[1] += r['size'] / MiB
        e[2] += r['size'] * r['ubwc'] / MiB
        e[3] += r['size'] * (r['tile'] == 'tiled') / MiB
    return c


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    logs = sys.argv[1:]
    parsed = [(p, parse(p)) for p in logs]
    for p, rows in parsed:
        print(f'=== {p}  ({len(rows)} creates) ===')
        total = sum(r['size'] for r in rows) / MiB
        for name, n, mib in summarize(rows):
            share = 100.0 * mib / total if total else 0
            print(f'  {name:20} {n:6}  {mib:8.1f} MiB  {share:5.1f} %')
        print()
    if len(parsed) == 2:
        a, b = combos(parsed[0][1]), combos(parsed[1][1])
        keys = sorted(set(a) | set(b), key=lambda k: -(a.get(k, [0, 0])[1] + b.get(k, [0, 0])[1]))
        print('=== MUTABLE with list: base -> list (MiB, of them ubwc) ===')
        print(f'{"base":22} {"list":34} {"A c/MiB":>14} {"B c/MiB":>14} {"A ubwc":>8} {"B ubwc":>8}')
        for k in keys:
            ea, eb = a.get(k, [0, 0.0, 0.0, 0.0]), b.get(k, [0, 0.0, 0.0, 0.0])
            print(f'{k[0].replace("PIPE_FORMAT_", ""):22} {k[1].replace("PIPE_FORMAT_", ""):34} '
                  f'{ea[0]:4}/{ea[1]:8.1f}  {eb[0]:4}/{eb[1]:8.1f}  {ea[2]:7.1f}  {eb[2]:7.1f}')


main()
