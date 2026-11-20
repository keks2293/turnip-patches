# 2.1. About UBWC: where it gets turned off and why these are different things

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

UBWC on A740 **is enabled for regular images**, and this is measured, not
assumed. Probe G (512x512 RGBA8, tiled, non-sparse, non-mutable) gives
`memreq 0x102000` versus `0x100000` for the LINEAR control — i.e. compression
metadata is present in the layout. Compression has always worked on A740.

`ubwc_enabled` starts out as `true` (`tu_image.cc:470`), and three gates clear
it, of different nature:

| Gate | Condition | Nature |
|---|---|---|
| sparse | `flags & SPARSE_RESIDENCY` → `ubwc_possible()` false | **structural**, see below |
| mutable | list not all in one `fd6_ubwc_compat_type` and `ubwc_all_formats_compatible == false` | driver conservatism |
| linear | `force_linear_tile` → `tile_mode = TILE6_LINEAR` | layout decision |

The second gate is a bit flag for the whole device, but the check before it is
per-list: if all formats of the list give the same non-`UNKNOWN`
`fd6_ubwc_compat_type`, the block is skipped entirely and UBWC stays. On A740
`ubwc_unorm_snorm_int_compatible = True`, so `{R8G8B8A8_UNORM,
R8G8B8A8_UINT}` already works in stock. This is exactly what **0006** fixes for
the B8G8R8A8 family, and it is verified numerically: probe T gives `memreq`
`0x100000` on stock and **`0x102000`** with the patches, with roundtrip
0/262144 — i.e. the UBWC metadata appeared, not just the layout changed.

It is important not to conflate two different gates: `ubwc_all_formats_compatible`
(a device property) and `ubwc_possible()` (a check inside the driver, which does
not depend on the generation). Therefore on the 830 casting the format of a UBWC
image is allowed, while UBWC on sparse resources is disabled there too.

### Why sparse + UBWC can't just be turned on

Not because of the hardware, and not only because of fast-clear. UBWC metadata
lives in a separate plane of the same allocation:

```c
struct fdl_layout {
   struct fdl_slice slices[...];        /* data planes */
   struct fdl_slice ubwc_slices[...];   /* UBWC metadata plane */
   uint64_t layer_size;
   uint64_t ubwc_layer_size;
   uint32_t mip_tail_first_lod;         /* for sparse resources */
};
```

`vkGetImageSparseMemoryRequirements` computes the requirements **from the data
only**: `fdl_sparse_miptail_size/offset` work exclusively off `slices[]` and
`layer_size`, and there is not a word about `ubwc_slices[]` there. The
application is told "bind `[mipTailOffset, +mipTailSize)` with a stride of
`layer_size`" — and neither of these ranges covers the metadata. So the
metadata of the bound tile will stay whatever the allocator left it as, and the
decompressor will read garbage.

This cannot be worked around within the API: `vkQueueBindSparse` accepts only
those offsets that the driver itself reported, and the metadata cannot be hid
inside the miptail — the layout and sizes are determined by the format. The
second layer is a guaranteed zero on unbound tiles: fast-clear exists on A740,
and the unpacker on an unbound tile may return something other than zero. The
upstream stub "Enable UBWC if nonResidentStrict isn't enabled"
(`tu_image.cc:332`) is closed **intentionally**: `tu_device.cc:1323` hardcodes
`sparseResidencyNonResidentStrict = true`. The driver itself declares "I don't
guarantee reading unbound as 0" — and that is exactly what is incompatible
with UBWC. The coupling is not accidental.

The benefit of a workaround would only be perf (bandwidth on bound tiles), and
for D3D12 it is zero: UBWC is an internal driver optimization, D3D12 neither
requests nor observes it. The harm from unbound metadata outweighs the
economics.

But turning the flag on is a bet on the unverified. If the assumption is wrong,
UBWC images with changing formats will go through silently, without a create
error, and this is the non-sparse path — exactly the class where data corruption
was already observed on stock and where 0006 (P6) fixes the situation by
merging B8G8R8A8 on the INT type.

From there vkd3d reaches the needed threshold without edits. The
`TiledResourcesTier` gate consists of three steps: exactly one is removed (feature
exposure), the second passes fully on A740, the third runs into 3D sparsity,
which A740 doesn't have, and returns `TIER_2` — exactly what feature level 12_0
requires.
