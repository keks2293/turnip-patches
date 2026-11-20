# 5. Nuance for upstream

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

In Mesa `main` the gate is present in two places:

- exposure of `sparseResidencyImage2D`;
- `vkGetPhysicalDeviceImageFormatProperties2` — the gate was added to the
  format property query path (commit "tu: Don't advertise sparse residency when
  the pdev can't do it", Emma Anholt, 03.09.2026).

vkd3d relies on exactly the second: `D3D12_FORMAT_SUPPORT2_TILED` is set from
the result of querying formats with `SPARSE_RESIDENCY`. Therefore the patch
must remove both gates — otherwise the feature will be advertised but TILED
won't.

In the version shipped in the Armada image (26.2.3) the second gate doesn't
exist yet: only the exposure is edited there. When moving to a fresher Mesa
there will be two edits.
