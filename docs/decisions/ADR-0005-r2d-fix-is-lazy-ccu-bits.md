# ADR-0005: the r2d readback fix is "lazy bits" executed at the next natural flush

Date: 2026-11-20 (recorded; measured 18.11, shipped as `patches/0013`)
Status: accepted

## Context

Reading back a `vkCmdCopyBufferToImage` in the same submit returned shifting windows of
zeros. Addressing, engine, format and geometry were each excluded by measurement; the
cause is memory visibility: CP_BLIT writes land in the CCU, public copy commands emit no
cache operations, and a barrier outside a renderpass only accumulates bits.

## Decision

Fix it by setting deferred bits - `flush_bits |= CCU_CLEAN_COLOR | WAIT_FOR_IDLE` -
executed at the nearest natural flush point, gated `CHIP >= A7XX`. The form was chosen
from the 16-mode `TU_B2I_SYNC` matrix (exp-15), mode 7.

## Consequences

- 19 MISMATCH -> 0, matrix 94/94 EXACT over three repeats, and one clean+WFI per group of
  copies instead of one per copy;
- rejected alternatives, all measured: per-copy clean+WFI (correct, more expensive), a
  dst-buffer surrogate format (no change), a src-format surrogate (no change), `SIZE/4`
  (already correct), `TU_I2B_R3D` (changes which cases fail, does not fix them);
- the uncovered chain is narrow and recorded: b2i read by a *blit* reader in the same
  submit, because a blit destination deliberately skips the clean
  (`tu_cmd_buffer.cc:5847`) while shader readers are covered by the existing barrier
  logic (`SRC_FLUSH(CCU_COLOR)` + `DST_FLUSH(UCHE)`). That correction to the earlier
  root-cause text is section 21.10.

## Evidence

journal 21.10, 21.11; `docs/bugs-found.md` (final section);
`patches/0013-turnip-b2i-ccu-clean.patch`; `results/test-b2isync-{0..15}.log`,
`results/test-BCcopy-0013cand*.log`.
