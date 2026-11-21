# 37. R64_UINT reads and writes a UBWC 64-bit image made without a list: exp-18(b) has a measured form (21.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md).

**Question.** Open question 14: does a `R64_UINT` view of a UBWC image work, once `STORAGE` makes the
view legal. It is the gap `exp-18 (b)` could not write around, and journal 32 could not answer it either,
because that run created its images *without* `STORAGE` on purpose. The reason the question is hard is
structural, and it decided the shape the question had to take:

* a format list that **names** `R64_UINT` can never be compressed. `fd6_ubwc_compat_mode()` has no case
  for `R64_*`, so the member answers `FD6_UBWC_UNKNOWN_COMPAT`, and
  `tu6_mutable_format_list_ubwc_compatible()` refuses any list holding an `UNKNOWN` member before it
  compares labels. No knob that folds two known labels together reaches it;
* `R64_UINT` has no vertex, colour or texture entry - `tu_formats.cc` grants it `STORAGE_IMAGE`,
  `STORAGE_IMAGE_ATOMIC` and the transfer features under `has_64b_image_atomics` and asserts the rest -
  so the only reader it has is an image descriptor;
* an image created **without** a list is viewable as `R64_UINT` as soon as its usage carries `STORAGE`,
  and that is precisely the create a class rule would hand UBWC.

So the question can only be asked of a no-list create with `STORAGE` in the usage, read by a storage
image. Nothing in the rig did that until now.

**The probe.** `probe_xr64` / `xr64_storage` in `tests/rp6-vkd3d-sparse-test.c`, with two new readers
(`tests/rp6-vkd3d-sparse-xr64_{load,atomic}.glsl`, generated into `rp6-vkd3d-sparse-xr64_spv.h` by
`scripts/gen-xr64-spv.sh`). Fill by `vkCmdCopyBufferToImage` through the base format, exactly as XMC
fills, then read every 64-bit word through a `r64ui` storage image, then `imageAtomicAdd(+1)` per word
and read again. The second pass is the part no sampled read can speak to: a wrong answer is a wrong
value per word, not a lost write, and XMC's own `DETECT` row stays the check that the comparison is able
to see wrong data at all. The device is created with `shaderInt64` and `shaderImageInt64Atomics` enabled
and prints what it found first: `shaderInt64=1, shaderImageInt64Atomics=1, sparseImageInt64Atomics=0` -
the third is absent, so sparse images with 64-bit atomics are outside these runs.

**The knob.** `experiments/exp-23-ubwc-nolist-64-knob.patch`, `TU_UBWC_NOLIST_64=1`, NOT FOR SHIP. It
declines the UBWC demotion in the no-list mutable branch of `tu_image_init()` for images whose base
texel block is 8 bytes, and for nothing else: no hook on an image with a list, nothing granted where
`ubwc_possible()` already said no, and the layout decision
(`tu6_mutable_format_list_forces_linear`) is not touched, so the hook cannot move an image between tiled
and linear. `is_mutable` stays `false`, which is the point: the compressor is asked about an image the
application may still reinterpret.

```
# the binary: podman run ... bash /scripts/build-test.sh   -> sha256 96e6167dcad6dc1e...
source scripts/env.sh && export RP6_TEST_BIN=$WORK/rp6-vkd3d-sparse-test
scripts/run-test.sh build/p14-shipped/freedreno_icd_p14.json        results/raw/xr64-p14.log
scripts/run-test.sh build/out-exp23/freedreno_icd_exp23.json        results/raw/xr64-exp23-knoboff.log
TU_UBWC_NOLIST_64=1 scripts/run-test.sh build/out-exp23/freedreno_icd_exp23.json results/raw/xr64-exp23-knobon.log
```

Drivers: `p14-shipped` = `c17d02bcaae9a960…`, the released stack; `out-exp23` = `2b61554b26ba63c0…` =
`0001..0013` + `exp-14` + `exp-21` + `exp-23`, used for both knob positions. Artifact:
[`../../results/test-xr64-nolist-64-ubwc.log`](../../results/test-xr64-nolist-64-ubwc.log). After the
runs the hook was taken out with `git apply -R` naming one file, and `git diff --stat` in `../mesa27-src`
is back to the recorded 8 files, +663/-80.

## 37.1 The hook moved nine lines, all of them the class it was asked about

The two runs of one binary differ in nine lines out of 134 EXACT-bearing ones: `NL[R16G16B16A16_FLOAT]`,
`NL[R32G32_FLOAT]`, `XMC[NOL]`, `XMC[DETECT]`, `XR64[NOL64]` gain the `+0x2000` metadata tail while
staying tiled, and the four 8-byte members of `CEIL` switch from `no-list: NO UBWC` to `no-list: has
UBWC`. `LST64` (a list naming `R64_UINT`) does not move: `tail=0x0` with the knob off and on - the
refusal the code predicts, and evidence that the knob cannot widen a shape it was not asked about.
`SGL64` (single-member list) keeps `tail=0x2000` in both runs, because a single-member list keeps UBWC
today with no hook at all.

## 37.2 The answer

| shape | layout, knob off | layout, knob on | `R64_UINT` load | after `imageAtomicAdd(+1)` |
|---|---|---|---|---|
| `NOL64` no list, `STORAGE` | tiled, `tail=0x0` | tiled, `tail=0x2000` | EXACT | EXACT |
| `LST64` list names `R64_UINT` | tiled, `tail=0x0` | tiled, `tail=0x0` | EXACT | not run (no compression to test) |
| `SGL64` one-member list | tiled, `tail=0x2000` | unchanged | EXACT | EXACT |

Both read passes are byte-exact on the released stack, on the knob-off run, and on the knob-on run. So
of the three branches written into the exp-23 header the run lands on the first: **a 64-bit image created
without a list, carrying UBWC, is readable through an `R64_UINT` storage image and survives
`imageAtomicAdd(+1)` per 64-bit word with every word exactly +1.** `SGL64` says the same about a
compressed 64-bit image without any hook, which is what makes the `NOL64` row an answer about the *shape*
rather than about the reader: the reader was already fine, the no-list shape is what was never compressed.

`exp-18 (b)` therefore has a form that is narrow and backed by a measurement. That is a licence to spend
a build on a ship candidate and a game run. It is not the result of either.

## 37.3 What this is not

* **Not a compression claim.** `+0x2000` is an allocated metadata plane (journal 22.2), and open question
  15 stays open: no rig here can say the compressor wrote compressed bytes, and on a740 no counter can -
  `UCHE_GMEM_*` read 0 and the UBWC counters do not fit the UCHE budget of 12 (`docs/fdperf-a7xx.md`,
  "hw budgets"). A byte-exact read is equally consistent with compressed and uncompressed storage.
* **One shape.** 512x512, one mip, one layer, base `R16G16B16A16_UINT`, filled by buffer-to-image copy.
  Clear, blit, r2d and render writes into such an image are not exercised; neither is a mip chain or an
  array, nor a second sampled read after the atomic.
* **Nothing about the game.** The 650.8 MiB is journal 28's byte count of no-list 64-bit images, not a
  traffic share, and the DRAM wall in `docs/fdperf-a7xx.md` is 81 % texture reads. ADR-0004 (BC + UBWC was
  not a perf lever) and ADR-0008 (no driver-side fps lever for this game) are the prior against it.
* `sparseImageInt64Atomics=0`, so the sparse corner of the class is not covered.

## 37.4 Three things closed without a build, recorded here so they are not re-asked

**(a) The composition of the linear residue.** Asked what sits in the ~1631 MiB that `0014` leaves
linear, the guess is usually 3D volumes, block-compressed or depth-stencil. Measured line by line in
`results/raw/game-patched-imginv5.log` (mutable-no-list set 2474 creates / 4081.1 MiB; tiled 1450 /
2450.3 MiB; linear 1024 / 1630.8 MiB): **4-byte class 1023.5 MiB (62.8 %), 2-byte class 606.7 MiB
(37.2 %), everything else 0.6 MiB.** Inside the residue: `VK_IMAGE_TYPE_3D` 75.1 MiB (4.6 %) and it is 3D
*of those same classes*, so dimensionality is not the reason; block-compressed 0.5 MiB; depth/stencil 0;
multi-planar 0; multisample 0. The reason is the two deliberate rows in `0014`'s header. Second, and this
is the number that matters for where compression could still go: **every one of the 2474 no-list creates
carries `ubwc=0`** (1183.8 MiB of 1-byte, 666.3 of 8-byte, 600.2 block-compressed are tiled and
uncompressed), while 1595 other creates carry `ubwc=1` on 3925.6 MiB - so the field is alive and the
no-list set is the only large body of bytes with no compression at all.

**(b) The swizzle question, closed by code and by two older runs.** Asked whether a channel swizzle could
be added on a740 to recover the cross-order read that `XV` measures (`XV[RGBA8_as_BGRA8] … the view is
ignored`, `XV[BGRA8_as_RGBA8] … memory is swapped`, both on the dropped `0014 v2`, both green on the ship
tree), the answer is in `fd6_pipe2swap()`: *"It seems CCU ignores swap and always uses WZYX when tiled.
TP, on the other hand, always respects swap. We should return WZYX such that CCU and TP agree"*
(`src/freedreno/fdl/fd6_format_table.c:399-404`), reached for `tile_mode && !is_mutable`. So the component
that cannot swap is the **CCU, i.e. UBWC**, not the tile layout, and the gap is that on gen2 the store and
the view disagree - journal 21.4, measured: *"the swap is applied once instead of twice"*, `0x5a5a0000`
read back as `0x5a00005a`. That is exactly what `experiments/exp-10-is-mutable-without-ubwc.patch` tried
and what ADR-0009 withdrew, with the second half - UBWC-metadata reinterpretation - named there as an
a750 capability this chip does not have. Two consequences worth writing down: the demotion is what makes
the driver **conformant** (the create succeeds, every view reads correctly, the driver just chooses a
layout it can serve), so there is no live spec violation to fix in this tree; and of the residue in (a),
the 2-byte half could not be helped by a swizzle at any price, because `R8G8_*` has a different tile
layout from other cpp=2 formats (`tu_clear_blit.cc:3443-3445`) - addressing, not channel order.

**(c) Which swap patches exist, and what each one was for** (asked directly on 21.11, recorded here
because the answer is easy to get wrong later). Two shipped patches are about channel order, and
neither adds a swizzle - they decide when the existing swap is uniform enough that no fallback is
needed: `patches/0005-turnip-mutable-uniform-swap-tiling.patch` ("a uniform-swap list stays tiled",
probe `S` FAIL -> PASS) and `patches/0010-turnip-single-channel-swap-tiling.patch` ("a
single-channel format does not argue about channel order", 2 of 72 classes, extends 0005's
`tu6_format_list_swaps_are_uniform()`); `0006` puts `B8G8R8A8` and its INT form in one UBWC compat
type. Attempts to *widen* the swizzle were all built and all measured:
`experiments/exp-2-force-is-mutable.patch` broke the read (journal 14.5.1, `T-tr` 0 -> 261120/262144
when `is_mutable` is forced); `experiments/exp-4-force-wzyx-when-mutable.patch` - the one patch here
that really edits `fd6_pipe2swap()`, by dropping `&& !is_mutable` - *cures* that corruption
(`T-tr` 261120/262144 -> 0/262144, `S-tr` 16384/16384 -> 0/16384, journal 14.5.1, artifacts
`results/test-expD-control.log` and `results/test-expD.log`), but it cures it by making store and
view agree on `WZYX`, which is the opposite of expressing a cross-order view;
`experiments/exp-9-single-channel-swap-vacuous.patch` is the ancestor of the shipped 0010; and
`experiments/exp-10-is-mutable-without-ubwc.patch` is the shape "swizzle in tiled with UBWC off",
measured in 21.4 as 261119/262144 wrong (`0x5a5a0000` read back as `0x5a00005a`) with the `R32_UINT`
view it was meant to fix unchanged to the byte. Nothing of that kind is in the ship stack, and
ADR-0009 records why: the swizzle half is curable by forced `WZYX`, the UBWC-metadata half is not,
and on this chip they arrive together.

The one place the tree itself asks for a swap change is narrower than either, and it is now counted:
`tu_image.cc:516-521` forces linear tiling when `VK_IMAGE_USAGE_HOST_TRANSFER_BIT_EXT` is used with a
swapped format ("Because tiled images are stored without the swap, we would have to apply the swap
when copying on the CPU, which for some formats is tricky. TODO: should we add a fast path for BGRA8
and allow tiling for it?"). That branch is gated on the host-transfer usage bit and on nothing else -
and `results/imginv-usage-bits.log` (regenerate:
`python3 scripts/imginv-usage-bits.py results/raw/game-patched-imginv{4,5}.log
results/raw/game-patched-stockflaginv.log`) counts **0** host-transfer images in all three game
inventories (3638 / 4176 / 4170 creates). The bit value is from the header the tree builds with -
`VK_IMAGE_USAGE_HOST_TRANSFER_BIT = 0x00400000`, `include/vulkan/vulkan_core.h:2815` at `6dfa32a`,
with the `_EXT` form at 2833 an alias - not from memory, which is the mistake this sentence exists to
prevent: an earlier count of the same field used `1<<18` and was wrong about the value while
accidentally right about the answer, because the largest usage mask any create in those inventories
carries is `0x117`. So the upstream TODO is worth zero bytes in this workload: not "unmeasured", but
counted absent.
