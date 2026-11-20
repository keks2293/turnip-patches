# 20. The first fill into a fresh image loses ~2% of texels (a probe defect, not formats)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

### 20.1 How it looked

Probe U (five TYPELESS classes of vkd3d, journal 20.4) initially gave MISMATCH on
almost all words, with `got=0x00000000`, and the mismatch count changed from
run to run. At first glance this looked like "UBWC breaks 32-bit formats",
which would have broken the whole reasoning about the gate.

### 20.2 Where the boundary is

Three controls, run through the same code as the main measurements, helped
isolate it:

| control | what we rule out |
|---|---|
| `linear` (no UBWC, no list) | compression isn't involved |
| `nonmut` (UBWC, no list) | the format list isn't involved |
| `CTRL_RGBA8`, `CTRL_BGRA8` (n=1) | the 32-bit float formats themselves aren't involved |

`CTRL_RGBA8` and `CTRL_BGRA8` are exactly the formats for which probe T-tr in
the same run gives `0/262144` mismatches with structurally identical code. So
the problem is in the probe, not in the driver and not in the formats.

Next, filling the readback buffer with the byte `0xCD` before copying showed:
`untouched = 0` with `zeros = 5120`. So `CopyImageToBuffer` wrote the whole
buffer, and the zeros really were in the image — i.e. **the fill itself didn't
finish writing**. The number of corrupted words was always a multiple of 64,
i.e. whole
64-texel chunks.

### 20.3 Cause

Extracted into a separate minimal program — `tests/repro-first-fill.c`:
512×512, `R8G8B8A8_UNORM`, only fill and readback, nothing from probe U. Each
run creates a **fresh** image and fresh memory, otherwise the second run hits a
warm image.

```sh
./repro-first-fill 3 cold   # one fill, measure immediately
./repro-first-fill 3 warm   # two fills in a row, measure after the second
```

```
cold:
rep0 OPTIMAL  memreq=0x102000: bad=5248/262144 zero=5248
rep0 LINEAR   memreq=0x100000: bad=5312/262144 zero=5312
rep1 OPTIMAL  memreq=0x102000: bad=5120/262144 zero=5120
rep1 LINEAR   memreq=0x100000: bad=5184/262144 zero=5184
rep2 OPTIMAL  memreq=0x102000: bad=5120/262144 zero=5120
rep2 LINEAR   memreq=0x100000: bad=4096/262144 zero=4096

warm:
all six lines bad=0/262144
```

The first `CopyBufferToImage` into a **newly created** image writes part of the
data as zeros. A second fill of the same image gives an exact picture. This
affects both `VK_IMAGE_TILING_OPTIMAL` and `VK_IMAGE_TILING_LINEAR`, i.e.
neither tiling nor UBWC is involved here. The format isn't involved either:
same result on `R8G8B8A8_UNORM`, which probe T-tr in the same binary measures
as EXACT.

Limitation of the finding: **the cause inside the driver has not been
established.** All that is known is "the first fill is incomplete, the second
is complete". It reproduces both on the stock driver and on 0004–0009 (log
`results/test-U-baseline-stock.log`, 14 MISMATCH), i.e. none of the project's
patches relates to it.

Practical conclusion for measurements: **a warm-up fill is needed before
measuring.** In probe U it was added; after it all lines give 0 mismatches.
This is the same class of artifact as the "usampler transform" from journal 14: a
wrong measurement setup, not a property of the hardware.

### 20.4 What was ultimately measured

After warm-up, on the stock driver and with the experiment
`experiments/exp-8-sfloat-int-ubwc-compat.patch`:

```
                              stock (0004-0006)          with patch
R32_TYPELESS          nonmut=0x102000 list=0x100000   list=0x102000
R16G16_TYPELESS       nonmut=0x102000 list=0x100000   list=0x102000
R32G32_TYPELESS       nonmut=0x202000 list=0x200000   list=0x202000
R16G16B16A16_TYPELESS nonmut=0x202000 list=0x200000   list=0x202000
R32G32B32A32_TYPELESS nonmut=0x404000 list=0x400000   list=0x404000
```

roundtrip (byte-wise, via transfer) — `0/262144`, `0/524288`, `0/1048576` in
all lines, both on stock and with the patch. No regressions: probes S and T —
PASS.

Logs: `results/test-U-baseline-stock.log` (before warm-up, 14 MISMATCH),
`results/test-U-baseline-warmup.log` (stock, warm-up, 0 MISMATCH),
`results/test-U-sfloat-gate-patched.log` (experiment, 0 MISMATCH).

A caveat about the `CTRL_*` lines: there `n=1`, the gate passes trivially, so
the `list` value on stock equals `nonmut`. In the first run the verdict was
printed as "NO (removed)" — that was a wording defect in the probe itself
(comparison `>` instead of `>=`). It didn't affect the measurement, nor the
numbers in the table above.

### 20.5 exp-8: `_FLOAT` into the integer compat classes

`experiments/exp-8-sfloat-int-ubwc-compat.patch` adds `_FLOAT`
members to `fd6_ubwc_compat_mode()` (`src/freedreno/common/freedreno_ubwc.h`):
`R16G16_FLOAT`, `R32_FLOAT`, `R32G32_FLOAT`, `R16G16B16A16_FLOAT`,
`R32G32B32A32_FLOAT` — into the same classes as their integer analogs.
`Z32_FLOAT` deliberately stays `UNKNOWN_COMPAT`: it belongs to no color
typeless family, and depth has its own clearing semantics.

What this gives in numbers: of vkd3d's 72 classes, 31 hold UBWC on stock, 36
with the experiment (`scripts/fmt-list-gate-check.py --vkd3d`, flag
`patch_0010`). The model and the measurement agreed on all five TYPELESS
classes.

The grounds are the layout, not the blob: UBWC encoding is determined by the
format class, and inside a class only channel sizes differ. An `_SFLOAT` member
has the same layout as the integer member of the same typeless format, and a
cast in Vulkan is a reinterpretation of the same bits, not a channel swap. The
stock comment `«a630 blob allows these, but not a660»` remains in force as an
indication that the blob table has no rows for float, not as proof of
incompatibility.

**What the patch does not check.** A byte roundtrip doesn't catch fast-clear:
the driver doesn't verify the contents of the clear metadata against the format
interpretation, so a wrong clear value will only show up where the application
does a fast-clear through a view in the float interpretation. To close this, a
probe is needed of the kind `vkCmdFillImage` with a color in float
interpretation → read raw bytes → compare with the same bit pattern
recomputed as integers. Until it exists, the caveat remains a risk; on
04.10.2026 exp-8 was nevertheless moved to
`patches/0012-turnip-ubwc-compat-sfloat-int.patch` — at the price of a caveat
recorded in the patch header (as with 0011).
