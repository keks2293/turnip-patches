# 9. Why the patched driver failed vkCreateInstance

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

The symptom looked enigmatic: `VK_LOADER_DEBUG=all` showed that the loader
finds and loads the ICD without a single error, yet the DXVK call doesn't even
produce the line `vkCreateInstance layer callstack setup to:` — i.e. the
rejection happens before entering the loader, inside winevulkan. Hence the
false conclusion "the patch is to blame".

The real cause is the build configuration, not the patch code:
`scripts/build-turnip.sh` built meson with `-Dplatforms=` (empty). Such a
build is fine for our own test from section 6 — it doesn't show a window — but
then the driver has no platform WSI extension at all. Comparing `vulkaninfo`:

| | `VK_KHR_xcb_surface` | `VK_KHR_xlib_surface` | `VK_KHR_wayland_surface` |
|---|---|---|---|
| image's packaged driver | yes | yes | yes |
| patched (`-Dplatforms=`) | no | no | no |

winevulkan translates the game's win32 surface (in DXVK's enabled list —
`VK_KHR_win32_surface`) into a host surface, i.e. xcb or wayland. With neither
present the translation is impossible, the instance is not created, and DXVK
dies.

The manifest shows exactly the same discrepancy: the built driver is a
different `libvulkan_freedreno.so`, not "the same one but with a patch", and it
must be compared with the stock one by its extension list, not by file name.

Fixes:

- `scripts/build-turnip.sh`: `-Dplatforms=x11,wayland` — the same set as in the
  image's packaged build (`image-build/mesa-x86-build.sh`);
- `container/Containerfile.mesa-build`: added the WSI dependencies
  (`libxcb-devel`, `libX11-devel`, `libxshmfence-devel`,
  `xcb-util-keysyms-devel`, `wayland-devel`, `wayland-protocols-devel`).
  Without them meson fails at the dependency check instead of silently building
  a driver without WSI;
- `container/Containerfile.mesa-glslang`: the package name in Fedora 44 is
  `glslang`, not `glslang-tools` (there is no `glslang-tools` in the repo, the
  install fails); the base was switched to the build image, otherwise it lacks
  meson/ninja/gcc;
- the ICD manifest is brought to the shape of the packaged driver:
  `api_version "1.4.341"`, `file_format_version "1.0.1"`,
  `library_arch "64"`.

Rule for the future: **do not run a driver build and a game at the same time.**
The device's memory (7.3 GB) is shared with the GPU; the game and
`ninja -j$(nproc)` together drive the system into OOM — the cursor freezes and a
reboot is needed. The same was observed last time, according to the user, and
the patch lost then was most likely caused by exactly this. `scripts/build-turnip.sh`
has a check for a running Wine before the build starts.

The image's own build script agrees: `image-build/mesa-x86-build.sh` (a copy of
the recipe) builds turnip with `-Dplatforms=x11,wayland`, i.e. the packaged
driver does have WSI and the discrepancy was only in the quick-start build
here. Also useful for the future from there: pressure-vessel runs a `dlopen`
inspection of every provider-ICD and silently drops the one that fails to
resolve some dependency — when swapping the driver through Steam this would
have looked like "ICD not found" rather than a loading error.

### Gate removed on a live application

After rebuilding with WSI (`results/game-patched.log`): DXVK creates the
instance, the device is created, and — the main thing — **12_0 is accepted**.
The rejection `Feature level 0xc000 is not supported` is gone, while the
rejection `0xc100` (12_1) remains, as it should: 12_1 runs into a different
gate (`ROVsSupported` + `ConservativeRasterizationTier >= 1`), and that is not
part of the task.

The proof is strict because the log trigger is tied to the code:
`WARN("Feature level %#x is not supported")` in `libs/vkd3d/device.c:10880`
sits exactly on the `!d3d12_device_supports_feature_level(...)` branch — i.e.
it is printed if and only if the requested level is above
`max_feature_level`. Comparison under identical conditions:

| | `d3d12_device_create` attempts | feature level rejections | max |
|---|---|---|---|
| packaged driver | 4 | `0xc100` (12_1) and `0xc000` (12_0) | 11_1 |
| patched | 3 | only `0xc100` (12_1) | **12_0** |

The attempt with `minimum_feature_level = 12_0` got no rejection, so
`max_feature_level >= 0xc000`. Meanwhile the game did not die: the process
lived to the end of the run (code 124 — our timeout), zero `err:`, zero
`Exception` in the log, and the log header says
`sparseResidencyImage2D | true`.

### Why 0xc100 (12_1) remains: one unimplemented extension (04.10.2026)

Above journal 9 called the 12_1 condition "`ROVsSupported` +
`ConservativeRasterizationTier >= 1`" and put it outside the task. Now it is
opened up fully — from the vkd3d-proton sources (`libs/vkd3d/device.c`, master
of 04.10.2026) and measurements on the device.

The `max_feature_level` cascade in `d3d12_device_init_caps()`:

    11_0 → 11_1 (OutputMergerLogicOp + storage slots)
        → 12_0 (TiledResourcesTier >= 2, ResourceBindingTier >= 2,
                TypedUAVLoadAdditionalFormats)
        → 12_1 (ROVsSupported && ConservativeRasterizationTier >= 1)
        → 12_2 (SM 6_5, RT 1_1, mesh, VRS tier 2, conservative tier 3, ...)

For us everything holds except `ROVsSupported`:

- **ConservativeRasterizationTier >= 1** — holds. Requires
  `EXT_conservative_rasterization`; Turnip enables it at `chip >= 7`
  (`tu_device.cc:312`), and both the packaged 26.2.3 and our build expose it
  (measured with `vulkaninfo` 04.10; `degenerateTrianglesRasterized = true`,
  i.e. the tier is no lower than 1, and by the function
  `d3d12_device_determine_conservative_rasterization_tier()` it is at least 2).
- **`ROVsSupported` = `fragmentShaderPixelInterlock && fragmentShaderSampleInterlock`**
  from `VK_EXT_fragment_shader_interlock` (`device.c:9270`). This is **not**
  rast-order-access: `VK_EXT/ARM_rasterization_order_attachment_access` exists
  in Turnip, but vkd3d doesn't read it for ROV.
- **`VK_EXT_fragment_shader_interlock` is not implemented in Turnip.** Checked
  against the ICD (`vulkaninfo` with `VK_DRIVER_FILES`, 04.10):
  `freedreno_icd` — 0; the line in the system output comes from `lvp_icd`
  (lavapipe). In the `src/freedreno` tree — not a trace of it, even though the
  SPIR-V/NIR infrastructure exists (`spirv_to_nir.c:7339`,
  `SpvOpBeginInvocationInterlockEXT`).

Status in the Mesa upstream (gitlab API, 04.10.2026): implemented in RADV
(MR 22250, via the HW primitive PoPS — `radv_has_pops`), ANV (enabled
unconditionally), lavapipe and zink; for nvk there is an open MR 38206. For
Turnip — neither an MR nor an issue.

Conclusion: 12_1 runs into exactly one extension not implemented in Turnip.
There is no publicly documented interlock primitive for Adreno, so an honest
implementation would be emulation: a spinlock table hashed by pixel in global
memory plus a fence (ir3 has both atomics in fragment shaders and the `fence`
instruction), with open questions: deadlock if a call is killed inside the
section, and helper-invocations. Enabling the flags without lowering would be
a lie about the caps. Also deserving a separate decision is that a single
consumer — `ROVsSupported` for the 12_1 flag — while RE4 doesn't use ROV at
all and runs on 12_0.

A force exists (`VKD3D_FEATURE_LEVEL=12_1`,
`d3d12_device_caps_override()`: sets `ROVsSupported = TRUE` and
`max_feature_level = 0xc100`), but this is caps spoofing; the check of the
"options" was done by measuring extensions and reading the vkd3d code, without
it.

### What remains unsolved

The game didn't reach a window: in 200 s `dxgi_vk_swap_chain_init` never
appeared (in the stock run it occurs right after the device is created), and on
the screen there was a window with the text "your GPU was not supported". This
is the game's own rejection, not proton's: the log is clean — zero `err:`,
zero `Exception`, the process lived to the end of the run (code 124 — our
timeout).

Compared to stock you can see the game went further than usual: it raises the
shader cache (`existing entries: 9962, new entries: 1898`) and reaches
`d3d12_device_CheckFeatureSupport`. So the 12_0 path works, while the
capability check breaks, and the game answers it with a rejection based on
requirements.

The guess was this: by design 0004 rejects create for the combination sparse +
MUTABLE without a compatible format list, while vkd3d sets
`MUTABLE_FORMAT_BIT` liberally and not always with a list; at 11_1 the game
doesn't touch this path, at 12_0 it does, and the 0004 rejection hits the
target. **The version was checked and disproved:** exp-3 removed
exactly that rejection while keeping the gate removal, and the game's behavior
didn't change — the swapchain still didn't come up (no
`dxgi_vk_swap_chain_init` line), the "your GPU was not supported" window still
appeared, the run still ended without a single `err:`. So the cause is not the
0004 rejection.

What needs looking at is the capability check the game itself performs: it is
called after device creation at 12_0 and concludes that the GPU is unsupported.
Tellingly, the user saw the same window last time as well, with a different
driver build — i.e. this is a stable symptom of 12_0, not a regression of the
current build. The candidate is the updated vkd3d, which at 12_0 reports a
different set of capabilities than the game expects; that is a separate branch
of the analysis.

The line `CheckFeatureSupport: Assuming device does not support tile based
rendering` is not a discriminator: it is present in the stock run too.

Separately about memory: the 7.3 GB of RAM on the device is shared with the
GPU. The game holds ~1.2 GB resident plus ~1.1 GB in zram, i.e. swapping is
happening; no OOM was observed meanwhile.

### Candidate No.1: the shader model (being checked)

The only line that is absent in the patched run and present four times in the
stock one is `d3d12_device_caps_init_shader_model: Enabling support for SM
6.6.` In the patched run it is absent in all three device creations. This
matters: levels 6.0/6.2/6.3/6.5 vkd3d prints via `TRACE` — with normal logging
they are not visible, while 6.6/6.7/6.8 go via `INFO`. The absence of the line
means `max_shader_model <= 6.5`.

The 6.6 condition (`device.c:9814`) rests entirely on physical device
properties: `computeDerivativeGroupLinear`, `shaderBufferInt64Atomics`,
`shaderInt8` and
`d3d12_device_supports_required_subgroup_size_for_stage(COMPUTE)`. Comparing
`vulkaninfo` for both ICDs shows that the Adreno property layout matches,
except for the sparse bits themselves:

| | stock | patched |
|---|---|---|
| extensions | 211 | 211 |
| `feature = true/false` lines | 416 | 416, one difference |
| differences | — | `sparseResidencyImage2D`, `sparseResidency{2,4,8}Samples` |
| `subgroupSize` / `minSubgroupSize` / `maxSubgroupSize` | 128 / 64 / 128 | same |
| `subgroupSupportedOperations` / `Stages` | 10 / 6 | same |
| `computeDerivativeGroupLinear`, `shaderInt8`, `shaderBufferInt64Atomics`, `subgroupSizeControl` | true | same |

So per the driver's data the 6.6 gate must pass in both cases. Either the
11:48 run log was taken from a different `build/out` build, or vkd3d reads
something beyond what `vulkaninfo` shows. This is resolved by a run with
`VKD3D_DEBUG=trace`: then vkd3d prints both `Enabling support for SM 6.5.` and
the version for 6.6.

The hypothesis agrees with the other facts: at 11_1 (the stock run) that same
rejection is absent because the game doesn't ask for 12_0. It is checked with
no code edits at all: `VKD3D_SHADER_MODEL=6_6`
(`d3d12_device_caps_shader_model_override`, `device.c:9646`) forces vkd3d to
report 6.6. If with this the window disappears and the swapchain comes up — the
cause is confirmed.

A side finding from the same comparison: our ICD manifest declared
`api_version 1.4.341`, while the packaged one is `1.4.354`, and that is exactly
the version the driver itself reports. It doesn't affect behavior, but the
mismatch was removed (`scripts/build-turnip.sh`).
