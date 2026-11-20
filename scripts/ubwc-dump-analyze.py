#!/usr/bin/env python3
"""Look for known content inside a raw image allocation dumped by tests/tp8bpp.c.

Why: "the data plane is not all zeros" does NOT mean the texels are in it.  A
UBWC block is not stored as the byte string of its pixels, so a plane can be
dense with non-zero bytes and still hold nothing readable - and a plane can hold
the content and not match a linear comparison.  The only honest question you can
ask of a dump without knowing the block encoding is: does the pattern show up as
a *contiguous run* anywhere?  For cpp=1 the a6xx data tile is 32 bytes wide
(tile_width_shift = 5 - log2(log2(cpp))), so a 32-byte run along x is the
smallest thing that should be contiguous if the plane were plain tile order.

The pattern must be the one the probe fills with: (x*31 + y*17 + 7) & 0xff.

Plane split: for a UBWC image the metadata is at the START of the allocation
(the kernel expects it there, fd6_get_plane_layouts() moves the data after it),
so --meta is subtracted from the front and defaults to size - W*H.

  python3 scripts/ubwc-dump-analyze.py /tmp/opencode/aa_tiled.bin
  python3 scripts/ubwc-dump-analyze.py --meta 0 /tmp/opencode/aa_linear.bin
"""
import argparse
import sys

W = H = 512


def pat(x, y):
    return (x * 31 + y * 17 + 7) & 0xFF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--meta", type=lambda s: int(s, 0), default=None,
                    help="metadata bytes at the front of the allocation; "
                         "default = filesize - W*H")
    ap.add_argument("--segs", type=int, default=32,
                    help="length of the x-run to look for (default 32, the "
                         "cpp=1 data tile width)")
    ap.add_argument("--pitch", type=lambda s: int(s, 0), default=64,
                    help="metadata row pitch in bytes, fdl_ubwc_pitch() gives "
                         "align(ceil(w/blockwidth), 64) = 64 for 512 px at cpp=1")
    ap.add_argument("--w", type=int, default=512, help="image width of the dump (default 512)")
    ap.add_argument("--h", type=int, default=512, help="image height of the dump (default 512)")
    args = ap.parse_args()

    W, H = args.w, args.h

    raw = open(args.dump, "rb").read()
    data_sz = W * H
    meta_sz = args.meta if args.meta is not None else len(raw) - data_sz
    if meta_sz < 0 or meta_sz + data_sz > len(raw):
        sys.exit("%s: %d bytes, cannot split into %d + %d" %
                 (args.dump, len(raw), meta_sz, data_sz))
    meta, data = raw[:meta_sz], raw[meta_sz:meta_sz + data_sz]

    print("%s: %d B = meta %d + data %d" % (args.dump, len(raw), meta_sz, len(data)))
    print("  meta nonzero %d/%d (%.1f %%)" %
          (sum(1 for b in meta if b), meta_sz, 100.0 * sum(1 for b in meta if b) / max(meta_sz, 1)))
    # Shape of the written metadata: the pitch the driver programs is
    # align(ceil(w/blockwidth), 64) bytes, so a map says whether the HW covered
    # the whole grid, one tile of it, or nothing.
    nz = [i for i, b in enumerate(meta) if b]
    if nz:
        from collections import Counter
        pitch = args.pitch
        rows = sorted({i // pitch for i in nz})
        cols = sorted({i % pitch for i in nz})
        print("  meta nonzero at %d offsets: rows %d..%d of %d, cols %d..%d of %d, values %s" %
              (len(nz), rows[0], rows[-1], meta_sz // pitch, cols[0], cols[-1], pitch,
               Counter(meta[i] for i in nz).most_common(4)))
        # The written bytes come in contiguous chunks.  Their size and stride is
        # the fingerprint of the block geometry the hardware used, which is the
        # whole point of this probe (the driver programs a plain pitch array).
        runs, s, p = [], nz[0], nz[0]
        for i in nz[1:]:
            if i == p + 1:
                p = i
            else:
                runs.append((s, p))
                s = p = i
        runs.append((s, p))
        print("  written as %d chunk(s): %s%s" %
              (len(runs), ["0x%x+0x%x" % (a, b - a + 1) for a, b in runs[:6]],
               " ..." if len(runs) > 6 else ""))
        if len(runs) > 1:
            print("  stride between chunk starts: %s" %
                  ["0x%x" % (runs[i + 1][0] - runs[i][0]) for i in range(min(4, len(runs) - 1))])
        # Cell count is the discriminator: a {32,8} grid over this image needs
        # (w/32)*(h/8) bytes, a {16,4} grid needs 4x that.
        for bw, bh in ((32, 8), (16, 8), (16, 4), (8, 4), (64, 4)):
            need = (W // bw) * (H // bh)
            print("    grid {%d,%d}: %d cells would be written for a %dx%d image%s" %
                  (bw, bh, need, W, H, "   <- equals the measured count" if need == len(nz) else ""))
    print("  data nonzero %d/%d (%.1f %%), matches the linear pattern %d (%.2f %%)" %
          (sum(1 for b in data if b), len(data),
           100.0 * sum(1 for b in data if b) / len(data),
           sum(1 for i, b in enumerate(data) if b == pat(i % W, i // W)),
           100.0 * sum(1 for i, b in enumerate(data) if b == pat(i % W, i // W)) / len(data)))

    # index every 8-byte window of the data plane, then look for the pattern
    # runs: 0 hits means the plane is not in an order this tool can read.
    idx = {}
    for off in range(len(data) - 8):
        k = data[off:off + 8]
        if k not in idx:
            idx[k] = off
    seg = args.segs
    hits, offs = 0, []
    for y in range(H):
        for x0 in range(0, W - seg + 1, seg):
            key = bytes(pat(x, y) for x in range(x0, x0 + seg))
            off = idx.get(key[:8])
            if off is not None and data[off:off + seg] == key:
                hits += 1
                offs.append(off)
    total = H * (W // seg)
    print("  contiguous %d-byte x-runs of the pattern found in the data plane: %d/%d" %
          (seg, hits, total))
    if hits:
        print("  their offsets: min 0x%x, max 0x%x" % (min(offs), max(offs)))
        print("  VERDICT: the content IS in the plane, only in a non-linear order")
    else:
        print("  VERDICT: the dump cannot say whether the content was written -"
              " the plane is not stored in a byte order this tool knows")


main()
