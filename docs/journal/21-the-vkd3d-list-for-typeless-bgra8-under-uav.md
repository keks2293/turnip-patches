# 21. The vkd3d list for typeless-BGRA8 under UAV: where tiling is lost and what MUTABLEEN does

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

The list that vkd3d-proton builds for typeless-BGRA8 under
`D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS`
(`d3d11_device.c` / `resource.c:393-401`, the D3D11 rule about typed UAV load):

```
B8G8R8A8_UNORM, B8G8R8A8_SRGB, R32_UINT, R32_SINT, R32_SFLOAT
```

Five formats, three of them single-channel. On stock the list goes to
**linear**, and these are the only 2 classes out of 72 that stock sends there
(`B8G8R8A8_TYPELESS+UAV` and `B8G8R8X8_TYPELESS+UAV`). Below is a measurement
of what happens with this list when tiling is kept after all.

### 21.1 How tiling was measured

Two detectors, both in probe `probe_mixed_swap_uav()` (tag `V`):

| detector | how | verdict |
|---|---|---|
| `memreq` at 512×512 | `vkGetImageMemoryRequirements` | **useless**: tile 64×64, 512×512 divides exactly 8×8, tiled and linear give the same `0x100000` |
| `memreq` at 500×500 | same | linear = `0xfa000` (row padded to 500×512×4), tiled = `0x100000` (padded to 512×512) — **distinguishable** |
| `SPARSE_RESIDENCY` + `TILING_OPTIMAL` | `vkCreateImage` | `SUCCESS` = tiling, `FEATURE_NOT_PRESENT` = linear (`tu_image.cc:660-664`) |

The tiling decision doesn't depend on the image size, so a 500×500 image sets
the same flag as the working 512×512. This is the only detector with which
**different driver versions** can be compared: the `SPARSE_RESIDENCY`
restriction under linear is `patches/0004-turnip-sparse-residency-gate-lift.patch`,
it doesn't exist upstream, and the system driver answers a sparse-create with
`SUCCESS` regardless of tiling.

A second important point about the sparse detector: the image for it must be
`TILING_OPTIMAL`. With `TILING_LINEAR` the result speaks about the modifier
choice rather than the format list, and the two detectors start contradicting
each other.

### 21.2 Three modes, one binary

Probe V makes two images with **the same** list: `t=0` — forcibly
`TILING_LINEAR` (reference), `t=1` — `TILING_OPTIMAL` (whatever the driver
decided). Filling via `vkCmdCopyBufferToImage` in the image's format
(`B8G8R8A8_UNORM`), reading — with the compute shader `cast_r32` through
`usampler2D` + an `R32_UINT` view, i.e. the **second** view is measured. The
BGRA8 side (fill and readback in the image's format) is measured by probe U,
class `B8G8R8A8_UAVLIST`.

| mode | 500×500 detector | UBWC | probe U (BGRA8 side) | probe V (R32 view vs linear) |
|---|---|---|---|---|
| system stock | `0xfa000` → **linear** | off | EXACT `0/262144` | matched `262144/262144` |
| stack 0004–0009 + exp. 0008 + **exp. 0009** | `0x100000` → **tiling** | off | EXACT `0/262144` | **diverged `261120/262144`** |
| same + **exp. 0010** (MUTABLEEN without UBWC) | `0x100000` → tiling | off | **MISMATCH `261119/262144`** | diverged `261120/262144`, byte-for-byte the same numbers as for 0009 |

Logs: `results/test-V-stock-linear.log`, `results/test-V-exp0009-tiled.log`,
`results/test-V-exp0009-0010-mutableen.log`.

Word values, for clarity:

| texel | written | linear (reference) | tiled |
|---|---|---|---|
| (0, 0) | `0x11223344` | `0x11223344` | `0x11443322` |
| (256, 256) | `0x11243444` | `0x11243444` | `0x11443424` |

In bytes this is a swap of byte 0 and byte 2: `[44,33,22,11] -> [22,33,44,11]`
and `[44,34,24,11] -> [24,34,44,11]`. So on tiling the linear→tile transition
lays out the four B8G8R8A8 components in tile order, and the `R32_UINT` view
hands out this same raw word with the swap.

### 21.3 exp-9: tiling obtained, BGRA8 untouched, the R32 reinterpretation changes

`experiments/exp-9-single-channel-swap-vacuous.patch` removes the
over-cautiousness in `tu6_format_list_swaps_are_uniform()`: a single-channel
format has no channel order to argue about with a foreign format; only block
shape must match, because the tile layout is a function of
`util_format_get_blocksize()` (`fd6_layout.c:115`) and nothing more.

The model over 72 classes (`scripts/fmt-list-gate-check.py --exp-9`)
matched the measurement: **exactly 2 classes** flip, and both are
typeless-BGRA8/BGRAX8 under UAV. The cross-order `{B8G8R8A8, R8G8B8A8}`, the
BGR family `{B5G6R5, B5G5R5A1}`, `ZINK_BIND_MUTABLE` without a list and NV12
remain linear — verified by separate lines in the model's output.

What this means in substance:

* **The gain is real.** The vkd3d list for BGRA8-UAV is the most common case
  (a typical texture with a UAV flag), and it gets tiled instead of linear.
  UBWC on it is off anyway, so the gain is exactly in the tiling.
* **The BGRA8 side is untouched.** Fill and readback in the image's format —
  EXACT, `0/262144`. So ordinary SRV/UAV access to such a resource reads
  exactly the same as on linear.
* **Only the second view changes.** The `R32_UINT` view hands out the word with
  byte 0 and byte 2 swapped. For a D3D11 typed UAV load this is exactly the
  case for which vkd3d adds `R32` to the list.

### 21.4 exp-10: MUTABLEEN without UBWC — worse than doing nothing

`experiments/exp-10-is-mutable-without-ubwc.patch` sets
`is_mutable = true` inside the `else if (!mutable_ubwc_fc)` branch
(`tu_image.cc:558`), where UBWC is already off — i.e. exactly that combination
`tiled + UBWC off + MUTABLEEN` that remained unmeasured in journal 14.

The measurement gives an all-around "no":

* The `R32_UINT` view **didn't change by a single byte** relative to the run
  without MUTABLEEN — i.e. the experiment didn't achieve its goal.
* The BGRA8 side meanwhile **broke**: `261119/262144` words MISMATCH,
  `pat=0x5a5a0000 got=0x5a00005a`, `zeros=0`, "untouched (0xCD)=0" — i.e. this
  is not a lost write but a genuine permutation.

The character of the breakage is the same as in journal 14 for probes T and S: **the
swap is applied once instead of twice.** The write goes through the layout,
where `fd6_pipe2swap()` under tiling forcibly returns WZYX to all formats
except `is_mutable` (`fd6_format_table.c:396-398`), while the read goes through
the view, where at `is_mutable` the format returns its own WXYZ
(`fd6_texture_format`, `fd6_view.cc:252`). Previously this wasn't visible
because probes H/T/S/S2/S3 used lists with the **same** swap: the asymmetry
doesn't show up there. The vkd3d list is the first measured list where the
swaps diverge, and on it the breakage is visible immediately.

**The gap in `is_mutable` measurements is closed:** the problem is not in the
missing UBWC/sparse combination but in `is_mutable` itself on gen2 with
diverging swaps. `is_mutable = true` is set in exactly one branch
(`tu_image.cc:591`), and the unreachability of that branch on gen2 was a
consequence, not a cause.

In the gate model this is reflected by a flag rather than by substituting the
layout: `tu_image_init(..., exp_10=True)` gives `tiled, no-UBWC, MUTABLEEN` —
the tiling doesn't change, only the contents do. That's exactly what the
measurement shows, and precisely why the flag is useless as an optimization.

### 21.5 What remains unclosed

* **1024 words out of 262144** in the tiled run matched the pattern even though
  the other 261120 diverged. The mismatches run from (0,0) to (511,511), i.e.
  this tail lies in the middle and doesn't follow the geometry of the
  64-texel chunks. exp-10 gives **exactly the same number**, so this is
  not an artifact of a single run; the cause is not established. The share is
  0.39%, it doesn't affect the verdict.
* **A view in the `B8G8R8A8_UNORM` format through `usampler2D` is unreadable** —
  this is invalid usage (the shader expects an integer format); the probe gave
  the same garbage `0xffcdcd89` in both modes. Therefore probe V measures only
  the R32 channel, and the BGRA8 side is measured by probe U. For completeness
  a separate float shader (`sampler2D` + `vec4`) would be needed, but it changes
  nothing: the BGRA8 side is already covered by probe U through the image's
  format.
* **Whether vkd3d sees this difference in practice.** For the gain it matters
  that the `R32` members of the list are auxiliary: vkd3d adds them to allow
  typed UAV load and usually creates a view in the resource's own format. This
  couldn't be verified against vkd3d's code — there are no vkd3d-proton sources
  on the machine.
* **Ship status of 0009.** The tiling gain is measured, the BGRA8 side is
  untouched, but the change in visibility through the `R32` view is real, not an
  artifact. Formally exp-9 belongs to `experiments/` until it is decided whether
  D3D11 code accesses the 32-bit raw reinterpretation of BGRA8. This is the
  same class of caveat as in journal 16 for the cross-order, and its risk is lower (it
  affects only raw-32 reads, not the picture).

### 21.6 What remains after 0010: the 38 "tiled, no-UBWC" classes analyzed by blockers

After 0010 no class of `tests/vkd3d-fmt-classes.h` goes into linear. What
remains is the single unused lever — removing UBWC on the 38 classes that live
in the `tiled, no-UBWC` mode. The question is whether this is blocked by the
gate (then the rule can be edited) or by the format itself (then there is
nothing to do).

#### 21.6.1 The model didn't distinguish these two cases

`fd6_ubwc_compat_mode()` returns `UNKNOWN_COMPAT` for a format that has no row
in the blob table, and `tu6_mutable_format_list_ubwc_compatible()` silently
returns `false` on that. `UNKNOWN` by itself means two different things, and
the model conflated them: either there is no compatibility in hardware, or the
compatibility exists and the table just doesn't know about it. Analyzing this
by enumeration is pointless — a measurement is needed.

Additionally the model didn't account for `has_8bpp_ubwc`: a property from
`freedreno_devices.py` by which on gen2 UBWC for 8-bits-per-block formats is
disabled entirely, regardless of the gate.

#### 21.6.2 Probe CEIL: gate or format

A probe `probe_ubwc_ceiling()` was added — only `memreq`, no fill or read. Three
images with the same list: linear (size reference), the same format **without**
a list (what it can do by itself) and the same with `MUTABLE_FORMAT` (what the
gate decided). It distinguishes exactly what is needed:

| line | meaning |
|---|---|
| `no ceiling` | `nonmut == lin`: the format holds no UBWC under any list |
| `GATE REMOVED` | `nonmut > lin`, but `list < nonmut`: the gate removed what the format can do |
| `gate is not in the way` | the list made nothing worse |

The point of the split is this: at `n = 1` the gate function returns `true`
unconditionally (`tu_formats.cc`, the `viewFormatCount == 1` branch), i.e. a
single format passes the gate entirely. So `nonmut > lin` is a statement about
hardware, and `list < nonmut` is a statement about the rule.

Logs: `results/test-CEIL-stock.log` (system stock from `/usr`, without the
project's patches), `results/test-CEIL-base.log` (working stack 0004–0009), and
`results/test-CEIL-exp0011.log` (the same stack plus 0011). The first two lines
of section 21.6.3 are about stock; the isolated A/B is in 21.6.4.

#### 21.6.3 Stock: the 41 classes without UBWC split into 18 and 23

The model (`--blockers`) and the measurement agreed on the boundary:

| group | size | blocked by | cured by the rule? |
|---|---|---|---|
| BC1–BC7, NV12, P010, P016 | **18** | `ubwc_possible()`: compressed and planar | **no** |
| R8_*, R16_*, R32G32B32_*, R10G10B10A2_*, B8G8R8A8_TYPELESS+UAV | **23** | the gate itself | **yes** |

The first 18 are a false target. `vk_format_is_compressed()` and
`vk_format_get_plane_count() > 1` cut them off before the gate is even
reached, and no edit of `fd6_ubwc_compat_mode()` touches them.

The second 23 are the only ones where an edit makes sense, and within them the
measurement split things that the model reported as one block:

| format | stock | conclusion |
|---|---|---|
| `R8_UNORM`, `R8_UINT` | `nonmut == lin` | **no ceiling.** `has_8bpp_ubwc = false` is a workaround for a text corruption bug (`0f770caa232`, "Disable 8bpp_ubwc on a6xx gen2", corruption in VSCode on a680), not a measured incapability — re-enabled and measured (21.7, re-verified 18.11 in split-submit mode): the contents of a740 are corrupted, the flag must stay False |
| `R32G32B32_SFLOAT/UINT/SINT` | `nonmut == lin` | **no ceiling.** The rows exist in `fd6_format_table.c` but without a render buffer: `VT_(R32G32B32_UINT/SINT/FLOAT)` — vertex and texture only (`VT_` = `FMT(pipe, fmt, fmt, NONE, swap)`, file header), while `V__` for UNORM/SNORM has no texture at all. There are no rows in the compat table, and UBWC is not visible in the measurements |
| `R16_*` (4 classes) | `nonmut = 0x82000` > `lin = 0x80000`, `list = 0x80000` | **the gate removed what the format can do.** There is a ceiling |
| `R10G10B10A2_TYPELESS` | `nonmut = 0x102000` > `lin = 0x100000`, `list = 0x100000` | **same.** There is a ceiling |

#### 21.6.3a How this looks on the working stack

The analysis above is on stock, where the `_SFLOAT` classes and cross-order
lists are not yet fixed. On the working stack (`0004, 0005, 0006, 0009, 0010,
0012`) of the 72 classes 36 hold UBWC, **0 linear**, and 36 remain in
`tiled, no-UBWC` — before 0012 and 0010 there were 38 of them. The breakdown of
these 36:

| what | size | can it be edited |
|---|---|---|
| BC1–BC7, NV12, P010, P016 | **18** | no: `ubwc_possible()` |
| `R8_TYPELESS`, `R8_UNORM/UINT/SINT/SNORM` | **5** | no: `has_8bpp_ubwc = false` |
| `R32G32B32_TYPELESS/UINT/SINT` | **3** | no: no ceiling |
| `R16_*`, `R10G10B10A2_*` | **8** | **yes: 0011** |
| `B8G8R8A8/B8G8R8X8_TYPELESS+UAV` | **2** | no: two compat classes in one list |

In total **26 of 36 cannot be closed**, 0011 closes 8, and 2 run into the fact
that vkd3d itself puts two different classes into the list (`B8G8R8A8_UNORM`
for typed reading and `R32_*` for typed UAV load) — this is not a defect of the
rule but the structure of the list.

Update (after 0012 A+B and the CEIL control, 18.11):

* **The BC rows: the 15 BC classes of the vkd3d lists are closed** - 0012
  stage A (the BC exclusion in `ubwc_possible()`) + stage B (the compat
  rows). An attribution correction: in stock BC+UBWC is **not enabled** -
  `ubwc_possible()` cuts `vk_format_is_compressed()` as a whole (verified
  with `git show HEAD:src/freedreno/vulkan/tu_image.cc`, there is no BC
  exclusion in stock); the BC+UBWC in the tree is our patch. On the A740:
  all 15 classes `V[vkd3d] mut=SUCCESS`, the U probe `list = lin + 0x2000`
  (`results/test-BCUBWC-stageAB.log`). NV12/P010/P016 (3) remain closed
  (planar).
* **R32G32B32: the "no ceiling" attribution is wrong.** The 128-bit control
  `CTRL_R32G32B32A32` **gets** UBWC (`lin=0x400000 nonmut=0x404000`,
  `results/test-BCcopy-base.log`) - the family has no ceiling; the 96-bit
  formats (cpp=12) are cut by the layout gate
  `!util_is_power_of_two_or_zero(cpp)` at `fd6_layout.c:127` (the comment
  "R8G8B8 and other 3 component formats don't get UBWC"), not by
  `ubwc_possible()`. A dead end confirmed, the priority is low.
* The updated count: of the 36 - **15** are closed by 0012 A+B, **8** are
  closed by 0011, **11** cannot be closed (NV12/P010/P016 + R8 +
  R32G32B32), **2** run into the structure of the list.

A caveat about method: the first version of this breakdown grouped by name
prefix, and `G16_B16R16_2PLANE_420_UNORM` fell into the `R16_*` group and
`G8_B8R8_2PLANE_420_UNORM` into `R8_*`, because `R16_` and `R8_` occur in them
as substrings. The final numbers above were counted in reverse order, with
`is_compressed()` checked first, and they add up to 72 (36 + 36 + 0).

The whole breakdown is reproducible with one command — `report_stack()` in
`scripts/fmt-list-gate-check.py`, flag `--stack`.

#### 21.6.4 exp-11: rows for R16_* and R10G10B10A2_*

`experiments/exp-11-ubwc-compat-r16-and-10bit.patch` adds two compat
classes to `fd6_ubwc_compat_mode()` that don't exist in the stock table:
`FD6_UBWC_R16_INT` (5 formats) and `FD6_UBWC_A2B10G10R10_INT` (2 formats).

Here the argument doesn't rely on a contradiction inside the source, as 0006
and 0008 did (those leaned on the stock comment "a630 blob allows these, but
not a660"). The support is the measurement of journal 21.6.3 plus the fact that both
formats are full-fledged on the texture path: in `fd6_format_table.c` there is
`VTC(R16_UNORM, 16_UNORM, WZYX)` (line 72) and
`FMT(R10G10B10A2_UNORM, …, WZYX)` (line 209), both with swap `WZYX`, i.e.
matching. The gap is exactly in the compat table, and the layout argument works
here in full: all variants of the same block size differ only in the
interpretation of the same bits,
`layout->cpp = util_format_get_blocksize()` (`fd6_layout.c:115`) doesn't depend
on the interpretation, and the swap is common to all members of the list — i.e.
the asymmetry that broke 0010 doesn't exist here by construction.

An error in the first version of this analysis, so as not to repeat it: the
absence of formats was searched via `grep A2B10G10R10 fd6_format_table.c`, i.e.
by the spelling of the Vulkan format, while the table uses pipe names
(`R10G10B10A2_*`). The empty result was interpreted as "the format isn't in the
format table either", although it is, lines 209 and 214. You must check by the
spelling the file actually uses.

The measurement is isolated: `results/test-CEIL-base.log` — the same stack with
0004–0009 and without 0011 (built by a `git apply -R` rollback),
`results/test-CEIL-exp0011.log` — the same stack with 0011. Comparing the
system stock with 0011 wouldn't do for this: `results/test-CEIL-stock.log` has
no patch 0004, and the differences in probes B/E/F/G0
(`sparseResidencyImage2D=0` versus `1`) belong to it, not to 0011.

A `diff` of the two isolated logs gives **exactly three changed lines for the
whole log**:

| class | baseline (without 0011) | with 0011 |
|---|---|---|
| `R16_TYPELESS` | GATE REMOVED (`list=0x80000`) | **gate is not in the way (`list=0x82000`)** |
| `R16_UINT` | GATE REMOVED | **gate is not in the way** |
| `R10G10B10A2_TYPELESS` | GATE REMOVED | **gate is not in the way** |
| `R8_*`, `R32G32B32_*` | no ceiling | no ceiling (untouched) |

On the working stack the model (`--stack`) gives 36 classes with UBWC out of
72, and with 0011 — **44**, i.e. 0011 closes 8 classes (5 on `R16` + 3 on
`R10G10B10A2`). The remainder 36 → 28 doesn't change in composition other than
these eight.

The names in the patch had to be pinned down against the compiler, and this is
worth recording because the obvious name is wrong:
`VK_FORMAT_A2B10G10R10_UNORM_PACK32` maps to
`PIPE_FORMAT_R10G10B10A2_UNORM` (`src/vulkan/util/vk_format.c:114`), while
`PIPE_FORMAT_A2B10G10R10_UNORM` never matches the `switch`. The first build of
0011 failed exactly on this.

#### 21.6.5 What 0011 doesn't prove

* **The contents under UBWC on the `R16_TYPELESS` list were not checked.** The
  CEIL probe measures only `memreq`. Removing the gate leads to `UBWC + tiled`,
  and if something besides the interpretation diverges between `R16_UNORM` and
  `R16_UINT` within one list, this would only surface via a byte roundtrip —
  the same one that broke in journal 14 and journal 21.4. The risk here is lower (all `R16_*`
  have the same swap, WZYX, so there will be no swap asymmetry), but the check
  hasn't been done.
* **Fast-clear** is not covered, as in exp-8.
* **`R10G10B10A2_SNORM` and `_SINT` were not added to the compat class.** 0011
  takes `_UNORM` and `_UINT` because in `fd6_format_table.c` the tiled entries
  exist exactly for them (`FMT` line 209 and `VTC` line 214); `_SNORM` and
  `_SINT` have `V__` there, i.e. no tiling. A list with them would run into the
  texture format table rather than the gate.
* **The classification of the 18 classes in the model is by the list of header
  lines**, not by measurement. The measurement confirmed the two main groups
  (`R8`, `R32G32B32`) as "no ceiling", but it wasn't run separately for all 18.

### 21.7 R8 and `has_8bpp_ubwc`: there is a memreq ceiling, the contents are corrupted (measurement 2026-10-02, re-verified 2026-11-18 with split submits)

The question "`has_8bpp_ubwc = false` on gen2 — protection against corruption
or does nothing break?" was settled by a measurement, without rebuilding: the
driver reads `FD_DEV_FEATURES` and overrides any prop
(`fd_dev_info_apply_dbg_options`, `freedreno_dev_info.c:85`),
`has_8bpp_ubwc` is present in the override table (generated
`freedreno_devices.h:159`).

First by the code: on a7xx_gen2 (FD740, `__info23` of the generated
`freedreno_devices.h`) the `has_8bpp_ubwc` field **doesn't exist at all** — the
C initializer zeroes it. An explicit `False` stands only for `a6xx_gen2/3/4`;
the a7xx chain `[a7xx_base, a7xx_gen2]` doesn't inherit from `a6xx_gen2`. So
the "a6xx gen2 bug workaround" was never carried over to a7xx — the flag simply
isn't set.

Then the measurement. `probe_ubwc_ceiling` for R8 on the baseline
(`has_8bpp_ubwc=0`) gives `nonmut == lin`, and this is **not** a statement
about hardware: the probe goes through `tu6_ubwc_possible()`, where
`has_8bpp_ubwc` is checked (`tu_image.cc:353`) **before** the compat gate. The
flag itself was lowering the "ceiling". With
`FD_DEV_FEATURES=has_8bpp_ubwc=1`:

```
base:   CEIL[R8_TYPELESS] lin=0x40000 nonmut=0x40000 list=0x40000 -> no ceiling
+flag:  CEIL[R8_TYPELESS] lin=0x40000 nonmut=0x42000 list=0x40000 -> GATE REMOVED
```

A `diff` of the whole CEIL block — exactly two R8 lines, the other 8 are
identical. Conclusion 1, as far as it goes: **the driver** allocates a metadata
plane for R8 once the flag is set (`+0x2000`), so the property is the only thing
that stops it. That is an allocation computed by `fd6_ubwc_alloc_size()`, not an
observation of the chip; whether the hardware can compress 8bpp is a separate
question, still open (see the third pass at the end of this section). The record
"no ceiling by measurement" in the analysis of the 36 classes was a confounded
quantity, not a chip property.

Then the contents: `probe_ubwc_class` (fill + readback) for R8 with the flag:

```
U[R8_TYPELESS] lin=0x40000 nonmut=0x42000 list=0x40000
  linear roundtrip:   0/65536 words EXACT
  nonmut roundtrip:   65536/65536 words MISMATCH  got=0x00000000 (all zeros)
  list roundtrip:     0/65536 words EXACT   (but list=lin: the gate removed UBWC, this is a linear test)
```

Conclusion 2: **the only path where UBWC is really enabled (nonmut, 0x42000)
reads pure zeros** — content corruption. "list EXACT" doesn't prove safety:
there the gate removed UBWC and the linear path is being measured. Conclusion 3:
`has_8bpp_ubwc` is **protection against real corruption** (the same class of bug
as on a6xx gen2, commit `0f770caa232`), keep it False.

Practical summary:

* The R8 classes (5) stay closed: not "no ceiling" but **"there is a ceiling,
  the contents are corrupted"** — a negative result on contents.
* `has_8bpp_ubwc=1` must **not** be enabled globally: single R8 images (not only
  mutable lists) would go down the broken UBWC path.
* R8 in `fd6_ubwc_compat_mode()` (in 0011 or separately) must **not** be added:
  mutable R8 lists would get UBWC and corruption.
* A false alarm was caught at the verification stage: "list EXACT" with the gate
  removed looks like success but measures the wrong thing. The rule: a roundtrip
  proves safety only for the mode that actually received UBWC
  (`nonmut/list > lin`).

**Update 20.11 (probes Z/AA/AB, grid sweep, allocation dumps).** Two things in
the conclusions above were stronger than the evidence, and one is now resolved:

* "the contents are corrupted" was measured through one engine. Probe Y (same
  section, `results/test-y-8bpp-{off,on}.log`) reads the image through the TP as
  well: at `has_8bpp_ubwc=1` both readers lose the content (195840 of 262144
  wrong, 196864 zeros — the counter prints wrong elements, journal 22.1), so the loss is
  in the driver/hardware interaction, not in one engine - which also means the
  "same class of bug as a6xx gen2 / CCU coherency"
  comparison is not supported by measurement.
* Conclusion 1 never said anything about the chip. `+0x2000` is
  `fd6_ubwc_alloc_size()`. Probe Z measures the chip: the NV12 Y plane (`cpp == 1`
  UBWC, grid `{32,8}`, not gated by the property) round-trips **EXACT** at 512x512
  and 256x256, both tilings (`results/test-z-nv12-y8.log`) - so a740 does compress
  an 8-bit UBWC plane today. What it does **not** buy is the step to
  `FMT6_8_UNORM`: `registers/adreno/a6xx_enums.xml:114-116` warns that the two
  8-bit formats are not UBWC-compatible, so this is a working path for the video
  format, not proof that the R8 zeros are only misconfiguration. journal 22.2 has the
  wording; the stronger version this paragraph carried was mine and is retracted.
* Measured where the configuration diverges (`tests/tp8bpp.c` + dumps, journal 22.3/journal 22.4):
  the GPU writes **one metadata byte per 256 texels** for `R8_UNORM` (1024 B at
  512x512, 256 B at 256x256), regardless of the grid the
  driver's layout uses (override swept: `{16,4}`, `{32,4}`, `{64,4}`, `{64,2}`)
  and of the plane it reserved (8 KiB vs 16 KiB). That count is the cell count of
  `{32,8}`, the geometry NV12 Y uses, while Mesa reserves and walks `{16,4}` - four
  times as many cells. Programs `{32,8}` for plain 8bpp and the first submit that
  touches the image faults the GPU, so the remaining gap is beyond the geometry
  table (descriptor grid field / CCU setup). A `vkCmdCopyBufferToImage` fill leaves
  the R8 metadata plane entirely zero, while the 3D writer fills the 1024 bytes it
  writes and the top-left 256x256 quadrant is the only part that reads back.

Keep `has_8bpp_ubwc = False` on `a7xx_gen2`. The ~70 MiB of R8 images in RE4
(journal 25) is not a hardware limit and not a prop either: journal 22.3 shows the
readable area is exactly the top-left quarter at every image size, journal 22.4 shows no
metadata geometry moves that number, and journal 22.6 keeps the patch out of the stack -
what is left is descriptor/CCU work for a format the open stack has never driven.

Logs: `results/test-r8-has8bpp-on.log`, `results/test-r8-has8bpp-off.log`
(full `rp6-vkd3d-sparse-test` run with the added R8 probes, baseline
`drv-base.so`).

**Re-verification (18.11, lesson of 21.10 applied).** Conclusion 2 rested on a
`probe_ubwc_class` that executes b2i and i2b in one submit - exactly the chain
the CCU-clean bug (21.10) poisons: a readback can return pre-fill memory. The
October verdict was therefore method-suspect, "maybe the corruption was the
readback bug". Added `RK_SPLIT_SUBMITS=1` to the test: fill and readback go in
separate submits with a wait between them, the way games/vkd3d do it. Re-run on
build `c9dad346…` both ways:

| run | R8 nonmut memreq | R8 nonmut roundtrip | controls (RGBA8/BGRA8/R32_*, incl. UBWC nonmut) |
|---|---|---|---|
| baseline | 0x40000 (= lin, no UBWC) | 0 bad | 0 bad |
| `FD_DEV_FEATURES=has_8bpp_ubwc=1` | 0x42000 (UBWC) | 65536/65536 bad, all zeros | 0 bad |

Split mode itself is clean - every 4bpp control with real UBWC round-trips
exactly across submits, so cross-submit visibility is not the issue. The zeros
follow only the 8bpp UBWC mode. Conclusion 2 survives the BC lesson: this is
**content corruption, not a readback artifact**; keep `has_8bpp_ubwc` False.
Logs: `results/test-r8-split-on.log`, `results/test-r8-split-off.log`.

**Third pass (20.11): the counter that cannot fail, and the metadata grid.**
Counting non-zero words is not a content check: `texelFetch` of a 1- or
2-channel format returns alpha = 255, so the word is non-zero whatever `r`
holds, and for `R8_UNORM`/`R8G8_UNORM` the `T[...]` line can never fail (it
only says something where alpha comes from the data). The split-submit numbers
above do compare values, but only on the copy path, so "the write is broken"
vs. "the i2b read lies" was still not separated. Probe `Y` does that: a
checkerboard written by `vkCmdCopyBufferToImage` in its own submit, then values
compared on two independent read paths (d2r copy, `texelFetch`), with 2 and
4 B/texel controls in the same run.

| `has_8bpp_ubwc` | R8_UNORM 512x512, d2r copy | R8_UNORM 512x512, `texelFetch` | R16/R8G8/RGBA8 controls |
|---|---|---|---|
| `0` (as shipped) | `0/262144 EXACT` | `0/262144 EXACT` | EXACT |
| `1` | `261120/262144` bad, `got=0x00` | `261120/262144` bad, `want=0xff000007 got=0xff000000` | EXACT |

(`results/test-y-8bpp-off.log`, `results/test-y-8bpp-on.log`, lines `Y[...]`;
256x256, 128x128, 130x66 and `R8_UINT` behave like 512x512.) With UBWC on both
readers agree the content is gone, so the "only the copy read lies" branch is
closed and the off-run being exact shows the probe, the copies and the barriers
are fine — the failure is specific to UBWC-on-8bpp.

The one hypothesis left was the metadata grid: `fdl6_get_ubwc_blockwidth()`
gives cpp=1 the generic {16, 4}, while the other 8bpp UBWC users in the same
function — `PIPE_FORMAT_Y8_UNORM` and the Y plane of 2-plane YUV, which are
**not** gated by `has_8bpp_ubwc` — get {32, 8}, and r8g8 / the UV plane get
{16, 8}. Tested with a throwaway env override
(`experiments/exp-17-cpp1-ubwc-blockwidth.patch`, since reverted; the override
is live — `1x1` grows the R8 metadata plane from `0x2000` to `0x40000`):
{16,4}, {32,4}, {64,4} corrupt the content identically, {16,8}, {32,8}, {8,8}
take the GPU down with `VK_ERROR_DEVICE_LOST`
(`results/test-y-8bpp-sweep-blockwidth.log`). The grid is not the cause. Conclusion 2 (content corruption, with the driver's
own parameters) stands; Conclusion 1 shrank to what it actually measured - the
driver allocates the metadata plane - because nothing here observes the chip
doing 8bpp compression. `has_8bpp_ubwc` stays False, now on value-compared
evidence. What would separate "driver parameters" from "the chip cannot do it":
the NV12 Y plane, which is cpp=1 UBWC and is *not* gated by the property
(`ubwc_possible()` rejects 8bpp only for `plane_count == 1`, `tu_image.cc:366`),
so a correct round-trip there would show the chip compressing 8bpp today.

### 21.8 BC copy (r2d): fill OK, readback broken; 0013v1 rejected, 0013-A - the dst-buffer surrogate format (18.11)

Task: after 0012 A+B, check the byte roundtrip of BC through the copy
pipeline. The T probe in `tests/rp6-vkd3d-sparse-test.c` (512x512, pattern;
fill = `vkCmdCopyBufferToImage` x2, readback = `vkCmdCopyImageToBuffer`, both
directions through r2d on a7xx; TP-readback `texelFetch` for the fill, the
CPU comparison for the readback). The allowlist: the BGRA8/R8 controls +
BC1/BC3/BC7.

The measurement on base / A+B / 0013v1 - **the behavior is identical**, i.e.
the defect predates 0012 and does not depend on UBWC. Logs:
`results/test-BCcopy-base.log`, `results/test-BCcopy-0013.log`.

* The controls (BGRA8/R8): fill 100% nz, roundtrip EXACT.
* Fill BC3/7: 100%/98% nz - OK.
* Fill BC1: 86-98% nz - the first-fill defect (journal 20): the CPU decode of the
  pattern = 29594 zero texels, the hardware = 34971, an excess of ~2%; the
  second BC1 fill does not fix it completely.
* **The readback (image->buffer) is broken**: BC1 - all zeros; BC3/7 - the
  first 512 B are exact (= the 32 4x4 blocks of the first row,
  `bad[0]=128(r0,c128)`), further a mix of exact and zero words (the zero
  words in the tail are 15184/15552/15872 between runs - uninitialized
  memory), ~76% of the words match the expected pattern (part of the matches
  is an artifact of the repeating pattern).

The candidates and the results:

* **0013v1**: `r2d_dst_buffer()` programmed `FMT6_NONE` for BC
  (`blit_format_color()` -> `tu6_format_color`: the BC rows in
  `fd6_format_table.c` are `_T_`, there is no color write). The patch: a
  fallback to `fd6_texture_format()`. Built (out-0013, sha256 `8c73a859`),
  run - **no change at all** -> rejected. The artifact:
  `experiments/0013-experiment-r2d-dest-buffer-bc-format.patch`.
* **0013-A (the current candidate)**: reinterpret the dst buffer as a
  surrogate uncompressed format with the same number of bytes per 4x4 block:
  one block = one "texel" of the surrogate (an 8B block -> `R32G32_UINT`, a
  16B block -> `R32G32B32A32_UINT`). The geometry in
  `tu_copy_image_to_buffer` is already in block units (`copy_compressed()`
  divides the extent by 4), the pitch is already in bytes of a block row
  (128 x 16B = 2048B for the 512x512 BC3) - the byte layout matches exactly.
  The precedent for the same trick in the same file: `copy_buffer()`
  (buffer->buffer) has long used R32G32B32A32_UINT / R32_UINT / R8_UNORM as
  surrogates. **The image side stays BC**: the tiled layout of a BC image is
  incompatible with the reinterpretation to a surrogate (a BC tile 32x32
  texel = 8x8 blocks = 1KB, the surrogate tile 32x32 texel = 16KB - after the
  first tile the engine would read someone else's bytes). The working fill
  (buffer-src BC -> image-dst BC) is not touched.

An auxiliary fact: the buffer-src in the fill is programmed in **block units**
(`r2d_src_buffer_unaligned` receives the extent already /4) and it works -
i.e. for BC the A2D engine counts coordinates/sizes in 4x4 blocks. For the
image-src (`r2d_src`), `TPL1_A2D_SRC_TEXTURE_SIZE` is taken from `fdl6_view`
in **texel units** (512x512 instead of 128x128) - if 0013-A does not close
the readback, the next candidate (0013-B): divide SIZE by 4 for BC in
`r2d_src`.

The RE4 credit of the defect is ~0: the hot path of vkd3d is buffer->image
(fill - works), image->buffer over BC is a rare staging/feedback, the RE4 BC
textures are sparse -> UBWC is not allowed for them in the first place
(journal 21.9). The experiment goes for the correctness of the driver (and for the
sake of upstream), not for RE4.

### 21.9 The economics of BC+UBWC: not an RE4-perf lever (18.11)

The user's thesis (confirmed, fixed as the main conclusion): UBWC creates
fixed overheads - the meta/flag plane (+1-3% of VRAM, the alignment of both
planes), the flag read before every block, a possible decompress/resolve pass
on the copy/reinterpretation. On BC1-BC7 the data is already of a fixed bit
rate (indexed content, almost no compression) - there is no compression
gain, only the overheads remain. **Conclusion: for BC, UBWC has no perf
sense. "It seems this was in vain" - yes, for RE4.**

The corrections to the details:

* "The drivers deliberately disable UBWC for BC" - true for **stock turnip**:
  `ubwc_possible()` cuts `vk_format_is_compressed()` as a whole (verified
  with `git show HEAD:src/freedreno/vulkan/tu_image.cc` - there is no BC
  exclusion in stock; the earlier mark "the BC list is stock" was a mistake).
  The BC+UBWC in our tree is the patch 0012 stage A. The BC+UBWC rows are
  present in the blob compat table, and the A740 TP reads BC+UBWC at 100%
  (the T probe) - the hardware can, stock deliberately does not enable it.
* **Sparse residency is excluded from UBWC** (the stock `ubwc_possible()`,
  `tu_image.cc` ~:361: "UBWC isn't possible with sparse residency, because
  unbound blocks may have leftover fast-clear data..."). The RE4 BC textures
  are created by vkd3d as sparse -> **UBWC is not allowed for them at all**,
  regardless of 0012 A+B.
* Consequently **0012 A+B is not an RE4-perf lever**. The reclassification:
  completeness/blob compatibility (the 15 BC classes of the vkd3d lists get
  the UBWC semantics: fast-clear/flag, the memreq `+0x2000`), not a perf
  claim. The RE4 A/B (base vs A+B) over BC is expected to be ~0; the
  measurement is kept as a control, not as a lever.

The real UBWC levers of RE4 are not BC: the fast-clear R8G8 (block 1:
`QCTDD12766770`/`has_generic_clear`; 30.09: the gain from
`has_generic_clear` is -61..-65% of vkmark vertex/shading/texture, the cost
of the quirk is ~0, the verdict - keep the blanket) and the 8bpp classes
(journal 21.7 - there is corruption there, the lever is closed).

**Final verdict (18.11): exp-12 (BC+UBWC) is retired, the files are removed from
`experiments/` (restorable from history, `39e103d`).** Three independent reasons:
(a) not a perf lever - vkd3d creates RE4's BC textures sparse, and `ubwc_possible()`
forbids UBWC for sparse images regardless of any format gate; (b) stacking lossless
memory compression over block-compressed formats is a deliberate industry norm, not
a turnip gap - AMD's DCC and Intel's render compression (CCS) exclude BC formats the
same way stock `ubwc_possible()` excludes all of `vk_format_is_compressed()`;
(c) the remaining "blob compat" justification has no observable symptom to verify
against, the blob is closed. What the thread produced instead is worth more than
the patch: it surfaced a real defect - r2d readback (image->buffer) drops
zero-windows, geometry- and state-dependent and **not BC-specific** (a plain
RGBA32 128x128 fails with the same signature; the fill direction is byte-clean) -
see Bug 2 and journal 21.8. That defect is tracked and fixed as a separate correctness
line: vkd3d `CopyTextureRegion` texture->buffer goes through the same path -
though not as an in-submit chain: vkd3d submits between the copy and its use, so
RE4 itself does not hit the defect (see journal 21.10, closed without game A/B).
