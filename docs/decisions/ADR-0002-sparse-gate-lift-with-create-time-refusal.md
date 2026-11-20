# ADR-0002: lift the sparse-residency gate, refuse sparse+MUTABLE without a list

Date: 2026-11-20 (recorded; the change shipped as `patches/0004`)
Status: accepted

## Context

Turnip exports `sparseResidencyImage2D` only when `ubwc_all_formats_compatible`,
which gen2 does not have, so vkd3d never sees `TILING_OPTIMAL`, `TiledResourcesTier`
stays `TIER_1`, and feature level 12_0 is unreachable although VM_BIND and PRR exist
on the device. Lifting the gate (`0004`) exposes one real hole: a sparse image with
`MUTABLE_FORMAT` and no format list goes linear and then reads back as zeros,
silently.

## Decision

Keep the gate lifted and close the hole at the point where it becomes observable:
`vkCreateImage` refuses `SPARSE_BIND | SPARSE_RESIDENCY | MUTABLE_FORMAT` with no
format list.

## Consequences

- `sparseResidencyImage2D` 0 -> 1, 12_0 becomes reachable through the tiling tier;
- the silent-zero case becomes an explicit create failure the application can see;
- the refusal is detectable across driver versions, which is why it is also the tiling
  detector used by the test (`SPARSE_RESIDENCY + TILING_OPTIMAL`: `SUCCESS` = tiled,
  `FEATURE_NOT_PRESENT` = linear).

## Evidence

journal 2-4 and 5; `patches/0004-turnip-sparse-residency-gate-lift.patch`;
probe `XV`/sparse rows in `results/test-p14-base.log` (EXACT 94 with the refusal in place).
