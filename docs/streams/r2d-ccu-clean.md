# Direction: copy-to-image (r2d) readback and the CCU

**State: closed, shipped as `0013`.** Kept as a page because the shape of the bug -
memory visibility, not addressing - is the thing most likely to be re-investigated from
scratch.

Believed, with the evidence:

- the shifting zero windows in a `vkCmdCopyBufferToImage` readback were excluded one by
  one: registers (GEOMDBG on failing and passing geometries: structurally identical),
  engine (`TU_I2B_R3D`), format (plain RGBA32), geometry (per-row blits,
  `TU_I2B_ROWS`), pipeline drain (`TU_B2I_WFI`), storage (CPU-FILL: the image is byte
  clean while the GPU readback fails) - journal 21.10, `docs/bugs-found.md`;
- CP_BLIT writes land in the CCU; the public copy commands emit no cache operations; a
  barrier outside a renderpass only accumulates bits;
- the minimal correct form is deferred bits executed at the next natural flush
  (exp-15 mode 7): journal 21.11, ADR-0005;
- shader readers were already covered by the existing barrier logic; the narrow
  uncovered chain is b2i read by a *blit* reader in the same submit, and a blit
  destination skips the clean deliberately (`tu_cmd_buffer.cc:5847`) - that is the
  correction to the first root-cause text, journal 21.10.

Open: the same shape under a GMEM renderpass, and b2i -> sampler / b2i -> dispatch
readers, were listed as probes to add and are NOT RUN. The "first fill loses ~2 %"
phenomenon is a related but separate thing and turned out to be a probe defect
(journal 20).

Decisions: ADR-0005. Artifacts: `results/test-b2isync-{0..15}.log`,
`results/test-BCcopy-*.log`, `tests/repro-first-fill.c`,
`experiments/exp-15-b2i-sync-env-bundle.patch`.
Next measurement: none required; the queue for this page is empty.
