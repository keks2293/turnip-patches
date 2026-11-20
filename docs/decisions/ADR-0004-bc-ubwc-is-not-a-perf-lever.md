# ADR-0004: BC + UBWC is not an RE4 performance lever; the line is closed

Date: 2026-11-20 (recorded; measured 18.11)
Status: accepted

## Context

`ubwc_possible()` returns false for every compressed format, which looks like a free
2x on BC textures. The volume question was measured before writing any patch.

## Decision

Do not pursue UBWC for block-compressed formats. No patch, no queue item.

## Consequences

- the BC classes stay tiled-without-UBWC, which is what they are today;
- the reason is structural, not economic: vkd3d creates RE4's BC textures sparse, and
  sparse forbids UBWC in the stock code; the industry norm for BC compression (DCC/CCS)
  excludes BC too, so a UBWC path for BC would be new hardware territory;
- the 600.7 MiB of BC in the no-list class (analysis section 28) is therefore out of the
  UBWC reserve, and the reserve is 64-bit only.

## Evidence

journal 21.8, 21.9; `results/test-BCcopy-i2b*.log`,
`results/test-BCcopy-0013cand*.log`; the class table in section 27.
