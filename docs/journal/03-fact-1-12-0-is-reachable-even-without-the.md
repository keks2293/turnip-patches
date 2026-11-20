# 3. Fact 1 — 12_0 is reachable even without the force

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

Forcing `VKD3D_FEATURE_LEVEL=12_0` through `game-tweaks.json` raises the level
regardless of the driver, and **games launch and run**. So neither the
application, nor Proton, nor the rendering stack require anything beyond what
the driver provides — the force merely masks the gate. Hence: 12_0 can be
obtained honestly, by removing the gate.

The force remains a working crutch, but it doesn't cure the cause: the real
tiled resources are still not handed out, and the application gets TILED
capabilities that the driver doesn't provide.
