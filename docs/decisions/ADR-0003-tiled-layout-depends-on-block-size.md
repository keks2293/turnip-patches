# ADR-0003: the tiled layout is a function of the block size; keep 0005/0006/0010/0011/0012

Date: 2026-11-20 (recorded; patches shipped 10-11.11)
Status: accepted

## Context

A whole family of "this format list cannot be tiled/compressed" answers turned out to
be false refusals: the driver compares channel order and reinterpretations that cannot
describe the same memory. `fd6_layout.c` derives the layout from the block size alone
(`layout->cpp = util_format_get_blocksize()`, tile height follows cpp), so two formats
of different block size cannot share a layout, and formats of one block size differ
only in channel order.

## Decision

Treat the block size as the axis of these predicates and keep the four patches that
follow from it: `0005` (uniform swap stays tiled), `0006` (B8G8R8A8 single INT compat
type), `0010` (single-channel does not argue about channel order), `0011`/`0012`
(R16/10-bit and `_SFLOAT` rows in `fd6_ubwc_compat_mode()`).

## Consequences

- 12_0-class tiling and UBWC for format lists that upstream refuses; UBWC compat
  classes in the matrix go 31 -> 36 -> 44;
- they are not redundant with ADR-0001: a build with those five removed and the prop
  set fails probes `S` (16384/16384) and `T` (261120/262144) - a compat mode is part
  of the layout, not a switch;
- two of them carry 0 MiB in RE4 (`0005`, `0010`) and `0006` has no supported Vulkan
  format for its probe; they stay because they are correctness, not workload tuning
  (see `patches/DROPPED.md`).

## Evidence

journal 2.1, 21.1-21.6, 24.3, 25; `results/test-CEIL-*.log`,
`results/test-gen2flag-minstack.log`; `src/freedreno/fdl/fd6_layout.c` in `../mesa27-src`.
