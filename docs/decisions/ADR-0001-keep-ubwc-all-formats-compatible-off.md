# ADR-0001: `ubwc_all_formats_compatible` stays off on a7xx gen2

Date: 2026-11-20 (recorded 20.11; the measurements are from 21.09, 30.09 and 19-20.11)
Status: accepted

## Context

One property line would expose `sparseResidencyImage2D` on gen2 and lift the
driver conservatism that keeps mutable images linear. It was measured three ways:
as an env override on the ship driver, as a table edit, and on bare upstream Mesa
27 with nothing else in the stack.

## Decision

`ubwc_all_formats_compatible` is not set for `a7xx_gen2` and is not added to the
shipped stack. `0007` (`TU_FORCE_PROPS`) stays the way to measure a prop without a
rebuild.

## Consequences

- three matrix regressions are avoided: `S3 PASS->FAIL`,
  `U[B8G8R8A8_UAVLIST] EXACT->MISMATCH`, `XV[BGRA8_as_RGBA8] OK->MISMATCH`
  (EXACT 94 -> 93);
- the mutation of `vkCreateImage(MUTABLE + SPARSE)` into `SUCCESS` on a bare driver
  - damage (1) of row 23 of `docs/a7xx-gen-props.md` - is not introduced;
- no patch becomes redundant by setting it (that was measured too), so nothing is
  saved by taking it;
- the flag is not "a bigger 0014": it tiles the 32/16-bit classes that 0014 refuses
  on purpose, and it adds no UBWC at all (48.6 % -> 48.8 %, session noise).

## Evidence

journal 1, 14.3-14.4, 24, 26, 27; `results/test-p14-base.log`,
`results/test-p14-ubwc-allformats.log`, `results/test-gen2flag-table.log`,
`results/test-gen2flag-minstack.log`, `results/test-stock-mesa27-matrix.log` (76
EXACT), `results/test-stock-flag-matrix.log` (73 EXACT), `results/imginv-3variants.txt`.
Builds `5e99409774838be5`, `c60dfb26`, `44cdf593a5200d8b`, `32d20074b8a128e4`.
