#!/usr/bin/env python3
"""Per-create decision diff between two TU_IMG_INV=1 inventories (exp-14).

  scripts/imginv-decisions.py results/raw/game-patched-imginv5.log \
                              results/raw/game-patched-exp21inv.log

imginv-stats.py and imginv-classes.py compare totals; this script compares the
decisions themselves.  Two images with the same create signature - format, view
format, extent, mip/array/sample counts, usage, flags, format-list length and
list content - must receive the same `tile=` and `ubwc=` verdict from two builds
that claim to make the same tiling decision.  One differing signature is a
finding; a difference in *which* images were created is not, because a game
session loads whatever part of the scene it reaches.

Lines whose `list=` field was cut by another writer's stderr (the driver's log
is interleaved with wine/vkd3d) are counted and excluded, never guessed at.
"""
import re
import sys
from collections import Counter

MiB = 1024.0 * 1024.0
FIELDS = re.compile(r'(\w+)=(\S+)')
DIMS = re.compile(r' \d+x\d+x\d+ ')
LIST_OK = re.compile(r'(PIPE_FORMAT_[A-Z0-9_]+)(,PIPE_FORMAT_[A-Z0-9_]+)*$')


def rows(path):
    out, broken, dirty = [], 0, 0
    for line in open(path, errors='replace'):
        if 'TU_IMG_INV ' not in line:
            continue
        d = dict(FIELDS.findall(line))
        if not {'fmt', 'size', 'listn', 'ubwc', 'mutable', 'tile'} <= set(d):
            broken += 1
            continue
        lst = d.get('list', '').rstrip(';')
        if lst and not LIST_OK.fullmatch(lst):
            dirty += 1
            continue
        d['list'] = lst
        d['dims'] = DIMS.search(line).group().strip()
        d['size'] = int(d['size'])
        out.append(d)
    if broken or dirty:
        print(f'  ({path}: {broken} truncated lines, {dirty} lines with a cut list= '
              f'field - excluded)')
    return out


def decision(d):
    return (d['fmt'], d['vkfmt'], d['dims'], d['mip'], d['arr'], d['samples'],
            d['usage'], d['flags'], d['listn'], d['list'])


def describe(d):
    kind = ('MUTABLE listn=%s' % d['listn']) if int(d['flags'], 16) & 0x8 else 'plain'
    return f"{d['fmt'].replace('PIPE_FORMAT_', ''):26} {d['dims']:12} {kind:18}"


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    pa, pb = sys.argv[1], sys.argv[2]
    a, b = rows(pa), rows(pb)
    da = Counter((decision(d), d['tile'], d['ubwc']) for d in a)
    db = Counter((decision(d), d['tile'], d['ubwc']) for d in b)

    verdicts_a, verdicts_b = {}, {}
    for d in a:
        verdicts_a.setdefault(decision(d), Counter())[(d['tile'], d['ubwc'])] += 1
    for d in b:
        verdicts_b.setdefault(decision(d), Counter())[(d['tile'], d['ubwc'])] += 1

    shared = set(verdicts_a) & set(verdicts_b)
    flipped = [k for k in shared if set(verdicts_a[k]) != set(verdicts_b[k])]

    print(f'=== {pa}  ({len(a)} creates) ===')
    print(f'=== {pb}  ({len(b)} creates) ===')
    print(f'signatures in both:              {len(shared)}')
    print(f'signatures with a DIFFERENT tile/ubwc verdict: {len(flipped)}')
    for k in flipped[:20]:
        print(f'  {k[0]:26} {k[2]:12} listn={k[8]}  A={dict(verdicts_a[k])} B={dict(verdicts_b[k])}')

    only_a = [d for d in a if decision(d) not in verdicts_b]
    only_b = [d for d in b if decision(d) not in verdicts_a]
    for name, rows_only in (('only in the first', only_a), ('only in the second', only_b)):
        mib = sum(d['size'] for d in rows_only) / MiB
        print(f'\n{name} (signature absent from the other log): {len(rows_only)} creates, {mib:.1f} MiB')
        cnt = Counter(decision(d) + (d['tile'], d['ubwc']) for d in rows_only)
        for k, n in cnt.most_common(12):
            print(f'  {k[0].replace("PIPE_FORMAT_", ""):26} {k[2]:12} listn={k[8]:2} '
                  f'tile={k[10]:7} ubwc={k[11]}  x{n}')

    # The same signature can be created a different number of times: that is scene
    # content (a session reaches a different part of the level), not a decision.
    ma = Counter(decision(d) for d in a)
    mb = Counter(decision(d) for d in b)
    size_of = {decision(d): d['size'] for d in a + b}
    for name, delta in (('the first has more of', ma - mb), ('the second has more of', mb - ma)):
        n = sum(delta.values())
        mib = sum(delta[k] * size_of[k] for k in delta) / MiB
        print(f'\nmultiset: {name}: {n} creates, {mib:.1f} MiB')
        for k, v in delta.most_common(8):
            print(f'  {k[0].replace("PIPE_FORMAT_", ""):26} {k[2]:12} listn={k[8]:2}  x{v}')


main()
