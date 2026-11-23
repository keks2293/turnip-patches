# Dropped patches

What this file is: the record of patches and patch-shaped artifacts that are
**not** in the shipping stack, and the measurement that says so. A patch is
dropped only for a reason that points at a committed artifact; "looks
redundant" is not a reason.

The shipping stack itself is `patches/0001..0014` — see `PATCHES.md`.

## The question that produced this directory

`ubwc_all_formats_compatible` is set for `a7xx_gen3` only, so A740 (gen2) is the
one family without it. If it were set for gen2, would parts of the stack become
unnecessary? Reading the code says yes: the prop is consulted at four sites
(`tu_formats.cc:397`, `tu_image.cc:582`, `tu_device.cc:499`, `:898`), and five
patches look like they would be short-circuited by it — `0005` and `0010` (their
predicates are evaluated below line 397, so the flag skips them) and `0006`,
`0011`, `0012` (their `fd6_ubwc_compat_mode()` is called only from
`tu6_mutable_format_list_ubwc_compatible()`, which `mutable_ubwc_fc` at
`tu_image.cc:582` overrides).

Measured, the answer is no. Two builds on the ship stack:

| build | stack | `.so` | matrix | result |
|---|---|---|---|---|
| flag baked in | `0001..0014` + `ubwc_all_formats_compatible = True` in `a7xx_gen2` | `5e99409774838be5` | `results/test-gen2flag-table.log` | EXACT 93, three regressions vs the ship driver: `S3 PASS→FAIL`, `U[B8G8R8A8_UAVLIST] EXACT→MISMATCH`, `XV[BGRA8_as_RGBA8] OK→MISMATCH` |
| flag + reduced | `0001..0004`, `0007`, `0008`, `0009`, `0013` (no `0005`, `0006`, `0010`, `0011`, `0012`, `0014`) | `c60dfb269b65b234` | `results/test-gen2flag-minstack.log` | EXACT 92, **two new FAILs against the line above** |

| probe | full stack + flag | reduced stack + flag | whose patch |
|---|---|---|---|
| `S` — uniform-swap BGRA + UINT, tiled + sparse | PASS | FAIL, 16384/16384, reads `0x000000a5` where `0x00a50000` was written | `0005` / `0010` |
| `T` — UBWC + tiled, UINT/UNORM raw round trip | PASS | FAIL, 261120/262144, same byte-exchange signature | `0006` (its `{B8G8R8A8_UNORM, B8G8R8A8_UINT}` list), `0011`/`0012` share the mechanism |

So the flag is not a superset of those patches, it is a loss of information:
`S` breaks because a uniform-swap tiled layout still has to be *read* correctly
(`0005`), and `T` — because the UBWC compat mode is part of the resource layout,
not an allow/deny switch that `mutable_ubwc_fc` recomputes. `0006` was
not isolated with its own build — it was removed together with the other four.

One caveat about `T`, found afterwards: the Vulkan formats of its list are
enum-only. `VK_FORMAT_B8G8R8A8_UINT/SINT/SNORM/USCALED/SSCALED` exist in
`vulkan_core.h`, but Vulkan defines no *supported* format with that packing (only
UNORM and SRGB), so no client puts that pair in a list. `T` is a probe of the
mechanism — what the compat mode does to the layout — not a workload shape. The
workload shapes and their volume are in journal 25
(`docs/analysis.md`): `0011` = 115 MiB (`R10G10B10A2` lists), `0012` =
43 MiB (`R32_UINT → {FLOAT,SINT,UINT}`), `0005`/`0006`/`0010` = **0 MiB in RE4**,
and 539 of the 767 MiB of list traffic come from the gen2 prop
`ubwc_unorm_snorm_int_compatible` alone.

Consequence: **the droppable list is empty.** The prop also buys nothing on this
workload — the shapes it changes are never created by the game (journal 24.1), and it costs three matrix regressions. It is not
in the table.

## Verdict per patch

| patch | verdict | why |
|---|---|---|
| `0001` sparse cross-queue sync | stays | committed in the Mesa tree as `ac08003`, not a file-level toggle |
| `0002` A830 chip-id (+ `-mesa26` sibling) | stays, both files | the Mesa 27 form is committed (`9845cfb`); the `mesa26` file is the Mesa 26.2.3 form the ArmadOS image patches use, not a leftover |
| `0003` ir3 bindless UBO const lowering | stays | unrelated to formats |
| `0004` sparse residency gate | stays | `0009` and the sparse probes depend on the gate's shape |
| `0005` mutable uniform-swap tiling | stays | removing it under the flag turns `S` into 16384/16384 mismatches. In RE4 it moves **0 MiB** (journal 25, the per-patch volume table) — it is insurance for `{BGRA…, RGBA…}`-style lists that the game never creates |
| `0006` B8G8R8A8 int compat type | stays | removed together with `0011`/`0012` in the reduced build; its own probe `T` fails under the flag. In RE4 **0 MiB** (journal 25): no `B8G8R8A8_*` appears in any list, and its Vulkan formats for the INT variants are enum-only (the caveat above) |
| `0007` `TU_FORCE_PROPS` | stays | the only way to measure a prop without a rebuild; the flag experiment in `docs/a7xx-gen-props.md` rows 23/24 runs through it |
| `0008` gen2 generic clear | stays | performance, unrelated to formats (journal 15) |
| `0009` NV12 mutable keeps tiling | stays | sparse-creation fix, its NV12 branches are reached before the flag is consulted |
| `0010` single-channel swap tiling | stays | removed with `0005` in the reduced build → `S` FAIL; like `0005`, **0 MiB** in RE4 |
| `0011` UBWC compat R16/10-bit | stays | removing it under the flag turns `T` into 261120/262144 mismatches, and in RE4 it has measured volume (journal 25): 53 creates / **115 MiB** of `R10G10B10A2_UNORM → {UINT,UNORM}` lists get UBWC only because of it |
| `0012` UBWC compat sfloat/int | stays | same file and probe as `0011`; measured volume 26 creates / **43 MiB** (`R32_UINT → {FLOAT,SINT,UINT}`). Its BC half is documented as completeness, not a perf lever — RE4 BC textures are sparse and sparse excludes UBWC (journal 21.11) |
| `0013` b2i CCU clean | stays | correctness of copy-to-image (journal 21.10, ADR-0005) |
| `0014` mutable no-list tiling | stays in the shipped form (v1) | see below for the v2 that was dropped |

## Numbers 0015 and 0016: retired, no file

The stack stops at `0014`, and the two numbers above it were spent before any file
existed - patch numbers are never reused, so a reader looking for `0015`/`0016` finds
none:

- **`0015`** - the withdrawn `MUTABLEEN`-on-gen2 candidate. It never became a file: the
  verdict that killed it is ADR-0009, the measurement is journal 21.4 (exp-10) plus
  24.1, and `results/raw/game-patched-imginv{4,5}.log` is the inventory evidence.
- **`0016`** - reserved for the `exp-21` candidate, then dissolved into `0014` on 23.11
  instead of graduating beside it: the one-decision text is now
  `patches/0014-turnip-mutable-no-list-tiling.patch`, and the number is retired with
  the experiment (`experiments/README.md`, journal 40.29).

## Files in `patches/dropped/`

| file | what it was | why it is here |
|---|---|---|
| `0014-turnip-mutable-no-list-tiling-block-rule.patch` | `0014` v2: answer the layout predicates with "same texel block" instead of enumerating the compatibility class | Built and run. It breaks `RGBA8→BGRA8` and `BGRA8→RGBA8` on the tiled non-mutable path: `results/test-0014v2-matrix.log` has `XV[RGBA8_as_BGRA8] -> MISMATCH (memory is raw: the view is ignored)` and `XV[BGRA8_as_RGBA8] -> MISMATCH (memory is swapped)` while the matrix counter still reads 94 EXACT — the counter does not catch this shape, the `XV` rows do. The header in the file still says "DRAFT - not built and not run"; that line predates the run and is superseded by this table and by journal 21.12 and 24.3 of `docs/analysis.md`. With v2 removed, `patches/0014-*.patch` is the shipped v1, re-extracted from tag `27.0.0-devel-p14`. |

## If the criterion were "RE4 only"

Then three patches would be candidates for removal, because the game's 726
list-creates never hit their predicates — 726 creates / 767 MiB, all nine real
combos are in journal 25 (`docs/analysis.md`):

| patch | RE4 volume | but |
|---|---|---|
| `0005` | 0 MiB | any list mixing channel orders (a legal Vulkan list, the class rule does not apply when a list is given) falls to linear without it |
| `0006` | 0 MiB | the B8G8R8A8 INT/SNORM variants have no supported Vulkan format, but the pipe-level compat type is what gallium/zink and any future `BGRA + UINT` list use |
| `0010` | 0 MiB | single-channel lists next to two-channel ones |

That is a "minimum stack for one game" argument, not a correctness argument, so
nothing was moved: they stay in `patches/`, and this table is the reason to look
at them first if the stack ever needs to shrink.

## Related experiment build (not a dropped patch)

`experiments/exp-16-gen2-ubwc-allformats-stock.patch` — stock Mesa 27
(`6dfa32a85f91`, no patches at all, `0001`/`0002` also reverted) plus the single
prop line. Built as `build/out-stock-flag/libvulkan_freedreno.so`
(`44cdf593a5200d8b…`, ICD
`build/out-stock-flag/freedreno_icd_stock_flag.json`), matrix
`results/test-stock-flag-matrix.log`: EXACT 73 against 76 for the same stock
without the prop. On a bare driver the flag by itself turns
`vkCreateImage(MUTABLE + SPARSE)` into `SUCCESS` — damage (1) of row 23 in
`docs/a7xx-gen-props.md` — so that damage is the prop's own, not something our
stack introduces. Journal 26 (`docs/analysis.md`).

## How to re-run this

```sh
# flag baked into the table, ship stack
#   (edit freedreno_devices.py: a7xx_gen2 -> ubwc_all_formats_compatible = True)
podman run --rm -v /var/home/armada/opencode/mesa27-src:/src:Z \
  -v /tmp/opencode/mesa27-build:/out:Z -v /tmp/opencode/ccache:/ccache:Z \
  -e CCACHE_DIR=/ccache localhost/mesa-build-fedora44-wsi-glslang-vulkan \
  bash -c 'cd /src && ninja -C /out/build -j2 src/freedreno/vulkan/libvulkan_freedreno.so'
scripts/run-test.sh /var/home/armada/opencode/build/out/freedreno_icd.json /tmp/run-flag.log

# the reduced stack: git apply -R of 0014, 0012, 0011, 0010, 0006, 0005, then rebuild
```

Restore afterwards with `git apply -R` of what is applied, then
`git apply patches/0003..0014` in order. Never `git checkout` a file in this
tree: several patches edit the same file, and a checkout drops their hunks with
no way to recover them from the index. Verify the restore by the matrix —
`results/test-restore-shipstack.log` matches `results/test-p14-base.log` line
for line — not by the `.so` hash: a rebuild of the same stack is not
bit-identical.
