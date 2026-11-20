# 4. Fact 2 — the gate can be lifted

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

The gate is removed, the missing support added, vkd3d patched. All three Mesa
patches are implemented, built and verified on the device — the stock driver
26.2.3 and one built from the patched sources, full logs in `results/`.

| Patch | What it does | Verification (stock → patches) |
|---|---|---|
| **0004** (P1+P3) | gate removal + rejection on create for the sparse+MUTABLE→linear hole | `sparseResidencyImage2D` `0 → 1`; hole creates `SUCCESS → FEATURE_NOT_PRESENT` |
| **0005** (P4) | uniform-swap lists work as tiled+sparse (implementation of the upstream TODO) | probe S: `FAIL` (all zeros) → `PASS`, both views exact, transfer 0/16384 |
| **0006** (P6) | B8G8R8A8 family merged on an INT-compatible type | probe T: `memreq 0x100000 → 0x102000` (UBWC metadata), roundtrip 0/262144 |

The key measurement is **S**: on stock the image is created but reads back all
zeros (the linear+sparse hole; create passes only because the feature and the
query lie). With 0004 create is honestly rejected, with exp-5 — it is created
and both views read exactly.

The key measurement for 0006 is **T**: the appearance of `0x2000` of UBWC
metadata at the same size, i.e. compression itself turned on, not just the
layout.

The boundary is checked by probe **S2**: mixed-swap `{BGRA8, RGBA8}` and the
NULL list remain rejected — on stock they passed. Separately rejected are E
(`{RGBA8, BGRA8}`) and F (NULL list) — see section 6 for the consequences for
vkd3d.

Separately verified that there is nothing to break: the D3D12 sampling paths
(float and real UINT) are clean, and the apparent 8888-INT read anomaly is a
combination of an UNORM image with a usampler, i.e. the specified "poison"
value — a test artifact, not a driver bug. Probe R (real `R8G8B8A8_UINT` +
usampler) reads exactly.
