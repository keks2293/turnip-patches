# 21.12. A mutable image without a list: the compatibility class instead of NULL (18.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

The inventory (`experiments/exp-14-image-inventory.patch`, `TU_IMG_INV=1`,
`results/raw/game-patched-imginv4.log`): of 7977 MiB of created images,
**4062 MiB (50.9%) are MUTABLE with `listn=0` in linear**. This is not the
"one bad format in the list" case (that one is cured by
0005/0009/0010/0011/0012), it is the absence of a list: the driver does not
know which format the image will be viewed as, so the three predicates get a
`NULL` and answer the worst case:

```
tu6_format_list_has_swaps(NULL)              = true
tu6_format_list_reinterprets_r8g8_r16(NULL)  = true
tu6_format_list_swaps_are_uniform(NULL)      = false
```

i.e. "there is a swap, there is an R8G8/R16 reinterpretation, and the swaps
are not uniform" - linear, even when every format the image may legally be
viewed as describes the same memory.

**The model.** `tu6_mutable_compat_class()` (0014) builds the set of formats
the base format may be viewed as, and the same predicates run on that set.
The grouping is the texel block: the same bits per block, the same block
width and height, the same compressed-ness. The tiled layout is a function of
the block size (`fd6_layout.c`: `layout->cpp =
util_format_get_blocksize()`, the tile height follows cpp), so a format
outside the block class can never describe the same memory. It is a
**superset** of the spec class ("occupies the same number of bits per texel
block"), and a superset can only make the answer more conservative. What is
left inside the class is the channel order - exactly what
`tu6_format_list_has_swaps()` and `tu6_format_list_swaps_are_uniform()`
already compare.

The "format is usable at all" filter has to consult both sides: the
block-compressed formats are texture-only in `fd6_format_table.c` (`_T_`
leaves `rb = NONE`), so `fd6_color_format() == NONE` alone drops them. With
only `fd6_color_format()` BC lost the tiling for nothing - measured: BC7
stayed linear until the `fd6_texture_format()` check was added.

**Measurement (probe NL, `tests/rp6-vkd3d-sparse-test.c`, 500x500 - not a
multiple of the tile, `results/test-0014-ship.log`, build `c17d02bcaae9`;
the same matrix on the instrumented build `050375a18b7b` is
`results/test-0014-final.log`; the intermediate build `97072a8f6376`, taken
before the UBWC-gate split below, gave the same 94/94):**

| class | base format | layout | why |
|---|---|---|---|
| 8-bit (1 B/texel) | `R8_UNORM` | tiled | no member needs a swap |
| 8-byte (64 bit) | `R16G16B16A16_FLOAT`, `R32G32_FLOAT` | tiled | every member is `WZYX` |
| block-compressed | `BC7_UNORM` | tiled | every member is `WZYX` |
| 4-byte (32 bit) | `R8G8B8A8_UNORM`, `R32_UINT` | linear | the class holds both RGBA8 and BGRA8 |
| 2-byte (16 bit) | `R8G8_UNORM`, `R16_UNORM` | linear | the class holds both R8G8 and R16 |

The last two rows are not an omission: it is the same demotion that
0005/0009/0010 guard on explicit lists, and a cross-order read through such a
class is genuinely undefined by the layout.

**The layout detector.** `memreq` separates the layouts only when the image is
not a multiple of the tile: tiled pads to the tile, linear pads rows. For BC
at 500x500 both totals are equal (`0x40000`), so the authoritative detector is
the sparse create: a linear image cannot be sparse (`tu_image_init()` refuses
it, see 0004), so `SUCCESS` means tiled and `FEATURE_NOT_PRESENT` means
linear. Both detectors agree with the model on all 8 probes, and all 8
fill+readback roundtrips are byte-exact (0 bytes differ). The roundtrip needs
0013: the fill is a `buffer->image` copy, and without the CCU clean its writes
are not visible to the reader.

**Agreement with the format query.** `tu_get_image_format_properties()`
refuses sparse+mutable when `tu6_mutable_format_list_forces_linear()` says
"linear", and it sees the same `NULL`. It now synthesizes the same class:
8-bit and 64-bit pass, 4- and 2-byte do not. The sparse-create column of the
probe is that agreement observed from the other side.

**The byte result.** Of the 3801 MiB "deposed" (that is how much of the
4062 MiB the script could classify by format), **2201 MiB (57.9%) go back to
tiled**: 1171 MiB 8-bit, 585 MiB 64-bit, 445 MiB BC; without BC (they need the
texture-side filter) - 1756 MiB. The per-class breakdown is
`scripts/fmt-list-gate-check.py --no-list results/raw/game-patched-imginv4.log`.

**Checked on the game.** The same script on the inventory taken with 0014
(`results/raw/game-patched-imginv5.log`, build `050375a18b7b`,
`results/test-0014-inventory-ab.log`): the deposed set is down to **1631 MiB
from 3801** - minus 2170 MiB, i.e. 57.1% against the predicted 57.9%. The
remainder is exactly the 32- and 16-bit classes (1023 + 600 + 7 MiB), as the
model said; slightly more was sampled than before (8110 vs 7764 MiB), so this
is not "the game loaded less". The 40-50 s window was healthy (680 MHz,
gpu_load 88%), but fps is not what this run measures - the inventory is
static.

**UBWC is deliberately not touched.** `tu6_mutable_format_list_ubwc_compatible()`
and `format_list_ubwc_possible()` are still handed the original pointer
(`ubwc_list` in `tu_image_init()`), which is NULL when the app passed no list,
so a no-list mutable image still loses UBWC exactly as in stock. Only the
tiling predicates are answered with the class. Keeping compression on such an
image would need its own content check (UBWC metadata reinterpretation is what
0011/0012 and exp-1/exp-2 were about), and mixing the two decisions in one
patch would make the byte result above unattributable. The 0014 patch header
states this too.

**Residual risk.** The content was checked in the base format; a read through
a *different* member of the same class (`R32_FLOAT` over `R8G8B8A8`) was not
run. The justification for it is the layout argument, not a measurement. For
the classes the patch actually moves to tiled, the argument is the same one
0005/0006 use for explicit lists: all members are `WZYX` with the same block,
so there is nothing to disagree about; but the honest statement is that the
tiled-no-list cross-view read has not been exercised.

---
