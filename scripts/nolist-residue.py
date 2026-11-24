#!/usr/bin/env python3
"""Residue of MUTABLE images created without a format list, per base format.

Question it answers: 0014 moves the no-list images whose assumed view set is
order- and layout-homogeneous into the tiled layout; what is left in linear, and
what does that remainder carry in its usage mask?  The answer decides how large a
problem any further no-list rule would be solving.

It counts, for every base format of a create that has VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT
and no VkImageFormatListCreateInfo (listn=0) and that ended up linear:

  n, MiB, and the MiB that also carry SAMPLED / STORAGE / TRANSFER_SRC|DST

The usage bit values are the Vulkan ones (include/vulkan/vulkan_core.h at 6dfa32a):
SAMPLED 0x4, STORAGE 0x8, TRANSFER_SRC 0x1, TRANSFER_DST 0x2.  MUTABLE_FORMAT is
flag bit 0x8 (vulkan_core.h:2764) - read from the header, not from memory: 0x100 and
0x200 are usage bits, not create flags, and an earlier count of this same field used
the wrong one.

Nothing here classifies formats as "order-mixing" or "layout-homogeneous" - that is a
spec question about the view set, and scripts/class-order-check.py answers it from the
class table and the driver's own predicates.  This script only produces the volume, plus
the `small`/`smallMiB` columns that separate creates the driver keeps linear because
level 0 is below its own width threshold - a stock rule, whatever the mutable rule says -
from the bytes a rule is actually about.

Usage:
    python3 scripts/nolist-residue.py results/raw/game-patched-imginv5.log
"""
import json
import os
import re
import sys
from collections import defaultdict

FIELDS = re.compile(r'(\w+)=(\S+)')
DIM = re.compile(r'(\d+)x(\d+)x(\d+) mip=')
MiB = 1024.0 * 1024.0

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLASSES_JSON = os.path.join(REPO, 'tests', 'vk-fmt-classes.json')

MUTABLE_FORMAT = 0x8          # VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT
SAMPLED = 0x4
STORAGE = 0x8
TRANSFER = 0x3                # TRANSFER_SRC | TRANSFER_DST

# FDL_LINEAR_FALLBACK_THRESHOLD, freedreno_layout.h:251, scaled by the block width on a7xx
# (supports_linear_mipmap_threshold_in_blocks, a7xx_base at freedreno_devices.py:785).
LINEAR_FALLBACK_TEXELS = 16


def load_blockw():
    """PIPE_FORMAT_* -> texel block width, from vk.xml via tests/vk-fmt-classes.json."""
    try:
        data = json.load(open(CLASSES_JSON))
    except OSError:
        return {}
    bw = {}
    for rec in data['formats'].values():
        if rec.get('pipe'):
            bw[rec['pipe']] = rec['blockExtent'][0]
    return bw


BLOCKW = load_blockw()


def is_small(vkfmt, width0):
    """fd6_layout.c:155-161: level 0 below the threshold -> ubwc off, tile_mode TILE6_LINEAR."""
    if width0 is None:
        return False
    return width0 < LINEAR_FALLBACK_TEXELS * BLOCKW.get(vkfmt.replace('PIPE_FORMAT_', ''), 1)


def parse(path):
    rows, broken = [], 0
    for line in open(path, errors='replace'):
        if 'TU_IMG_INV ' not in line:
            continue
        d = dict(FIELDS.findall(line))
        need = {'vkfmt', 'size', 'tile', 'ubwc', 'flags', 'usage', 'listn'}
        if not need <= set(d):
            broken += 1
            continue
        d['size'] = int(d['size'])
        d['flags'] = int(d['flags'], 16)
        d['usage'] = int(d['usage'], 16)
        m = DIM.search(line)
        d['width0'] = int(m.group(1)) if m else None
        rows.append(d)
    if broken:
        print(f'  ({path}: {broken} inventory lines cut by foreign stderr, not counted)')
    return rows


def report(path, rows):
    nolist = [r for r in rows
              if r['flags'] & MUTABLE_FORMAT and r['listn'] == '0']
    lin = [r for r in nolist if r['tile'] == 'linear']
    tiled = [r for r in nolist if r['tile'] != 'linear']
    print(f'=== {path} ===')
    print(f'  MUTABLE without a list : {len(nolist)} creates, '
          f'{sum(r["size"] for r in nolist) / MiB:.1f} MiB')
    for name, grp in (('tiled by 0014', tiled), ('linear residue', lin)):
        print(f'  {name:23}: {len(grp)} creates, {sum(r["size"] for r in grp) / MiB:.1f} MiB')

    by = defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0.0, 0, 0.0])
    for r in lin:
        b = by[r['vkfmt']]
        b[0] += 1
        b[1] += r['size'] / MiB
        if r['usage'] & SAMPLED:
            b[2] += r['size'] / MiB
        if r['usage'] & STORAGE:
            b[3] += r['size'] / MiB
        if r['usage'] & TRANSFER:
            b[4] += r['size'] / MiB
        if is_small(r['vkfmt'], r['width0']):
            b[5] += 1
            b[6] += r['size'] / MiB
    print(f'\n  {"base vkfmt":30}{"n":>6}{"MiB":>9}{"SAMPLED":>10}{"STORAGE":>10}{"xfer":>9}'
          f'{"small":>7}{"smallMiB":>10}')
    tot = [0, 0.0, 0.0, 0.0, 0.0, 0, 0.0]
    for k, b in sorted(by.items(), key=lambda kv: -kv[1][1]):
        print(f'  {k:30}{b[0]:6}{b[1]:9.1f}{b[2]:10.1f}{b[3]:10.1f}{b[4]:9.1f}{b[5]:7}{b[6]:10.1f}')
        tot[0] += b[0]
        for i in range(1, 7):
            tot[i] += b[i]
    print(f'  {"TOTAL":30}{tot[0]:6}{tot[1]:9.1f}{tot[2]:10.1f}{tot[3]:10.1f}{tot[4]:9.1f}'
          f'{tot[5]:7}{tot[6]:10.1f}')
    print('\n  `small` / `smallMiB` count the residue creates that are linear by a stock rule that has')
    print('  nothing to do with MUTABLE or with a format list: fd6_layout.c:155-161')
    print('    if (!params->force_ubwc && layout->width0 < linear_fallback_threshold_texels) ->')
    print('       ubwc = false, tile_mode = TILE6_LINEAR')
    print('  with the threshold 16 * blockwidth on a7xx (`FDL_LINEAR_FALLBACK_THRESHOLD` in')
    print('  freedreno_layout.h:251, scaled by supports_linear_mipmap_threshold_in_blocks at :254-261,')
    print('  which a7xx_base sets True at freedreno_devices.py:785).  Block widths come from vk.xml via')
    print(f'  tests/vk-fmt-classes.json ({len(BLOCKW)} pipe formats, default 1).  Visible in the log by')
    print('  one format on both sides of its threshold:')
    print('    PIPE_FORMAT_R16G16B16A16_FLOAT 8x8x8 ... tile=linear ... size=32768   (8 < 16)')
    print('    PIPE_FORMAT_R16G16B16A16_FLOAT 32x32x16 ... tile=tiled ... size=262144 (32 >= 16)')
    print('    PIPE_FORMAT_RGTC1_UNORM 32x32x32 ... tile=linear ... size=131072      (32 < 16*4)')
    print('    PIPE_FORMAT_RGTC1_UNORM 256x256x1 ... tile=tiled ... size=32768       (256 >= 16*4)')


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
