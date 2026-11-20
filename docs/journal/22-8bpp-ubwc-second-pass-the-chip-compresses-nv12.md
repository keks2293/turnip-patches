# 22. 8bpp UBWC, second pass: the chip compresses NV12, a plain R8 image reads back a quarter (20.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

journal 21.7 stopped one measurement short: it could show that the driver allocates a
metadata plane for `cpp == 1` and that the content comes back wrong, but not
whether the chip compresses 8bpp at all. That measurement now exists, plus three
sweepings around it. Nothing here produced a patch, and journal 22.6 says why.

Tool: `tests/tp8bpp.c` (new, standalone, no vkd3d), built in the container:

```
podman run --rm -v $PWD/tests:/work:Z -v $PWD/../build:/out:Z \
  localhost/mesa-build-fedora44-wsi-glslang-vulkan \
  bash -c 'cd /work && gcc -O2 -Wall -o /out/tp8bpp tp8bpp.c -lvulkan'
VK_DRIVER_FILES=$PWD/../build/out/freedreno_icd.json FD_DEV_FEATURES=has_8bpp_ubwc=1 ../build/tp8bpp [dump-prefix]
```

Driver: ship build `4c3cdb2100823b2f…`; the geometry override rows use the same
tree + `experiments/exp-17-cpp1-ubwc-blockwidth.patch` (build
`5395a4f3f2c6fcce…`), which adds `TU_8BPP_UBWC=<w>x<h>` on top of the table.

Three probes: **Z** NV12 (`FMT6_NV12_Y`, `cpp == 1`, grid `{32,8}`, *not* gated by
`has_8bpp_ubwc`) as the positive control; **AA** `R8_UNORM` written by `imageStore`
(3D/TP path), read by `texelFetch` and by `vkCmdCopyImageToBuffer`; **AB** the same
image filled by `vkCmdCopyBufferToImage` (2D copy engine) instead. Both AA and AB
run tiled and linear.

### 22.1 Reading the counters (a correction to my own first read)

`tp8bpp.c` prints the number of **mismatching** elements: `texelFetch: 195840/262144
words MISMATCH` means 195840 wrong, 66304 right (25.29 %). The tables I drafted
during the day labelled those numbers as "readable" and inverted the story; the
curated logs carry the legend now, so the same trap is not sprung twice.

Which reader to believe: `i2b` (`vkCmdCopyImageToBuffer`). Its own control - the
same image without UBWC - is EXACT at 512x512, 256x256, 64x64 and 512x32. The
`texelFetch` path of the tool is **not under control** at other widths: at 256x256
and 64x64 it reports mismatches even for the linear image (first bad `(x0,y1)`),
and at heights <= 16 both readers fail in both tilings. That is a defect of the
probe at small images - dispatch and buffer sizes do follow `-DW`/`-DH`, so it is
not an obvious off-by-size - and it is recorded as a probe defect, not as a
property of UBWC. The `good %` map is drawn from the `texelFetch` buffer, so it is
only trusted at width 512.

### 22.2 The positive control holds, and it does not say what it looked like it said

Probe Z is EXACT everywhere: `0/262144 MISMATCH` at 512x512, at 256x256, and at
heights 4/8/16/32, both tiling flavors, on the ship `.so`
(`results/test-8bpp-tp8bpp-stock.log`, `results/test-8bpp-tp8bpp-sizes.log`,
`results/test-z-nv12-y8.log`). Its metadata plane is busy, not decorative:
3569 of 8192 bytes non-zero, values `27`/`4`/`125`/`247`…
(`results/test-8bpp-meta-shape.txt`). So a740 does compress a `cpp == 1` UBWC plane
today.

What it does not license is the step to `R8_UNORM`, and the tree says so itself -
`registers/adreno/a6xx_enums.xml:114-116`:

> Note: tiling/UBWC for these may be different from equivalent formats. For
> example FMT6_NV12_Y is not compatible with FMT6_8_UNORM

Z is a proof about `FMT6_NV12_Y`, on the `{32,8}` geometry, with copies forced
through r3d (`tu_clear_blit.cc`). Yesterday's wording here ("the hardware side is
working") was too strong; it is corrected in place.

### 22.3 What a plain R8 image does: exactly one quarter, at every size

`results/test-8bpp-tp8bpp-sizes.log`, `i2b` column, ship `.so`, `has_8bpp_ubwc=1`:

| image | tiled `memreq` | linear `memreq` | `i2b` wrong | readable | first wrong | linear control |
|---|---|---|---|---|---|---|
| 512x512 | `0x42000` | `0x40000` | 195840/262144 | 25.29 % | `(x256,y0)` | EXACT |
| 256x256 | `0x11000` | `0x10000` | 48963/65536 | 25.29 % | `(x128,y0)` | EXACT |
| 64x64 | `0x3000` | `0x1000` | 3060/4096 | 25.29 % | `(x32,y0)` | EXACT |
| 512x32 | `0x5000` | `0x4000` | 12240/16384 | 25.29 % | `(x256,y0)` | EXACT |

The readable fraction does not depend on the size at all: it is one quarter, the
top-left one, at every size where the reader is under control, and the first wrong
texel is always exactly at `x = W/2`. At width 512 the map shows the shape - the
quadrant `x < W/2`, `y < H/2` is 100 % correct, everything else reads `0x00`
(`0xff000000` in the `texelFetch` word, i.e. alpha from the format conversion, zero
`r`). Yesterday's note here claimed the readable area "does not scale with the
image"; that was the inverted counter, and the opposite is true: it scales exactly.

The metadata side, same dumps: the 3D writer spends **one byte per 256 texels** -
1024 B at 512x512, 256 B at 256x256 - all of them `0x1f`, written as four
256-byte chunks with a stride of 16 rows of the driver's metadata pitch. AB (image
filled by `vkCmdCopyBufferToImage`) leaves the metadata plane entirely zero and
reads back 1024 bytes of 262144, all coincidences with the zero texels of the
pattern: the 2D copier neither writes metadata nor anything the reader resolves.

Arithmetic worth recording, explicitly as coincidence and not as mechanism: 256
texels per metadata byte is the cell count of the `{32,8}` grid (what NV12 Y uses),
four times the `{16,4}` the driver reserves and walks for plain 8bpp, and the
readable area is smaller by the same factor four - two in each axis. Nothing
measured today separates "the writer uses `{32,8}`" from "the writer uses
something else that happens to touch 1/256 of the texels".

### 22.4 Metadata pitch is not the bug either

The hypothesis this kills is the obvious one: *the driver's `ubwc_pitch` is wrong,
so the reader walks into the wrong cell*. `fdl6_layout.c` computes the metadata
pitch as `align(width / blockwidth, 64)`, i.e. 64 bytes at the default `{16,4}`.
Widening it by making the block narrower (`TU_8BPP_UBWC`, exp-17) gives:

| grid | `memreq` | metadata plane | metadata written | chunk stride | readable |
|---|---|---|---|---|---|
| `{16,4}` (table) | `0x42000` | 8 KiB | 1024 B | `0x400` | 25.29 % |
| `{64,2}` | `0x44000` | 16 KiB | 1024 B | `0x400` | 25.29 % |
| `{4,1}` | `0x50000` | 64 KiB | 1024 B | `0x800` | 25.29 % |
| `{2,1}` | `0x60000` | 128 KiB | 1024 B | `0x1000` | 25.29 % |
| `{1,1}` | `0x80000` | 256 KiB | 1024 B | `0x2000` | 25.29 % |

(`results/test-8bpp-meta-pitch-height.log`, base rows from
`results/test-8bpp-grid-sweep.log`, same dumps.) The pitch grows 8x, the plane
32x, and the hardware writes the same 1024 bytes in four 256-byte chunks whose
stride is always "16 rows of the current pitch" - and reads back the same quarter.
The writer does not use the geometry the driver computed. A wrong `ubwc_pitch` in
`fdl6_layout.c` is excluded: it was swept, the result did not move by one byte.

Heights (`-DH` with width 512, base grid): the "one block row is safe, the step to
the second row breaks" model - the one that would follow from a wrong vertical
pitch - is not supported, but it also cannot be tested at `H <= 16`, because there
the linear control fails too (probe defect, journal 22.1). The one honest row is `H = 32`:
control EXACT, readable 25.29 %, first wrong `x = 256` - the same quarter rule.

And the confound in the grid sweep, which yesterday's note did not have:
`fdl6_ubwc_tile_dimensions()` switches the *data* tile to 64x16 whenever
`blockheight == 16`, so the `{16,16}`, `{32,16}`, `{64,16}`, `{8,16}`, `{32,32}`
rows never tested metadata geometry alone. The rows that kept the 64x4 data tile -
`{16,8}`, `{32,8}`, `{8,8}` - are the clean ones, they allocate `0x41000` (4 KiB of
metadata, less than the base 8 KiB) and the first submission that touches the image
faults the GPU; everything after `VK_ERROR_DEVICE_LOST` in those logs, including
the AB rows, is void and must not be read as a measurement.

### 22.5 Why NV12 works and plain R8 does not, on upstream evidence

- The NV12 Y branch is separately maintained and separately *fixed*: `8ea6f17fdf93`
  (22.10.2021, "freedreno/layout: Fix the UBWC block size for the Y plane"),
  `fb2646e527e9` (28.01.2026, Lakshman Chandu Kondreddy, "Fix UBWC block sizes for
  `PIPE_FORMAT_R8_G8B8_420_UNORM`" - that Gallium name is NV12, not `R8_UNORM`),
  and `18399c041267` (01.09.2026, "fdl: generalize UBWC block dimensions for all
  2-plane YUV formats").
- Checked with `git apply -R --check` against `mesa27-src`: **`18399c041267` is
  already applied here** (`layout->plane == 0/1` special cases at
  `fdl6_layout.c:44-50`, `.plane = i` at `tu_image.cc:804`), and it subsumes
  `fb2646e527e9`. So "our tree lacks the per-plane plumbing" is false and is not
  written anywhere in this repo: the `{32,8}` geometry of the Y plane is present,
  and journal 22.4 sweeps it anyway.
- What the property is: `0f770caa232` (Joshua Ashton, 23.09.2022), "freedreno:
  Disable 8bpp_ubwc on a6xx gen2 - Fixes text corruption in VSCode on a680". A
  workaround for corrupted glyphs, no diagnosis, untouched since. In upstream
  `main` (raw file fetched 20.11) `has_8bpp_ubwc` appears 4 times, all in the a6xx
  chain: `a6xx_base=True` (118), `a6xx_gen2/3/4=False` (190/204/234); no a7xx or
  a8xx entry sets it.
- Corroboration from the vendor, with a caveat: the Adreno Game Developer Guide
  (doc 80-78185-2, "Spec Sheets", texture-format table) leaves the UBWC column
  empty for `A8_UNORM`, `R8_UNORM/SNORM/UINT` and checks it for `R8G8_UNORM`. The
  same table's header calls itself "A5X Surface Format", and a web page is not one
  of our committed artifacts, so this is recorded as agreement with the vendor's
  public matrix, not as evidence for our driver.

### 22.6 Verdict

`has_8bpp_ubwc` stays `False` on `a7xx_gen2`, and no patch for it enters the stack.
Four things were swept today - grid, metadata pitch, image size, writer - and the
readable fraction did not move from 25.29 % once. What the numbers do change is the
shape of the remaining gap: it is not "the bit is harmful" and not "the metadata
pitch is wrong", it is that the 3D writer for `FMT6_8_UNORM` produces metadata at
1 byte per 256 texels and a reader that resolves only the first half of each axis.
Closing that means programming the descriptor/CCU side for 8bpp UBWC under a format
the open stack has never driven, against a chip document we do not have. Cost of a
wrong guess is a faulted GPU on the first submit (seen three times today); the gain
is the ~70 MiB of RE4 `R8_*` images in journal 25, and it is negative for small
images: `0x42000` vs `0x40000`, UBWC on a 512x512 R8 image costs 8 KiB.

Criterion for any future attempt, unchanged: probe AA round-trips EXACT without
faulting. Probe AB is a second, separate criterion - if the copy path with the same
allocation reads EXACT while the 3D path does not, the bug is the writer, and that
is a different patch than the one journal 22.6 declines.
