# Direction: linear deposition of mutable images without a format list

**State: active - this is the current front.** `0014` v1 shipped (ADR-0006); the next
item is the UBWC half of the same branch, `exp-18`, which has no patch file yet.

Believed, with the evidence:

- an absent format list means "any format of the base's class", not "the worst case";
  the three predicates that answer on `NULL` are the whole cause
  (`analysis` 21.12, ADR-0006);
- `0014` returns about 60 % of the deposited volume to tiled and the residue is exactly
  the classes that legitimately reinterpret a layout (`analysis` 27, class table);
- UBWC in that class is zero in every variant measured, including the crude prop - the
  block is one upstream line, `format_list_ubwc_possible()` answering false on `NULL`
  with `TODO: limit based on compatiblity class` (`analysis` 28);
- the reserve is 64-bit only: 8-bit is closed by ADR-0007, BC by ADR-0004, and 32/16-bit
  stay linear by design (`analysis` 28).

Open questions, all in `docs/plan-next-checks.md`: who creates the DEPOSED no-list
images (vkd3d or DXVK - not separated, and it decides which path to verify); and two
unmeasured facts before exp-18 (a UBWC format variant for `R16G16B16A16_FLOAT`, and the
fate of `R32G32_FLOAT`, which has no compat mode).

The shape of exp-18, so that it does not get written wrong: (a) move
`format_list_reinterprets_r8g8_r16()` and `format_list_has_swaps()` out of the
`!mutable_ubwc_fc` branch - today the `is_mutable` branch skips them, which is why the
prop tiles 16-bit images without a list, a real hazard; (b) implement the TODO against
`tests/vk-fmt-classes.json` with the **strict** Vulkan class, with the risk on legal but
non-UBWC class members (`E5B9G9R9`, `R64_*`) written down, and a `perf_debug` counter;
(c) probe no-list casts before any claim about volume. Gate: matrix 94 EXACT, and the
`UBR`/`XV` rows unchanged. Blocked on restoring `0003..0014` in `../mesa27-src`.

Decisions: ADR-0006, ADR-0004, ADR-0007, ADR-0008. Artifacts:
`patches/0014-turnip-mutable-no-list-tiling.patch`,
`experiments/exp-14-image-inventory.patch`, `scripts/imginv-stats.py`,
`scripts/imginv-classes.py`, `results/imginv-3variants.txt`,
`results/test-0014-*.log`.
