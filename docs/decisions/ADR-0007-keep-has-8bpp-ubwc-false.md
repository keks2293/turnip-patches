# ADR-0007: `has_8bpp_ubwc` stays False; no 8bpp UBWC patch

Date: 2026-11-20
Status: accepted

## Context

`has_8bpp_ubwc` is not set anywhere in the a7xx chain (`True` appears only in
`a6xx_base:118`), and its origin (`0f770caa232`, 2022, "Fixes text corruption in VSCode
on a680") is an undiagnosed workaround, not a capability statement. RE4 creates 754
`R8_UNORM` + 72 `R8_UINT` images (~70 MiB inside lists, 1181.8 MiB in the no-list class),
so the question is worth measuring rather than assuming.

## Decision

Leave the property False and do not add a patch. Nothing in the stack changes 8bpp UBWC.

## Consequences

- the R8 classes stay uncompressed; on a 512x512 image UBWC would also *cost* 8 KiB
  (memreq `0x40000 -> 0x42000`), so small images lose even in the best case;
- the measured behaviour with the prop forced on is content corruption, not a readback
  artefact: an R8 image reads back exactly the top-left quadrant (25.29 %) at 512^2,
  256^2, 64^2 and 512x32, everything else zero, first wrong texel always `x = W/2`;
- the metadata geometry is excluded as the cause by a full sweep of the block grid and
  of the metadata pitch (64 B -> 512 B, plane 8 KiB -> 256 KiB): the writer always writes
  1 byte per 256 texels and the readable fraction does not move;
- probe Z (NV12 Y, `cpp == 1` UBWC) is EXACT everywhere, which proves the chip compresses
  an 8-bit UBWC plane but does not license `FMT6_8_UNORM`: `registers/adreno/a6xx_enums.xml:114-116`
  says the two are not UBWC-compatible. Fixing this means descriptor/CCU programming for
  `FMT6_8_UNORM`, which open-source Mesa has never tracked and which cannot be verified
  without Qualcomm documentation;
- one cheap discriminator stays open (exp-19): probe AB - the same image filled by the 2D
  copier - read back in a fresh process, to say whether the writer or the reader is wrong.

## Evidence

journal 21.7, 22 (all subsections); `results/test-r8-split-{on,off}.log`,
`results/test-y-8bpp-{on,off}.log`, `results/test-y-8bpp-sweep-blockwidth.log`,
`results/test-8bpp-tp8bpp-{stock,sizes}.log`, `results/test-8bpp-meta-pitch-height.log`,
`results/test-8bpp-meta-shape.txt`, `results/test-z-nv12-y8.log`; upstream
`0f770caa232`, `8ea6f17fdf93`, `fb2646e527e9`, `18399c041267` (the last verified already
applied in `../mesa27-src` by `git apply -R --check`).
