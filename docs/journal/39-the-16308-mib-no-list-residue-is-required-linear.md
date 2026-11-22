# 39. The 1630.8 MiB no-list residue is required linear by the spec, not by our predicates (21.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules
for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or
`journal N.M`, where the number is also the start of the file name.

Bottom line: the compatibility class of an uncompressed colour format **is** its texel block, the
cross-member view is legal and the driver must make it work, and the A740 tiled path cannot express a
view with another channel order - so 1630.2 MiB of the 1630.8 MiB residue is required linear and there is
no `0014` v3 to write; the remaining 0.65 MiB is linear because of image size (39.3). The no-list number
still worth measuring is the other side: the value of the 2450.3 MiB `0014` v1 already moved, queue 16.

## 39.1 The proposal, and the spec sentence that closes it

Proposal put forward on 21.11 (the "variant 1" of the no-list question): grant the tiled layout to the
`MUTABLE` images created **without** a format list that `0014` v1 left in linear, by splitting on the
*base format* — keep linear only the bases whose own swap is not `WZYX` (`!is_swapped_format(base)`),
tile the rest; and inside the 2-byte class single out `R8G8_*` so it stops sharing a class with
`R16_*`. The volume attached to it: 1630.8 MiB. Recomputed from the residue artifact (39.3) that volume
is 1023.5 MiB of 32-bit-class bases (624 creates), 606.7 MiB of 16-bit-class bases (347) and 0.65 MiB of
BC, 64-bit and 8-bit bases (53) that are linear for an image-size reason and have nothing to do with the
rule. Sums of the byte totals behind `results/nolist-residue-p14.log`, whose printed rows are each rounded
to 0.1 MiB.

The premise to check, asked for explicitly ("вроде в самом Vulkan такое запрещено… но перепроверить
стоит"): is the cross-member view forbidden by Vulkan? It is not. From the current Vulkan
specification, section *Format Compatibility Classes* (the chapter fetched 21.11 from
`https://docs.vulkan.org/spec/latest/chapters/formats.html`; not committed here, so treat it as
corroboration - the same grouping is committed in-tree, see the vk.xml table below):

> Uncompressed color formats are compatible with each other if they occupy the same number of bits per
> texel block as long as neither or both are alpha formats (e.g., `VK_FORMAT_A8_UNORM`).
> …
> In the following table, all the formats in the same row are compatible.

and the same page's *Size Compatibility* section, which is the half that matters for a view:

> Color formats with the same texel block size are considered size-compatible as long as neither or both
> are alpha formats (e.g., `VK_FORMAT_A8_UNORM`).

What is *not* quoted here: the VUID number for the view rule. The reference pages fetched on 21.11
(`docs.vulkan.org/refpages/latest/refpages/source/vkCreateImageView.html` and the `formats.html` chapter)
carry no validity-language identifiers, so a VUID id could not be re-read and none is asserted. What the
driver itself enforces is committed and readable, and it states the same assumption - `tu_formats.cc`
answers a missing format list with "the app may reinterpret to any compatible format"
(`tu6_format_list_has_swaps()`, `tu6_format_list_reinterprets_r8g8_r16()`, quoted in full in 39.6). That
is the rule our predicates implement, and it is the strict reading: the driver assumes the whole class is
in play, because the specification lets the application ask for any of it.

The classes are also in the tree the ship stack builds with, as the `class` attribute of the `<format>`
elements in `src/vulkan/registry/vk.xml` (line numbers at `6dfa32a`):

| format | line | class | blockSize |
|---|---|---|---|
| `VK_FORMAT_R8G8_UNORM` | 32866 | 16-bit | 2 |
| `VK_FORMAT_R16_UNORM` | 33172 | 16-bit | 2 |
| `VK_FORMAT_R8G8B8A8_UNORM` | 32968 | 32-bit | 4 |
| `VK_FORMAT_B8G8R8A8_UNORM` | 33014 | 32-bit | 4 |
| `VK_FORMAT_R32_UINT` | 33313 | 32-bit | 4 |
| `VK_FORMAT_R16G16_SFLOAT` | 33226 | 32-bit | 4 |
| `VK_FORMAT_B10G11R11_UFLOAT_PACK32` | 33432 | 32-bit | 4 |
| `VK_FORMAT_A2R10G10B10_UNORM_PACK32` | 33098 | 32-bit | 4 |
| `VK_FORMAT_A2B10G10R10_UNORM_PACK32` | 33134 | 32-bit | 4 |

So the set a no-list `MUTABLE` image may be viewed as **is the texel block**. The base format cannot
narrow it: an `R32_UINT` image may legally be viewed as `B8G8R8A8_UNORM`, and an `R8G8_UNORM` image as
`R16_UINT`. The split the proposal needs is not blocked by our predicates — it is blocked by the rule
those predicates implement. `0014` v1's own header describes the block grouping as "a superset of the
spec class"; for uncompressed colour it is the spec class, and the only difference is the alpha
exception in the quoted sentence, which in this workload is worth 3 creates and 0.0 MiB.

## 39.2 Why that makes linear mandatory on this chip, and what dropping v2 actually said

The hardware half, from the same tree:

```c
   /* It seems CCU ignores swap and always uses WZYX when tiled.  TP, on the
    * other hand, always respects swap.  We should return WZYX such that CCU
    * and TP agree each other.
    */
   if (tile_mode && !is_mutable)
      return WZYX;
```

(`fd6_pipe2swap()`, `src/freedreno/fdl/fd6_format_table.c:399-404`.) `is_mutable` is set true only in
the `mutable_ubwc_fc` branch of the create (`tu_image.cc:611`), and `mutable_ubwc_fc` is
`info->props.ubwc_all_formats_compatible` (`tu_image.cc:563`), which stays False for A740 (ADR-0001,
and the measured damage in `docs/a7xx-gen-props.md` row 23). So for our no-list images the flag
declared at `tu_image.cc:490` stays false and the tiled path returns `WZYX` for every format: **the
channel order of a reinterpreting view is not expressible in `TILE6_3` on this chip.** Upstream says the
same thing where the blitter deals with it, in the comment above `is_swapped_format()`
(`src/freedreno/vulkan/tu_clear_blit.cc:3424-3431`):

```
/* Tiled formats don't support swapping, which means that we can't support
 * formats that require a non-WZYX swap like B8G8R8A8 natively. Also, some
 * formats like B5G5R5A1 have a separate linear-only format when sampling.
 * Currently we fake support for tiled swapped formats and use the unswapped
 * format instead, but this means that reinterpreting copies to and from
 * swapped formats can't be performed correctly unless we can swizzle the
 * components by reinterpreting the other image as the "correct" swapped
 * format, i.e. only when the other image is linear.
 */
```

"we fake support for tiled swapped formats and use the unswapped format instead" is exactly what the
`XV` rows below measure: the fake is invisible to a same-order read and wrong to a reinterpreting one.

That last step is not only read in the source, it is printed by the game run. exp-14's inventory
(`experiments/exp-14-image-inventory.patch`) prints the create-path local `is_mutable` as the `mutable=`
field, and in `results/raw/game-patched-imginv5.log` the value is `0` in every one of them: `grep -c
'TU_IMG_INV.*mutable=1'` prints `0` against 4177 `TU_IMG_INV` lines, including the 3200 whose
`flags & 0x8` is set. Not one create in the game reached the `is_mutable = true` branch, so every
create in that run - tiled or not - was laid out under `fd6_pipe2swap(..., is_mutable = false)`.

Nor can the driver fall back on "the application will not ask": the view path has no format-compatibility
test anywhere in it. Turnip's `tu_image_view_init` (`tu_image.cc:168-185`) contains only
`assert(iview->vk.format != VK_FORMAT_UNDEFINED)` at `:185`, and the common code it calls first,
`vk_image_view_init` (`src/vulkan/runtime/vk_image.c:496`), sets `image_view->format =
pCreateInfo->format` at `:512` and falls back to the create format when it is `VK_FORMAT_UNDEFINED`
(`:513-514`) without consulting the compatibility classes. `tu_CreateImageView` (`tu_image.cc:1532`)
is the entry point. The only thing between a legal cross-member view and a wrong picture is therefore
the layout the create chose.

The measurement is the `XV` section of `tests/rp6-vkd3d-sparse-test.c`. Its counter semantics are read in
its source before its output is quoted - the AGENTS rule, learned from journal 22.1, and these counters are
the inverted kind: the three numbers on a `read through ... view` line are counts of words that are **wrong**
for each hypothesis, against the fill word unchanged (`bad_id`), against the first and third byte exchanged
(`bad_swap`), against the byte-reversed word (`bad_rev`) — `:1617-1627` — and the verdict line prints the
hypothesis that case expects, from the `swap` argument of its call site (`:1636-1643`). So `0/250000 raw`
means "every word came back exactly as written". The views are UINT (`R8G8B8A8_UINT` / `B8G8R8A8_UINT`,
call sites `:6488-6493`) so that no `[0,1]` decode sits between the memory and the answer.

The `0014` v2 build, `results/test-0014v2-matrix.log` lines 452-454 (the two rows of the other direction
are 456-458, and the same-format control is 449-451):

```
XV[RGBA8_as_BGRA8          ] 500x500 lin=0x000fa000 opt=0x00100000 sparse=SUCCESS -> layout tiled, rule says tiled OK
XV[RGBA8_as_BGRA8          ] read through 8x4-channel view: 0/250000 raw, 250000/250000 R<->B, 250000/250000 reversed
XV[RGBA8_as_BGRA8          ] wanted the first and third byte exchanged -> MISMATCH  (memory is raw: the view is ignored)
```

Those counts are identical to the control two rows above, `XV[RGBA8_as_RGBA8]` (a view of the base format
itself, `0/250000 raw`, verdict OK): the `B8G8R8A8_UINT` view of an `R8G8B8A8_UINT` image answers exactly
like a view that changes nothing. The other direction is the mirror image - over a B-order base the tiled
read returns the exchanged word where the probe expects the raw one:

```
XV[BGRA8_as_RGBA8          ] 500x500 lin=0x000fa000 opt=0x00100000 sparse=SUCCESS -> layout tiled, rule says tiled OK
XV[BGRA8_as_RGBA8          ] read through 8x4-channel view: 250000/250000 raw, 0/250000 R<->B, 250000/250000 reversed
XV[BGRA8_as_RGBA8          ] wanted the raw words -> MISMATCH  (memory is swapped)
```

and the same two shapes on the shipped stack (`results/test-p14-base.log` lines 443-445 and 446-448), where
both answers are right precisely because the image is linear:

```
XV[RGBA8_as_BGRA8          ] 500x500 lin=0x000fa000 opt=0x000fa000 sparse=FEATURE_NOT_PRESENT -> layout linear, rule says tiled UNEXPECTED
XV[RGBA8_as_BGRA8          ] read through 8x4-channel view: 250000/250000 raw, 0/250000 R<->B, 250000/250000 reversed
XV[RGBA8_as_BGRA8          ] wanted the first and third byte exchanged -> OK
XV[BGRA8_as_RGBA8          ] ... wanted the raw words -> OK            (line 448, layout line 446)
```

So linear serves the cross-member view in both directions and tiled answers with the order of the memory
rather than the order of the view. The third member of that class, the order-free `R32_UINT` view, is
undamaged on the tiled build (`XV[RGBA8_as_R32] ... wanted the raw words -> OK`, v2 log line 459): the
breakage is exactly the channel order, which is what `fd6_pipe2swap()` cannot express in `TILE6_3`.

That is the whole reason `patches/DROPPED.md` keeps v2: not that Vulkan forbids the cast — it requires it
to work — but that v2 answered a view the application is entitled to make with the memory's order, 250000
of 250000 words wrong for the view, while the 94-check matrix still printed EXACT.

The 2-byte half is the same argument with geometry instead of order: `R8G8` and `R16` are one class (vk.xml rows above), and upstream's own
rule for the pair is the comment above `image_is_r8g8()`
(`src/freedreno/vulkan/tu_clear_blit.cc:3443-3452`):

```
/* R8G8_* formats have a different tiling layout than other cpp=2 formats, and
 * therefore R8G8 images can't be reinterpreted as non-R8G8 images (and vice
 * versa). This should mirror the logic in fdl6_layout.
 */
```

with `is_swapped_format()` at `:3434-3441` the code that compares the linear and the tiled encoding of
one format and finds them different (journal 22, ADR-0007).

## 39.3 The residue counted, and closed without a build

New artifact [`../results/nolist-residue-p14.log`](../results/nolist-residue-p14.log), regenerate with
`python3 scripts/nolist-residue.py results/raw/game-patched-imginv5.log` (the p14-stack inventory, so
this is the residue *after* v1):

| | creates | MiB |
|---|---|---|
| `MUTABLE` with no list | 2474 | 4081.1 |
| tiled by `0014` v1 | 1450 | 2450.3 |
| linear residue | 1024 | **1630.8** |

The residue carries `SAMPLED` in 1630.8 MiB of 1630.8 and `STORAGE` in 1012.1 — it is a TP-side pile,
and TP is the client that owns the memory wall (12.0 GB/s of 14.8, 81 % of DRAM reads, in
`results/games/re4/mesa27-vertex/steady-state.txt`). That is the only reason it looked interesting, and it
still is the right client. It does not matter, because of 39.1:

- 32-bit-class bases — `R11G11B10_FLOAT` 374.7, `R32_UINT` 358.4, `R32_FLOAT` 79.0, `R8G8B8A8_SNORM`
  67.9, `R16G16_FLOAT` 62.7, `R8G8B8A8_SRGB` 45.9, `R8G8B8A8_UNORM` 32.0, `R10G10B10A2_UNORM` 3.0
  (1023.6 MiB) — every one of them sits in a set that contains a B-order member (`B8G8R8A8_*`,
  `B10G11R11_UFLOAT_PACK32`, `A2B10G10R10_*`), so the tiled layout cannot express a legal view.
  Mandatory linear. (`PIPE_FORMAT_R11G11B10_FLOAT` is itself the B-order spelling:
  `VK_FORMAT_B10G11R11_UFLOAT_PACK32` is the only Vulkan format that maps to it.)
- 16-bit-class bases — `R8G8_UNORM` 587.2, `R16_UNORM` 12.4, `R16_FLOAT` 7.1, `R16_SNORM` 0.1 (606.8
  MiB) — one class, two different tiled addressings. Mandatory linear.
- everything else in the residue (BC and 64-bit rows, 0.5 MiB total) is already tiled by v1 wherever the
  class is homogeneous.

So there is no v3 predicate to write: the grant the proposal wants is a spec violation, not a
conservatism. To tile those bytes one would have to change how the A740 tiled path expresses a
reinterpreted view — and on this chip the other half of that is the UBWC metadata reinterpretation the
A740 does not have (ADR-0009). That is an upstream-sized change, not a branch patch.

Correction, same day, about the third bullet. "Everything else in the residue (BC and 64-bit rows, 0.5
MiB total) is already tiled by v1 wherever the class is homogeneous" is wrong in its first half: those
rows are in the residue, i.e. `0014` v1 did **not** tile them. Re-counted from the same log, the residue
splits as 971 creates / **1630.2 MiB** of 16-bit- and 32-bit-class bases (the class-required linear
bytes above) and 53 creates / **0.65 MiB** of BC, 64-bit and 8-bit bases whose class
`scripts/class-order-check.py` reports homogeneous - so at first sight v1's rule left 0.65 MiB it should,
by its own logic, have tiled. It is not a rule question at all. All 53 are in the `small` column of
`results/nolist-residue-p14.log`: level 0 below the driver's own width fallback, `fd6_layout.c:155-161`

```c
   if (!params->force_ubwc &&
       layout->width0 < layout->linear_fallback_threshold_texels) {
      layout->ubwc = false;
      /* Linear D/S is not supported by HW. */
      if (!util_format_is_depth_or_stencil(params->format))
         layout->tile_mode = TILE6_LINEAR;
   }
```

with the threshold `16 * blockwidth` on a7xx (`FDL_LINEAR_FALLBACK_THRESHOLD` = 16 at
`freedreno_layout.h:251`, scaled at `:254-261` by `supports_linear_mipmap_threshold_in_blocks`, which
`a7xx_base` sets True at `freedreno_devices.py:785`). The log shows each of those formats on both sides
of its threshold:

```
TU_IMG_INV fmt=PIPE_FORMAT_R16G16B16A16_FLOAT ... 8x8x8 ...     tile=linear ... size=32768   (8 < 16)
TU_IMG_INV fmt=PIPE_FORMAT_R16G16B16A16_FLOAT ... 32x32x16 ...  tile=tiled  ... size=262144  (32 >= 16)
TU_IMG_INV fmt=PIPE_FORMAT_RGTC1_UNORM       ... 32x32x32 ...   tile=linear ... size=131072  (32 < 16*4)
TU_IMG_INV fmt=PIPE_FORMAT_RGTC1_UNORM       ... 256x256x1 ...  tile=tiled  ... size=32768   (256 >= 16*4)
```

(`results/raw/game-patched-imginv5.log` lines 260, 242, 364, 1071.) 84 of the 1024 residue creates,
0.9 MiB, are `small` by that rule; the other 31 of them are class-required linear as well. So the
residue is fully accounted for - 1630.2 MiB by the class rule, 0.65 MiB by image size - and no part of it
is a gap in `0014` v1's predicate.

## 39.4 What is still unmeasured, and it is a different number

`0014` v1 moved 2450.3 MiB of no-list images into tiled, and that has never been measured for traffic
or fps: journal 21.12 says so in its own text ("fps is not what this run measures - the inventory
is"), and the 17.11 fdperf runs predate `0014` (entries 21.11 and 21.12 are both dated 18.11), which
makes `results/games/re4/mesa27-vertex/steady-state.txt` a baseline taken with *everything* in linear. The
A/B needs no new patch, only a build of the ship stack without `0014`, same scene, compared by the
per-client ratios journal 38 allows (TP GB/s, starve), not by levels. Queue 16 - and it starts with the
revert problem of 39.7, because the committed patch file does not revert the tree.

## 39.5 Corrections, kept visible

- Analysis earlier the same day claimed the `R11G11B10`/`R32_*`/`R16G16_*` part of the residue was "not
  refuted" because those formats have no swapped sibling. That wording must not be reused, and the
  conclusion with it: `PIPE_FORMAT_R11G11B10_FLOAT` *is* the B-order format
  (`VK_FORMAT_B10G11R11_UFLOAT_PACK32`, vk.xml:33432, class 32-bit), and the set of `R32_UINT` contains
  `B8G8R8A8_UNORM` (33014). The error came from grouping by component layout instead of by the spec's
  bits-per-texel-block rule.
- The proposal's premise that Vulkan forbids the cross-member cast is the opposite of 39.1. Recorded
  because it is the second time this shape has been re-derived in one day, and the short answer is worth
  having in one line: *the class is the texel block, the view is legal, the A740 tiled path cannot
  express it, therefore linear.*
- The comment in the shipped `patches/0014-*.patch` calling the block grouping "a superset of the spec
  class" is imprecise in the safe direction and omits the alpha exception of the quoted rule. It is
  left untouched: `0014` belongs to the p14 release, and rewording a shipped patch moves the artifact.
  The precise wording belongs in an upstream submission of this change.
- A first draft of 39.1 quoted the view rule by VUID (`VUID-VkImageViewCreateInfo-image-01761`) and
  quoted a second spec sentence about texel-to-memory mapping. Both are removed, not corrected: the pages
  fetched on 21.11 contain no VUID numbers and no such sentence, so neither could be re-read, and this
  repository does not quote what it cannot point at. The claim they were carried for is made in 39.1 by
  the driver's own code instead, which is committed and readable.

## 39.6 The class check, offline and re-runnable

`scripts/class-order-check.py` (new with this entry) answers the question for any base format without a
build, by putting the driver's own predicates onto the class instead of onto the base. It reads two
tables, both already in this repository's inputs: `tests/vk-fmt-classes.json` (`scripts/gen-vk-fmt-classes.py`
over vk.xml `@f7de774cace1` and Mesa's `vk_format.c` at `6dfa32a`) and the swap column of
`src/freedreno/fdl/fd6_format_table.c`. Reproduce with `python3 scripts/class-order-check.py`.

The predicates it reproduces are stock code, and their comments are the driver's own statement of the
rule that 39.1 quotes from the specification - `src/freedreno/vulkan/tu_formats.cc:115-149`:

```c
tu6_format_list_has_swaps(const VkImageFormatListCreateInfo *fmt_list)
{
   /* If there's no format list, then the app may reinterpret to any compatible
    * format, and presumably one would have the swap set.
    */
   if (!fmt_list || !fmt_list->viewFormatCount)
      return true;
...
tu6_format_list_reinterprets_r8g8_r16(...)
   /* If there's no format list, then the app may reinterpret to any compatible
    * format.
    */
   if (!fmt_list || !fmt_list->viewFormatCount)
      return true;
```

Stock, a no-list `MUTABLE` image is therefore answered with the worst case of its whole class, which is
why it is linear. What `0014` v1 does is replace that `NULL` with the enumerated class
(`tu6_mutable_compat_class()`) and let the same predicates speak - the patch header says so in its own
words ("the grouping is the texel block ... what is left inside the block class is the channel order,
and that is exactly what `tu6_format_list_has_swaps()` and `tu6_format_list_swaps_are_uniform()` already
compare"). 39.6 is the offline version of that argument, so the claim can be re-checked without a build.

Output for the classes that matter, from that script (members counted are those with a pipe format, i.e.
a view Turnip can build):

| class | members | swap-diff from a WZYX base | not-R8G8 in a 2-byte base | verdict |
|---|---|---|---|---|
| 8-bit | 7 | 0 | - | class homogeneous - tiled |
| 64-bit | 13 | 0 | - | class homogeneous - tiled |
| 32-bit | 45 | 13 | - | linear required |
| 16-bit | 21 | 6 | 14 | linear required |

which is the same per-class answer the shipped patch published from the probe matrix (8-bit tiled,
8-byte tiled, block-compressed tiled, 4-byte linear, 2-byte linear) - reached now from the class table
instead of from 94 probe checks. The 13 offending members of the 32-bit class are all `WXYZ`: six
`A2R10G10B10_*` and seven `B8G8R8A8_*`. The 16-bit class has six non-`WZYX` members, two each of `WXYZ`
(`A1R5G5B5_UNORM_PACK16`, `R5G6B5_UNORM_PACK16`), `ZYXW` (`B4G4R4A4_UNORM_PACK16`,
`B5G5R5A1_UNORM_PACK16`) and `XYZW` (`R4G4B4A4_UNORM_PACK16`, `R5G5B5A1_UNORM_PACK16`), and on top of
that the 14 members that are not `tu_is_r8g8`, which is the second complaint.

One detail worth having recorded, because it is the exception in the quoted spec sentence: vk.xml encodes
the alpha rule in the `class` attribute itself - `VK_FORMAT_A8_UNORM` is `class="8-bit alpha"`
(`src/vulkan/registry/vk.xml:32838`), alone in its class, not merged with `8-bit`. So the generated table
needs no hand-written alpha rule, and the "superset" wording of 0014's header is smaller than it sounds:
for uncompressed colour the generated grouping *is* the spec class.

What this section does not show: it is arithmetic over tables, not a measurement. Only the order case has
a pixel count behind it (39.2's `XV` rows). The 2-byte `r8g8-r16` column is the driver's rule plus ADR-0007's
layout finding; a content read of an `R16` view of a tiled `R8G8` image has still never been done, and
the probe's guard for that pair prints `content not judged` (`results/test-p14-base.log` line 453).

## 39.7 The committed `0014` patch file does not revert the tree it is supposed to describe

Found while pre-registering the A/B of 39.4 (queue 16), which was going to start with one revert. Measured
on 21.11 with the working directory `../mesa27-src`, in the recorded ship-stack state (8 files, +663/-80),
by running `git apply -R --check` on `patches/0014-turnip-mutable-no-list-tiling.patch` named relative to
that directory. Output verbatim:

```
error: patch failed: src/freedreno/vulkan/tu_image.cc:552
error: src/freedreno/vulkan/tu_image.cc: patch does not apply
error: patch failed: src/freedreno/vulkan/tu_formats.h:34
error: src/freedreno/vulkan/tu_formats.h: patch does not apply
error: patch failed: src/freedreno/vulkan/tu_formats.cc:261
error: src/freedreno/vulkan/tu_formats.cc: patch does not apply
```

and the same failure with the two ways out of a fuzz problem:

```
$ git apply -R -3 --check ...
error: src/freedreno/vulkan/tu_image.cc: does not match index      (the shallow clone has no blobs)
error: src/freedreno/vulkan/tu_formats.h: does not match index
error: src/freedreno/vulkan/tu_formats.cc: does not match index

$ git apply -R --recount --ignore-space-change --check ...
error: patch failed: src/freedreno/vulkan/tu_formats.cc:261
error: src/freedreno/vulkan/tu_formats.cc: patch does not apply
```

So it is not fuzz: the two texts differ. The class-building function is named
`tu6_mutable_compat_class()` in the patch file (lines 151, 221, 273, 296 of
`patches/0014-turnip-mutable-no-list-tiling.patch`), while the tree has it as a static
`mutable_compat_class()` at `tu_formats.cc:290`, together with a wrapper `mutable_views()` at `:351` that
the patch file does not contain and that `tu6_mutable_format_list_forces_linear()` calls at `:409`. The
comments differ too, same meaning, different words - second line of that block, and the block is 26 lines
in the patch file against 25 in the tree (264-288):

```
patch file :  * VkImageFormatListCreateInfo may be viewed as: every color format with the
tree       :  * VkImageFormatListCreateInfo may still be viewed as: every color format with
```

File dates: the patch file is 19.11 22:00 and last committed as `96796f7`
("0014: back to the class form that was built and measured; block rule dropped", 20.11);
`tu_formats.cc` is dated 21.11 02:31 and `tu_image.cc` 21.11 13:13, both from apply/revert cycles of this
week's experiments.

What is *not* settled, and it is a real question about the artifacts: which of the two texts produced the
shipped `c17d02bcaae9…` build. `docs/release.md` records hashes of builds and of patch files, and the
commit message of `96796f7` claims the patch file is "the class form that was built and measured", but
nothing in this repository compares that file against the tree. The difference is in names and comments,
which cannot change a result - so no conclusion of 39.1-39.6 depends on it.

What it costs is queue 16's first step, and the cheap way is gone. Two routes, and queue 16 now says
which to take: rebuild in a copy of the tree (`cp -a ../mesa27-src ../mesa27-src-no0014`, 370 MB, 23 GB
free) and delete `0014`'s three pieces there, or make one disabling edit in the copy - in `mutable_views()`
(`tu_formats.cc:351`) return the caller's own `fmt_list` unchanged, i.e. put the `NULL` back, which is
exactly the state the stock predicates were written for. Either way the build is accepted only if exp-14's
inventory prints the pre-`0014` signature: `MUTABLE` with `listn=0` and 0 MiB tiled, the imginv4 row of
`results/imginv-3variants.txt`. Never the `.so` hash, which identifies nothing (journal 24.3).
