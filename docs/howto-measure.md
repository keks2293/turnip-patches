# How to measure anything here

Commands only, in the order they are needed. Why each rule exists is a journal entry,
quoted per step; the incidents are collected in journal entry 29 and the honesty rules
in `AGENTS.md`.

## Before any run

```sh
free -m                                   # swap almost full = the run is poisoned
pgrep -af 're4\.exe|wine'                 # zombies from yesterday pace the frames
cat /sys/class/kgsl/kgsl-3d0/gpuclk_monitor_en 2>/dev/null
cat /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage
VK_DRIVER_FILES=/var/home/armada/opencode/build/out/freedreno_icd.json   # absolute path
sha256sum build/out/libvulkan_freedreno.so | cut -c1-12                  # the build id
```

`VK_DRIVER_FILES` must be absolute: a relative path is resolved from the game process's
cwd, not from the repository. The signature of a poisoned fps run is `min == max` for
fps (frames paced by a timeout, not by rendering) - journal 29.

Never build while the game runs; builds happen in the container with `-j2` and ccache
under `/tmp` (`AGENTS.md`). A rebuild invalidates the vkd3d pipeline cache, so the first
run after it is a warm-up, not a measurement (journal 29).

## The correctness protocol

```sh
scripts/run-test.sh                       # one ICD at a time, game closed
scripts/run-b2i-matrix.sh                 # the 94-row matrix, TU_B2I_SYNC modes
```

- Every probe prints `EXACT n/m` or `MISMATCH n/m`. `tests/tp8bpp.c` prints the number
  of **wrong** elements - check a tool's counter semantics before quoting it (journal 22.1).
- Content before numbers: a memory- or layout-related A/B starts with a round trip in
  the mode that actually turned on (journal 21.10).
- Prove the mode turned on: UBWC shows up in `memreq` (`+0x2000` at 512x512 for an
  R16 image), tiling shows up as `SPARSE_RESIDENCY + TILING_OPTIMAL` - `SUCCESS` =
  tiled, `FEATURE_NOT_PRESENT` = linear. `SUCCESS` alone is not tiling, and a green
  round trip measured in linear proves nothing (journal 21.12, 22.2).
- `memreq` as a tiling detector works only at a size that is not a multiple of the tile
  (500x500, not 512x512).
- Cross-submit visibility: `RK_SPLIT_SUBMITS=1` puts fill and readback in different
  submits with a wait between them.
- Name the reader. `texelFetch`, `i2b` and `imageLoad` are three paths; `i2b` is the one
  whose linear control was EXACT at every size tested (journal 22.1).

## The fps protocol

- Window: `elapsed` 40-50 s from start - the first 40 s are a fixed intro, the next 10 s
  are the 3D menu; the scene is deterministic, no scripted playthrough is needed.
- Metric: p25 of `fps` inside the window, 100 ms sampling (`HUDINTERVAL=100`), ~100 samples.
- `elapsed` in the MangoHud CSV is **nanoseconds** - divide by 1e9.
- Filter `fps < 30` away, otherwise loading and menu samples raise the number.
- Compare window with window, and only inside one build (`sha256sum | cut -c1-12`):
  stack identity is proven by the matrix, not by the hash, because a rebuild of the same
  stack is not bit-for-bit (journal 24.3).
- Sessions differ in length by ~7 %; for inventories compare shares and classes, never
  absolute MiB (journal 27).

```sh
TAG=myrun scripts/run-game.sh patched 90          # finds the game dir itself, GAME_DIR= to override
scripts/fps-window.py <csv> 40 50                 # ns -> s, p25
```

`HUDLOG` recreates its directory: copy the CSV straight after the run. `timeout` does
not kill the game; `run-game.sh` sends SIGTERM then SIGKILL (journal 29).

## Counters (fdperf)

Root only (`DRM_IOCTL_MSM_PERFCNTR_CONFIG` on the render node gives EPERM); incompatible
with `TU_AUTOTUNE_FLAGS=preempt_optimize`; stock `-d` lies, use
`tools/fdperf/fdperf-windowed-delta.patch`; dividers SP/TP `/12`, UCHE `/2`, CCU `/6`,
RB `/4`; fdperf silently ignores config rows beyond the group's table size, which is why
the UBWC counters are missing from every old run. Details, clock domains and the
measured steady state: `docs/fdperf-a7xx.md`.

## Driver builds

```sh
scripts/build-turnip-mesa27.sh                    # container, -j2, ccache in /tmp
sha256sum build/out/libvulkan_freedreno.so | cut -c1-12
grep -ac TU_B2I_SYNC build/out/libvulkan_freedreno.so    # is the exp-15 rig in this .so
```

`MESA_GIT_SHA1` is not embedded (`git_sha1.h` is empty), so the version string identifies
nothing. Reference builds are recorded in `docs/release.md`; the same stack rebuilt is a
different hash with the same matrix (journal 24.3).

The Mesa trees are patched by hand: `git apply` / `git apply -R` with explicit file
names, never `git checkout` or `git restore` (journal 24.3 tells what that cost).
