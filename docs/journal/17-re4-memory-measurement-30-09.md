# 17. RE4 memory measurement (30.09)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

Method: run `scripts/run-game.sh patched 150` with
`VKD3D_CONFIG=log_memory_budget VKD3D_DEBUG=info VKD3D_LOG_FILE=...`
(vkd3d prints every allocation: size + running total per memory type, after
each — a `Memory heap #0 ... usage` report from VK_EXT_memory_budget),
`TU_DEBUG=bos` (top of turnip's live BOs; printed after every submit, therefore
the raw 4,215,096 lines / 242 MB stayed in results/raw/, only the last dump in
git) and MangoHud CSV (`ram_used`/`swap_used`). Artifacts:
`results/vkd3d-mem.log`, `results/games/re4/game-patched-mem.log`,
`results/games/re4/fps-at-mem.csv`.

### Numbers

| source | result |
|---|---|
| vkd3d: peak / end | 3129 MiB / 3108 MiB (720 allocations) |
| budget | the driver declares a budget of 2672 MiB at usage 3122 MiB — vkd3d's non-budgeted path bypasses it |
| vkd3d top | chunks 16 MiB ×66 = 1056 MiB (VA chunks for small buffers), paired heaps 187500 KiB ×2 and 133640 KiB ×2, then 128/50/42.7 MiB |
| turnip: live BOs | 3490 MiB, internals ~370 MiB |
| — `pipeline_suballoc` | 1798 BO = 225 MiB |
| — `pvtmem` | ×3 = 120 MiB (fiber/wave private memory, grows in powers of two, tu_shader.cc:2871) |
| — `embedded samplers` | 3025 BO = 12 MiB |
| system | `ram_used` mean 6.76 / max 7.24 of 7.32 GiB, `swap_used` max 4.95 GiB |

### Conclusions

1. The main volume is the game's own resources (≈3 GiB): the only big lever is
   the in-game texture/quality settings.
2. Driver internals ~370 MiB are secondary; `pipeline_suballoc` and `pvtmem`
   are areas where reduction is only possible by editing the driver (`pvtmem`
   is set by shader requirements, it can't be cut by force).
3. There are no env levers for memory — confirmation of journal 15: all the env moves
   neither FPS nor footprint. `VKD3D_SWAPCHAIN_IMAGES=2` (the swapchain is by
   default `max(3,minImageCount)`, swapchain.c:2207) yields single-digit MB.
4. The system lives on borrowed time (swap max 4.95 GiB with sum ≈ 10 GiB);
   swappiness=180/zram — root only, outside the project's scope.
5. `TU_DEBUG=bos` must not be used in repeated measurements: a dump after every
   submit = 242 MB of log.

### Narrowing of conclusion 3 (21.11)

Conclusion 3 says "There are no env levers for memory". For what it searched - the env surface of
journal 15 and journal 15.5, whose options change what the driver *holds* and what it submits - it
still stands, and none of the numbers above moved. It did not cover the option that changes what
the driver **reports**: `heap_memory_percent`, a driconf option outside Turnip's own `perf`/`misc`
groups, which on this machine decides how much DEVICE_LOCAL memory a fresh application is told
exists (the measured number is owned by journal 34.4 and `results/vulkaninfo-heap-report.log`).
Whether a smaller report changes what vkd3d-proton does with the 3129 MiB measured above is
queue 13 - NOT MEASURED, and the 4.95 GiB of swap recorded here is why the question is worth a
game run rather than another probe.
