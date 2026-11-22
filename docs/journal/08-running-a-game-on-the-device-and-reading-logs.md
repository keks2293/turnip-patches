# 8. Running a game on the device and reading logs

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

The game is a third-party repack outside Steam, the prefix comes from Heroic
(sideload). Launch goes directly through proton, bypassing both Steam and
Heroic: Heroic adds umu-launcher, and then you can't see exactly what the game
gets.

```sh
scripts/run-game.sh stock 300     # packaged driver — baseline
scripts/run-game.sh patched 120   # patched one from build/out via VK_DRIVER_FILES
```

```sh
scripts/curate-game-log.sh results/raw/game-stock.log   # filter manually
```

### What matters in the script

- **CWD = the game folder.** RE4 opens `re_chunk_000.pak` and
  `local_config.ini` relative to the current directory. Launching from the repo
  left an empty `local_config.ini` (32 bytes) in the repo instead of the real
  one (20 KB), and the game showed a **black screen** — while the vkd3d
  rejections were exactly the same as in a successful run. So the black screen
  has nothing to do with the feature level.
- `VK_DRIVER_FILES` points to `build/out/freedreno_icd.json`; `/usr` is not
  touched. With it the device is a single one (Adreno), without it — two
  (Adreno + llvmpipe).
- `STEAM_COMPAT_APP_ID=2050650` is needed only by protonfixes (fix selection).
- Logs: the full proton/wine output — `results/raw/game-<mode>.log` (in
  `.gitignore`: 1.2 MB, of which only a handful of lines are significant), the
  filtered one — `results/game-<mode>.log` (collected by
  `scripts/curate-game-log.sh`).

### What to look for in the log

| Line | What it means |
|---|---|
| `d3d12_device_create: Feature level 0xc100 is not supported` | rejection on 12_1 (`0xc100`) |
| `d3d12_device_create: Feature level 0xc000 is not supported` | rejection on 12_0; after that vkd3d falls back to 11_1 |
| `dxgi_vk_swap_chain_init` / `Reallocating swapchain` | device created and a mode change is under way — the game started |
| `DxvkInstance::createInstance: Failed to create Vulkan instance` | DXVK failed to create a Vulkan instance: the game won't launch at all |
| `[Vulkan Loader]` | loader output (`VK_LOADER_DEBUG`); with `error,warn` it stays silent if the ICD loads without errors |

`VK_LOADER_DEBUG` defaults to `error,warn`; the full picture for the ICD comes
from `VK_LOADER_DEBUG=all scripts/run-game.sh patched`.

### What was measured

- **stock, CWD = the game folder**: rejections of 12_1 and 12_0, fallback to
  11_1, swapchain 1920x1080 → 2560x1440, postprocessing pipelines load, **the
  game loads**. The game has no separate "12_0 only" mode — 11_1 satisfies it
  (`results/games/re4/game-stock.log`).
- **stock, CWD = the repo**: the same rejections, but `local_config.ini` went
  into the repo → black screen.
- **a single stock ICD** (via `VK_DRIVER_FILES` pointing at the packaged
  freedreno) — same behavior: so "one device instead of two" by itself changes
  nothing.
- **the patched ICD**: `sparseResidencyImage2D = true`, but DXVK dies on
  `vkCreateInstance` before the game even (`results/games/re4/game-patched.log`). It is
  not a dependency problem: the patched `.so` links only against `libz`,
  `libdrm`, `libexpat`, `libstdc++` and `libc` — gallium is compiled into it.
  The cause of the rejection is analyzed in section 9.
