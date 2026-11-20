# 1. Symptom

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

> The title and the stand this investigation started under, kept verbatim from the head
> of `docs/analysis.md` when the journal was split into entries on 20.11 - it was the
> whole document's title, so it belonged to no entry. The stand in its current form is
> owned by [`docs/release.md`](../release.md) ("The stand and the versions"); these lines
> say what the stand was in September, and the dates are in its History.

**RP6: why DX12 games don't reach feature level 12_0**

**Device:** Retroid Pocket 6 — QCS8550, Adreno **A740** (gen2, not A750)
**Build image:** Armada main — Mesa 26.2.3, kernel 7.2.6, CachyOS Proton 11
**Measurements:** stock Mesa 26.2.2, 20–21.09.2026

Under Proton 11, DX12 games don't get past D3D12 feature level 11_1: vkd3d
does not expose `TiledResourcesTier` (it stays `NOT_SUPPORTED`), and the 12_0
gate does not pass. By the driver code it "should get there".
