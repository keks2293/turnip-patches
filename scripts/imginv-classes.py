#!/usr/bin/env python3
"""Linear/tiled split of MUTABLE-no-list images by texel-block class.

  scripts/imginv-classes.py results/raw/game-patched-imginv4.log [more logs]

This is the class view behind 0014 (`docs/analysis.md` §21.12): with no format list
the driver answers the three predicates on the compatibility class of the base
format, and the classes whose members differ in channel order (32-bit: RGBA8 vs
BGRA8; 16-bit: R8G8 vs R16) stay linear on purpose.  A class here is bytes per texel
block, which is what the tiled layout is a function of.

One log prints its own table; several logs are printed side by side (MiB and the
tiled share), which is how "without 0014" / "with 0014" / "with the prop" compare.
"""
import re
import sys
from collections import defaultdict

MiB = 1024.0 * 1024.0
FIELDS = re.compile(r'(\w+)=(\S+)')

# bits per texel block, by the format name the inventory prints
WIDTH = {
    'R8': 8, 'R8G8': 16, 'R16': 16,
    'R8G8B8A8': 32, 'B8G8R8A8': 32, 'R16G16': 32, 'R32': 32, 'A2B10G10R10': 32,
    'R10G10B10A2': 32, 'R11G11B10': 32,
    'R16G16B16A16': 64, 'R32G32': 64,
    'R32G32B32A32': 128,
}
DEPTH = ('D16', 'D24', 'D32', 'S8', 'X8_D24')
COMPRESSED = ('BC', 'DXT', 'BPTC', 'RGTC', 'ETC', 'ASTC', 'FXT1')


def klass(fmt):
    name = fmt.replace('PIPE_FORMAT_', '')
    if name.startswith(COMPRESSED):
        return 'BC (compressed)'
    if name.startswith(DEPTH):
        return 'depth/stencil'
    base = re.sub(r'_(UNORM|SNORM|USCALED|SSCALED|UINT|SINT|FLOAT|SRGB|UAV|SFIXED5|D16|D24|D32).*$|_S8_UINT$', '', name)
    w = WIDTH.get(base)
    if w is None:
        # anything unlisted: keep the name, it is its own class
        return 'other: ' + base
    return f'{w} bit'


def parse(path):
    for line in open(path, errors='replace'):
        if 'TU_IMG_INV ' not in line:
            continue
        d = dict(FIELDS.findall(line))
        if not {'fmt', 'size', 'listn', 'ubwc', 'flags', 'tile'} <= set(d):
            continue
        yield d


def collect(path):
    c = defaultdict(lambda: [0, 0.0, 0.0, 0.0])
    for d in parse(path):
        if int(d['flags'], 16) & 0x8 == 0 or int(d['listn']) != 0:
            continue
        e = c[klass(d['fmt'])]
        mib = int(d['size']) / MiB
        e[0] += 1
        e[1] += mib
        e[2] += mib if d['tile'] == 'tiled' else 0.0
        e[3] += mib if int(d['ubwc']) else 0.0
    return c


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    logs = sys.argv[1:]
    data = [(p.split('/')[-1].replace('game-patched-', '').replace('.log', ''), collect(p)) for p in logs]
    names = [n for n, _ in data]

    if len(data) == 1:
        c = data[0][1]
        tot = sum(v[1] for v in c.values())
        print(f'=== {names[0]}: MUTABLE без списка, {tot:.1f} MiB ===')
        print(f'{"класс":18} {"созда":>6} {"MiB":>9} {"tiled":>9} {"linear":>9} {"ubwc":>7}  доля tiled')
        for k in sorted(c, key=lambda k: -c[k][1]):
            cnt, m, t, u = c[k]
            print(f'{k:18} {cnt:6} {m:9.1f} {t:9.1f} {m - t:9.1f} {u:7.1f}  {100 * t / m:5.1f} %')
        return

    classes = sorted({k for _, c in data for k in c},
                     key=lambda k: -max(c[k][1] for _, c in data if k in c))
    print('=== MUTABLE без списка: MiB и доля tiled по классам тексельного блока ===')
    head = f'{"класс":18}' + ''.join(f'{n[:20]:>26}' for n in names)
    print(head)
    for k in classes:
        row = f'{k:18}'
        for _, c in data:
            cnt, m, t, u = c.get(k, [0, 0.0, 0.0, 0.0])
            row += f'{m:11.1f} {100 * t / m if m else 0:5.1f} %{u:7.1f}u' if m else f'{"—":>26}'
        print(row)
    row = f'{"ИТОГО":18}'
    for _, c in data:
        m = sum(v[1] for v in c.values())
        t = sum(v[2] for v in c.values())
        u = sum(v[3] for v in c.values())
        row += f'{m:11.1f} {100 * t / m:5.1f} %{u:7.1f}u'
    print(row)
    print('\nколонка: MiB, доля tiled, MiB с ubwc (суффикс u)')


main()
