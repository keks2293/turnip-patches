# 15. Measuring the props: vkmark and RE4

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

Flags are overridden via `TU_FORCE_PROPS` (patch 0007), i.e. one rebuild for
all configurations and no compiler drift between runs.

### 15.1 Method

```bash
$VK --winsys xcb --winsys-dir $D/lib64/vkmark --data-dir $D/share/vkmark \
    --size 1280x800 --present immediate \
    -b clear -b vertex -b shading -b texture
```

The metric is `FrameTime` per frame in ms (lower = better). Configurations are
alternated in an interleaved fashion (base/flag/base/flag…) rather than in
blocks, so that frequency and temperature drift doesn't line up with a single
config. **Comparison is only valid within one series**: between series the
patch set in the tree changed, and the vertex baseline moved from 0.210 (29.09)
to 0.141 (30.09).

Files: `results/vkmark-flags.txt` (series of 29.09, `has_gmem_vpc_attr_buf` and
the first estimate of `has_generic_clear`), `results/vkmark-ab-combo.txt`
(combo), `results/vkmark-ab-r8g8.txt` (series of 30.09: base / gc / gc_r8g8 /
tp plus a separate clear series of 6 pairs).

### 15.2 Synthetic: what enabling the gen3 flags gave

Series of 30.09, average over 2 runs:

| scene | base | gc | gc_r8g8 | tp | gc | gc_r8g8 | tp |
|---|---|---|---|---|---|---|---|
| | | | | | delta vs base | | |
| clear | 0.057 | 0.058 | 0.058 | 0.058 | +0.9% | +1.8% | +1.8% |
| vertex | 0.141 | 0.052 | 0.053 | 0.141 | **−63.1%** | −62.1% | +0.0% |
| shading | 0.158 | 0.061 | 0.057 | 0.159 | **−61.1%** | −64.2% | +0.3% |
| texture | 0.153 | 0.054 | 0.054 | 0.153 | **−64.5%** | −64.5% | −0.3% |

- **`has_generic_clear` is the only flag with an effect.** An important detail:
  the `clear` scene itself doesn't get faster (+0.9%); vertex/shading/texture
  do. The reason is not the clearing itself but that generic clear disables
  conditional load/store (`tu_pass.cc:560`): the "clear and draw" pass stops
  loading the previous render target contents.
- **`r8g8_faulty_fast_clear_quirk` in a pair with gc is free**: gc_r8g8 ≈ gc in
  all scenes, i.e. the gain doesn't come from removing the R8G8 protection. The
  previously observed −25…−39% were inflated by an old baseline (vertex 0.210
  versus today's 0.141).
- **`enable_tp_ubwc_flag_hint` gives 0 on a740.** The "+1.8%" on clear is
  0.001 ms on a 57 µs frame, i.e. vkmark's quantization: a separate series of 6
  pairs on the clear scene gave 0.1433±0.0029 (base) versus 0.1438±0.0028
  (tp), delta +0.3% at t≈0.3.
- `has_gmem_vpc_attr_buf` (series of 29.09) — within noise (0–4%), the combo
  gives nothing beyond gc alone.

### 15.3 Check for corruption: test and picture

- **Functionally** — `scripts/run-test.sh` with `TU_FORCE_PROPS`:
  `results/test-props2-{base,cs_lock_unlock_quirk,enable_tp_ubwc_flag_hint,
  r8g8_faulty_fast_clear_quirk,gc,gc_r8g8}.log`. All six give PASS and a
  byte-for-byte identical result to base; base on the new binary matched the
  old base, i.e. there is no drift.
- **Visually** — `scripts/shot.py` + `scripts/pixelcheck.py`, scheme
  base1/flag/base2 **interleaved**: comparing screenshots with a ten-minute gap
  yields false positives (wallpaper change, panel). Results: gc and gc_r8g8 —
  0 changes on clear, 1 pixel out of 880 on texture (delta 6/255 on an animated
  edge); tp — 0 of 880 in both scenes. Black screenshots in the series turned
  out to be a race (vkmark exited before the shot) — fixed by `--run-forever`
  plus a `kill -0` check.

### 15.4 RE4: no gain, and tp produces artifacts

Protocol: `HUDLOG=120 scripts/run-game.sh patched 150`, the segment is walked
by hand, the metric is `p25` over frames with `fps < 30` (section 13). Three
runs in a row so that the compared segment is identical (a fresh baseline is
needed precisely for this: the old 13.9 is a different day and a different
playthrough).

| run | fps p25 | median | mean | n |
|---|---|---|---|---|
| base | 11.0 | 12.4 | 12.33 | 73 |
| `enable_tp_ubwc_flag_hint` | 11.0 | 12.5 | 13.34 | 66 |
| `has_generic_clear,r8g8` | 11.5 | 12.4 | 12.50 | 77 |

CSV: `results/games/re4/fps-abbase.csv`, `fps-abtp.csv`, `fps-abgc.csv`; logs
`results/games/re4/game-patched-ab{base,tp,gc}.log`. The force reached the driver — in
`results/raw/game-patched-ab{tp,gc}.log` there are lines
`TU_FORCE_PROPS: <name>` (in base there are none).

- **`gc+r8g8`: median −0.4%, i.e. zero.** In vkmark the `clear` scene consists
  entirely of clears, and they account for the whole frame; in the game a frame
  is ~75 ms and is bound by memory bandwidth (section 13), while clears are a
  small part of it. −60% on a small share gives no noticeable gain overall.
- **`enable_tp_ubwc_flag_hint=True`: artifacts on screen** (screenshots
  `/tmp/opencode/shots/gametp-artifact-{1,2,3}.png`; in base they are absent).
  vkmark didn't show them because it doesn't do scaling blits — and
  `BLIT_OP_SCALE` is exactly what the prop's comment mentions
  (`freedreno_dev_info.h:394`). The prop is not "empty": on a740 it must
  remain `False` (the value per the v6xx blob).

### 15.5 Autotune, draw states and preamble series (30.09)

The second series of env switches, this time without rebuilding the driver.
Protocol as in 15.4 (`HUDLOG=120`, `p25` over frames with `fps < 30`), two
rounds (the second in reverse order), configurations interleaved with the
baseline within the day. Baselines over the day: 12.2 / 12.7 / 12.6, i.e. the
series noise is ±0.3. vkmark of the same series
(`results/vkmark-ab-autotune.txt`) is entirely within noise: 0.053–0.059 ms on
all four configurations.

| config | p25 (mean) | runs | Δ vs baseline |
|---|---|---|---|
| base | 12.5 | 12.2, 12.7, 12.6 | — |
| `TU_AUTOTUNE_ALGO=profiled` | 12.6 | 12.5, 12.7 | 0 |
| `TU_AUTOTUNE_FLAGS=big_gmem` | 11.05 | 11.1, 11.0 | **−1.5** |
| `TU_MAX_DRAW_STATES=64` | 12.7 | 12.7, 12.7 | 0 |
| `64 + TU_AUTOTUNE_FLAGS=preempt_optimize` | 12.6 | 12.6, 12.6 | 0 |
| `TU_FORCE_PROPS=load_inline_uniforms_via_preamble_ldgk` | 12.6 | 12.6, 12.6 | 0 |

CSV: `results/games/re4/fps-at-*.csv` (the mapping of names to configs is in
`results/series-autotune.txt`; the mislabeled `fps-at-bigb.csv` is an extra
baseline run), logs `results/games/re4/game-patched-at-*.log`.

- **`big_gmem` is consistently 1.5 frames worse (~12%)**: occupying more GMEM
  on this game's pass is harmful. Anti-recommendation.
- **`profiled` = 0**: the profiled autotune algorithm finds nothing better than
  the baseline — the tiling decisions are already correct.
- **`TU_MAX_DRAW_STATES=64` is a no-op by itself.** The prop
  (`max_draw_states`, "The amount of valid draw state IDs",
  `freedreno_dev_info.h:484`; a740 inherits 32 from `a6xx_base`,
  `freedreno_devices.py:152`, the gen3 template sets 64 at `:901`) is read in
  the tree in exactly one place — `tu_autotune.cc:339`: it gates
  `mod_flag::PREEMPT_OPTIMIZE` among the supported autotune flags, with the
  condition `max_draw_states > TU_DRAW_STATE_AT_WRITE_RP_HASH`. The threshold
  is `COUNT+1` = (19 static + 13 dynamic) + 1 = **33**: at 32 the condition is
  false (the flag is cut out at assignment on `tu_autotune.cc:319`), at 64 it
  is true. So 64 is exactly the number with which gen3 unlocks the autotune
  preempt optimization, and the separate `TU_MAX_DRAW_STATES` variable is
  needed because the prop is numeric (`tu_device.cc:1708`).
- **Combo `64 + preempt_optimize` = 0** — the flag itself doesn't move the
  frame.
- **`load_inline_uniforms_via_preamble_ldgk` = 0.** Correctness before the
  measurement: `results/test-preamble-iu.log` matches
  `results/test-props2-base.log` byte for byte (comparison without the
  `TU_FORCE_PROPS` lines). `load_shader_consts_via_preamble` was not measured
  in the series: its corruption was reproduced by a separate run — all reads
  `0x00000000`, section 14.3.

### 15.6 drirc: `tu_override_uncached_as_cache_coherent`

This option is not in `TU_FORCE_PROPS` — it is a driconf one, and in **all**
game logs, including the stock driver, there are lines
`ATTENTION: default value of option ... overridden by environment`. The source
was found: FEX inside proton-cachyos-11.0-arm64 calls
`__wine_set_unix_env("tu_override_uncached_as_cache_coherent", "true")`
(the string is baked into `files/lib/wine/aarch64-windows/libwow64fex.dll` and
`libarm64ecfex.dll`), i.e. the value is always `true`, regardless of the
driver. FEX doesn't overwrite its own `false` (verified via
`/proc/<pid>/environ` of the wine processes), so A/B is possible with a plain
environment variable.

Semantics (`tu_device.cc:1887`, `tu_knl.cc:57`): with the option, every
allocation requested as `DEVICE_LOCAL|HOST_VISIBLE|HOST_COHERENT`
("uncached" by default — this catches vkd3d-proton's UPLOAD heaps) is redirected
to the `+HOST_CACHED` type. The type exists (vulkaninfo: `memoryTypes[1]` =
`DL|HV|HC|CACHED`), i.e. the option is "live".

Protocol as in 15.5, interleaved within the day:

| run | p25 | median | n |
|---|---|---|---|
| `=false` (offA) | 11.6 | 11.6 | 90 |
| default, `true` (base6) | 12.6 | 12.7 | 90 |
| `=false` (offB) | 11.7 | 11.7 | 88 |
| default, `true` (base7) | 12.6 | 12.7 | 87 |

**Turning the option off is 1.0 frames worse (~8%)**, both switches agree, the
series noise is ±0.3. Cached-coherent host memory under FEX is faster than
uncached — the option must not be turned off, there is nothing left to measure.
CSV: `results/games/re4/fps-at-{offA,base6,offB,base7}.csv`, series —
`results/series-drirc.txt`.

### 15.7 Summary

No gen1/gen3 property needs to be enabled on a740. Of the 28 gen3 and 5 gen1
properties in `TU_FORCE_PROPS`, only 10 actually apply (list —
`docs/a7xx-gen-props.md`, section "Coverage"), and per them:

| category | flags | grounds |
|---|---|---|
| breaks | `load_shader_consts_via_preamble`, `ubwc_all_formats_compatible` | corruption in the test (sections 14.3 and 14.5) |
| 0 / noise | `has_gmem_vpc_attr_buf`, `ubwc_coherency_quirk`, `has_compliant_dp4acc`, `has_persistent_counter`, `has_abs_bin_mask`, `cs_lock_unlock_quirk` | test and vkmark show no differences |
| synthetic, 0% in game | `has_generic_clear`, `r8g8_faulty_fast_clear_quirk` | sections 15.2 and 15.4 |
| 0 in game | `load_inline_uniforms_via_preamble_ldgk` | test ok, measurement: section 15.5 |
| corruption in game | `enable_tp_ubwc_flag_hint` | section 15.4 |

Also checked were not props but algorithm/size switches (autotune,
`TU_MAX_DRAW_STATES`, the driconf `tu_override_uncached_as_cache_coherent`)
— all zeros except the harmful `big_gmem`; the drirc option is on the contrary
useful (turning it off is 8% worse) — sections 15.5 and 15.6.

The remaining gen3 properties aren't in `TU_FORCE_PROPS` at all — they can only
be enabled by editing `freedreno_devices.py`. Per the code, two of them don't
apply to a740: `new_control_regs` (on a750 the control register layout is
permuted) and `has_sw_fuse` (it would read SW_FUSE and blow away raytracing,
`tu_device.cc:204`). `has_alias_rt` and `has_rt_workaround` haven't been
checked by anything: we have no ray tracing test.

Of the gen1-only ones (`cs_lock_unlock_quirk`, `stsc_duplication_quirk`) the
first was checked and gave nothing; the second cannot be checked in principle:
`TU_FORCE_PROPS` only does `True`, and ours is `True` already (gen2).

Since 30.09.2026 the pair `has_generic_clear` + `r8g8_faulty_fast_clear_quirk`
is enabled for gen2 **by default** — patch 0008
(`patches/0008-turnip-gen2-generic-clear.patch`, editing `a7xx_gen2` in
`freedreno_devices.py`); the env force of the pair is no longer needed. Check
after the rebuild (`results/test-gen2gc.log`): the test matches byte for byte
both `test-props2-base.log` (default before the edit) and
`test-props2-gc_r8g8.log` (forced pair) — only the `TU_FORCE_PROPS` lines
differ; the `FAIL` lines are the same 6 as in all the references. The generated
table: FD740 `(True, True)`, FD730 `(False, False)` — gen1 untouched, FD750
`(True, True)` — as before. The picture for the pair is the `gc-*`/`gcr8-*`
screenshots from 15.3.
