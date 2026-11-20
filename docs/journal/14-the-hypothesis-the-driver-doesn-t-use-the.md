# 14. The hypothesis "the driver doesn't use the capabilities of the 750/830" — checked and rejected

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

### 14.1 Where the hypothesis came from

In the device table `common/freedreno_devices.py` our a740 gets
`[a7xx_base, a7xx_gen2]`, while a750 gets `[a7xx_base, a7xx_gen3]`. The flags
that only gen3 has look like unused capabilities:

| flag | meaning | effect on a740 |
|---|---|---|
| `load_shader_consts_via_preamble` | constants via preamble | **corruption, see 14.3** |
| `load_inline_uniforms_via_preamble_ldgk` | inline uniforms via preamble | test can't distinguish |
| `has_generic_clear` | one clear for sysmem+gmem | test can't distinguish |
| `has_gmem_vpc_attr_buf` | VPC in GMEM | test can't distinguish |
| `has_compliant_dp4acc` | signed SDOT | test can't distinguish |
| `has_persistent_counter` | counters survive suspend | test can't distinguish |
| `has_abs_bin_mask` | `CP_SET_BIN_DATA5::ABS_MASK` | test can't distinguish |
| `ubwc_all_formats_compatible` | UBWC for all formats | **brings back the stock hole** |
| `max_draw_states = 64` | state slots | one place in the code, no effect on FPS |

Important: this is not a division by generation but observations from the
Qualcomm blob for a specific chip. Formally the 830 doesn't take part in the
table.

### 14.2 How it was checked

`TU_FORCE_PROPS` was added by editing `tu_device.cc` — a comma-separated list
of flag names — plus `TU_MAX_DRAW_STATES`. This allows checking the hypothesis
with one rebuild instead of a rebuild per flag. Each applied value is printed
to the log; there is no silent ignoring. Patch `0007`.

The correctness check is `rp6-vkd3d-sparse-test` (`scripts/run-test.sh`), the
game is not launched. One caveat: the test doesn't render a scene, so it cannot
possibly refute the render-path flags (bin mask, generic clear, VPC). "No
difference" means "not covered by the test", not "safe".

Incidentally `scripts/run-test.sh` was fixed: it ignored `RP6_TEST_BIN` from
`env.sh` and used a hard-coded `./rp6-vkd3d-sparse-test`, i.e. it only ran from
`build/` and didn't run from the repository.

### 14.3 Result

**`load_shader_consts_via_preamble` does not work on a740.** The test catches
real corruption, not cosmetics:

- `T probe: FAIL` — `UINT view read=MISMATCH` (EXACT in the baseline)
- `S probe: FAIL` — `s-uint=8 mismatches`
- view-cast probe: reads `0x00000000` instead of `0x37373737`
- `t-uint y7 x128: read 0x800787a5 want 0x80a58707`

The hypothesis was rejected by measurement, not by reasoning.

**`ubwc_all_formats_compatible` must not be enabled.** With it `vkCreateImage`
(MUTABLE+SPARSE) starts returning `SUCCESS` — i.e. the driver is **lying**
again, and vkd3d gets a linear sparse instead of a tiled one. Exactly the hole
that patches 0004 and 0005 close: the baseline build honestly returns
`FORMAT_NOT_SUPPORTED` / `FEATURE_NOT_PRESENT`. The flag doesn't "enable a
capability", it brings back wrong behavior.

**The test can't distinguish the other six flags.** None showed either
corrupted data or changes. This is not proof of safety — it is simply outside
the test's coverage.

### 14.4 Can `ubwc_all_formats_compatible` be fixed by another flag

Hypothesis: since the corruption from `ubwc_all_formats_compatible` is "we read
what we didn't write", maybe a second flag (say about UBWC coherency) will
remove it.

**In the code — there is nothing to use.** In the whole path of creating a
mutable UBWC image exactly two properties are read:
`ubwc_all_formats_compatible` (`tu_image.cc:541`, `tu_formats.cc:248`) and
`ubwc_unorm_snorm_int_compatible` (`tu_image.cc:350`, `freedreno_ubwc.h`). The
second is **already enabled** on gen2. The other UBWC gates
(`has_8bpp_ubwc`, `supports_uav_ubwc`, `has_ubwc_linear_mipmap_fallback`,
`supports_linear_mipmap_threshold_in_blocks`) are enabled for us,
`broken_ds_ubwc_quirk` is not about color formats. What comes next is not a
property but a bit in the descriptor: `fd6_view.cc:265` sets
`A6XX_TEX_MEMOBJ_1_MUTABLEEN`, and `fd6_format_table.c:396` meanwhile changes
the swap (`if (tile_mode && !is_mutable) return WZYX;`). No prop affects this
calculation — the hardware decides.

The only candidate that even sounds like "we read the wrong thing" is
`ubwc_coherency_quirk` (gen3, `False` for us; at a barrier with a shader stage
it adds `CACHE_CLEAN`, `tu_cmd_buffer.cc:10108`).

**Check.** `ubwc_coherency_quirk` was added to the `TU_FORCE_PROPS` list
(patch 0007), one incremental rebuild, then four runs of
`scripts/run-test.sh` with no rebuilds:

| config | `TU_FORCE_PROPS` |
|---|---|
| base | — |
| `ubwc_coherency_quirk` | `ubwc_coherency_quirk` |
| `ubwc_all_formats_compatible` | `ubwc_all_formats_compatible` |
| combo | `ubwc_all_formats_compatible,ubwc_coherency_quirk` |

Logs: `results/test-props-base.log`,
`results/test-props-ubwc_coherency_quirk.log`,
`results/test-props-ubwc_all_formats_compatible.log`,
`results/test-props-ubwc_all+coherency.log`.

| | base | +coherency | +ubwc_all | +both |
|---|---|---|---|---|
| `H memreq` | `0x100000` | `0x100000` | `0x102000` | `0x102000` |
| `H d1'` (R32_UINT view) | no UBWC → not engaged | same | 8 rows of garbage | 8 rows of garbage |
| `S2 vkCreateImage(MUTABLE+SPARSE)` | `FEATURE_NOT_PRESENT` | `FEATURE_NOT_PRESENT` | `SUCCESS` (hole) | `SUCCESS` (hole) |
| `T-tr` / `S-tr` | 0/262144, 0/16384 | 0/262144, 0/16384 | 0/262144, 0/16384 | 0/262144, 0/16384 |

**Result: the logs are pairwise byte-for-byte identical** (a diff without the
`TU_FORCE_PROPS` lines yields nothing for both base/`+coherency` and
`ubwc_all`/combo). Plus both fresh runs matched the already committed ones —
the rebuild shifted nothing and the runs are deterministic.

The check was meanwhile working rather than silently not firing: the test's
barriers contain `VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT` in srcStage in two
places (`rp6-vkd3d-sparse-test.c:380` and `:1426`), i.e. the quirk condition is
met and `CACHE_CLEAN` really is emitted.

**Conclusion: `ubwc_coherency_quirk` does not fix
`ubwc_all_formats_compatible`, and there is no other flag in this path.** Both
corruptions (the hole on MUTABLE+SPARSE and the garbage in `H d1'`) remain
exactly the same. There is nothing to pick as a set of props that would enable
on gen2 what gen3 enables — next, the workaround paths themselves were checked,
section 14.5.

### 14.5 Hardware hacks: `swap` can be cured, UBWC reinterpretation — cannot

"Hardware behavior" is not a sentence: the driver is full of hacks for
hardware, and half of them are about `swap` exactly. What is already used in
this path:

| Hack | Where | What it does |
|---|---|---|
| force `WZYX` for tiled | `fd6_format_table.c:396` | CCU ignores swap when tiling, TP respects it → keep both on `WZYX` |
| turn off UBWC/tile for mutable lists with a foreign swap | `tu_image.cc:559-578` | this is exactly the baseline behavior — works |
| staging blit instead of HW reinterpretation | `tu_clear_blit.cc:3096` | doesn't let HW do the wrong swap |
| S8→A8 to avoid using swap | `tu_clear_blit.cc:382` | "swap sometimes doesn't work with D24S8" |
| `if (!is_mutable) set_swap(WZYX)` in the GMEM patch | `tu_cmd_buffer.cc:2874` | same, but for attachments |
| separate swap recomputation for `store_cp_blit` | `tu_clear_blit.cc:5547` | "GMEM ignores swap, **except MUTABLEEN**" |

The hacks here are of two types: **(a)** disable the broken thing — there is an
abundance of those and all of them are already applied; **(b)** make HW compute
in a way it can't — there is none of that anywhere, nor can there be. One
unverified hack of type (a) remained.

#### 14.5.1 Hack 0004: `WZYX` also at `is_mutable`

From exp0002: at `is_mutable=true` the driver substitutes the view's real swap
(`fd6_format_table.c:491/514/543`) and sets `MUTABLEEN`; `T-tr` breaks
(0 → 261120/262144). So on a740 `MUTABLEEN` possibly enables reinterpretation
of UBWC metadata, but does **not** enable swap respect in the CCU, and write
and read diverge. This is cured by the same hack: remove `&& !is_mutable`.

A/B on a single test binary, 0002 is applied in both cases:

| | 0002 (control) | 0002 + 0004 |
|---|---|---|
| `T-tr` | **261120/262144** | **0/262144** |
| `S-tr` | **16384/16384** | **0/16384** |

Logs: `results/test-expD-control.log`, `results/test-expD.log`, patch
`experiments/exp-4-force-wzyx-when-mutable.patch`.

**All the corruption from `MUTABLEEN` turned out to be in `swap`, and the old
hack removes it.** Incidentally it turned out that 0004 alone (without 0002)
gives zero difference: under the `ubwc_all_formats_compatible` flag the list T
{BGRA8, BGRA8_UINT} passes the homogeneity check and never reaches the
`is_mutable` branch.

#### 14.5.2 Hack 0005: UBWC on, `MUTABLEEN=0`

The second question is whether 0004 cures the format reinterpretation itself.
It doesn't, because `H` doesn't change with 0004 anyway: for {RGBA8, R32_UINT}
the swap of both formats is `WZYX`, the hack touches nothing there. A separate
question is needed: **is the bit harmful, or is the capability missing?**

exp-5 keeps UBWC enabled for an incompatible list but doesn't raise
`is_mutable` — i.e. `MUTABLEEN=0` while UBWC stays:

| | base (no UBWC) | 0001 (UBWC + `MUTABLEEN=1`) | 0005 (UBWC + `MUTABLEEN=0`) |
|---|---|---|---|
| `H memreq` | `0x100000` | `0x102000` | `0x102000` |
| `H d1'` | not engaged | garbage `0x079d685e…` | **the same garbage, byte-for-byte** |

Log: `results/test-expE.log`, patch
`experiments/exp-5-ubwc-on-without-mutableen.patch`.

**The answer: the capability is missing, not "the bit is harmful".** a740 can't
read a UBWC-compressed image through a view of another format at all — with the
bit and without the bit you get the same garbage array. The hack doesn't cure
this: you can replace SWAP with SWIZ (`a6xx_descriptors.xml:53-56`, 2 bits per
component, TP respects it), but SWIZ permutes channels rather than changing the
format of UBWC metadata, and for attachments there is no SWIZ at all
(`RB_MRT_BUF_INFO` only gives `COLOR_SWAP`).

#### 14.5.3 What this changes

1. **The corruption from `ubwc_all_formats_compatible` consists of two
   independent parts.** A fresh `diff` of base ↔ flag: the unique damage is only
   `H d1'` and the holes on `S2`/`G0`/`E`/`F`. The other `FAIL`s (D/G/K/M/Q,
   "UNORM + usampler") are present in base too — the flag didn't add them.
2. **The `swap` part is cured by hack 0004**, but it cures exactly what it
   itself produces: without 0004 `is_mutable` breaks `T-tr`/`S-tr`, with 0004
   they return to normal. The test showed no case where 0004 did better than
   base.
3. **The `UBWC` part is cured by nothing** — that is exactly the missing a750
   capability on a740.
4. **Summary: enabling `ubwc_all_formats_compatible` on gen2 is still not
   allowed.** Hack 0004 makes the flag harmless (removes the swap corruption)
   but doesn't make it useful: there is no gain from UBWC on such lists,
   because reading through a foreign format is impossible anyway, and the holes
   on sparse-create remain.

A caveat about the tables: the line `H: memreq ... -> MUTABLEEN in play` is the
test's own inference from the memreq value, not a fact about the bit. In
exp-5 `MUTABLEEN=0` yet the line is the same; the fact was checked by
the `tu_image.cc` edit not raising `is_mutable`.
