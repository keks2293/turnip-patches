# 16. mixed-swap (cross-order experiment): tiled+UBWC for {BGRA8, RGBA8}

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

> Here and below "cross-order experiment" is **not patch 0006** (that one adds
> `FD6_UBWC_B8G8R8A8_INT`, see journal 5 and `patches/`), but the probe
> `experiments/exp-6-cross-order-list-tiled-ubwc.patch`. Experiments are
> numbered `exp-N`, patches `000N`: which experiment went into which
> patch - the lineage table in the main README.

One reinterpretation scenario remained unused: a format list with the same
block geometry but a different channel order —
`{B8G8R8A8_UNORM, R8G8B8A8_UNORM}`. The control (stock and patches
0004–0008): `swaps_are_uniform()` rejects such a list → `tu_image_init()`
turns off UBWC and forcibly puts the image in linear. The cross-order
experiment (`experiments/exp-6-cross-order-list-tiled-ubwc.patch`)
introduces the predicate `tu6_format_list_same_shape()` (all formats of the
list are the same texel block: channels, bits, shape) and in the mutable branch
leaves such a list tiled+UBWC; the sparse query
(`tu6_mutable_format_list_forces_linear`) is deliberately not touched.

The check is a new probe **S3** in `rp6-vkd3d-sparse-test.c` (non-sparse
MUTABLE `{BGRA8, RGBA8}`: fill, read with the base BGRA view, read with the
cross view RGBA, raw transfer). Logs `results/test-s3-*.log`:

| Run | memreq | base BGRA | cross RGBA | raw |
|---|---|---|---|---|
| stock 26.2.3 (`stock`) | 0x100000, linear | EXACT | identity (`== fill2`) | 0/262144 |
| control 0004–0008 (`control`) | 0x100000, linear | EXACT | identity | 0/262144 |
| experiment (`ubwc`) | 0x102000, tiled+UBWC | EXACT | **swapped** (`b0<->b2`) | 0/262144 |
| after rollback (`postrev`) | 0x100000, linear | EXACT | identity | 0/262144 |

What follows from this:

- **Mechanically the HW copes**: raw bytes pass through
  compress-on-store/decompress-on-copy without loss, the base view reads
  exactly, the cross view is deterministic — there is no garbage.
- **But the view's semantics changes.** Identity is positional
  reinterpretation of bytes: the RGBA view reads memory byte0 as Red. Both the
  linear path and stock give this. On UBWC the cross view returned the same
  channels as the base (swapped) — the view's channel order is ignored, the
  behavior deviates from stock, against which the other probes were verified.
  (The S3 PASS criterion is deliberately structural — "one of the two
  candidates"; the correctness decision is made by comparison with the
  control.)
- **There is no practical gain**: vkd3d-proton doesn't build cross-order lists —
  0 of 72 in `tests/vkd3d-fmt-classes.h`. This is a consequence of the code,
  not just of parsing the header: the list comes from a single table
  `dxgi_format_compatibility_list[]` (`libs/vkd3d/utils.c:457+`, copy of the
  sources in `srcs/vkd3d-proton`), where the classes mirror DXGI-typeless
  families and don't mix channel order (the cast `R8G8B8A8 ↔ B8G8R8A8` is
  forbidden in D3D12), and the runtime additions
  (`vkd3d_format_compatibility_list_add_format`, 5 places in `resource.c`) add
  only the image's base format, the view formats of the same entry, the
  R32-UAV set and `R64_UINT`.
- Incidentally, sparse-create opened up for such lists: `E` and `S2` changed
  `FEATURE_NOT_PRESENT` to `SUCCESS` (as on stock), while the query stayed
  `FORMAT_NOT_SUPPORTED` — create and query diverged. `F` (NULL list) was not
  touched, the rest of the test output didn't change (the same 6 `FAIL`s).

Summary: rollback via `git apply -R experiments/exp-6-cross-order-…`,
rebuild the driver, a control run matched the control byte for byte
(`postrev` == `control`), the mesa tree files were compared with the backup —
identical. Conclusion: "cross-order tiled+UBWC" is mechanically achievable in
HW, but the observed cross-view semantics is not equal to the stock/linear one
→ do not enable. S3 stays in the test as a control of this boundary.

### 16.1. Who builds cross-order lists at all (checked against the code)

The absence of such lists in vkd3d is neither coincidence nor a shortcoming but
a consequence of the D3D12 specification. In `dxgi_format_compatibility_list[]`
(`srcs/vkd3d-proton/libs/vkd3d/utils.c`) the classes mirror the typeless
families, and BGRA/RGBA are two **non-overlapping** classes:

```c
// utils.c:317 — RGBA8 family: only variants of one channel order
{DXGI_FORMAT_R8G8B8A8_TYPELESS,
        {R8G8B8A8_UINT, R8G8B8A8_SINT, R8G8B8A8_UNORM,
         R8G8B8A8_UNORM_SRGB, R8G8B8A8_SNORM}, …},

// utils.c:457 — BGRA8 family, separately
{DXGI_FORMAT_B8G8R8A8_TYPELESS,
        {B8G8R8A8_UNORM, B8G8R8A8_UNORM_SRGB}, …},
```

UNORM/SNORM/UINT/SINT are compatible because they interpret the same bits the
same way; `R8G8B8A8 ↔ B8G8R8A8` are not — the channel order differs, and D3D12
doesn't allow such a cast.

The second consumer of mutable lists is **Zink** (a GL gateway into Vulkan,
i.e. into our turnip; `src/gallium/drivers/zink/zink_resource.c:1561`,
`setup_format_list()`) — it builds exactly two kinds of lists:

```c
if (!(templ->bind & ZINK_BIND_MUTABLE) && can_srgb) {   /* linear ↔ srgb */
   srgb = util_format_is_srgb(templ->format) ? util_format_linear(templ->format)
                                             : util_format_srgb(templ->format);
}
if (srgb) { formats[0] = zink_get_format(…, templ->format);
            formats[1] = zink_get_format(…, srgb); }      /* same channel order */
else if (templ->bind & ZINK_BIND_VIDEO) { … }            /* planes of one format */
```

So it is always `format + its sRGB variant` or the planes of one format —
**the channel order is the same**, there is no cross-order.

Summary: cross-order lists are unreachable both for D3D12 and for GL through
Zink.

About the Zink pairs `format + sRGB variant` — see journal 16.2: they stay
tiled+UBWC even on stock, the code never reaches `has_swaps`. Neither the
cross-order list nor the uniform-swap list for which patch 0005 was written is
built by either D3D12 or Zink.

### 16.2. Who actually ends up in linear: an enumeration accounting for the early exit

The first analysis in journal 16.1 gave an incorrect conclusion ("0005 fixes the Zink
pairs `RGBA8 ↔ RGBA8_SRGB`"). The reason was a simplified enumeration that only
counted `has_swaps()`. The decisive detail it missed: **`tu6_mutable_format_list_ubwc_compatible()`
sits above `has_swaps()` and skips the whole block**, and this gate exists in
stock:

```c
// tu_image.cc:539 — stock, tu_image.cc:530 — git HEAD, without our edits
if ((pCreateInfo->flags & VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT) &&
    !vk_format_is_depth_or_stencil(image->vk.format)) {
   const VkImageFormatListCreateInfo *fmt_list = …;
   if (!tu6_mutable_format_list_ubwc_compatible(info, fmt_list)) {
      … NV12 branch, UBWC removal, r8g8_r16, has_swaps …
   }
}
```

The same early exit exists in `tu6_mutable_format_list_forces_linear()`
(`tu_formats.cc:230`), i.e. in the sparse query of patch 0004 — it too is
consistent with create. List compatibility is decided by `fd6_ubwc_compat_mode()`
(`freedreno_ubwc.h`), where the `linear` variant and the `_SRGB` variant of the
same format always give **the same** type.

FD740 properties: `freedreno_devices.py` → `[a7xx_base, a7xx_gen2]`, i.e.
`ubwc_unorm_snorm_int_compatible = True`, `ubwc_all_formats_compatible = 0`.
Enumeration: `scripts/fmt-list-gate-check.py` (ports the driver's predicates to
Python, taking the properties from `fd6_format_table.c` and
`fd6_ubwc_compat_mode()`).

**vkd3d, 70 classes of `tests/vkd3d-fmt-classes.h` (at the time; about the two
classes added later `B8G8R8A8/B8G8R8X8_TYPELESS+UAV` — journal 21.3):**

| Fate | Classes | create on stock | +0005 | +0005+0006 |
|---|---|---|---|---|
| early exit, list UBWC-compatible | 31 | tiled+UBWC | same | same |
| gate didn't pass, but no swaps | 38 | tiled, UBWC off | same | same |
| planar NV12 | 1 | tiled, UBWC off | same | same |
| **into linear** | **0** | — | — | — |

**No class from `tests/vkd3d-fmt-classes.h` reaches linear on gen2 even on
stock.** The six BGRA classes (`tests/vkd3d-fmt-classes.h:51-56`) are
`{B8G8R8A8_UNORM, B8G8R8A8_SRGB}`, both formats give `FD6_UBWC_B8G8R8A8_UNORM`,
the gate passes, and stock deliberately contains this case with the comment
"zink would really like to". The earlier "6 BGRA classes in linear" was an
enumeration error.

**But there is a path into linear in D3D12, and the table above doesn't model
it.** `vkd3d_get_format_compatibility_list()` (`utils.c:393-401`) for a
TYPELESS format with `byte_count == 4` under the `ALLOW_UNORDERED_ACCESS` flag
adds `{R32_UINT, R32_SINT, R32_SFLOAT}` to the list — this is the D3D11 rule
about typed UAV loads. For `B8G8R8A8_TYPELESS + ALLOW_UNORDERED_ACCESS` you get
a mixed list of five formats:

```
B8G8R8A8_UNORM + B8G8R8A8_SRGB + R32_UINT + R32_SINT + R32_SFLOAT
  gate: stock=False  0006=False  0010=False   ->  linear
```

The answer here is correct: BGR and R32 are different layouts, a common compat
class doesn't fit them, linear is legitimate. But it followed that the claim
"on gen2 no vkd3d image goes into linear" holds only for the 70 classes listed
at the time, not for vkd3d in general: `tests/vkd3d-fmt-classes.h` contained no
R32 additions to the BGRA classes, i.e. the model didn't check this case.

Later these two classes were added to the model (`B8G8R8A8_TYPELESS+UAV`,
`B8G8R8X8_TYPELESS+UAV`) and measured on hardware — section 21. It turned out
that the "linear is legitimate" rule is excessive here: only single-channel
formats diverge, which have no channel order at all, so changing visibility
through
`R32_UINT` view is nothing to change. `experiments/exp-9-single-channel-swap-vacuous.patch`
removes this rule, and tiling returns on the 740. Neither 0005 nor 0006 closes
this case, see journal 21.3.

**Zink.** `setup_format_list()` (`zink_resource.c:1561`) builds exactly two
kinds of lists — `(F, F_SRGB)` and the planes of a video format. Of the 11
pairs `(F, F_SRGB)` that exist in the format table at all:

| Pairs | stock create | +0005 | +0006 |
|---|---|---|---|
| `R8G8B8A8`, `R8G8`, `B8G8R8A8` (3) | tiled+UBWC (early exit) | same | same |
| `A8B8G8R8`, `A8R8G8B8`, `B8G8R8X8`, `X8B8G8R8`, `X8R8G8B8` (5) | **linear** | tiled | linear |
| `L8`, `R8`, `R8G8B8X8` (3) | tiled, UBWC off | same | same |

But Zink doesn't build these five pairs either. GL hands Zink only
`B8G8R8A8_UNORM` from this set (`st_format.c:268`, `{ GL_BGRA, GL_BGRA8_EXT, 0 }`),
and its pair passes the gate. `PIPE_FORMAT_A8R8G8B8_*`, `A8B8G8R8_*`,
`X8R8G8B8_*`, `X8B8G8R8_*`, `B8G8R8X8_*` don't appear even once in
`src/gallium/drivers/zink/` — only inside `zink_format_emulate_x8()`, i.e. as a
result of emulation rather than as a resource format.

The third Zink case is `ZINK_BIND_MUTABLE`. Here the format list is
**absent**: `init_ici()` (`zink_resource.c`) sets `MUTABLE_FORMAT_BIT` and
zeroes `pNext`; `emit_usage_candidates()` under `always_mutable` doesn't build
a fmtlist variant either. Such an image → linear without UBWC on stock and with
the patches, and this is correct: no list is set, so the application is entitled
to reinterpret the image into any compatible format, and
`has_swaps(NULL) == true` by stock design. The x8/alpha-emulation pairs
(`zink_format_needs_mutable()`, `zink_format.h:53`) give `false`, i.e. mutable
isn't needed for them at all.

**Who 0005 actually fixes.** Enumeration of all ordered format pairs of the
table (`--all-pairs`, 115×114):

- **0005** restores tiling for **158** pairs — exclusively the BGR/BGRA family
  (`B5G6R5 ↔ B5G5R5A1`, `B5G6R5 ↔ B8G8R8A8`, …). Of those, **18** pairs are
  also covered by 0006 (`B8G8R8A8` with `UNORM/SRGB/SNORM/UINT/SINT`, where UBWC
  is also restored), the remaining **140** — only by 0005.
- **0006** — 18 pairs: exactly `{B8G8R8A8_X, B8G8R8A8_Y}` for all `X ≠ Y` from
  `{UNORM, SNORM, UINT, SINT, SRGB}`.
- `r8g8_r16` doesn't fire on any pair of the table.

**Checked against the consumer's code, not by enumerating pairs.** Previously
here stood "vkd3d translates DXGI-BGR into RGBA order, therefore it doesn't
build lists". This is true only for 16-bit BGR (`B5G6R5 →
VK_FORMAT_R5G6B5_UNORM_PACK16`, `B5G5R5A1 → A1R5G5B5_UNORM_PACK16`,
`B4G4R4A4 → A4R4G4B4_UNORM_PACK16`, `A4B4G4R4 → R4G4B4A4_UNORM_PACK16` —
`utils.c:114-138`), while 32-bit BGRA8 vkd3d doesn't touch: `utils.c:107-112`
hands out `VK_FORMAT_B8G8R8A8_UNORM` directly. Therefore the B8G8R8A8 family
lists must be analyzed separately:

* In `dxgi_format_compatibility_list` (`utils.c:279-303`) the B8G8R8A8 entries
  **do exist**, and the only list vkd3d builds from them is
  `{B8G8R8A8_UNORM, B8G8R8A8_SRGB}` (`utils.c:279-282`). Both formats give one
  compat type `FD6_UBWC_B8G8R8A8_UNORM`, the gate passes on stock, and
  0006/0010 change nothing on this pair: `tiled=True ubwc=True` in all four
  combinations.
* 0006 adds `UINT`/`SINT`/`SNORM` to this class, but such DXGI formats don't
  exist in vkd3d **at all** — `grep 'B8G8R8A8_{UINT,SINT,SNORM}' libs/vkd3d/utils.c`
  is empty. vkd3d cannot build the list for which 0006 was written.
* 0005 fixes the cross pairs of 16-bit BGR, and Zink doesn't know them:
  `PIPE_FORMAT_{A8R8G8B8,A8B8G8R8,X8R8G8B8,X8B8G8R8}` don't appear even once in
  `src/gallium/drivers/zink/`; `B8G8R8X8`/`B8G8R8A8` — two occurrences each,
  both inside `zink_format_emulate_x8()`, i.e. the result of emulation rather
  than a resource format.

Summary: **on gen2 neither 0005 nor 0006 changes a single image, neither for
D3D12 nor for GL/Zink.** Both are logically correct and implement the upstream
TODO, both are safe, but their only consumer is our own synthetic probes S and
T. This was verified by enumeration over the 72 classes, including the two
added later `B8G8R8A8/B8G8R8X8_TYPELESS+UAV`: they don't reach 0005/0006, for
the reasons analyzed in journal 21.3. There is no point in keeping them in the working
stack for ArmadOS; `0004` (removing the sparse gate) and `0009` (NV12) are
another matter — they change behavior on real lists.

**A side risk of 0004 found in this analysis.** vkd3d creates `MUTABLE`
**without** a format list in three places (`libs/vkd3d/resource.c`): planar
formats (`:383`, `:363` — `VK_IMAGE_ASPECT_PLANE_0_BIT`), compatibility list
overflow (`:365-368`, needing 10 formats out of
`VKD3D_MAX_COMPATIBLE_FORMAT_COUNT = 10`) and bypassing
`DISABLE_SIMULTANEOUS_UAV_COMPRESSION` (`:826`). The first case on gen2 is
NV12, and 0009 closes it. The other two give linear + sparse → our 0004
rejects create (`FEATURE_NOT_PRESENT`, exactly like probe F), i.e. vkd3d gets
an error instead of silent corruption. This is a deliberate trade: upstream
instead of rejecting simply doesn't advertise `sparseResidencyImage2D`.
