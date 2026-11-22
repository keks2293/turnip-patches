# Mesa 27.0-devel: migration and rebase of the 0001-0012 stack

Verification date: 17.11.2026.

- Base: Mesa main, commit `6dfa32a85f91f2227e4003d13e51eb24be7892b8`
  (2026-11-17), `VERSION` = `27.0.0-devel`.
- Method: `git apply --check` of each patch in order on a clean tree,
  then applying the whole stack and comparing the resulting tree with the tree
  built by sequential commits (`git diff --quiet` -> identical).
- "Turnip 27" in the handheld community is exactly `27.0.0-devel` (builds from
  Banners-Turnip, StevenMXZ, etc.). These are Android/AdrenoTools packages; they
  must not be used on Linux/mainline-msm, the driver is built from source.

## Outcome

- **6 of 12** patches applied to 27.0-devel without edits:
  0003, 0006, 0009, 0010, 0011, 0012.
- **5 required a rebase**: 0001, 0002, 0004, 0005, 0008; one applied
  "cleanly" by context but broke the build and required an edit: 0007
  (the `TU_FORCE_PROPS` table referenced two props removed in 27).
- After the edits all 12 apply in order on a clean tree **and
  build**.
- Semantics did not change. The edits are context and names only, apart from three
  cases: 0002 (upstream already added one of the chip-ids), 0008 (upstream
  renamed the quirk) and 0007 (quirks became bitfields of `info->quirks`).

## Rebase matrix

| Patch | 27.0-devel | What changed in upstream | What was done |
|---|---|---|---|
| **0001** | rebase | the `extra_wait_count`/`extra_signal_count` block moved from `msm_queue_submit` 1257 -> 997; `vk_zalloc` is wrapped in `static_cast` | context line `(struct drm_msm_syncobj *) vk_zalloc(` -> `static_cast<struct drm_msm_syncobj *>(vk_zalloc(` |
| **0002** | rebase | upstream added `GPUId(chip_id=0xffff44050001, …)` **and** the KGSL `0x44050000` (read off `git show HEAD:…freedreno_devices.py`, 20.11) | two of the three original ids were dropped; the one line left duplicates an upstream row, so on Mesa 27 the patch changes nothing (the table matches on the first entry). Kept for file-list parity with the image build; see the correction inside the patch file |
| **0003** | clean | - | - |
| **0004** | rebase | `tu_format_linear_filtering_supported` became non-`static`; the tail of `tu_formats.h` changed; line shifts in `tu_device.cc`/`tu_image.cc` | context `static bool` -> `bool`; the declarations in `tu_formats.h` were inserted before the new function; the `tu_image.cc` hunks applied with an offset of 1-29 lines |
| **0005** | rebase | the same `static` rename | context `static bool` -> `bool` |
| **0006** | clean | - | - |
| **0007** | edit after the build | `cs_lock_unlock_quirk` -> the quirk `QCTDD08407086_cs_lock_unlock`, `r8g8_faulty_fast_clear_quirk` -> the quirk `QCTDD12766770_r8g8_fc_alignment`; quirks are bitfields of `info->quirks`, their address cannot be taken | both removed from the `props` table; handled separately in the `TU_FORCE_PROPS` loop under the new names |
| **0008** | rebase | `r8g8_faulty_fast_clear_quirk` was removed; instead there is the quirk `QCTDD12766770_r8g8_fc_alignment`; `has_resbase` was added to `a7xx_gen2` | insertion after `has_resbase`; `has_generic_clear = True` + `QCTDD12766770 = True` |
| **0009** | clean | - | - |
| **0010** | clean (after 0005) | - | - |
| **0011** | clean | - | - |
| **0012** | clean | - | - |

Patches 0013 and 0014 were written later, directly against this same
27.0-devel tree, so they need no rebase: 0013 touches only the end of
`tu_copy_buffer_to_image()` (`tu_clear_blit.cc`), 0014 adds a function to
`tu_formats.cc`/`.h` and one block in `tu_image_init()`. Both apply on top of
0001-0012 in order and reverse-apply cleanly (`git apply --check -R`).

### 0008: quirk rename

In Mesa 26 the flag was called `r8g8_faulty_fast_clear_quirk` and lived in
`GPUProps`. In Mesa 27 it is gone: the logic moved into the common quirk
mechanism, `FD_QUIRK(info, QCTDD12766770_r8g8_fc_alignment)` in
`tu_clear_blit.cc:4465`. In the device table the quirk is written without a suffix:

```python
has_generic_clear = True,
QCTDD12766770 = True,
```

The meaning is the same: `use_generic_clear_for_image_clear()` returns
`has_generic_clear && !(quirk && image_is_r8g8(image))`, i.e. with the
quirk enabled R8G8 clears go the old way. The pair is still
enabled as a whole: `has_generic_clear` alone without the quirk gives a GPU fault on
R8G8.

## What to check after the build

- **0007.** The build passed; verify behavior by running with
  `TU_FORCE_PROPS=has_generic_clear` and the line `TU_FORCE_PROPS: has_generic_clear`
  in the driver log (`MESA_DEBUG=1`). The quirk names in the table are the new
  ones (QCTDD format).
- **0003.** The patch applies, but its header says "offsets for Mesa
  26.2.0". The hunk context is stable, however the offset values themselves in
  `ir3_nir_analyze_ubo_ranges.c` must be checked against 27.0: if upstream changed
  the UBO layout, the patch may apply and silently disable the wrong thing. The check is
  a run of `sparseResidencyImage2D` and feature level 12_0, as in `docs/analysis.md`.
- **0008.** Make sure R8G8 fast-clear does not fault: the synthetic
  `vkmark`/`repro-first-fill.c` + RE4. Expected: synthetic -61...-65 %,
  RE4 0 % (as on 26.2).
- **0004/0005/0010.** Repeat probes S/N/V from `docs/analysis.md`; on 27.0
  upstream may have changed `tu_image_init()` and `tu_get_image_format_properties()`.
- **0002.** Not testable on our A740: the patch is about A830.

## Building: rules so as not to kill the SD card

`/var` is `mmcblk0p3` (btrfs, 58 GB, ~25 GB free), i.e. that very
SD card. Every Mesa rebuild writes hundreds of megabytes of objects and cache;
that is exactly what wears the card out. The rules are mandatory:

1. **Compiler cache - `/tmp` only.**

   ```sh
   export CCACHE_DIR=/tmp/opencode/ccache
   export CCACHE_MAXSIZE=1G
   export CCACHE_COMPRESS=true
   ```

   `/tmp` is tmpfs, it does not write to the card. After a reboot the cache is
   lost - that is fine, the sources and patches are restored in minutes.

2. **Build directory - `/tmp` only.**

   ```sh
   BUILD=/tmp/opencode/mesa27-build
   ```

   This is where ninja writes `.o` files and binaries. Not a single
   object file may land on the SD.

3. **Sources - on the SD, read-only.** A one-off shallow clone
   (`SRC=/var/home/armada/opencode/mesa27-src`, ~0.5 GB). The patches are applied
   once. **Do not use** `git checkout` in this tree - it destroys
   the uncommitted stack (that is how 0005-0010 were lost before); to roll back use
   `git apply -R`.

4. **Do not build while a game is running.** The script `scripts/build-turnip.sh`
   already checks for `re4.exe`/`wine`. The 7.3 GiB of RAM is shared with the GPU; build + game =
   OOM and a frozen cursor.

5. **`-j2`, not `-j$(nproc)`.** With 7.3 GiB of RAM and zram a build on 8 threads
   goes into swap and can hang the system. `-j2` is slower but safer.

6. **Clean up after yourself.** `rm -rf /tmp/opencode/mesa27-build` after a session;
   if the cache overflows - `ccache -C` and `ccache --trim-max-size 512M`.

7. **The container - also in `/tmp`, if it is not there yet.** Otherwise the image layers (~1 GB)
   land on the SD:

   ```sh
   podman --root /tmp/opencode/containers/storage \
          --runroot /tmp/opencode/containers/run ...
   ```

   If the image `localhost/mesa-build-fedora44-wsi-glslang` already exists - just
   mount the cache from `/tmp`.

8. **No reboot is needed.** The driver is slipped in via `VK_DRIVER_FILES`
   and its own ICD manifest; `/usr` is not touched.

### Pre-build check

```sh
df -h /tmp        # need >= 2.5 GB free
free -h           # need >= 2 GB available
pgrep -af 're4\.exe|wine' || true   # must be empty
```

### Space budget

| Item | Where | Size |
|---|---|---|
| Mesa source (shallow) | SD, `/var/home/armada/opencode/mesa27-src` | ~0.5 GB, one-off |
| build dir | tmpfs, `/tmp/opencode/mesa27-build` | ~0.4 GB |
| ccache | tmpfs, `/tmp/opencode/ccache` | <= 1 GB |
| container image (if rebuilding) | tmpfs, `/tmp/opencode/containers` | ~1 GB |
| **total in `/tmp`** | | **~1.4-2.4 GB** |

`/tmp` is currently 3.7 GB with ~2.2 GB free. Before a build, clean old artifacts
out of `/tmp/opencode` (`fex32.core`, `full_disasm.txt`,
`winebox`, `box64new`, tarballs - ~1.3 GB together); they are not needed for the build.

## Build order

```sh
# 1. Sources (once, on the SD)
cd /var/home/armada/opencode
git clone --depth=1 https://gitlab.freedesktop.org/mesa/mesa.git mesa27-src
cd mesa27-src
git checkout 6dfa32a85f91f2227e4003d13e51eb24be7892b8   # or a fresh main
for p in ../turnip-patches/patches/0*.patch; do git apply "$p"; done
git apply --check ../turnip-patches/patches/0012-*.patch && echo "stack is in place"

# 2. Configuration (build - in /tmp)
export CCACHE_DIR=/tmp/opencode/ccache
export CCACHE_MAXSIZE=1G
export CC="ccache gcc"
export CXX="ccache g++"
meson setup /tmp/opencode/mesa27-build \
    --buildtype=release \
    --prefix=/usr \
    -Dopengl=false \
    -Dplatforms=x11,wayland \
    -Dgallium-drivers= \
    -Dvulkan-drivers=freedreno \
    -Dfreedreno-kmds=msm \
    -Dvulkan-layers= \
    -Dshared-glapi=disabled \
    -Dllvm=disabled \
    -Dvalgrind=disabled \
    -Dlibunwind=disabled \
    -Dbuild-tests=false

# 3. Build
ninja -C /tmp/opencode/mesa27-build -j2 \
    src/freedreno/vulkan/libvulkan_freedreno.so

# 4. Check the KMD and the layout
nm -D --undefined-only \
    /tmp/opencode/mesa27-build/src/freedreno/vulkan/libvulkan_freedreno.so \
  | grep -q drmGetVersion && echo "KMD=msm, ok"
```

The flags are the same as in `scripts/build-turnip.sh`; the reasons are written out in its
header (KMD=msm, `-Dplatforms` not empty, `--prefix=/usr` for driconf).
The only difference is the build directory: `/tmp` instead of `build/` on the SD.

## Trap: ninja "succeeds" but the .so is not relinked (meson PHONY)

Symptom (reproduced 17.11.2026, RUN 3): the tree is clean, the file
`build/PHONY` does not exist. Ninja shows a plan of 7 edges, but after the first edge
all 6 dependent ones are dropped from the plan - **RC=0, the .so is not relinked,
the mtime did not change**:

```
$ ninja -C /tmp/opencode/mesa27-build/build src/freedreno/vulkan/libvulkan_freedreno.so
ninja: Entering directory `/out/build'
[1/7] Generating src/git_sha1.h with a custom command
RC=0    # .so not relinked
```

**RC=0 and ninja's output are not proof of a build.**

The mechanism (ninja 1.13.2 + meson 1.11.2, worked out from the sources):

- In Mesa `src/meson.build` the target `git_sha1.h` is declared with
  `build_always_stale : true` (comment: "commit sha1 can change
  without having touched these files").
- The meson ninja backend (ninjabackend.py:1238) translates this into an order-only
  dependency on a service target: `if target.build_always_stale:
  deps.append('PHONY')`. In `build.ninja`:

  ```
  # Phony build target, always out of date         (line 61)
  build PHONY: phony                               (line 63)
  build src/git_sha1.h: CUSTOM_COMMAND | ... PHONY (line 806)
  ```

- Ninja compares the mtime of the order-only dependency against the output: the file
  `PHONY` does not exist (a fresh `meson setup`) or its mtime is newer than that of
  `src/git_sha1.h` -> the edge is "dirty" -> the plan picks up three .o files that include
  git_sha1.h (loader.c, freedreno_uuid.c, tu_device.c), two static
  archives and the .so - a plan of 7 edges.
- The generator (`bin/git_sha1_gen.py`) rewrites the file only when the contents
  change (write_if_different; there is no git in the container, the contents are
  stable at `#define MESA_GIT_SHA1 ""`) -> after a no-op the mtime does not change.
- The `CUSTOM_COMMAND` rule has `restat = 1`: ninja re-stats the output,
  sees that nothing changed, and drops the dependent edges from the plan
  right during the run. On the output this shows in the changing denominator:
  `[1/8] ... [2/3] ... [3/3]`.
- A genuinely dirty file does not get dropped (verified: touched
  `tu_image.cc` and `tu_device.cc` compile under the trap conditions and the .so
  is relinked) - but on a clean tree the whole 7-edge plan turns out to be a
  no-op: RC=0, nothing is built.

There is no configuration flag: `build_always_stale` is a property of a specific target in
Mesa's meson files and cannot be turned off from `meson configure`. It can only be
removed by editing `src/meson.build` (a 10th unrelated edit in the tree on top of a
stack of 9 files) - not worth it: the generator is a no-op anyway.

The fix (verified): a `PHONY` file with an mtime **older** than that of
`src/git_sha1.h`:

```sh
touch -d @0 /tmp/opencode/mesa27-build/build/PHONY
```

After a fresh `meson setup` (a new build directory) - repeat it.
A plain `touch PHONY` (current mtime) does not guarantee silence: the mtime
will be newer than that of git_sha1.h and the 7-edge plan remains.

Verification rule: after every build compare the mtime of the .so in the build tree
and in `build/out` (the driver is loaded from there); RC=0 by itself means nothing.
Optional reinforcement: build with
`MESA_GIT_SHA1_OVERRIDE=<tag>` (the generator reads this variable) -
the `<tag>` string lands in the .so, and `strings ... | grep <tag>` proves
"the loaded driver = the built one", stronger than mtime.

## Building the test (rp6-vkd3d-sparse-test)

There is no compiler on the device - the test is built only in the container,
via `scripts/build-test.sh`:

```sh
podman run --rm \
  -v /var/home/armada/opencode/turnip-patches/tests:/work:Z \
  -v /var/home/armada/opencode/build:/out:Z \
  -v /var/home/armada/opencode/turnip-patches:/repo:Z \
  localhost/mesa-build-fedora44-wsi-glslang-vulkan \
  bash /repo/scripts/build-test.sh
```

- **Mounts - absolute paths only.** A relative
  `-v tests:/work:Z` breaks silently: the container starts, the script fails on
  `/work`.
- **Packages in the image.** `localhost/mesa-build-fedora44-wsi-glslang-vulkan`
  (17.11.2026, `podman commit` on top of `mesa-build-fedora44-wsi-glslang`)
  contains gcc + vulkan-headers + vulkan-loader-devel - dnf is no longer needed
  to build the test. With `--rm` packages installed in one run
  do not carry over to the next (journal 19.3), so "install into the
  image" means a commit of the image only, not an install into the container. Two pitfalls
  were recorded when it was created: (a) `podman start` without `-a` does not wait for
  dnf to finish - a commit in the middle of a transaction corrupts the rpm DB, wait for completion;
  (b) dnf pulls weak dependencies (mesa-vulkan-drivers + llvm-libs
  ~150 MB) - harmless for the build (the container does not run Vulkan,
  `-Dllvm=disabled`). The line `dnf -y install ...` in `build-test.sh` remains
  a no-op safety net for the old image.
- Result: `/var/home/armada/opencode/build/rp6-vkd3d-sparse-test`
  (`RP6_TEST_BIN` in `scripts/env.sh` points there too).
- **BC formats: names and values.** The driver is compiled against the
  vendored `mesa27-src/include/vulkan/vulkan_core.h`
  (VK_HEADER_VERSION 368); it and the system vulkan-headers 1.4.341
  (VK_HEADER_VERSION 341) have identical BC names/values (131-146):
  `BC1_RGB_{UNORM,SRGB}_BLOCK`=131/132,
  `BC1_RGBA_{UNORM,SRGB}_BLOCK`=133/134, BC2=135/136, BC3=137/138,
  `BC4_{UNORM,SNORM}_BLOCK`=139/140, `BC5_{UNORM,SNORM}_BLOCK`=141/142,
  `BC6H_{UFLOAT,SFLOAT}_BLOCK`=143/144, BC7=145/146. There are no names without the
  `_BLOCK` suffix, no `*_SFLOAT_BLOCK` (BC4/5) and no `BC6H_*_SRGB_BLOCK`. vkd3d
  maps DXGI BC1 to **BC1_RGBA**; the test (`tests/vkd3d-fmt-classes.h`) and the
  driver agree on the values.

## A/B on RE4

- The same scene section, the `p25` fps metric, as in journal 13.
- Expectation: 13-15 fps +/-1. Stock 26.2 and patched 26.2 already give the same
  result, and the bottleneck is the 7.3 GiB of RAM and the shared LPDDR5, not the driver code.
- If possible - RE4's built-in benchmark instead of the manual scene
  (closes the open question about `softfloat32`).
- Per-block counters - done via `fdperf` (`meson -Dtools=freedreno`):
  methodology, domains/dividers, pitfalls and the RE4 result are in
  [`docs/fdperf-a7xx.md`](fdperf-a7xx.md) (tools in
  `tools/fdperf/` + `scripts/fdperf-*.py`). Keep in mind:
  `TU_AUTOTUNE_FLAGS=preempt_optimize` occupies the last two
  CP counters and conflicts with `fdperf`.

### First measurement (17.11.2026)

Protocol journal 13: `HUDLOG=120 HUDINTERVAL=100 scripts/run-game.sh patched 150`,
DX12 (vkd3d -> Turnip), `p25` over frames `fps < 30`, one run.

| config | fps p25 | n |
|---|---|---|
| 26.2 stock | 13.0 | - |
| 26.2 patched (journal 13 baseline) | 13.9 | - |
| **27.0-devel, patched** | **14.57** | 700 |

p50 14.90, p95 17.36, mean 13.93. +0.7 fps over the baseline - within the expected
+/-1, slightly above zero: 27 does not break anything and possibly gives a small
gain, but there is no structural change (the bottleneck remains in memory/hardware). The nature of the
bottleneck was measured with per-block counters: L2/UCHE arbitration + DRAM latency ~220 ns
through the vertex path, not DRAM bandwidth - `docs/fdperf-a7xx.md`,
`results/games/re4/mesa27/`. The data is in
`results/mesa27/` (`fps-mesa27.csv`, the filtered and raw logs; the log
has the device signed: `Turnip Adreno (TM) 740 | sparseResidencyImage2D
true`). To conclude "27 is better" 2-3 repetitions are needed.

### A/B 0012 BC: methodology (the scene is the 3D menu) and current state (17.11.2026)

Compared are the **baseline** (0012-baseline, stack 0001-0011 without BC, .so sha256
`c9dad346f906...`) and **A+B** (stack + 0012 stage A+B, .so sha256
`704aa643f087...`). The drivers live in `build/out-base/` and `build/out-ab/`
(with their own ICD manifests); for a run the needed .so is copied into
`build/out/libvulkan_freedreno.so` (that is what
`build/out/freedreno_icd.json` points at, and `run-game.sh patched` reads it).

- Protocol: `HUDLOG=120 HUDINTERVAL=100 TAG=<name> scripts/run-game.sh patched 150`,
  DX12 (vkd3d -> Turnip), 2 runs per config, one at a time.
- Driver: **before every run** verify the sha256 of the .so in `build/out`;
  the raw log signs the device and `sparseResidencyImage2D` (stock 26.2
  does not have this - proof that the stack driver was loaded;
  base and A+B cannot be told apart by the flags - only by hash).
- Scene: the game starts through the intro (high fps - do not count it), then
  the **3D menu appears - this is the section with fps ~ 15**: the 3D scene saturates the GPU
  (`gpu_load` ~ 94-97 %, `gpu_core_clock` ~ 680 MHz - steady state).
  **Comparison window: [40, 60] s** from the first MangoHud sample (the menu
  appears at ~40 s). Metric: p25 + median over the window.
  (`elapsed` in the CSV is nanoseconds from process start; the first sample is ~0.1 s.)
  The old protocol from journal 13 ("p25 over all samples with fps<30" for the whole run) is
  equivalent for the mesa27 run: p25=14.57, n=700 reproduces exactly.
- Reference (mesa27, 14:21, baseline): window [40,60) s: med=15.0, n=198.

Pitfalls (17.11.2026): the game **does not always reach the 3D menu** - the run
ends on a static screen, and its numbers cannot be compared with the menu.
Three non-working states were recorded: ab-base1 - 49 fps,
`gpu_load` 28 % (the GPU is idle, static screen); ab-base2 - 171.5 fps for 60 s,
then fps 0 (the game is idling); ab-shot - 2.1 fps, `gpu_load` 0 %
(hung from ~20 s). The discriminator is `gpu_load` in the CSV: 3D menu 94-97 %,
any static screen <50 %. A run in a non-working state is invalid, repeat it.
Screenshot during a run: `scripts/shot.py`
(xdg-desktop-portal) - the portal **waits for user consent** in a dialog;
without a person at the machine it does not answer (30 s timeout). The reason for
the non-reproducible screens has not been established: there are no saves in the prefix,
`local_config.ini` has not changed since 05.11; both non-working runs were on
the same base driver as the reference one (hash verified) - the 0012 edits have
nothing to do with the difference.

State: **A/B paused** (17.11.2026) - until a reproducible 3D menu is
restored. The CEIL/roundtrip verification of stage A+B is
complete (logs `results/test-BCUBWC-stageA.log`,
`results/test-BCUBWC-stageAB.log`).

## Risks

- **devel branch.** 27.0.0-devel is not a release; there may be regressions that
  26.2 does not have. To roll back, return to 26.2.6 and the old stack (the 0001-0012 patches for 26.2
  are in the git history).
- **0003.** Offsets for 26.2.0 - the only patch where "applies" does not
  mean "does the same thing". Verify on hardware.
- **Memory.** A build in tmpfs eats RAM; with `-j8` an OOM is possible. `-j2` only,
  with the game closed.
- **Expected gain +/-1 fps.** The move is justified only as a test of the
  hypothesis "27 changes something", not as a way to raise FPS.
- Closed 18.11: BC+UBWC (exp-12 A+B) is retired as a lever and removed from the
  repo (journal 21.9) - RE4's BC textures are sparse, UBWC is forbidden
  for them regardless. The A/B here stays on record as a control, not a lever;
  the verification thread became the r2d-readback bug fix (bugs-found Bug 2).
