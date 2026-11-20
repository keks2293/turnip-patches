# 32. The two 64-bit UBWC compat labels behave as one cell on A740, and that label is all the strict class rule is missing (21.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md).

**Question.** `exp-18 (b)` asks whether the refusal of UBWC to a `VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT`
image created *without* a `VkImageFormatListCreateInfo` can be narrowed by the Vulkan
compatibility class instead of being absolute - upstream's own `TODO: limit based on
compatiblity class` (`tu_image.cc`) suggests exactly that. Two things had to be separated
before that is written either way:

1. **What the rule would grant** if it were read strictly, class by class, on a7xx_gen2 -
   a question about tables, answerable without the GPU;
2. **One hardware fact** that the tables assert but nobody measured: `fd6_ubwc_compat_mode()`
   answers `FD6_UBWC_R16G16B16A16_INT` for the five 4x16 members of the 64-bit class and
   `FD6_UBWC_R32G32_INT` for its three 2x32 members. Is that difference a property of the
   compressor, or a label for a pair the blob never mixed?

Journal 28 counts 650.8 MiB of the game's no-list bytes in that one class, so the second
question is also the largest volume still on the table.

## 32.1 The strict class rule, modelled: 22 of 23 classes refuse for reasons the rule cannot fix

`scripts/fmt-list-gate-check.py --strict-class` ports three predicates to Python -
`ubwc_possible()` (`tu_image.cc`), `fd6_ubwc_compat_mode()` (`freedreno_ubwc.h`, with the
rows patches 0006/0011/0012 add) and the refusal of a missing list in
`format_list_ubwc_possible()` / `tu6_mutable_format_list_ubwc_compatible()` - and asks, for
each of the 23 Vulkan compatibility classes, whether every member turnip can build a view
for passes `ubwc_possible()` and agrees on one compat mode. A member that has no UBWC at all
*refuses* the class rather than being skipped: a no-list image may be viewed as any of its
members, so the permission can be no wider than the class. That is the strict reading.

| block | classes granted | what differs |
|---|---|---|
| shipped stack, every member counted | 0 of 23 | - |
| Mesa 27 base, rows as upstream wrote them | 0 of 23 | no 0006/0011/0012 rows |
| shipped stack, members with no `fd6_format_table.c` row excluded | 1 of 23 (128-bit) | the gap is upstream's and pre-existing: a view in such a format is broken with UBWC and without it |
| same, **plus** the 4x16/2x32 pair folded into one label | **2 of 23** (128-bit **and 64-bit**) | the fold is the question of 32.2, and nothing else |

Two numbers out of that table are the reason the entry exists. First: the 64-bit class is
refused by *one* line of the model - `the class wants R16G16B16A16_INT(5) + R32G32_INT(3)` -
once the five members the format table gives no texture format to are excluded
(`R16G16B16A16_SSCALED`, `_USCALED`, `R64_FLOAT`, `R64_SINT`, `R64_UINT`). Second: folding
that pair is the only fold the model is given, so no other class can be widened by it -
the 32-bit class still wants six different labels, the 16-bit class three, and both have
measured breakage of their own (ADR-0001, ADR-0007).

Artifact: [`../../results/model-strict-class-nolist.txt`](../../results/model-strict-class-nolist.txt)
(regenerate: `python3 scripts/fmt-list-gate-check.py --strict-class`). It is a model: nothing
in it ran on the GPU, and no line of it says what the chip does.

## 32.2 The probe: one image, two views, one knob

A no-list image never gets UBWC at all (journal 31, on the shipped stack and on the bare
Mesa 27 base), and a list that names both families is refused by the rule under test - so no
create available today shows the compression. `probe_xmc()` in `tests/rp6-vkd3d-sparse-test.c`
therefore creates the create the rule refuses, and the driver carries an experiment switch:

* the image is 512x512, 8 bytes per texel, `OPTIMAL + MUTABLE_FORMAT`, usage
  `SAMPLED | TRANSFER_SRC | TRANSFER_DST`; **no `STORAGE`**, because storage usage is what
  would let an app reach `R64_UINT` (journal 31) and that is a different question;
* the format list names both families - `{R16G16B16A16_UINT, R32G32_UINT}` (`MIX42`), or the
  mirror with `R32G32_UINT` as the base (`MIX24`) - which is also what makes both views legal;
* `TU_UBWC_64B_MIX=1` (`experiments/exp-22-ubwc-64b-mix-knob.patch`, not for ship) answers the
  compat question with "one cell" and nothing else: it folds `R16G16B16A16_INT` into
  `R32G32_INT` inside `tu6_mutable_format_list_ubwc_compatible()`. Because
  `tu6_mutable_format_list_forces_linear()` starts from the same call, the knob moves UBWC and
  tiling together - which is what makes the image measurable at all;
* the fill is a `vkCmdCopyBufferToImage` of a pattern in which every eighth 32-bit word is one
  of the values upstream calls special (`0`, all ones, `1`, `0x80008000`, ... - the values the
  `tu_image.cc` comment names as UBWC-incompatible for unorm/snorm before a740), the rest
  index-tagged, so neither a decode error nor a layout error can hide in a uniform fill;
* the read is a compute `texelFetch` through a `usampler2D`, twice: `x4` through a
  `R16G16B16A16_UINT` view (the four 16-bit halves) and `g32` through a `R32G32_UINT` view (the
  two 32-bit words). Both ends are integer formats, so no `[0,1]` decode sits between the
  memory and the answer. Readers: `tests/rp6-vkd3d-sparse-xmc_u32x4.glsl`,
  `tests/rp6-vkd3d-sparse-xmc_u32g32.glsl` (embedded as `tests/rp6-vkd3d-sparse-xmc_spv.h`,
  regenerate with `scripts/gen-xmc-spv.sh`).

Four shapes need no knob and are the rig's own controls:

| shape | the create | what it is there to prove |
|---|---|---|
| `SGL4`, `SGL2` | a **single**-member list | that a compressed 64-bit image survives this fill and this reader at all - a single-member list keeps UBWC today, so this is the control the MIX verdict is read against |
| `NOL` | no list | the same content uncompressed, read both ways: that the two views themselves are honest |
| `DETECT` | no list, and the fill given a row length **in words instead of texels** on purpose | that the rig can count wrong at all: this row must NOT be `EXACT` |

`DETECT` is not decoration. The first XMC run came back "196352/262144 wrong, 131072 all
zero" on every shape because of exactly that mistake in the probe, and a row that says
"0 wrong" is only a statement if the comparison has been shown to see wrong data.

```sh
# the readers, in the glslang container (glslangValidator, -S comp for .glsl)
podman run --rm -v "$REPO/tests":/work:z -v "$REPO/scripts":/scripts:z \
    localhost/mesa-build-fedora44-wsi-glslang-vulkan bash /scripts/gen-xmc-spv.sh
# the tool (scripts/build-test.sh now skips its dnf step when the image has the toolchain)
podman run --rm -v "$REPO/tests":/work:z -v "$REPO/scripts":/scripts:z -v "$WORK":/out:z \
    localhost/mesa-build-fedora44-wsi-glslang-vulkan bash /scripts/build-test.sh

# three runs of ONE binary, sha256 5f44a7f7e6ae...
source scripts/env.sh
export RP6_TEST_BIN=$WORK/rp6-vkd3d-sparse-test
scripts/run-test.sh build/p14-shipped/freedreno_icd_p14.json      results/raw/xmc-p14-noknob.log
scripts/run-test.sh build/out-exp22/freedreno_icd_exp22.json      results/raw/xmc-exp22-knoboff.log
TU_UBWC_64B_MIX=1 scripts/run-test.sh build/out-exp22/freedreno_icd_exp22.json results/raw/xmc-exp22-knobon.log
```

| run | driver | identity |
|---|---|---|
| A | `build/p14-shipped/libvulkan_freedreno.so` | `c17d02bcaae9a960…`, the released stack; no knob in it |
| B | `build/out-exp22/libvulkan_freedreno.so` | `0e934fc6b3e0…` = `0001..0013` + `exp-14` + `exp-21` + `exp-22`, run with the knob **off** |
| C | the same `.so` as B | run with `TU_UBWC_64B_MIX=1` |

`0014` is deliberately not applied: `results/test-exp21-equiv-p14.log` (journal 33) shows the
`0001..0013 + exp-14 + exp-21` tree behaving like the released one on every probe.

## 32.3 The knob moves two lines out of 621, and both of them read EXACT

Run A against run B: **0 differing lines** out of 621 - the exp-22 tree without the knob is
the released stack on every probe. Run B against run C, the knob switched on: **two log
lines change** (the `diff` that prints them is 8 lines). They are the two creates in question:

```
XMC[MIX42 ] base R16G16B16A16_UINT list 2: opt=0x200000 ... tail=0x0     -> tiled (only a tiled image can be sparse)
XMC[MIX42 ] base R16G16B16A16_UINT list 2: opt=0x202000 ... tail=0x2000  -> tiled (size)
XMC[MIX24 ] base R32G32_UINT       list 2: opt=0x200000 ... tail=0x0     -> tiled (only a tiled image can be sparse)
XMC[MIX24 ] base R32G32_UINT       list 2: opt=0x202000 ... tail=0x2000  -> tiled (size)
```

(truncated at the `tail=` field for width; the full rows are in the curated log). With the
knob off the mixed create is refused UBWC - `tail=0x0`, the same signature journal 31
measured for a no-list image - and with it on the create carries the `0x2000` metadata tail
against a `0x200000` image, the signature `UBR` and `CEIL` use for a UBWC image.

The content, in all three runs, `0/262144` wrong texels where a verdict exists:

| shape | knob off: layout | knob on: layout | the `x4` read | the `g32` read |
|---|---|---|---|---|
| `MIX42` | tiled, no metadata tail | tiled, `tail=0x2000` | EXACT | EXACT |
| `MIX24` | tiled, no metadata tail | tiled, `tail=0x2000` | EXACT | EXACT |
| `SGL4` | tiled, `tail=0x2000` | same | EXACT | the view is not in the list, no verdict |
| `SGL2` | tiled, `tail=0x2000` | same | the view is not in the list, no verdict | EXACT |
| `NOL` | tiled, no metadata tail | same | EXACT | EXACT |
| `DETECT` | broken fill, on purpose | same | `196352/262144` wrong, `131072` all zero -> MISMATCH | same |

Artifact: [`../../results/test-xmc-64bit-compat.log`](../../results/test-xmc-64bit-compat.log) -
the three XMC sections verbatim, the diff, and the reading of each row.

**Verdict.** On this A740, in the paths the probe exercises, the two labels are **one cell of
the compressor**: a UBWC image created as 4x16 reads exactly through a 2x32 view and the other
way round, at 0 wrong texels of 262144, with the same-family control, the uncompressed
control and the detection control all behaving. Nothing else in the driver changes behaviour
when the pair is treated as compatible, and nothing in the test corpus regresses - the knob
moved two lines of 621, all of them the two creates it is about.

That closes 32.1's open end with a measurement instead of a prediction: the one line that
stands between a strict class rule and the 64-bit class is a label that this chip does not
honour in these paths. `exp-18 (b)` is therefore no longer argued from a table. It is still
not written: see what this does not show, and queue 1.

## What this does not show

* **It is not a claim that the chip compressed these images.** `+0x2000` in
  `vkGetImageMemoryRequirements` is the driver reserving a metadata plane (journal 22.2).
  What is measured is that the create took the UBWC decision and that the content still
  round-trips through both views. A detector that would show compression directly (a
  fast-clear that leaves the bytes untouched) is a different rig and was not built.
* **It is one pair of labels of one class.** It says nothing about the 32-bit class, where the
  measured break is a channel order (`XV[BGRA8_as_RGBA8] MISMATCH (memory is swapped)`,
  journal 24, ADR-0001), nor about the 8-bit class, which reads back as zeros under UBWC
  (ADR-0007).
* **It does not license a rule keyed on the base format**, which is the form the operator
  proposed and the queue declined: a no-list image is viewable as *every* member of its
  class, and the members this probe deliberately avoided (`R64_UINT`, `R64_SINT`, reachable
  once `STORAGE` is in the usage) are refused by `ubwc_possible()` for their own reasons
  (journal 31).
* **One geometry, one usage set, one reader.** 512x512, no `STORAGE`, no mips, no arrays, no
  multisample, compute `texelFetch` only - no render-target read, no depth, no sampling with
  filtering, no BC, no game. Graduation of any rule built on this needs the matrix rig
  (`exp-15`, `TU_B2I_SYNC`), which neither `build/out-exp21` nor the shipped build carries
  (`grep -ac TU_B2I_SYNC` = 0 in both).

Related: journal 28 (the class-by-class volume of the game's no-list bytes), journal 31 (the
ceiling, and the R64 refusal), ADR-0001 and ADR-0007 (the two classes where a compat
difference *is* hardware), `docs/streams/ubwc-format-lists.md`.
