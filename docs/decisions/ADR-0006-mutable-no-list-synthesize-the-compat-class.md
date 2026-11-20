# ADR-0006: for a mutable image with no list, synthesize the compatibility class (0014 v1)

Date: 2026-11-20 (recorded; v1 shipped, v2 dropped 19.11)
Status: accepted

## Context

With `MUTABLE_FORMAT` and no `VkImageFormatListCreateInfo`, Vulkan allows any format of
the base format's class, but the driver hands `NULL` to three predicates that answer the
worst case, so the image goes linear. In the RE4 inventory that is 4062 MiB of 7977 MiB
sampled, 50.9 %, all linear, while DRAM traffic is 81 % texture reads.

## Decision

Ship `0014` v1: `tu6_mutable_compat_class()` synthesizes a format list from the texel
block and the existing predicates run on that list; `tu_image_init()` uses it for both
the create path and the format query, so the sparse answer and the create cannot diverge.
The v2 form - answering the predicates directly with the block rule - is rejected and
lives in `patches/dropped/`.

## Consequences

- 2201 MiB of deposited volume returns to tiled by the model, 2170 MiB measured on the
  game (linear residue 3801 -> 1631 MiB), content byte-identical, matrix 94/94 EXACT,
  probe NL 8/8 layouts and round trips;
- the 32- and 16-bit classes stay linear on purpose: inside them RGBA8 <-> BGRA8 and
  R8G8 <-> R16 reinterpret a layout, and reading back through such a view is undefined.
  The stock + prop build tiles them and fails exactly those probes (analysis 24.3, 27);
- a tiling patch may only pull images out of linear, never push them in - the rule this
  shape follows;
- UBWC is NOT part of this: `format_list_ubwc_possible()` still answers false for an
  absent list (analysis 28). Extending the class rule to the UBWC predicates is exp-18,
  and for UBWC the *strict* Vulkan class is required, not the block class;
- v2 broke `RGBA8->BGRA8` and `BGRA8->RGBA8` on the tiled non-mutable path while the 94
  row counter still said EXACT - the failure was visible only in the `XV` rows, which is
  why "the counter is green" is not a gate.

## Evidence

journal 21.12, 24.3, 27, 28; `patches/0014-turnip-mutable-no-list-tiling.patch`,
`patches/dropped/0014-turnip-mutable-no-list-tiling-block-rule.patch`, `patches/DROPPED.md`;
`results/test-0014-ship.log`, `results/test-0014-inventory-ab.log`,
`results/test-0014v2-matrix.log`, `results/imginv-3variants.txt`.
