# 26. Stock Mesa 27 plus one prop line (exp-16, 19-20.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

A driver with **no patches at all** and one line
`ubwc_all_formats_compatible = True` in `a7xx_gen2`, to see what the prop does with
nothing else in the way.

| | |
|---|---|
| tree | upstream `6dfa32a85f91`; `0001` and `0002` also reverted (`git apply -R` of their files - they are equal to commits `ac08003`/`9845cfb`), plus 7 lines in `freedreno_devices.py`. `git diff 6dfa32a` was empty before the prop edit, which is what "no patches" means here |
| `.so` | `build/out-stock-flag/libvulkan_freedreno.so`, sha256 `44cdf593a5200d8b…`, KMD = msm (`nm -D` -> `drmGetVersion`) |
| ICD | `build/out-stock-flag/freedreno_icd_stock_flag.json` |
| edit | `experiments/exp-16-gen2-ubwc-allformats-stock.patch` |
| matrix | `results/test-stock-flag-matrix.log`, EXACT **73** against **76** for stock without the prop (`results/test-stock-mesa27-matrix.log`) |
| game run | `ICD=/var/home/armada/opencode/build/out-stock-flag/freedreno_icd_stock_flag.json scripts/run-game.sh patched`. The `ICD=` override was added to `run-game.sh`, modelled on `RP6_TEST_BIN` in `run-test.sh`. The path must be **absolute**: a relative `VK_DRIVER_FILES` is resolved from the game process's cwd, not from the repository |
| play check | `results/raw/game-patched-stockflag.log` (1628 lines, the header records `VK_DRIVER_FILES=…/freedreno_icd_stock_flag.json`): the loader accepted the ICD, the device enumerated (`Turnip Adreno (TM) 740`, `sparseResidencyImage2D: true`), `Capability=DirectX12` from `local_config.ini`. Frames for all 90 s: **886 samples of 898 with fps > 1**, median 17.4 fps, `GPU Load` mean 65.5 % with a 100 % peak (`results/raw/game-stock-flag-mangohud.csv`, summary `…_summary.csv`); the game was stopped by timeout (exit 124), it did not crash. This is **not a benchmark** (startup scene, settings not pinned): it proves that bare Mesa 27 with one prop line plays, without 0001 and 0013 in the stack |

Path gotcha, found on this run: the exFAT partition is mounted under its volume
label, and the label changed from `Z Slim` to `Slim`, so `/run/media/armada/Z
Slim/…` no longer exists although the game is intact. `run-game.sh` and `run-wtno.sh`
now find the directory themselves (`ls -d /run/media/armada/*/Games/<game>`) with a
`GAME_DIR=` override; under `set -euo pipefail` the substitution must carry `|| true`,
otherwise the script dies on that very line, with no message, when the disk is not
mounted.

What is visible only on the bare driver, with no other patch in the way: `XV[…]`
loses its `sparse=FEATURE_NOT_PRESENT` answer and `vkCreateImage(MUTABLE+SPARSE)`
starts answering `SUCCESS` (`sparse=SUCCESS`, rows 381-388 of the log) - that is
damage (1) of row 23 in `docs/a7xx-gen-props.md`, and it is brought by the prop
itself through `tu_device.cc:898` (`has_sparse_prr && ubwc_all_formats_compatible`),
not by our patches. Second: three rows of `rule says tiled UNEXPECTED` become `tiled
OK`, i.e. on bare stock the prop also tiles no-list mutable images - a crude version
of 0014, without its care (a class by texel block instead of "any reinterpretation").

The stack was rebuilt afterwards (`0001..0014`), `build/out` is the ship driver
again (`4c3cdb21…`, matrix line for line with p14, section 24.3).
