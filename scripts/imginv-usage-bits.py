#!/usr/bin/env python3
"""Census of VkImageUsageFlagBits over TU_IMG_INV=1 inventory logs.

  scripts/imginv-usage-bits.py results/raw/game-patched-imginv5.log [more.log ...]

The inventory line carries the usage mask the application passed to vkCreateImage
(`usage=0x...`).  The existing stats script never looked at that field, so paths
that are advertised by a usage bit and not by anything else - fragment shading
rate, fragment density map and host-transfer (HIC) in particular - were invisible
in every inventory published so far.

Bit values are the Vulkan ones, checked against the header the tree builds with
(include/vulkan/vulkan_core.h in the mesa checkout, 6dfa32a): core bits end at
INPUT_ATTACHMENT 0x80, FRAGMENT_SHADING_RATE_ATTACHMENT_BIT_KHR is 0x100,
FRAGMENT_DENSITY_MAP_BIT_EXT is 0x200 and HOST_TRANSFER is 0x400000.  Those three
are the point of the script; they are also the ones whose order is easy to get
wrong from memory, so they are printed side by side rather than summed.
"""
import re
import sys
from collections import Counter, defaultdict

FIELDS = re.compile(r'(\w+)=(\S+)')
MiB = 1024.0 * 1024.0

BITS = [
    (0x001, 'TRANSFER_SRC'),
    (0x002, 'TRANSFER_DST'),
    (0x004, 'SAMPLED'),
    (0x008, 'STORAGE'),
    (0x010, 'COLOR_ATTACHMENT'),
    (0x020, 'DEPTH_STENCIL_ATTACHMENT'),
    (0x040, 'TRANSIENT_ATTACHMENT'),
    (0x080, 'INPUT_ATTACHMENT'),
    (0x100, 'FRAGMENT_SHADING_RATE_ATTACHMENT'),
    (0x200, 'FRAGMENT_DENSITY_MAP'),
    (0x400, 'VIDEO_DECODE_DST'),
    (0x800, 'VIDEO_DECODE_SRC'),
    (0x1000, 'VIDEO_ENCODE_DST'),
    (0x2000, 'VIDEO_ENCODE_SRC'),
    # VK_IMAGE_USAGE_HOST_TRANSFER_BIT = 0x00400000 (vulkan_core.h:2815 in 6dfa32a); the
    # _EXT alias at 2833 is the same value.  Not from memory: the value gates the driver's
    # "force linear for HIC with swapped formats" branch (tu_image.cc), see journal 37.4(b).
    (0x400000, 'HOST_TRANSFER'),
]

FSR = 0x100
FDM = 0x200
HIC = 0x400000


def parse(path):
    rows, broken = [], 0
    for line in open(path, errors='replace'):
        if 'TU_IMG_INV ' not in line:
            continue
        d = dict(FIELDS.findall(line))
        if not {'fmt', 'size', 'ubwc', 'mutable', 'tile'} <= set(d) or 'usage' not in d:
            broken += 1
            continue
        d['size'] = int(d['size'])
        d['ubwc'] = int(d['ubwc'])
        d['usage'] = int(d['usage'], 16)
        d['flags'] = int(d['flags'], 16)
        d['dims'] = re.search(r' \d+x\d+x\d+ ', line).group().strip()
        rows.append(d)
    if broken:
        print(f'  ({path}: {broken} inventory lines cut by foreign stderr, not counted)')
    return rows


def report(path, rows):
    print(f'=== {path}  ({len(rows)} creates, {sum(r["size"] for r in rows) / MiB:.1f} MiB) ===')
    for bit, name in BITS:
        hit = [r for r in rows if r['usage'] & bit]
        if not hit:
            continue
        mib = sum(r['size'] for r in hit) / MiB
        print(f'  {name:34} 0x{bit:03x}  {len(hit):5}  {mib:9.1f} MiB')
    rest = Counter()
    known = 0
    for bit, _ in BITS:
        known |= bit
    for r in rows:
        if r['usage'] & ~known:
            rest[hex(r['usage'] & ~known)] += 1
    if rest:
        print(f'  unknown bits: {dict(rest)}')

    for bit, name in ((FSR, 'shading rate'), (FDM, 'density map'),
                      (HIC, 'host-transfer (HIC)')):
        hit = [r for r in rows if r['usage'] & bit]
        if not hit:
            print(f'\n  {name} images: none')
            continue
        by = defaultdict(lambda: [0, 0])
        for r in hit:
            key = (r['fmt'], r['dims'], r['tile'], r['ubwc'])
            by[key][0] += 1
            by[key][1] += r['size']
        print(f'\n  {name} images: {len(hit)}, {sum(r["size"] for r in hit) / MiB:.1f} MiB')
        for key in sorted(by, key=lambda k: -by[k][1]):
            fmt, dims, tile, ubwc = key
            print(f'    {fmt:28} {dims:12} tile={tile} ubwc={ubwc}  '
                  f'x{by[key][0]:3} {by[key][1] / MiB:7.2f} MiB')


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    for path in argv[1:]:
        report(path, parse(path))
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
