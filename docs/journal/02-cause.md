# 2. Cause

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

Turnip exports the `sparseResidencyImage2D` feature only when two conditions
hold:

- `has_sparse_prr` — PRR is supported by the hardware and the kernel; it works
  on the RP6;
- `ubwc_all_formats_compatible` — "a UBWC image can be reinterpreted into a
  different format"; the driver claims this **only for gen3 / A750+**, on gen2
  it was never checked.

A740 is gen2, so the second condition is always false. The feature is not
exported, vkd3d doesn't hand out TILED, and 12_0 becomes unreachable.

The obstacle is exactly one thing — exposing the feature. The hardware and
kernel are fine: VM_BIND and PRR exist on the RP6, the driver detects and uses
them. On the sparse path Turnip disables UBWC entirely, so format casting is
impossible there and the gate is redundant.

Removing the gate is a single line: drop `&& ubwc_all_formats_compatible` from
the exposure condition. On gen2 this flag is always false anyway, so the gate
was the only obstacle there, while on gen3 and newer it stays in force.

The exposure condition **does not depend on the chip**: after the edit
`sparseResidencyImage2D = has_sparse_prr`, and PRR comes from the kernel
(`MSM_PARAM_HAS_PRR` for drm/msm, `kgsl_is_virtual_bo_supported` for kgsl).
Therefore the gate is removed identically for gen1 (FD725/FD730) and for a6xx
(Adreno 640 and neighbors) — `ubwc_all_formats_compatible` is not set for them
either, so the stock driver didn't hand them the feature. From there everything
is decided by vkd3d: the steps of
`d3d12_device_determine_tiled_resources_tier` (`device.c:8898`) check only the
features and sparse properties that turnip exposes the same way for all chips
(`tu_device.cc:1321-1325`), so with PRR present the result is the same
everywhere — `TIER_2` (the third step runs into the lack of 3D sparsity) and
feature level 12_0 is reachable. This was not tested on FD730/Adreno 640:
neither the kernel (needs a fresh msm drm with `MSM_PARAM_HAS_PRR`) nor a run.

Turning the flag itself on in `a7xx_gen2` is worse, and this is now a
measurement, not a hypothesis. The flag denotes a specific hardware mechanism:
the driver sets the `MUTABLEEN` bit in the texture descriptor, and the hardware
with it must correctly reinterpret UBWC when the format changes. Upstream
introduced it only for A750+ ("A750+ added a special flag"), although the bit
in the register map is declared for a7xx as a whole, and nobody has tested A740
in this respect. The check has been done — **A740 can't do this**, see below.
The Vulkan spec says nothing about UBWC: it is Adreno proprietary compression,
and in API terms such a claim cannot be expressed — it had to be checked by
behavior.

### On what grounds `False` for A740

This deserves separate treatment, because `False` is easy to mistake for a
tested result. Checked against the sources and the generated header
`freedreno_devices.h` (33 `__info*` records):

- the property is declared as a plain `bool ubwc_all_formats_compatible;`
  (`freedreno_dev_info.h:408`) with no initializer, so unset fields equal
  `false` — the codegen enumerates only explicitly set properties;
- in `freedreno_devices.py` the property occurs **exactly once** — line 878,
  in the `a7xx_gen3` block. Neither `a7xx_base` nor `a7xx_gen2` set it;
- in the generated header the flag is present in 7 of the 33 records, and our
  `FD740` (`__info23`, chip-id `0x43050a01`) is among those without it;
- confirmed by measurement: the stock driver reports
  `sparseResidencyImage2D=0`, the patched one — `1`.

So `False` is **the absence of the flag, not a test result**. The grounds for
`True` come only from the upstream comment: "A750+ added a special flag that
allows HW to correctly interpret UBWC, including UBWC fast-clear when casting
image to a different format permitted by Vulkan" — i.e. knowledge about A750,
extrapolated back to the whole a7xx line. Meanwhile the `MUTABLEEN` bit in the
register map is marked `variants="A7XX-"`, i.e. the position is declared for
all a7xx including gen2: **declared does not mean it works**.

### Check on A740: MUTABLEEN does not work

The question is settled by two experiments. The first turns the flag on and
shows that MUTABLEEN breaks reads; the second isolates the cause, because the
first changed two variables at once.

**Experiment 1** — one line `ubwc_all_formats_compatible = True` in the
`a7xx_gen2` block. The rebuild is incremental (codegen + linking), and in the
generated header the flag is confirmed for records 22–32 (was 26–32), i.e. it
also turned on for our `__info23` (FD740).

Probe **H** is the only one that can reach MUTABLEEN at all: a non-sparse
image + `MUTABLE` with the list `{RGBA8, R32_UINT}`, and those two formats have
different `fd6_ubwc_compat_type`. All sparse probes (B, E, F, S2) don't engage
MUTABLEEN: on the sparse path `ubwc_possible()` is always false, UBWC is off
there regardless of the flag.

| | flag off (upstream) | flag on |
|---|---|---|
| `H` memreq | `0x100000` — no UBWC metadata | `0x102000` — **UBWC turned on** |
| `H d2'` — 8888 view (same class as base) | `TRANSFORMED` | `TRANSFORMED` — **unchanged** |
| `H d1'` — R32_UINT view (different class) | 0 mismatches, **EXACT** | 8 mismatches, garbage |

`memreq` grew to `0x102000` — so the `is_mutable = true` branch really was
taken and UBWC really turned on, rather than "the flag changed nothing". A view
of the same class as the base format (`d2'`) reads byte-identically: MUTABLEEN
does not participate in this read, and this is a control showing the problem is
not a general breakage of compression. But a view of a different class
(`d1'`, R32_UINT over RGBA8) — exactly the one whose reading MUTABLEEN
regulates — fell apart.

**But the conclusion about MUTABLEEN by itself did not follow from this.** Two
things changed at once: the MUTABLEEN bit and the composition of the list
(cross-class versus single-class). "Something else turned on" is a legitimate
objection.

**Experiment 2** separates them. From the code it is visible that
`is_mutable = true` sits in exactly one branch — the `else` of
`!mutable_ubwc_fc` — and that whole branch lies inside
`if (!tu6_mutable_format_list_ubwc_compatible(...))`. So for probes T and S
(lists 0006-compatible) the block is not executed at all, and MUTABLEEN is
**not set** there, even though UBWC is on and reads are exact. This already
shows that UBWC on a mutable image works by itself, and the suspicion "something
else turned on" is half-dispelled. To close it entirely, MUTABLEEN is forced
unconditionally for all mutable non-depth images — **with the flag off** — so
that no new format list is allowed and no probe changes its layout.

The result — and it is stronger than what the first experiment gave:

| probe (list **the same** as 0006) | without MUTABLEEN | MUTABLEEN forced |
|---|---|---|
| `T-tr` (BGRA8_UNORM/BGRA8_UINT, UBWC) | **0/262144** | **261120/262144** |
| `S-tr` (BGRA8, sparse) | **0/16384** | **16384/16384** |
| `H` memreq / `d1'` | `0x100000` / EXACT | `0x100000` / EXACT — **unchanged** |

`H` didn't move by a single bit — so the variable "list composition / layout /
other inclusions" is indeed ruled out, and what breaks is **MUTABLEEN itself**.

Moreover it breaks not only on cross-class pairs but also on exactly the
BGRA8_UNORM/BGRA8_UINT pair that 0006 relies on. The character of the
corruption is telling:

```
t-uint y0 x0: read 0x000000a5 want 0x00a50000
S-tr  (0, 0):  got  0x00a50000 want 0x000000a5
```

What was read is **exactly what was written** (`fill2[0] = 0x000000a5`), but the
B↔R channel permutation disappeared, i.e. `want` and `read` swapped places. The
data is not garbage — the byte order is broken. This is precisely the mechanism
described by the upstream comment in `tu_clear_blit.cc:5547`: "the attachment in
GMEM ignores the swap except when MUTABLEEN is enabled".

**Conclusion: `ubwc_all_formats_compatible` on gen2 must stay `false`, and this
is now a measurement, not conservatism.** A740 does not reinterpret the
programmable format with MUTABLEEN: the data is preserved, but the channels end
up in the wrong place. Hence the second, more important consequence for the
patches: **MUTABLEEN must not be turned on on gen2 with any list**, therefore
0006 must solve the problem by merging types rather than by allowing the flag —
and that is how it is done. Checked separately: in the patched tree `is_mutable`
is assigned `true` in exactly one line, and it sits inside the branch that 0006
makes unreachable for compatible lists; `T-tr` and `S-tr` give 0 mismatches.

Changes in probes with the flag turned on are explained as follows: B, E, F and
S2 started to be created (gate 0004 is bypassed by the first clause of the
predicate), and they read correctly at that — `0x37` in the bound tile, zeros
outside it — because the sparse path is tiled even without UBWC, and the
linear+sparse hole does not occur there. So these changes are harmless; the
harm is concentrated in non-sparse MUTABLEEN.

Run logs: `results/test-mutableen.log` (experiment 1),
`results/test-expC.log` (experiment 2), `results/test-patched.log` (the
reference — any clean rebuild matches it byte for byte). The experiment patches
are in `experiments/`; they are **not intended for commit** and are not part of
0004–0006.

### Applicability scope of 0004 — gen1 and gen2

The flag exists on `a7xx_gen3`, hence on A750 and all a8xx (810, 829, **830**,
840, X2-85/90). On them `sparseResidencyImage2D` is exported by the stock
driver, and 0004 there is not just redundant but unreachable: even with a NULL
list the mutable image stays tiled, because when `mutable_ubwc_fc == true` the
branch sets `is_mutable = true` and only clears UBWC, without touching
`force_linear_tile`. The linear+sparse hole does not occur on gen3, hence the
rejection on create doesn't trigger either.

Gen1 is FD725/FD730, gen2 is X1-45/FD735, **FD740 + X1-85 (ours)**, FDA32,
**FD740v3 (Quest 3)** (`docs/a7xx-gen-props.md`, binding table). None of them
has the flag — previously FD730 was mistakenly listed here as gen2 — so the
rejection on create is needed on all chips outside gen3.

For removing the gate this question isn't even needed. On the sparse path UBWC
is disabled unconditionally: `ubwc_possible()` returns false for
`SPARSE_RESIDENCY`. It was assumed that the reason was only leftovers of
fast-clear — that's half-truth; the real reason is structural, see below. In
any case the gate checks a capability that the sparse path doesn't use anyway —
removing it is safe regardless of the answer about A740.
