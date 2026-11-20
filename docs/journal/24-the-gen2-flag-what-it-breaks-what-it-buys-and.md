# 24. The gen2 flag: what it breaks, what it buys, and what it frees (19.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

Three separate questions, three builds. The prop in all of them is
`ubwc_all_formats_compatible` on `a7xx_gen2`.

### 24.1 What it buys in this workload: nothing

Both inventories broken down by the `list=` field and by
`VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT` (`flags & 0x8`):
`results/raw/game-patched-imginv4.log` (base, before 0014) and
`.../game-patched-imginv5.log` (with 0014).

| fact | inv4, 3639 creates | inv5, 4177 creates |
|---|---|---|
| `MUTABLE_FORMAT` | 2671 / 4559 MiB | 3201 / 4847 MiB |
| of those without a list | 1983 / 3801 MiB | 2475 / 4081 MiB |
| lists containing both an RGB- and a BGR-order format | **0 / 0 MiB** | **0 / 0 MiB** |
| distinct formats inside lists | 20, all RGB-first or single-channel | same |
| BGR-like formats inside lists | **none** | **none** |
| bases with BGR order | 12 x `B8G8R8A8_UNORM`, all **without** `MUTABLE_FORMAT`, already `tiled` + `ubwc=1` | 12, same |
| lists with `R8G8*` next to `R16*` (2 bpp, layout conflict) | **0** | **0** |
| lists: `tiled` + UBWC | 634 / 703 MiB | 632 / 696 MiB |
| lists: `tiled` without UBWC | 54 / 55 MiB | 76 / 70 MiB |

All four regressions the flag causes (`S3 PASS->FAIL`,
`U[B8G8R8A8_UAVLIST] EXACT->MISMATCH`, `XV[BGRA8_as_RGBA8] OK->MISMATCH`, EXACT
94->93; `results/test-p14-base.log` against `results/test-p14-ubwc-allformats.log`)
are one and the same case: a list whose byte order differs from the base. The game
creates **zero** such images. The benefit has the same origin and is also zero: the
UBWC the flag adds goes to `R8G8` <-> `R16` lists (probe `UBR`, the same `+8192` for
metadata), and the game creates zero of those. So on this workload the flag moves
nothing, and there is nothing to fix in it for RE4. One caveat, exactly one:
"does not occur in the game" is not an argument to turn the prop on; it is an
argument not to spend the queue on it.

(20.11: 24.4 narrows this. "Zero mixed-order lists" is a statement about the view-format
list only. A `MUTABLE_FORMAT` image with an empty list can be reinterpreted with no list
at all, so the sentence above does not exclude the broken shape in the no-list classes.)

Consequence for the plan: **0015 (MUTABLEEN on gen2) is withdrawn as a game fix**.
Without a reproduced form that carries volume it can neither be turned on by a
criterion (`XV` 4/4 on something the game never creates) nor checked in game. It
stays only as an upstream-shaped change for an application that does create
`{BGRA8, RGBA8}` lists, and there is no such application here.

What remains as a lever by volume is the same no-list branch, and 0014 exposed its
second half: after 0014 there are 1450 creates / 2450 MiB **`tiled` but `ubwc=0`**
and 1024 creates / 1631 MiB still `linear`. 0014 returned the tiling, not the UBWC,
because `format_list_ubwc_possible()` answers `false` for an empty list with the
upstream TODO "limit based on compatiblity class" (`tu_image.cc:448-453`). The next
candidate is to close exactly that TODO, with one correction: UBWC needs the
**strict Vulkan compatibility class** of the base (there `R16_UNORM` over
`R8G8_UNORM` is forbidden), not the texel-block class of 0014, which answers a
question about layout. A small separate debt is visible in the same tables: 55-70
MiB of lists without UBWC are the single-channel 8-bit families
(`R8_UINT`/`R8_UNORM` with `SINT`/`SNORM` inside) - another hole in
`fd6_ubwc_compat_mode()`.

### 24.2 The prop in the properties table behaves exactly like the env override

One line, `ubwc_all_formats_compatible = True` in the `a7xx_gen2` block
(`freedreno_devices.py`), stack `0001..0014` v1 as shipped, build `.so
5e99409774838be5`. Matrix `results/test-gen2flag-table.log`: EXACT 93 and exactly
the three regressions of the environment measurement. The only difference from
`results/test-p14-ubwc-allformats.log` is the junk texel row `V[BGR+R32]`
(`18038001` against `18ff8001`), where the probe is `DIVERGED 262144/262144` in
both runs anyway. So the table edit and `TU_FORCE_PROPS` give the same behaviour,
and 0007 remains the only way to measure a prop without a rebuild.

### 24.3 What it frees: nothing, and the code reading said the opposite

The prop is read in four places (`tu_formats.cc:397`, `tu_image.cc:582`,
`tu_device.cc:499`, `:898`), and reading the code one would expect it to make five
patches redundant: `0005` and `0010` (their predicates sit below line 397 and are
not computed when the prop is set) and `0006`/`0011`/`0012` (their
`fd6_ubwc_compat_mode()` is called only from
`tu6_mutable_format_list_ubwc_compatible()`, which `mutable_ubwc_fc` at
`tu_image.cc:582` overrides).

Measured the opposite. Stack without `0005`, `0006`, `0010`, `0011`, `0012` and
without `0014` (`0014` cannot be applied to the reduced stack: its context at
`tu_formats.cc:261` *is* the removed predicates), `.so c60dfb26`, matrix
`results/test-gen2flag-minstack.log`: EXACT 92 and two new FAILs against the full
stack.

| probe | full stack + flag | reduced stack + flag | whose patch |
|---|---|---|---|
| `S` - uniform-swap BGRA+UINT, tiled+sparse | PASS | FAIL, 16384/16384: reads `0x000000a5` where `0x00a50000` is expected | `0005`/`0010` |
| `T` - UBWC+tiled, UINT/UNORM round trip | PASS | FAIL, 261120/262144, same byte-swap signature | `0011`/`0012` |

So the prop is not a superset of the patches, it is lost information. `S` breaks
because a uniform-swap layout must also be *read* correctly (that is 0005); `T`
breaks because the UBWC compatibility mode is part of the resource's layout, not an
on/off switch, and `mutable_ubwc_fc` does not compute it. Isolating `0006` in its
own build: NOT MEASURED, it was in this build together with the other four.

**Verdict: the list of removable patches is empty.** The only thing removed from the
tree is `0014` v2 (the direct block rule) - it was built, and it breaks
`RGBA8->BGRA8`/`BGRA8->RGBA8` on the tiled non-mutable path
(`results/test-0014v2-matrix.log`: `XV[RGBA8_as_BGRA8] -> MISMATCH (memory is raw:
the view is ignored)` and `XV[BGRA8_as_RGBA8] -> MISMATCH (memory is swapped)`) at
EXACT 94 - the matrix counter does not see this breakage, only the `XV` rows do. The
file lives in `patches/dropped/`, verdicts for all candidates in
`patches/DROPPED.md`.

The prop itself does not enter the table: three matrix regressions, zero benefit on
this workload, zero patches freed (see 24.1, 24.3).

**Tree restored** after the experiment (`git apply -R` of what was taken out, then
`0003..0014` in order), `.so 4c3cdb21`; `results/test-restore-shipstack.log` matches
`results/test-p14-base.log` line for line, EXACT 94. The hash is *not* equal to the
ship `c17d02bcaae9a960…`: rebuilding the same stack is not bit-for-bit, so stack
identity is proven by the matrix, not by the hash - the same lesson as
`MESA_GIT_SHA1` (see `docs/release.md`, build identification).

**Incident, and the rule it earned.** During the revert one `git checkout
src/freedreno/common/freedreno_devices.py` erased, together with the flag edit, the
`0008` hunk in the same file (`0008` touches only that file). Nothing was lost only
because the file belongs to one patch and was re-applied; for a file touched by
several patches the same command would have destroyed part of the stack with no way
back from the index. Revert with `git apply -R` and explicit paths, literally (the
rule is in `AGENTS.md`).

### 24.4 24.1's "the game never creates that shape" is narrower than it reads (20.11)

Added after the operator asked whether the broken class is reachable at all, and
whether another prop covers it. Counted again from the committed inventories
(`results/raw/game-patched-imginv5.log`, ship stack with `0014`;
`results/raw/game-patched-stockflaginv.log`, stock + the prop) and from the committed
compatibility-class table `tests/vk-fmt-classes.json`.

A `MUTABLE_FORMAT` image with an empty list needs no list to be reinterpreted: with
`viewFormatCount == 0` Vulkan allows every format of the base's texel compatibility
class, and the committed table says that class holds both byte orders and several
other types at once - `classes["32-bit"]` has 52 members including `B8G8R8A8_UNORM`,
`R8G8B8A8_UNORM`, `R8G8B8A8_SNORM`, `R32_UINT`, `R16G16_SFLOAT`, `B10G11R11_UFLOAT`
(generated by `scripts/gen-vk-fmt-classes.py` from vk.xml `KhronosGroup/Vulkan-Docs
@f7de774cace1` and `vk_format.c` mesa `6dfa32a`). So "zero lists mixing byte orders"
does not exclude a cross-order view: it only excludes the case where the cast is
visible in the `list=` field. 24.1's one caveat was about the wrong field.

| population (imginv5) | creates | MiB | today, ship + `0014` | under the prop |
|---|---|---|---|---|
| `MUTABLE_FORMAT`, no list | 2474 | 4081.1 | 1450 / 2450.3 tiled | 2367 / 4071.2 tiled |
| - in the 32-bit class | - | 1023.5 | 0 % tiled (`0014` refuses it) | ~100 % tiled |
| - in the 16-bit class | - | 606.7 | 0 % tiled (`0014` refuses it) | 99.9 % tiled |
| - of those, base in an 8x4 order | 180 | 145.8 | linear | tiled, `ubwc=0` |
| lists mixing an RGB- and a BGR-order format | 0 | 0 | - | - |
| `B8G8R8A8_*` bases | 12 | 77.3 | tiled + `ubwc=1`, **no** `MUTABLE_FORMAT` | cannot be re-viewed: a non-mutable image's view format must equal its format |

The two rows that matter are the refused classes: 1630.2 MiB of the game's images are
`tiled` under the prop and `linear` today, and that is the whole difference between
79.8 % and 100 % tiling - while `ubwc` in the no-list class stays `0` in both runs
(`results/imginv-3variants.txt`, the `u` column). The prop therefore moves 1630 MiB of
this workload onto the layout whose cross-order behaviour the matrix reports as wrong
(`S3`, `U[B8G8R8A8_UAVLIST]`, `XV[BGRA8_as_RGBA8]`), and returns no compression for it.

**NOT MEASURED, and this is the only open point of the direction:** whether vkd3d
actually creates a view whose format differs from the base within one class on any of
those images. Nothing has ever seen the answer - the inventory hook logs
`vkCreateImage`, not `vkCreateImageView` (`experiments/exp-14-image-inventory.patch`),
so the game's casts are outside every artifact in this repository. The measurement is
one hook line in the view path, one rebuild, one 150 s run, and the number to report is
`views where the format is in the base's class but is not the base`, split by whether
the byte order or the class of the type changes. If it is zero, 24.1 becomes a complete
argument for this game, not a half one, and that is the strongest support ADR-0001 can
get here. If it is not zero, the prop is unsafe on a shape that carries volume, and
ADR-0001 stands for a second, better reason. Queue: `exp-20` in
[`docs/plan-next-checks.md`](../plan-next-checks.md).

What the prop does *not* need a measurement for, stated here because it is what it is
usually asked for: it opens the 12_0 gate by itself - upstream's own line is
`sparseResidencyImage2D = has_sparse_prr && props.ubwc_all_formats_compatible`
(quoted in the header of `0004`, `tu_device.cc:491`) - and it frees no patch
(journal 24.3), so the choice was never "the prop or the stack", it is "the prop
instead of `0004`'s first hunk, plus 1630 MiB re-laid out". No prop covers the
breakage: the run above is the **full** ship stack with `0014` in it
(`results/test-p14-ubwc-allformats.log`), so there is nothing left in the stack that
suppresses it, and the other two UBWC props on gen2 are `ubwc_coherency_quirk`, which
has no case on gen2 (journal 23), and `ubwc_unorm_snorm_int_compatible`, which upstream
already sets `True` for gen2 and which is what supplies 539 of the 767 MiB of UBWC the
game's lists already have (`patches/DROPPED.md`).
