# 34. After the props, five driconf perf options are left that this device has never run with (21.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md).

**Question.** ADR-0008 closed driver-side fps levers for RE4, and `docs/streams/re4-perf.md`
says so. The operator asked again for a search rather than a verdict. The searches so far were
two: `TU_FORCE_PROPS` over the gen1/gen3 properties (journal 15) and the env/algorithm switches
of journal 13 and 15.5. Both are legitimately exhausted - but neither touched the option surface
that a driver actually uses to change the **command stream**, because that surface is not in the
`TU_FORCE_PROPS` list. So the question is narrow: which perf-relevant options exist in the Mesa 27
tree, which of them has this device never run with, and can any of them be reached without a
build?

## 34.1 What has already been measured, so the search does not repeat it

| surface | measured | result |
|---|---|---|
| gen1/gen3 boolean props (`TU_FORCE_PROPS`, patch 0007) | journal 15.7 | none needs enabling on a740: of the flags that apply to it, two corrupt the test (`load_shader_consts_via_preamble`, `ubwc_all_formats_compatible`), one corrupts in game (`enable_tp_ubwc_flag_hint`), the rest are zeros or the generic-clear pair - which since 30.09 is on for gen2 by default through patch 0008 |
| `tu_enable_softfloat32` off | journal 13 | 0 (the game is not bound by arithmetic) |
| `tu_autotune_algorithm` = `prefer_gmem` | journal 13 | 12.9 against 13.9 - no gain |
| `TU_AUTOTUNE_ALGO=profiled`, `TU_AUTOTUNE_FLAGS=big_gmem/preempt_optimize`, `TU_MAX_DRAW_STATES=64` | journal 15.5 | zeros, except `big_gmem` which is **-12 %** |
| `tu_override_uncached_as_cache_coherent` off | journal 15.6 | **-8 %**, so it must stay on |
| resolution, feature level, shadows, blur, governor | journal 13, 15 | no lever; the wall is `UCHE` 90 % busy and ~220 ns `UCHE`->`VBIF` (`docs/fdperf-a7xx.md`) |

## 34.2 The surface none of them covered, read off the tree

`src/freedreno/vulkan/tu_drirc_gen.py` is the list of Turnip's driconf options, split into a
`perf` group and a `misc` group. Each is overridable by an environment variable carrying the
option's own name - journal 15.6 already used that mechanism (FEX sets one), and the driver
confirms an override in its own output, so a run cannot silently do nothing. Five of them are
perf-relevant, are off for this device by default, and have never been measured here; one of the
five turns out not to be reachable without a build:

| option (group) | where the value is read | what the driver's own description says | reachable on a740 |
|---|---|---|---|
| `tu_disable_conservative_fdm_binning` (misc) | `tu_cmd_buffer.cc:3674` (`cons_vis_in_binning` when the pass has FDM), `tu_pipeline.cc:3489` (`CHIP == A7XX && fdm && !…`) | "Don't enable conservative rasterization during binning of a renderpass with FDM, for non-identity FDM tiles may result in tiny see-through gaps … **Improves performance up to 4% on A7XX.**" | yes, and it is the only option here with an upstream number attached |
| `tu_allow_concurrent_binning` (perf) | `tu_cmd_buffer.cc:560` (cache flush, `CHIP >= A7XX`), `tu_cmd_buffer.cc:3225` (`tu7_cb_disable_reason(.., "globally disabled")`), `tu_queue.cc:187` (how many visibility streams the queue reserves) | "Allow concurrent binning on A7XX+, the CB is disabled by default because **it regresses performance on desktop games**" | yes, and also as `TU_DEBUG=forcecb` / `nocb` (`tu_util.cc:56-57`), which overwrite the option after driconf is parsed (`tu_device.cc:2083-2086`) - and "desktop games" describes an x86 discrete GPU, not this SoC running a desktop game through translation |
| `disable_conservative_lrz` (misc) | `tu_lrz.cc:1524`, `:1533`, where the conservative default calls `tu_lrz_disable_write_for_rp(cmd, "Depth write + blending")` and `("Depth write + no color writes")` | "Disable conservative LRZ"; the driconf comment allows it "for games which do not have the problematic sequence of draws *and* suffer a performance loss with conservative LRZ" | yes, needs a picture check: the code comment above those two lines is a three-draw sequence where the non-conservative choice discards fragments that should be visible, so this option is a correctness trade by construction |
| `tu_dont_reserve_descriptor_set` (misc) | `tu_device.cc:1876` (whether one HW descriptor set is reserved at create) | "…frees up an extra descriptor set at the cost of that feature" (descriptor set dynamic offsets) | yes, but the cost is a feature vkd3d-proton can use; low priority |
| `tu_independent_icache_miss` (perf) | `tu_cmd_buffer.cc:2226` ANDs the option with the prop `has_independent_icache_miss` | "On A750, let each wave handle its instruction cache misses independently instead of stalling all waves together" | **no** - the prop is set only for FD750/753 (`freedreno_devices.py:1341`) and `freedreno_dev_info.h:408` documents the bit as "A750 only". Env-only would be a silent no-op; asking the hardware needs a build |

Three things worth recording because they look like levers and are not. LRZ itself is already on
for this chip (`a7xx_base` sets `enable_lrz_fast_clear`, `has_lrz_dir_tracking`,
`has_lrz_feedback`), so there is no "enable LRZ" to do. The `UCHE`-side registers -
`a740_raw_magic_regs` writes `UCHE_CACHE_WAYS`, `TPL1_DBG_ECO_CNTL`, `TPL1_DBG_ECO_CNTL1` - are
mirrored from the vendor driver for this exact chip, which is the same driver the 13-15 fps
baseline comes from; a deviation there is a hang-risk experiment with no prior, not a lever. And
the options that driconf already turns **on** for this game (`00-turnip-defaults.conf`, the
`DXVK|vkd3d` and `vkd3d` engine blocks: `tu_enable_softfloat32`,
`tu_autotune_algorithm=prefer_sysmem`, `tu_emulate_alpha_to_coverage`,
`tu_use_tex_coord_round_nearest_even_mode`,
`tu_enable_fast_border_color_for_undefined_formats`) are workarounds and accuracy switches, not
deferred gains: two of them were measured in the game (journal 13: softfloat32 off = 0; journal
13: `prefer_gmem` instead of `prefer_sysmem` = worse), and the rest change what is drawn rather
than how fast it is drawn. Upstream also declares a version constant for the RE Engine,
`VKD3D_APPLICATION_VERSION_ENGINE_RE_ENGINE` (`00-turnip-defaults.conf:8`), and no block uses it:
this game has no driconf entry of its own, only the engine-wide ones.

What upstream itself does with two of these options is worth quoting, because it says how the
option is meant to be used. `00-turnip-defaults.conf` enables both of them for one application,
Half-Life: Alyx (`application_name_match="hlvr"`): `tu_disable_conservative_fdm_binning`, and
below it `tu_independent_icache_miss` with the comment `<!-- 2.4% faster. -->`. So the FDM option
is a per-application trade upstream makes once it has a reason measured on a screen, and the
number it attaches to these switches in-tree is of the order of a few percent, not a factor. No
`<application>` block in that file matches RE4, and the two engine blocks that do match it
(`DXVK|vkd3d`, `vkd3d`) enable the workaround options above and none of the five in the table -
so on this game all five sit at their default: the four reachable ones are off, and the icache
one is off and inert. Upstream also declares an application-version constant for the RE Engine,
`VKD3D_APPLICATION_VERSION_ENGINE_RE_ENGINE` (`00-turnip-defaults.conf:8`), and no block uses it.

## 34.3 The correctness gate the rig can give, on the released driver

Four runs of the test with the options forced, against a base run, one binary
(`5f44a7f7e6ae…`), the released `.so` (`c17d02bcaae9a960…`):

| run | lines | differing lines vs base |
|---|---|---|
| base | 621 | - |
| `tu_allow_concurrent_binning=true` | 622 | 0 |
| `tu_disable_conservative_fdm_binning=true` | 622 | 0 |
| `disable_conservative_lrz=true` | 622 | 0 |
| `tu_dont_reserve_descriptor_set=true` | 622 | 0 |

(622 = 621 plus the driver's `ATTENTION: default value of option <name> overridden by
environment.` line, which is what proves the option reached the driver. The verdict-word counts
match too - lines containing each word over the whole log: `EXACT` 124, `MISMATCH` 8, `FAIL` 6.)

Artifact: [`../../results/test-perfprops-rig.log`](../../results/test-perfprops-rig.log).

**Verdict.** Four of the five options are reachable with an environment variable and no rebuild,
and none of the four changes anything on every shape this rig creates: concurrent binning,
conservative FDM binning, conservative LRZ and the reserved descriptor set each leave the run
byte-identical to the base run. Three of them are candidates for a real measurement - the fourth
buys one HW descriptor set by giving up descriptor set dynamic offsets, which vkd3d-proton can
use, so it is not a perf option here but a feature trade. The fifth, the independent icache-miss
option, cannot be asked of a740 at all without a build, because the code ANDs it with a property
upstream gives only to FD750.

Nothing in this entry is a speedup. The rig has no textured depth renderpass, which is exactly
where the three candidates act, so the measurement that decides them is the game (queue 12), and
the bound on the expectation is the wall of ADR-0008 - except for the FDM option, which carries
upstream's own "Improves performance up to 4% on A7XX." and is the first candidate in the queue.

## 34.4 The same surface, second kind: what the driver reports about memory (added the same day)

The five options above change the command stream. The surface has a second kind, and on a machine
whose wall is memory it is the one worth naming, so the search is complete rather than narrow:
options that change what the driver **reports**, which an application then sizes itself against.
One of them is reachable without a build and had never been looked at here.

`heap_memory_percent` is not in Turnip's own `perf`/`misc` groups and not in `TU_FORCE_PROPS`. It is
one of the three "common vk" driconf options Turnip accepts (`tu_drirc_gen.py:8-12`, next to
`force_vk_devicename` and `force_vk_vendor`), its description is "Percentage of total system memory
to report as gpu heap memory (0 = driver default)" (`drirc_gen.py:393`), and an environment variable
of the same name overrides it. What it feeds is `tu_get_system_heap_size()` (`tu_device.cc:2255`):
with the default `0.0` the driver takes `os_gpu_heap_size_calculate()`'s heuristic branch
(`os_misc.h:170`), which for a machine above 4 GiB of RAM returns **0.75**.

Five runs of `vulkaninfo` against the released driver, one variable, verbatim in the artifact:

| run | reported `size` | reported `budget` |
|---|---|---|
| default | 5.49 GiB | 980 MiB |
| `heap_memory_percent=0.5` | 3.66 GiB | 965 MiB |
| `heap_memory_percent=0.4` | 2.93 GiB | 958 MiB |
| `heap_memory_percent=0.25` | 1.83 GiB | 979 MiB |
| `heap_memory_percent=0.05` | 374 MiB | 374 MiB |

So on this machine the driver tells a fresh application that there are 5.49 GiB of DEVICE_LOCAL
memory - 75 % of 7.32 GiB, because of the heuristic, not because anyone chose it - while journal 17
measured that the game's own vkd3d resources peak at 3129 MiB and turnip's live BOs at 3490 MiB on
a system that was then already running with 4.95 GiB of swap used. The budget is a separate number:
`tu_get_budget_memory()` (`tu_device.cc:2269`) hard-codes 0.9 of *free* system memory, so the budget
follows the machine and not the option, until the heap drops below it - which is why the last row
has `budget == size` and why that row is a control on the cap at `vk_physical_device.h:196`, not a
candidate value.

The memory-type switch in the same area, `tu_expose_device_local_only_memory_type`, is a different
axis and was checked as a control: it moves the reported type count 4 -> 5, the new type being
`0x0001` (DEVICE_LOCAL, not host-visible), with the heap block unchanged. Upstream enables it in one
place only, for RDR2's native Vulkan renderer, i.e. when an application is known to ask for such a
type.

**Verdict of 34.4.** One number in the driver, reachable by environment, decides what this game is
told about memory: 5.49 GiB on this machine. Nothing here says the number is wrong, and nothing here
says changing it helps - journal 17's own conclusion ("no env levers for memory") stands for what it
measured, which is *use*; this is the *report*, and no rig here has ever observed what vkd3d-proton
does when the report shrinks. It is the one unasked question in the option surface that points at
the bound in ADR-0008 rather than away from it, so it is queued with the game as queue 13 and open
question 17, and it is explicitly not a patch: the 0.9 in `tu_get_budget_memory()` is a literal and
would need code, which is a different conversation with different risk.

Artifact: [`../../results/vulkaninfo-heap-report.log`](../../results/vulkaninfo-heap-report.log).

## What this does not show

* It measures **nothing about frame rate**. No fps was taken in this entry: RE4 needs about
  7 GiB, which is the whole machine, and the machine had 1.1 GiB free at the time of the runs.
* The rig's equality is not a safety verdict - see the last section of the artifact: no
  textured depth renderpass, no visibility stream, no FDM tiles. The precedent for what "the
  counter is green" is worth is ADR-0006.
* The 34.4 numbers are a **report**, taken with `vulkaninfo` while the game was not running and the
  machine had roughly 0.7-0.8 GiB available. The `budget` column is therefore a statement about the
  machine at that minute; only the `size` column follows the option.
* The second rig journal 15 used (`vkmark`) is no longer installed on this system: the prefix
  its `$D` pointed at is gone. Until it is reinstalled, the game is the only workload here that
  exercises these paths, so the queue item names it directly.
* The 4 % in the FDM option's description is upstream's measurement on their hardware and their
  scenes, not ours; it is a reason to run, not a number to quote as ours.

**Correction (21.11, same day, commit `965d817`).** The first version of the table above spelled
the two debug names `TU_DEBUG=force_concurrent_binning` and `no_concurrent_binning`, taken from the
enum constants at `tu_device.cc:2083-2086`. Those are not the names the parser accepts: the strings
in `tu_util.cc:56-57` are `nocb` and `forcecb`, so the wording as committed would have described a
`TU_DEBUG` value that does nothing. The table now carries the parser's names. Nothing measured here
used `TU_DEBUG` at all - the four runs forced the driconf options by their own environment
variables - so no number in this entry depends on the correction.

Related: journal 13 (the env switches), journal 15 (the props), journal 17 and
`docs/fdperf-a7xx.md` (the wall), ADR-0008 (the verdict this entry narrows but does not reopen),
`docs/streams/re4-perf.md`, queue 12 in `docs/plan-next-checks.md`.
