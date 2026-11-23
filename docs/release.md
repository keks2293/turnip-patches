# How a driver release is made here

A release here is a build of the driver plus the source bundle that reproduces
it. Nothing is published that was not run on the device first: the asset is the
exact binary that produced the log referenced in its notes.

## The stand and the versions

Everything below was measured on this machine and no other. Procedures (how to build,
how to run, how to take a window) are in `docs/howto-measure.md`.

| | |
|---|---|
| device | Retroid Pocket 6 (aarch64) |
| GPU | Adreno 740, `FD740`, a7xx **gen2**, chip_id `0x43050a01` |
| memory | 7.32 GiB RAM, LPDDR5X, ~51 GB/s peak; zram ~7.9 GiB |
| disk | the game on an exFAT volume mounted **by label** (the label changed from `Z Slim` to `Slim` and broke absolute paths; the scripts now find the directory) |
| kernel | 7.2.6 |

Properties the analysis rests on:

* 6 CCU and `num_sp_cores = num_ccu`, so `number_of_usptp = 12`;
* `has_8bpp_ubwc` is **absent** from the generated table for a7xx gen2 - the C
  initializer zeroes the field, the explicit `False` exists only on a6xx gen2/3/4, and
  the chain `[a7xx_base, a7xx_gen2]` does not inherit from it (ADR-0007);
* `num_ccu = 6` and the counter dividers: `docs/fdperf-a7xx.md`.

| component | version |
|---|---|
| stock Mesa (the system driver) | 26.2.3 (`mesa-vulkan-drivers-26.2.3-1.fc44.armada`) |
| working tree | Mesa 27.0-devel (`../mesa27-src`, base `6dfa32a85f91`) |
| vkd3d-proton | 3.1.0 (DX12) |
| DXVK | 3.1.1 (DXGI) |
| Proton | `proton-cachyos-11.0-arm64` |
| prefix | `/var/home/armada/Games/Heroic/Prefixes/re4` |
| game | RE4 Gold Edition, DX12, `VKD3D_CONFIG=''` |

RE4 goes down the DX12 path: DXVK provides DXGI, vkd3d-proton provides D3D12. The logs
contain both `re4.exe` and `xalia.exe` - two different clients, both of which load the
driver.

### Reference builds

`MESA_GIT_SHA1` is not embedded in the `.so`, and rebuilding the same stack is not
bit-for-bit, so a hash names a build and never a source state; stack identity is proven
by the 94-row matrix (journal 24.3).

*Corrected 23.11*: rebuilding the same **source tree** is bit-for-bit - the queue-16
verify tree built twice gave `f80d33ab2077` both times (journal 40.28) - so a hash
difference is a source difference. What is not reproducible is the **published** stack:
the bench tree drifted after 19.11 (journal 39.7), and the bundle's `0014` text is not
the text in `patches/` today (see the note at the end of "Provenance").

| build | what it is | journal |
|---|---|---|
| `c17d02bcaae9a960…` | the shipped `.so` (tag `27.0.0-devel-p14`) | - |
| `4c3cdb2100823b2f…` | the ship stack rebuilt on the bench, 94 EXACT, matrix line for line with p14 | 24.3 |
| `c9dad346f906` | clean base: stack 0001-0012 without the experimental rig | 29 |
| `cd436fd897f2` | stack + the `TU_B2I_SYNC` rig (modes 0-7, 15) | 21.11 |
| `050375a18b7b` | ship stack with 0014, the `imginv5` inventory run | 27 |
| `5e99409774838be5` | ship stack + `ubwc_all_formats_compatible` written into the gen2 table | 24.2 |
| `c60dfb26` | stack without 0005/0006/0010/0011/0012/0014, plus the prop | 24.3 |
| `44cdf593a5200d8b…` | stock Mesa 27 (`0001`/`0002` reverted too) + the prop line | 26 |
| `32d20074b8a128e4…` | the same + the `exp-14` inventory | 27 |
| `23ccf659c90d3ddf…` | stock + inventory, **no** prop: the honest bare base, built and NOT RUN | 27 |
| `5395a4f3f2c6fcce` | the exp-17 build (`TU_8BPP_UBWC` override) | 22.4 |

## What goes into a release

| asset | contents |
|---|---|
| `Turnip_<ver>.zip` | `libvulkan_freedreno.so` (unstripped, the tested bytes), `freedreno_icd.json` with `library_path` pointing at the same directory, `meta.json` (driver-manager metadata, `schemaVersion 1`), `README.txt` (install, what the patches do, how it was checked, known limits), `SHA256SUMS` |
| `turnip-<ver>-source-bundle.tar.gz` | `patches/0*.patch`, `PATCHES.md`, `HOW-TO-APPLY.txt` (Mesa base commit, sha256 of the applied diff, build command, resulting `.so` hash), `SHA256SUMS-patches`. Only the form that applies to the base commit of this stack goes in: the Mesa 26.2.3 variant kept in `patches/` for the image build stays out of the bundle, otherwise the `for p in patches/0*.patch` loop hits a patch that fails `git apply --check`. |

Naming follows the Vulkan driver releases people are used to comparing against
(`Turnip_v27.0.0-R2.zip` and friends). The tag carries the Mesa version and the
patch level: `27.0.0-devel-p14`.

Do not ship a stripped `.so` as the primary asset: the point of publishing a
devel build is that a bug report can be turned into a stack trace. Stripping
saves 1.5 MB of 11 MB and costs the symbols.

## Checklist before publishing

1. The tree that gets built is the ship tree: no measurement code in it. The
   experiment patches (`experiments/exp-14-image-inventory.patch`,
   `exp-15-b2i-sync-env-bundle.patch`) are what must NOT be there - exp-14
   prints one line per image created, so a log of a game session becomes
   several megabytes and the driver is doing I/O in `vkCreateImage`.
   Check the env knobs are gone from the tree:
   `grep -rn "TU_IMG_INV\|TU_B2I_SYNC" src/freedreno/` prints nothing.
2. The build is reproducible. Rebuild the same tree twice, the sha256 of
   `libvulkan_freedreno.so` must be identical:

   ```sh
   podman run --rm -v <src>:/src:Z -v /tmp/opencode/mesa27-build:/out:Z \
     -v /tmp/opencode/ccache:/ccache:Z -e CCACHE_DIR=/ccache \
     localhost/mesa-build-fedora44-wsi-glslang-vulkan \
     bash -c 'cd /src && ninja -C /out/build -j2 src/freedreno/vulkan/libvulkan_freedreno.so'
   ```

   The last rebuild after removing exp-14 gave the same hash as the build
   before it, which is what says the removal did not change the driver.
3. The test suite runs on exactly this binary, on the device, with the game
   closed: `tests/rp6-vkd3d-sparse-test --ver <hash12> --checks` -
   94 EXACT / 0 MISMATCH, plus the layout probe verdicts. Log into `results/`.
4. Record the hashes, all of them, in `results/test-<patch>-ship.log` and in
   the release notes:
   - the `.so` sha256 (the primary identity - it is what a user can verify);
   - the Mesa base commit (`git -C <src> rev-parse HEAD`) and `meson-version`
     from `--buildinfo` in `vulkaninfo`;
   - `sha256` of `git diff <base>` over the applied tree - this pins the source
     of a build whose tree is not committed anywhere, and it lets a third party
     check that the published patches produce the published binary;
   - the sha256 of every patch file, so the bundle can be verified on its own.
5. Every number in the release notes must point at a file in this repository
   (a log, a script, a patch header). If a number came from a run whose raw log
   is not committed, say so and say how to re-measure it - see the "how to
   reproduce" block at the end of `results/test-0014-inventory-ab.log`.
6. The game A/B is not a gate for a release. It is not a usable signal on this
   device (GPU clock ramping dominates the frame time - `docs/fdperf-a7xx.md`),
   so the notes state the memory and byte-exactness results instead, and say
   what was not measured.
7. The bundle is installed before it is published, not after. Extract the
   source bundle somewhere and run its own `HOW-TO-APPLY.txt` loop against a
   clean clone of the base commit: every patch must pass `git apply --check`
   with no `--3way` and no fuzz, and the `git diff <base> | sha256sum` of the
   result is the number that goes into `HOW-TO-APPLY.txt`. A patch that was
   hand-assembled from a head and a body diff is the usual way this fails.
   Hashing the bench tree instead of the re-applied tree is the other one: the
   bench tree is what the compiler saw, but it is not reproducible by anyone
   else, and it drifts the moment a patch is re-exported.

## Provenance of `27.0.0-devel-p14`

What shipped is the tested binary: `.so` `c17d02bcaae9a960a1350d98b81786dd75f1b5149cc79cb52b0409b59c345815`,
94 EXACT / 0 MISMATCH in `results/test-0014-ship.log`.

The tree hash recorded for the build tree at build time,
`70c46b7d9d97ab851328857a4fcba455214ccef489019a28fd4801ef0bd79177`, is **not**
reproducible from the published patches, and `HOW-TO-APPLY.txt` says so. It was
recorded before two corrections to the stack on 19.11:

* `0002` was re-exported from the Mesa 26.2.3 form (which upstream 27 rejects:
  `git apply --check` fails, and two of its three ids are already upstream)
  into the Mesa 27 form that adds only the KGSL base id `0x44050000`;
* `0014` carried one blank context line in the `tu_image.cc` hunk that
  `6dfa32a85f91` does not have and no patch of 0001-0013 adds, so the published
  file failed `git apply --check` on its own base - fixed, note in the patch
  header, added and removed lines untouched.

Re-applying the published bundle into a clean clone of `6dfa32a85f91` (14/14
patches pass `git apply --check`, 9 files change) gives
`93ab719ce512c622b75d5a8ae487392ea959de127677dfc57e12feb5a8d1e065`. Against the
applied-stack tree kept on the bench from that day the two trees differ in one
file of 11798: `freedreno_devices.py`, the A830 KGSL id line. So the driver
logic of the shipped binary is reproduced by these patches byte for byte; the
id-table row is what a rebuild would add, and an A740 never looks it up.

**The `0014` text moved on 23.11.** `patches/0014-*.patch` now carries the one-decision
form that queue 16 built as its A arm (journal 40.29): `exp-21` plus its static tail.
The p14 binary `c17d02bcaae9` and the published bundle keep the 19.11 text. The two were
measured equal - 0 of 598 full-suite lines (journal 33) and 784 game create signatures
with 0 differing `tile=`/`ubwc=` (journal 36) - and the inventory pair reproduces on the
dedicated builds (journal 40.29). A rebuild from today's `patches/` differs from the
bundle in this file's text, not in its decisions.

## Publishing

The release is created over the API, so it needs a token; SSH alone can push
the tag but cannot create a release or upload assets.

```sh
gh auth login --hostname github.com --git-protocol ssh --web   # device flow
git tag -a 27.0.0-devel-p14 -m "Turnip 27.0.0-devel, patch stack 0001-0014" <commit>
git push origin 27.0.0-devel-p14
gh release create 27.0.0-devel-p14 \
  --title "Turnip 27.0.0-devel + patch stack 0001-0014 (Adreno A7xx)" \
  --notes-file /tmp/opencode/release-notes.md \
  /tmp/opencode/release-bundle.zip#Turnip_27.0.0-devel_p14.zip \
  /tmp/opencode/turnip-p14-source-bundle.tar.gz
```

`gh release create` with an existing tag works; the tag must be pushed first so
that the release points at a commit that exists on the remote.

## History

| tag | date | note |
|---|---|---|
| `27.0.0-devel-p14` | 19.11.2026 | first release of this repository: stack 0001-0014 on Mesa 27.0.0-devel `6dfa32a85f91`, `.so` `c17d02bcaae9`, 94/94. The source bundle was rebuilt the same day: 0002 in its Mesa 27 form and 0014 with the context fixed, so the published stack installs clean on its stated base - see "Provenance" above. |

## Chronology of the work

Not a release history - a timeline of when the measurements happened, so that an entry
in `docs/analysis.md` can be placed in time. Journal entries 7-19 carry no date in their
heading; this is where the dates come from.

| date | what happened |
|---|---|
| 21.09 | the initial RP6/vkd3d analysis: why DX12 games refuse 12_0 (journal 1-6) |
| 30.09 | vkmark and RE4 props, memory measurement, autotune (journal 15, 17) |
| 02.10 | R8 and `has_8bpp_ubwc`, the first measurement (journal 21.7, superseded by 22) |
| 04.10 | 12_1 traced to `VK_EXT_fragment_shader_interlock`; 0012 into the stack (ADR-0011) |
| 17.11 | fdperf: the memory wall (`docs/fdperf-a7xx.md`) |
| 18.11 | BC readback: 0013 v1/A/B rejected, root cause is the CCU, i2b 91/91; the form of the fix chosen later by exp-15 (journal 21.8, 21.10) |
| 18.11 | R8 re-checked in split submits; the CPU governor checked and dismissed (journal 21.7, 29) |
| 19.11 | exp-15: 16 modes, mode 7 -> 0013; the root-cause text corrected; the linear-deposition inventory -> 0014 (2201 MiB by the model, 2170 MiB in game); the "1.86 fps" artefact (journal 21.10-21.12, 29) |
| 19.11 evening | `ubwc_all_formats_compatible` on gen2 reconciled with the patch stack - the removable list is empty; 0014 v2 rejected; stock + one prop line built and shown to play (journal 24-26, ADR-0001) |
| 20.11 | 8bpp second pass: R8 + UBWC reads back exactly a quarter at every size, metadata geometry excluded, no patch (journal 22, ADR-0007); documentation restructured into journal/decisions/streams |
