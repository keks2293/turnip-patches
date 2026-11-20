# 31. The 64-bit class has a UBWC ceiling, and the missing UBWC of a no-list image is upstream's, not ours (20.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md).

**Question.** Queue 1 (`exp-18`) named two facts that had to be measured before its rule is
written, both left open by journal 28: whether a UBWC metadata plane is allocated for the
64-bit class at all, and what becomes of `R32G32_FLOAT`, which there is described as having
"no compat mode at all". While the probe was being written a third question became the
important one: when a `VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT` image is created with no
`VkImageFormatListCreateInfo`, is the absent UBWC something this repository's stack takes
away, or something Mesa 27 already refuses? RE4 holds 4073.0 MiB of exactly that class
(journal 28), so the answer decides whether `exp-18` grants a new permission or reverses an
upstream default.

**Method.** `probe_ubwc_ceiling()` in `tests/rp6-vkd3d-sparse-test.c` creates one more
image: `MUTABLE_FORMAT` with `pNext == NULL`. Nothing else about the probe changes - still
`vkGetImageMemoryRequirements` only, no fill and no read, still 512x512, so the columns
journal 21.6.2 defined keep their meaning and position and `nolist=` is appended:

| column | the image it measures | what a rise over `lin` means |
|---|---|---|
| `lin` | `VK_IMAGE_TILING_LINEAR` | the reference |
| `nonmut` | `OPTIMAL`, no `MUTABLE_FORMAT` | the format has a ceiling: the driver allocated a metadata plane |
| `list` | `OPTIMAL + MUTABLE` with the listed formats | whether the compat gate removed that ceiling |
| `nolist` | `OPTIMAL + MUTABLE`, no `VkImageFormatListCreateInfo` | whether a list-less image reaches the ceiling - the `exp-18` target |

Five rows were added: the four formats journal 28 counts as the game's no-list 64-bit volume
(`R16G16B16A16_FLOAT` 312 creates, `_UNORM` 146, `_SNORM` 56, `R32G32_FLOAT` 22) plus the
five-member typeless list vkd3d builds for a 64-bit resource. The queue had suggested
500x500 for this; the probe's own 512x512 was kept, because a size change would have broken
comparability with the existing rows for no benefit to the question.

```sh
# build in the container; the dnf step is now skipped when the image already has
# the toolchain (the Fedora mirror metadata failed on this run) - see the note in
# scripts/build-test.sh. It reproduces the binary the three runs below used.
podman run --rm -v "$REPO/tests":/work:Z -v "$WORK":/out:Z -v "$REPO":/repo:Z \
    localhost/mesa-build-fedora44-wsi-glslang-vulkan bash /repo/scripts/build-test.sh

# three drivers, one binary: sha256 63848afdba52bfa0...
source scripts/env.sh
scripts/run-test.sh build/p14-shipped/freedreno_icd_p14.json            results/raw/ceil-nolist-p14-full.log
scripts/run-test.sh build/out-stock-inv/freedreno_icd_stock_inv.json     results/raw/ceil-nolist-mesa27base-full.log
scripts/run-test.sh ""                                                   results/raw/ceil-nolist-mesa26system-full.log
```

| driver | build identity |
|---|---|
| the shipped stack | `build/p14-shipped/libvulkan_freedreno.so`, `c17d02bcaae9a960…` (`0001..0014`) |
| the bare Mesa 27 base | `build/out-stock-inv/libvulkan_freedreno.so`, `23ccf659c90d3ddf…` (base `6dfa32a85f91` + `exp-14`, no patches, no prop) - built for journal 27 and never run until this entry |
| the system driver | `/usr/lib64/libvulkan_freedreno.so`, package `mesa-vulkan-drivers-26.2.6-1.fc44.armada` - a different, downstream branch |

Logs: `results/test-CEIL-nolist-p14.log`, `results/test-CEIL-nolist-mesa27base.log`,
`results/test-CEIL-nolist-mesa26system.log` (each is the `CEIL[` grep of the named full run,
with the tool and build hashes in its header).

## The 64-bit class has a ceiling, and a plain image reaches it

All four new rows agree on both Mesa 27 builds and on the system driver:
`lin=0x00200000`, `nonmut=0x00200000+0x2000`. At 8 B/texel the extra `0x2000` is the
metadata plane, the same signature journal 21.7 established for the 16-bit and 32-bit
classes. So the answer to journal 28's first fact is yes: a 64-bit image that is not
`MUTABLE` gets UBWC allocated, `R16G16B16A16_FLOAT` and `R32G32_FLOAT` included. That is an
allocation by the driver, not a statement that the chip compressed anything (journal 22.2).

## No no-list image reaches the ceiling, and this stack is not what stops it

Ten of the seventeen rows have a ceiling. Of those ten, none reaches it as `nolist` - on any
of the three drivers. And comparing the bare base with the shipped stack row by row:

| column | rows where base and the shipped stack differ |
|---|---|
| `lin` | none |
| `nonmut` | none |
| `nolist` | **none** |
| `list` | 5: `R16_TYPELESS`, `R16_UINT`, `R10G10B10A2_TYPELESS`, `R16G16B16A16_TYPELESS`, `R32G32_TYPELESS` |

The stack therefore changes nothing for an image the application does not mark `MUTABLE`, and
nothing for a `MUTABLE` image without a list. The refusal is upstream, in two places that
both answer `false` to "no list": `format_list_ubwc_possible()` (`tu_image.cc`) and
`tu6_mutable_format_list_ubwc_compatible()` (`tu_formats.cc`). Both bodies are identical to
refs `mesa-26.2.6` and `main` (diffed against
`https://gitlab.freedesktop.org/mesa/mesa/-/raw/<ref>/src/freedreno/vulkan/tu_formats.cc`
and `.../tu_image.cc` on 20.11 - an outside source, not committed in this repository), and
`main` still carries the comment above that line: `TODO: limit based on compatiblity class`.
The TODO that `exp-18` would implement is still open upstream.

## The five differing `list` rows are 0011 and 0012, measured against the real base

On the bare base those five rows read `GATE REMOVED` (`list == lin` although a ceiling
exists); on the shipped stack all five read `gate is not in the way` (`list == nonmut`). The
three first-named are the `0011` recoveries journal 21.6.2 recorded; the two 64-bit ones are
the answer to journal 28's second fact: `R32G32_FLOAT` and `R16G16B16A16_FLOAT` have compat
modes in the shipped stack because `0012` added `PIPE_FORMAT_R32G32_FLOAT →
FD6_UBWC_R32G32_INT` and `PIPE_FORMAT_R16G16B16A16_FLOAT → FD6_UBWC_R16G16B16A16_INT`. On
the base they have none, and their classes lose UBWC. This is the first time that claim is
measured against the Mesa 27 base rather than against the working stack of the day.

## Three corrections

1. journal 28 wrote, of `R16G16B16A16_FLOAT`, that "the name is not found by grep in
   `tu_formats.cc`, so the mapping is in the generated header". There is no generated header
   to look in. UBWC is a layout flag (`image->layout[0].ubwc`, passed to
   `fdl6_layout_image()` as `.ubwc`), and the only per-format gate is `fd6_ubwc_compat_mode()`
   in `src/freedreno/common/freedreno_ubwc.h`, which has exactly two consumers:
   `tu_formats.cc:71` and gallium's `fd6_resource.cc:154-158`. The layout code never consults
   the compat table - which is why `nonmut` shows a ceiling for a format the table calls
   `FD6_UBWC_UNKNOWN_COMPAT`.
2. The controls journal 21.6.2 compared were the system driver (Mesa 26) and the working
   stack; it said itself that comparing the system stock with `0011` "wouldn't do for this".
   This entry adds the control it was missing: the same probe on `23ccf659c90d…`, the bare
   Mesa 27 base.
3. A prediction of mine, written into the probe's comment before the run and corrected in
   that comment afterwards: `R16G16B16A16_SNORM` was meant to be the control row for the
   snorm refusal in `ubwc_possible()`. That refusal is conditional on
   `ubwc_unorm_snorm_int_compatible`, which is True on `a7xx_gen2`
   (`freedreno_devices.py:817`), so the row is not a control - it has a ceiling like its
   three siblings, and it belongs to the reserve.

## One row nobody can explain yet (open question 13)

The system driver differs from both Mesa 27 builds on exactly one cell:
`B8G8R8A8_UNORM`, `nolist=0x00102000` against `0x00100000` - it gives UBWC to a `MUTABLE`
image with no format list. Both refusal functions are byte-identical between our base and
the tag `mesa-26.2.6`, and the `is_mutable` branch of `tu_image_init()` at that tag has the
same shape, so the difference is not in them. The package is a distribution build
(`-1.fc44.armada`) whose own patches are not in this repository, so this row is neither a
control nor a claim about upstream 26.2. It is recorded because it is the one measurement
here that a Mesa 27 driver cannot reproduce.

**Verdict.** Both facts journal 28 asked for are answered, and they answer in favour of
writing `exp-18`: the 64-bit class has a ceiling, all four of the game's 64-bit formats
reach it as plain images, and between a no-list image and that ceiling there is only the two
`NULL` refusals, one of which upstream still marks as a TODO. But the direction of that fact
matters for the bar: `exp-18` does not unlock hardware, it reverses a deliberate and current
upstream default, so it must arrive with the strict Vulkan class (journal 24.4), the 94-row
matrix with `NL`, `XV`, `UBR`, `S`, `N` read separately (ADR-0006), and a no-list cast probe
before any volume number is quoted. `NOT BUILT` - no driver was rebuilt for this entry, and
nothing here measures a patched `exp-18`.

**What this does not show.**

* a metadata plane is not compressed content (journal 22.2); no fill, no readback and no
  counter was taken in this entry, so nothing here says a no-list UBWC image would read back
  correctly - that is `exp-18`'s gate, not this measurement;
* `nolist` cannot separate tiled from linear: a tiled image without UBWC and a linear one
  have the same `memreq` at this size, which is why probe `NL` decides layouts with a sparse
  create instead. "NO UBWC" is all the column is entitled to say;
* the volume figures (650.8 MiB of 64-bit, 4073.0 MiB no-list) are journal 28's, from game
  inventories; no run in this entry reproduces or re-derives them;
* the game was not run, and the base build `23ccf659c90d…` is still unrun against the game -
  queue 3 stays open.

Artifacts: `tests/rp6-vkd3d-sparse-test.c` (fourth image in `probe_ubwc_ceiling()`, five new
rows), `results/test-CEIL-nolist-p14.log`, `results/test-CEIL-nolist-mesa27base.log`,
`results/test-CEIL-nolist-mesa26system.log`, full runs under `results/raw/` (gitignored,
regenerable with the three commands above).
