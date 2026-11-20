# Direction: 8bpp UBWC (`has_8bpp_ubwc`, `FMT6_8_UNORM`)

**State: closed, no patch (ADR-0007).** One cheap discriminator is still open, recorded
as exp-19.

Believed, with the evidence:

- the property is already False on every a7xx (`True` only in `a6xx_base:118`; the a7xx
  chain does not inherit it) and its origin is a 2022 workaround for text corruption in
  VSCode on an a680, with no diagnosis - `analysis` 22.5;
- with the prop forced on, a plain R8 image reads back exactly the top-left quadrant at
  every size measured, and the metadata geometry does not matter: block grid and metadata
  pitch were both swept and the readable fraction does not move (`analysis` 22.3, 22.4);
- the chip does compress an 8-bit UBWC plane - NV12 Y round-trips EXACT - and that does
  NOT license `FMT6_8_UNORM`: the tree itself says the two are not UBWC-compatible
  (`registers/adreno/a6xx_enums.xml:114-116`), `analysis` 22.2;
- "our tree lacks the per-plane plumbing" is false: the last of the three upstream fixes
  for that branch is already applied here (checked with `git apply -R --check`),
  `analysis` 22.5;
- what a fix would require is descriptor/CCU programming for `FMT6_8_UNORM` with 8bpp
  UBWC - not a prop, not a table row, and unverifiable without Qualcomm documentation.

exp-19 (open, cheaper than one build): the same R8 image filled by
`vkCmdCopyBufferToImage` (probe AB) read by `i2b` in a fresh process, at the base grid
and at `{32,8}`. Today the AB rows of the sweep are post-fault and mean nothing. If AB
ever reads EXACT while AA does not, the fault is the 3D writer and the fix is not the
descriptor patch this page declines.

Note on the vendor literature: the 80-78185-2 spec sheet leaves the UBWC column empty for
A8/R8 and checked for R8G8. That is corroboration only - it is the "A5X Surface Format"
table and it is not a committed artifact in this repository.

Decisions: ADR-0007. Artifacts: `tests/tp8bpp.c`, `tests/tp_write.comp`,
`scripts/sweep-8bpp-grid.sh`, `scripts/ubwc-dump-analyze.py`,
`experiments/exp-17-cpp1-ubwc-blockwidth.patch`, and the `results/test-8bpp-*` /
`results/test-y-8bpp-*` / `results/test-z-nv12-y8.log` logs.
