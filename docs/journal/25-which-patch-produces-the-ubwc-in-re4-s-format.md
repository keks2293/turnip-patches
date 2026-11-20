# 25. Which patch produces the UBWC in RE4's format lists (19.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

First, what Vulkan actually requires of a list. The compatibility-class rule
(`VUID-VkImageViewCreateInfo-image-02399`) applies only when no list is given. With
`MUTABLE_FORMAT` + `VkImageFormatListCreateInfo` the view only has to be a member of
the list (`...-02398`), and the list itself is unconstrained - which is exactly how
vkd3d-proton and DXVK express D3D12 typeless casts. So all 726 list-creates in the
game are outside the base format's class, and that is the normal path, not an
exotic one.

`results/raw/game-patched-imginv5.log` laid out against the upstream table
`fd6_ubwc_compat_mode()` (taken from `git show HEAD:src/freedreno/common/freedreno_ubwc.h`,
with the gen2 prop `ubwc_unorm_snorm_int_compatible = True`) and checked against the
actual `ubwc=` field. There are nine distinct "base -> list" combos:

| combo | creates | MiB | `ubwc=` | who gives it |
|---|---|---|---|---|
| `RGBA8_UNORM -> {UNORM,SRGB,UINT,SINT}` | 424 | 190 | 1 | upstream + prop `ubwc_unorm_snorm_int_compatible` |
| `RGBA8_SRGB -> same list` | 43 | 199 | 1 | same |
| `R16G16B16A16_UNORM/SNORM -> own lists` | 64 | 126 | 1 | same |
| `R8G8_UNORM -> {UNORM,UINT,SINT}` | 22 | 24 | 1 | same |
| **`R10G10B10A2_UNORM -> {UINT,UNORM}`** | **53** | **115** | 1 | **0011** (`A2B10G10R10_INT`) |
| **`R32_UINT -> {FLOAT,SINT,UINT}`** | **26** | **43** | 1 | **0012** (`R32_FLOAT -> R32_INT`) |
| `R8_UNORM -> {SINT,UINT,UNORM}` | 57 | 50 | **0** | nobody: the block sits before the compat table - `has_8bpp_ubwc` is False on a7xx (section 28, section 22) - and the table has no mode for it, adding one is forbidden by measurement |
| `R8_UINT -> {SINT,SNORM,UINT,UNORM}` | 37 | 20 | **0** | same |

By volume: **539 MiB of 767** ride on the upstream prop and do not depend on
`0005`/`0006`/`0010`/`0011`/`0012`; **158 MiB are `0011` (115) plus `0012` (43)**,
exactly the two combos where a format with `UNKNOWN_COMPAT` appears in the list;
**70 MiB** is the open `R8_*` hole. `0005`, `0006` and `0010` move **0 MiB** in this
game: the lists contain no B8G8R8A8 (the 12 BGR bases are created without
`MUTABLE_FORMAT`), no pairs that differ in byte order, and no single-channel next to
two-channel. The correlation is complete: `ubwc=1` wherever every format of the list
has a compat mode in the upstream table or is closed by 0011/0012, and `ubwc=0`
exactly where a hole remains.

Correction to section 24.3 about probe `T`. Its list is
`{B8G8R8A8_UNORM, B8G8R8A8_UINT}`; `vulkan_core.h` in the build container does have
`VK_FORMAT_B8G8R8A8_UINT/SINT/SNORM/USCALED/SSCALED` as enum values, but Vulkan
defines no *supported* format with that packing (only UNORM and SRGB are supported).
So `T` probes the **mechanism** (what a compat mode does to a layout), it is not a
workload shape, and among the five removed patches its form belongs to `0006` -
whose upstream motive is zink/gallium - rather than to `0011`/`0012`. `S` stays
attributed to `0005`/`0010`.
