# 28. Why UBWC in RE4 is 49 %, not 99 % - and what the real reserve is (20.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

Counted from the `stockflaginv` log (8088.0 MiB total, `ubwc=1` 3944.9 MiB). Where
the 4143.1 MiB without compression go:

| class | MiB | `ubwc=` | why |
|---|---|---|---|
| without `MUTABLE` | 3245.1 | 3245.1 (100 %) | - |
| `MUTABLE` with a list | 769.9 | 699.8 (90.9 %) | the 70.1 MiB residue is `R8_*`: `fd6_ubwc_compat_mode()` has no mode for `R8_*` in the upstream table, and adding one is **forbidden by measurement** (`results/test-r8-split-{on,off}.log` - content corruption, not a readback artefact; section 22) |
| **`MUTABLE` without a list** | **4073.0** | **0.0** | one upstream line: `format_list_ubwc_possible()` returns false when there is no list, with the comment `TODO: limit based on compatiblity class` |

So "48.8 %" is not a hardware ceiling, it is one conservative branch. The same 4073.0
MiB by class, with the reason for each refusal:

| no-list class | MiB | UBWC availability |
|---|---|---|
| 32-bit and 16-bit | 1014.7 + 624.9 | neither: those images are `linear` anyway (0014 does not tile them deliberately) and UBWC does not apply to linear |
| 8-bit (`R8_*`) | 1181.8 | no, and the reason is earlier than the compat table: `has_8bpp_ubwc` is **already** False on a7xx (`True` appears only in `a6xx_base:118`; the a7xx chain is `[a7xx_base, a7xx_gen2, …]` and `a7xx_base` does not set the bit, so the generated GPUProps default is False). The check at `tu_image.cc:353` sits **before** the compat gate, so R8 gets no UBWC even where a mode exists. It must not be turned on: section 22 (`FD_DEV_FEATURES=has_8bpp_ubwc=1` -> 65536/65536 readback bad, all zeros; re-verified 18.11 in split submits and 20.11 by comparing values on two readers and sweeping the metadata geometry) - content corruption, not a readback artefact |
| BC (DXT/BPTC/RGTC) | 600.7 | no: `ubwc_possible()` returns false for every `vk_format_is_compressed` ("no UBWC with compressed formats"). That is driver policy, not absent hardware, but changing it is a separate large piece of work (section 21.9) |
| **64-bit** | **650.8** | **this is the reserve**: in game it is `R16G16B16A16_FLOAT` 312 creates, `_UNORM` 146, `_SNORM` 56, `R32G32_FLOAT` 22; 0014 already tiles them (the class is homogeneous) and `ubwc_possible()` does not block them |

Direct evidence in the log: the game also has **plain** (non-`MUTABLE`) R8 images -
`R8_UNORM` plain, 4 creates / 4.0 MiB, `tile=tiled`, `ubwc=0`. If 8bpp UBWC were
allowed on gen2 they would have been compressed; they were not, so the block sits
before any format list. The same block explains the `R8_*` hole inside lists
(70.1 MiB), so the cause of that zero in section 25 is not only `UNKNOWN_COMPAT` in
the table but an earlier format check.

The practical ceiling, if the "texel block" rule were extended to the UBWC predicates
(`tu6_mutable_format_list_ubwc_compatible` and `format_list_ubwc_possible` instead of
`NULL`): 3944.9 + 650.8 = **4595.7 MiB, 56.8 %**, against today's 48.8 %. Not 99 %,
because half of the game's volume is R8 masks and BC textures, both cut for other
reasons. Before doing it, two facts that no measurement covers: whether
`R16G16B16A16_FLOAT` has a UBWC variant of the format in the table (the name is not
found by grep in `tu_formats.cc`, so the mapping is in the generated header), and what
happens to `R32G32_FLOAT`, which has no compat mode at all.

The prop `ubwc_all_formats_compatible` has nothing to do with these numbers: it
bypasses `tu6_mutable_format_list_forces_linear()` (tiling) and influences
`mutable_ubwc_fc` **for lists**, while `format_list_ubwc_possible()` is called earlier
and answers "no" for `NULL` regardless of props - which is why its no-list class shows
`ubwc=` zero in section 27 as well.

## Update 20.11 (later): the two facts above are answered, and one of them was mis-framed

Journal 31 measures both, with a fourth image added to probe `CEIL` (a `MUTABLE` image with
no format list). The class has a ceiling: a plain `R16G16B16A16_FLOAT`, `_UNORM`, `_SNORM`
or `R32G32_FLOAT` image gets the metadata plane, `+0x2000` at 8 B/texel. `R32G32_FLOAT` and
`R16G16B16A16_FLOAT` have compat modes in the shipped stack because `0012` added them; on the
bare Mesa 27 base those two classes lose UBWC, which is the first time that was measured
against the base rather than against the working stack of the day.

The sentence "the name is not found by grep in `tu_formats.cc`, so the mapping is in the
generated header" is wrong, and there is no such header to go looking for: UBWC is a layout
flag, and the only per-format gate is `fd6_ubwc_compat_mode()` in
`src/freedreno/common/freedreno_ubwc.h`, whose consumers are `tu_formats.cc:71` and gallium's
`fd6_resource.cc` - the layout code never consults it, which is why a plain image shows a
ceiling even for a format the table calls `FD6_UBWC_UNKNOWN_COMPAT`.

Unchanged by the correction: the 650.8 MiB, and the refusal of `NULL`. What journal 31 adds
is that the refusal is identical on the base and on the shipped stack for all seventeen
`CEIL` rows - the reserve is upstream's, not something this stack took away.
