# ADR-0010: `ubwc_coherency_quirk` is not set on a7xx gen2

Date: 2026-11-20 (recorded; measured 19.11)
Status: accepted

## Context

`a7xx_gen2` sets `supports_uav_ubwc` (`freedreno_devices.py:818`) while the guard
`ubwc_coherency_quirk` exists only in `a7xx_gen3` (`:863`). The earlier note that "the
quirk changes nothing" had been measured in a combo with `ubwc_all_formats_compatible`,
so it proved nothing.

## Decision

Do not set the quirk on gen2, and do not keep the probe in the tree.

## Consequences

- the guard's own trigger shape (compute writes a UBWC image, a later read returns the
  fast-clear color, `COMPUTE -> COMPUTE` barrier, UBWC confirmed on by memreq) is
  observable and does not fail: `bad=0/262144` on both readers, with a positive control
  that returned the clear color in 262144/262144 words;
- setting the quirk would cost one `CACHE_CLEAN` per barrier with a shader src stage for
  no measured gain;
- the boundary is recorded in the journal: one form, one size, one layout; no GMEM
  renderpass after the blit, no UBWC image as a blit source, no CTS run, gen3 not
  checkable here.

## Evidence

journal 23; `results/test-uq-quirk-{off,on}.log`,
`results/test-uq-after-removal.log`; row 24 of `docs/a7xx-gen-props.md`.
