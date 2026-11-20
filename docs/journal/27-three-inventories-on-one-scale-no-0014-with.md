# 27. Three inventories on one scale: no 0014, with 0014, with the prop (20.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

To compare the two ways of getting rid of linear deposition by class rather than by
impression, the same tooling (`exp-14`) ran over three driver states. Logs:
`results/raw/game-patched-imginv4.log` (ship stack **before** 0014 - the base for the
question, `0001..0013` present), `…/game-patched-imginv5.log` (ship stack **with**
0014, build `050375a18b7b`), `…/game-patched-stockflaginv.log` (stock + only the prop
line, section 26 plus `exp-14`: `.so build/out-stock-flag-inv/libvulkan_freedreno.so`,
sha256 `32d20074b8a128e4…`, `TU_IMG_INV` present in `strings`, KMD = msm, ICD
`build/out-stock-flag-inv/freedreno_icd_stock_flag_inv.json`, run
`TU_IMG_INV=1 ICD=… TAG=stockflaginv scripts/run-game.sh patched 170`, 4179
`TU_IMG_INV` lines of which 9 are truncated by another writer's stderr). The counters
are `scripts/imginv-stats.py` and `scripts/imginv-classes.py`; their output for all
three logs is committed as `results/imginv-3variants.txt`, so the tables below are
reproducible from a committed artifact (raw game logs are not in git).
`imginv-stats.py` takes `MUTABLE_FORMAT` from `flags & 0x8`, not from the `mutable=`
field, whose meaning changed between revisions of the tooling.

| variant | creates / total | `tile=tiled` | `ubwc=1` | no-list: tiled | no-list: linear |
|---|---|---|---|---|---|
| ship stack without 0014 (imginv4) | 3638 / 7740.5 MiB | 3939.5 (50.9 %) | 3884.5 (50.2 %) | 0.0 (0 %) | **3800.9** |
| ship stack with 0014 (imginv5) | 4176 / 8080.8 | 6449.9 (79.8 %) | 3925.6 (48.6 %) | 2450.3 (60.0 %) | **1630.8** |
| stock + prop (stockflaginv) | 4170 / 8088.0 | 8086.1 (100.0 %) | 3944.9 (48.8 %) | 4071.2 (99.95 %) | **1.8** |

The sessions are not the same length (`imginv4` has ~7 % fewer creates), so only
shares and classes are comparable, never absolute MiB.

The same set, broken down by texel-block class (MiB of the no-list class and the
tiled share inside it; `MUTABLE` without a list is the only class where the three
variants differ):

| class | without 0014 | with 0014 | stock + prop |
|---|---|---|---|
| 8-bit (`R8_*`) | 1170.6 / 0 % | 1183.8 / **100 %** | 1181.8 / **100 %** |
| 64-bit (`R16G16B16A16_*`, `R32G32_*`) | 585.0 / 0 % | 666.4 / **100 %** | 650.8 / **100 %** |
| BC (DXT/BPTC/RGTC) | 445.1 / 0 % | 600.7 / **99.9 %** | 600.7 / **99.9 %** |
| 32-bit (incl. `R11G11B10`, `R10G10B10A2`) | 993.0 / 0 % | 1023.5 / **0 %** (deliberate) | 1014.7 / **100 %** |
| 16-bit (`R8G8_*`, `R16_*`) | 607.3 / 0 % | 606.7 / **0 %** (deliberate) | 624.9 / **99.9 %** |
| **total** | **3800.9 / 0 %** | **4081.1 / 60.0 %** | **4073.0 / 100 %** |

Three conclusions:

1. **The prop and 0014 agree in exactly three classes** (8-bit, 64-bit, BC) - the
   classes where nothing inside the class differs in channel layout, so tiling is
   safe. That is an independent confirmation of the model in section 21.12: 0014
   returns 60 % of the volume to tiled, and the whole remaining linear residue -
   1630.8 MiB - is the 32- and 16-bit classes that 0014 does **not** tile on purpose.
2. **Everything the prop has beyond 0014 is those 1630 MiB.** It tiles them too
   (1014.7 + 624.9 MiB), i.e. the difference between "0014" and "the prop" is exactly
   the classes where the compatibility class mixes RGBA8 <-> BGRA8 and R8G8 <-> R16,
   and a readback through such a reinterpretation is not defined by the layout -
   those are the very rows where probes `S` and `T` fail (section 24.3). The prop is
   not "better", it removes a guard that is there for a reason.
3. **No variant gives UBWC in this class: `ubwc=` is 0.0 MiB there in all three
   inventories.** The total UBWC share across the run moves 48.6 % -> 48.8 %, which
   is zero within session noise. So "the prop saves bandwidth" is not confirmed for
   this workload: the prop changes only `tiled/linear`, and that tiling the 32- and
   16-bit classes may be harmful is a separately documented risk (row 23 of
   `docs/a7xx-gen-props.md`, damages (1)-(3)).

The direct ship-vs-prop pair, same scenario, both with the inventory
(`imginv5` = A, `stockflaginv` = B): creates 4176/8080.8 MiB against 4170/8088.0;
`tiled` 79.8 % against 100.0 % (**+1636 MiB**); `ubwc=1` 48.6 % against 48.8 %
(+19 MiB, i.e. nothing); MUTABLE with a list 726/766.3 against 727/769.9 with UBWC in
632/696.3 against 633/699.8 - **the same per combo**; MUTABLE without a list 2474 /
4081.1 against 2470 / 4073.0, of which tiled 1450 / 2450.3 (60 %) against 2367 /
4071.2 (99.95 %), and UBWC 0.0 in both; without `MUTABLE` 976 / 3233.4 / 3229.3 UBWC
against 973 / 3245.1 / 3245.1.

So, three facts. (1) **The prop tiles but does not compress**: all of the tiling gain
is the no-list class, precisely the 1630 MiB of linear that 0014 was written for, and
UBWC does not move at all. By volume the prop is a crude 0014, exactly as the matrix
suggested (section 26), and it is **not** a bandwidth lever. (2) **By lists the prop
reproduces the volume of 0011/0012**: build B has neither `0011` nor `0012` nor
`0003`, yet `R10G10B10A2 -> {UNORM,UINT}` (114.8 -> 118.3 MiB) and `R32_UINT ->
{FLOAT,SINT,UINT}` (42.6 MiB) keep their UBWC - `mutable_ubwc_fc` (`tu_image.cc:582`)
gives those whenever the prop is set. The `R8_*` hole (94 creates / 70 MiB) did not
close: `ubwc=0` in both builds. (3) **Only the volume is reproduced, not the
correctness**: the `0005`/`0006`/`0010` that were removed together with the prop break
probes `S` and `T` (section 24.3), because a compat mode is part of the layout, not a
switch. So "the prop instead of the patches" is still a no: 0014 is needed for the
careful rule and for the UBWC inside lists, `0005`/`0006`/`0010` for correct reads.

Caveat about the cleanliness of that pair: B differs from A not only by the prop but
by the absence of the whole stack (including `0003`, which does limit UBWC for
mutable images), so conclusion (1) transfers, while (2) must be read as "the prop
alone yields these 158 MiB", not as "the ship stack with the prop would yield exactly
the same". The build "ship stack + prop + inventory" is NOT DONE (a build is ~4
minutes).

The game part of the run is the same as in section 26: DX12, frames for all 90 s, RAM
6.5 GiB of 7.32, swap 5.9 GiB, GPU load median 92 %; `process_rss` and `gpu_vram_used`
are zero in this MangoHud build, so how much of that the game holds itself is not
visible from this log.

What the scale does not have: an honest "bare" base (stock with no patches **and** no
prop). `imginv4` is the ship stack without 0014, not bare stock. The build for the
real base exists (`6dfa32a` + `exp-14`, without `exp-16`):
`build/out-stock-inv/libvulkan_freedreno.so`, sha256 `23ccf659c90d3ddf…`, ICD
`build/out-stock-inv/freedreno_icd_stock_inv.json` - only the run is missing, NOT
MEASURED.
