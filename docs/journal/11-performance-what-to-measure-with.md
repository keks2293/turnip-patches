# 11. Performance: what to measure with

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

MangoHud is a Vulkan layer, not DXVK, which is why it is needed for DX12 games:
`DXVK_HUD` is useless here; RE4 goes through `d3d12` = vkd3d-proton, DXVK does
not take part in this path. The layer is enabled implicitly and off by default,
activated by `MANGOHUD=1` (verified with `VK_LOADER_DEBUG=all`:
`Insert instance layer VK_LAYER_MANGOHUD_overlay_aarch64`).

```bash
HUD=1    scripts/run-game.sh patched 180   # overlay on screen
HUDLOG=90 scripts/run-game.sh patched 120  # overlay + CSV in /tmp/opencode/mangologs
```

`HUDLOG` is needed because FPS can't be read off the screen, while comparing
runs requires numbers. MangoHud writes `<app>_<date>.csv` (one sample per
second) and next to it `_summary.csv` — you need the first one; the second has
no data rows.

CSV format: the first row is device info, the second is the headers, data from
the third. On Adreno `gpu_core_clock` is filled in, `gpu_temp` exists, but
`cpu`/`gpu` (time in ms) does not — so CPU-bound and GPU-bound cannot be split
by time, only by `gpu_load`.

### 11.1. What RE4 showed

Two phases, unambiguously distinguishable (`results/games/re4/game-patched-hud.log`):

| phase | fps | gpu_load | core clock |
|---|---|---|---|
| menus, loading | 55–70 | 3–37% | 475 MHz |
| gameplay | 12–19 | 85–99% | 680 MHz |
Temperature 68–71 °C, no throttling. So 13 fps in the game is a **GPU
bandwidth limit**, not vsync (frametime is not a multiple of 16.7 ms) and not
CPU (`cpu_load` 66% across eight cores, a significant part of which is wine).
GPU load rises as fps falls, and the core clocks up to the limit.

Also visible is a frequency drop to 220 MHz in the waiting phase
(`gpu_load` 0–11% at 19 fps) — the governor drops the overclock when the GPU is
idle. This is not the cause of the 13 fps.

What the measurement does **not** separate: how much of those 13 fps
`softfloat32` eats. The option is enabled by the driconf block for the `vkd3d`
engine and doesn't depend on the feature level, so it is present in both runs
below, and its contribution is inside both numbers.

### 11.1a. 12_0 versus 11_1 — is there a difference

`VKD3D_FEATURE_LEVEL=11_1` (the value format is `11_1`, parsing in
`d3d12_device_caps_override`, `device.c:9905`), same scene, same driver:

| metric (tail 40 s) | 12_0 | 11_1 |
|---|---|---|
| fps | 19.6 | 18.4 |
| gpu_load | 80% | 82% |
| cpu_load | 66% | 56% |
| core | 680 MHz | 680 MHz |
| gpu_temp | 68 °C | 66 °C |
| ram_used | 6.86 GB | 6.87 GB |
| swap_used | 3.15 GB | 3.13 GB |

**12_0 costs nothing** — neither in FPS nor in GPU load. The `cpu_load`
difference is within the scene's noise, and the windows are not fully
comparable (in the 12_0 run the core dropped to 220 MHz, i.e. part of the tail
was not gameplay).

Logs: `results/games/re4/game-patched-fl1111.log`, `results/games/re4/fps-patched-fl1111.csv`.

A side observation from the log: with the force to 11_1 the game asked for 12_0
and got the rejection `0xc000` — and went ahead and played on 11_1 anyway. So
the "your GPU was not supported" window doesn't latch onto the 12_0 rejection
but onto a separate SM 6.6 check. This independently confirms the conclusion of
section 10.

Also visible is the device state: RAM is 99% used (7.2 of 7.32 GiB) plus 3.1 GB
in zram. Swap is configured as zram, i.e. compressed pages sit in the same RAM.
Of the three explanations for why 13 fps, "ran out of memory" looks stronger
than "12_0 is expensive" — the latter has already been ruled out.

### 11.2. The DX11 attempt — didn't work, and here is why

RE4's `re4.exe` has a property name `via.render.RenderDeviceAPI` with values
`DirectX11 | DirectX12 | OpenGL | OpenGLES | Vulkan`, so the question "can it
run on DX11" is legitimate.

Checked by changing `[Render] Capability` in `local_config.ini`
(`DirectX12` → `DirectX11`): **the game doesn't read this value.** It rewrote
the key back to `DirectX12` on the next launch, and the log showed the usual
DX12 path — `d3d12_device_create`, SM 6.6, swapchain through vkd3d. So
`Capability` is an output key (which was determined), not an input one (what to
run with).

A non-working switching method does not yield the conclusion "DX11 is
unreachable": the command-line key has not been tried. The check should be done
like this — see whether the vkd3d markers (`d3d12_device_create`) appear in the
log when launched with an argument: if they are gone, the game went through
DXVK.

A caveat about the point of such a check: the DX11 path goes through DXVK, and
it doesn't verify what the patches were made for at the vkd3d level — neither
`12_0` nor SM 6.6 is required there. The driver itself, meanwhile, is not left
out: DXVK talks to Vulkan, i.e. to the same turnip, and its patches (UBWC lists,
clear-path, `TU_FORCE_PROPS`) do take effect in a DX11 game. So such a check
speaks about the health of the driver but says nothing about the patches of the
vkd3d stack.

About installed games: **God of War (AppId 1593500) is not DX12**, it has only
DX11 and Vulkan (this was previously recorded here by mistake). The DX12 games
among the installed ones are Avowed and Starfield. Launching them with the
patched driver is possible only with `VK_DRIVER_FILES`, as in
`scripts/run-game.sh`: Heroic's configs don't have this variable, so a launch
from the launcher goes on the stock driver `/usr`.
