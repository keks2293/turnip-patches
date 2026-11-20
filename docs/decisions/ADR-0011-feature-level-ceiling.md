# ADR-0011: feature level - 12_0 through the tiling tier, 12_1 stays out of reach

Date: 2026-11-20 (recorded; measured 21.09 and 04.10)
Status: accepted

## Context

RE4 asks for 12_0. The blocker was never hardware: VM_BIND and PRR exist on the device.
Turnip exports `sparseResidencyImage2D` only under `ubwc_all_formats_compatible`, so
vkd3d computes `TiledResourcesTier = TIER_1` and refuses 12_0.

## Decision

Pursue 12_0 by exposing the tiling tier (`0004`, see ADR-0002) and stop at 12_1: it needs
`VK_EXT_fragment_shader_interlock`, which Turnip does not implement, and that is out of
scope for this stack.

## Consequences

- 12_0 is reachable with the shipped stack; the shipped `.so` is built that way;
- no attempt is made to fake or emulate interlock;
- the boundary is a driver gap, not a device gap, and is written down as such so it is not
  re-investigated every time the tier number is quoted.

## Evidence

journal 2-5 and 12; `patches/0004-turnip-sparse-residency-gate-lift.patch`;
`docs/release.md` (provenance of `27.0.0-devel-p14`).
