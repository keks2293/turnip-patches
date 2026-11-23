# 42. Both export counters count one event per group of 8 components of vertex export, and the probe built to measure them had been carrying one varying (24.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules
for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or
`journal N.M`, where the number is also the start of the file name.

Bottom line: queue 34's two unnamed units have one - `PERF_VPC_SP_COMPONENTS` (VPC selector 10) and
`PERF_SP_EXPORT_VPC_TRANS` (SP selector 48) each count one event per group of 8 components (32 bytes of
32-bit components) of vertex-shader output crossing the VPC, position included, and they count the same
events from the two ends of it; neither is per pixel, which the export that certainly is per pixel
(`SP_EXPORT_RB_TRANS`, exactly 0.2500 per quad in every arm) shows by staying still while selector 48
moves 8.5x. Getting that answer needed a second one first, because the fragment shader of the rig this
sweep ran on summed its sixteen varyings, and a sum is one of the operations `nir_opt_varyings` moves out
of the fragment shader and into the vertex one: the interface was one vec4 wide, the pipeline ran, the
counters moved, and the probe's own banner printed "16 vec4 varyings out".

## 42.1 A sum of varyings is not an interface: the attribute-buffer probe had been shipping one vec4, and the wrong form is now a control

**Question.** 42.2's sweep is worth nothing unless an arm that asks for N vec4 outputs actually has N
vec4 outputs. The rig it was going to run on already existed - `tests/vpc-attrbuf.c`, written for
queue 35 - and both `docs/artifacts.md` and the probe's own banner described its default shader pair as
sixteen vec4 wide, "every one of them derived from an attribute so `nir_opt_varyings` cannot promote any
of them away". That sentence is a claim about a compiler pass, so it was read out of the driver rather
than agreed with, and the arms were built on the answer.

**Method.** [`../../scripts/check-varyings-arms.py`](../../scripts/check-varyings-arms.py): one 1 s run
per arm with `IR3_SHADER_DEBUG=vs,fs` and `MESA_SHADER_CACHE_DISABLE=true` (a pipeline served from the
disk cache is never compiled, so the disassembler has nothing to print, and "no FRAG native code" reads
like a broken arm rather than a cache hit), reading the FS's input list - `VARYING_SLOT_VARk … il=,b=`,
the VPC location `pack_inlocs` handed each varying (`ir3_compiler_nir.c:5274-5290`, printed at
`ir3_shader.c:1266`) - and the VS's output list, where `hr` would mark a 16-bit slot
(`ir3_shader.c:1259`). No hw counter is sampled here. The two wrong forms were then built on purpose and
re-checked by [`../../scripts/check-varyings-controls.sh`](../../scripts/check-varyings-controls.sh),
which regenerates the shader pairs with `FS_REDUCE=plain` and `=fract`
([`../../tests/gen-varyings-spv.sh`](../../tests/gen-varyings-spv.sh)), compiles the probe in the
glslang container, and leaves `tests/varyings_spv.h` and `../build/vpc-attrbuf` in the production form at
the end. Tables: [`../results/synthetics/varyings/interface-check.txt`](../results/synthetics/varyings/interface-check.txt)
and [`../results/synthetics/varyings/negative-controls.txt`](../results/synthetics/varyings/negative-controls.txt).

**Numbers.** With the reduce the pass cannot move (`acc += v_i * v_i * c`), every arm is what it asks
for: N VAR outputs from the VS, none half, POSITION present, and the same N read back by the FS at
`il = 0, 4, …, 4(N-1)` with compmask `f` and the bary flag - arms 1, 2, 4, 8, 16 and the rig's default
pair at 16. With `FS_REDUCE=plain` (`acc += v0 + v1 + …`) the interface is **one** VAR output in arms 2,
4, 8 and 16, and the frame rate is flat across them - 10.79, 10.69, 10.69, 10.70 fps - while the correct
16-wide arm runs at 0.91 fps. That is the trap in one line: the wrong interface does not fail, it runs at
a speed that scales with nothing.

The rig's default pair was that shape - `vec4 a = v0 + v1 + v2 + v3; … vec4 acc = a + b + c + d;` - and
its compiled interface read `FRAG: inputs: r0.z (VARYING_SLOT_VAR0 slot=32 cm=f,il=0,b=1)` and
`VERT: outputs: r8.x (VARYING_SLOT_POS) r6.w (VARYING_SLOT_VAR0)`: one varying plus position. Each input
is now multiplied by itself before anything combines it, and the same pair then reads sixteen VAR outputs
at `il = 0..60 by 4`. The cost of the interface the source had always asked for, on the identical mesh,
from the two runs' own logs: `fps 6.89` before
([`../results/synthetics/attrbuf/smoke/run.txt`](../results/synthetics/attrbuf/smoke/run.txt), 23.11)
against `fps 1.64` after
([`../results/synthetics/varyings/attrbuf/run.txt`](../results/synthetics/varyings/attrbuf/run.txt)) -
4.2x, measured by nothing but the frame rate and the disassembly. 42.2 adds the counters' side of the
same fact: that run's own dump implies a stride of 7.99 components where the fixed arm implies 66.74.

**Verdict.** Two claims fall and one smaller one stands. `docs/artifacts.md`'s reason - that deriving
every varying from an attribute keeps it on the interface - is not what the pass asks: what decides is
whether the *use* can be moved, and a chain of adds can (`can_move_alu_across_interp()`,
`nir/nir_opt_varyings.c:3738-3795`, with the unlimited budget `tu_shader.cc:3878` gives the pass). And
the note written with the rig on 23.11, that wrapping varyings in `fract()` makes the pass pack slots to
16 bits, is withdrawn with this entry: the `fract` table reads sixteen VAR outputs, none half, at the
same inlocs as the production form - the mixed `(r)K`/`K` offsets that suggested packing were a reading
artefact of `(rpt3)`-compressed disassembly, not packing. What survives is the narrow half: an FS whose
reduce the pass cannot move keeps N varyings, and a sum does not. The two forms stay buildable
(`FS_REDUCE=plain|prod|fract`) so both remain checkable rather than remembered.

Consequence for what was already measured: the smoke run of the attribute-buffer probe, and the queue-35
arms that are parked behind it, were run with an interface one vec4 wide. Nothing in 40.35's verdict
depends on the interface - its finding is that the pass renders in sysmem and never bins - but a re-run
with this binary is what queue 39 asks for, and `docs/artifacts.md` now describes the pair as corrected.

**Does not show.** Whether any *other* rig in this repository is affected: only the two shader pairs
here were read at disassembly level, and a rig whose FS nobody read may carry the same surprise. Nothing
about counter semantics, which is 42.2. And nothing about the attribute-buffer carve-out itself: queue 35
stays where 40.35 left it, parked by the operator.

## 42.2 `VPC_SP_COMPONENTS` and `SP_EXPORT_VPC_TRANS` count one event per 8 components, from both ends, and neither is per pixel

**Question.** Queue 34. 40.36 left the pair question hedged and the unit unnamed, for a reason that was
itself the finding: no committed dump knows how many vec4 varyings cross the VS/FS interface, so nothing
in it can separate "components" from "transactions" from "one per vertex". The arms of 42.1 know.

**Method.** [`../../scripts/run-varyings-sweep.sh`](../../scripts/run-varyings-sweep.sh), arms
1, 2, 4, 8, 16 and the rig's own pair (`attrbuf`): 60 s per arm, the sampler over the last 45 s at
1000 ms with [`../../tools/fdperf/fdperf.cfg-varyings`](../../tools/fdperf/fdperf.cfg-varyings), one
curated directory per arm under `results/synthetics/varyings/` with `fdperf-raw.txt`, `run.txt` and a
`meta.txt` naming the probe's sha256 (`a18c2fcb0129`), the driver's (`libvulkan_freedreno.so`
`4c3cdb210082`) and the arm's expected `SP_VS_OUTPUT_CNTL.OUT` / `VPC_VS_CNTL.STRIDE_IN_VPC`. The sweep
will not start unless `check-varyings-arms.py` confirms every requested arm for the binary it is about to
sample - 42.1 is why that gate exists. Reader
[`../../scripts/varyings-table.py`](../../scripts/varyings-table.py), table
[`../results/synthetics/varyings/arms.txt`](../results/synthetics/varyings/arms.txt); its rules are
`scripts/fdperf_sections.py`'s, and no window is filtered on clock, because an event counter over `fdperf
-r 1000` is a per-wall-second rate whatever the clock and each duty column divides by that window's own
`CP_ALWAYS_COUNT` (the arms ran at 605-680 MHz, the governor's own, this part's ceiling being 680).

**Numbers.** Same picture in every arm, per frame: 0.19-0.20 M vertices, the same number again as
`PC_IA_VERTICES` and again as `PC_VS_INVOCATIONS` - no vertex reuse, so a delivered vertex *is* one
vertex-shader invocation, which is what makes "per vertex" a statement about the interface - 0.06-0.07 M
input primitives, matching on the TSE side and on `PC_VPC_PRIMITIVES`, 2873-2937 M pixel invocations,
211-216 M colour blocks: a spread of 1.02 across arms whose frame rate spans 10.87 to 0.92 fps - and
`VSC_INPUT_TILES` 0 in all 127 kept windows: sysmem, never binned, the same fact 40.35 recorded for this
mesh.

Against that, one thing moves, and it is the interface. `VPC_SP_COMPONENTS` per delivered vertex is
1.0011, 1.5002, 2.5004, 4.5008, 8.5109 for N = 1, 2, 4, 8, 16, and 8.5110 for the rig's own 16-vec4 pair
built from a different shader. Divided by the stride the driver programs, `VPC_VS_CNTL.STRIDE_IN_VPC` =
4N + 4, that ratio is **0.1250-0.1252 in every arm** - one event per 8 components, with the intercept
(N = 0 would give 0.5 events) showing that position's 4 components are inside the count.
`SP_EXPORT_VPC_TRANS` equals it to four significant digits in all six arms (2.140/2.890/2.541/2.304/
2.698/1.535 Mc/s), and window by window the two are the same integer in 7 to 16 of 21-22 windows, with a
median absolute difference of 0 counts in four of the five generated arms, a largest difference of 544
counts against a 1.5 M count, and **no window more than 0.1 % apart** in any arm.

Three cross-checks make the reading safe. On the pixel side the FS fetches what the interface says it must:
`SP_FS_STAGE_BARY_INSTRUCTIONS` per pixel invocation is 1.017, 2.034, 4.068, 8.135, 16.270 across the arms
- N plus the 1.7 % a killed or flat quad costs - and `SP_BARY_FP32_INSTRUCTIONS` is equal to it to three
decimals in every arm (ratio 1.0000), so nothing was packed to half precision, which is the counter-side
reading of the `fract` result in 42.1.
`SP_EXPORT_RB_TRANS` - the colour-side export, which has no reason to
care about a vertex interface - is 0.063811 to 0.063837 per pixel invocation across the five arms
(spread 1.0004) and 0.2500-0.2501 per quad: flat, while `id 48 / pixel` in the same table rises 8.5x.
And `VPC_NUM_VPCRAM_WRITE` sits at exactly 2x selector 10 in every arm (id10/VPCRAM 0.5001-0.5006), so it
is one write per 4 components - a 128-bit word - which lets the VPC's own RAM counter state the stride it
believes it is shipping: 8.00, 11.76, 20.00, 36.07, 68.12 components for the generated arms, 66.74 for
the rig's pair, and **7.99 for the 23.11 smoke run of the pre-fix probe** - read from its committed dump,
that run shipped a stride of 8, which is one vec4 plus position, which is what 42.1's disassembly says.

**Verdict.** One unit, two names. VPC selector 10 and SP selector 48 each count one event per group of 8
components of VS-output payload shipped for a delivered vertex, position included; the mesh is 8192
independent triangles per instance and shares no vertices, so "per delivered vertex" is "per vertex
shipped to the pixel pipe". They count the same events, VPC-side and SP-side, so quoting the two names as
two facts - as 40.14 and 40.27 do - double-counts one quantity. Neither is a per-pixel counter: what the
name `EXPORT_VPC_TRANS` suggests is what `SP_EXPORT_RB_TRANS` does. For RE4, 40.36's `id10 / vertex` of
0.55000-1.87157 (median 0.89284) reads as a stride of 4.4 to 15 components, that is roughly one to three
vec4 plus position per vertex - a claim that holds only while the counter counts 32-bit components, and
`e3711f4` ("a7xx: no 16-bit VPC path exists") says this driver ships none.

40.36's hedged half resolves the same way. Its residue - 2.41 % bit-identical windows, a sign flip in all
34 arms, a median magnitude of 0.00295 % of id 10 - is what two selectors reading *one* quantity look like
when they are latched at different instants: this rig's unit is identical by construction across its
arms, and it reproduces the sign flip, the 3e-5 relative median (0.00299 % in the narrowest arm, 0 % in
the others), and the low bit-identity rate (7-16 of 21-22). What this rig does *not* reproduce is RE4's
tail: 26 windows over 1 % apart, in two arms, against 0 of the 127 windows here, so the tail is a fact about
those dumps and not about the counters' relation.

One number in the same table is a warning rather than a finding: `VPC_BUSY_CYCLES` is 99.99-100.00 % of
`CP_ALWAYS_COUNT` in every arm, including the one running 0.92 fps with 8.5x the payload per vertex, while
`SP_STALL_CYCLES_VPC` over the same windows is 0.000-0.019 Mc/s of a 680 Mc/s clock - the pixel pipe is
never held up by the VPC. A busy counter pinned at full across a 12x range of load is not a measure of
load, so the busy percentages of journal 40 carry whatever weight the stall counters give them and none
from `BUSY` alone.

**Does not show.** Whether the unit is 8 components or 2 vec4 outputs - identical predictions while every
output is a full vec4, which all six arms are; an arm with `vec2` or `vec3` outputs separates them and is
queue 38. Whether `VPC_WORKING_CYCLES` counts cycles of transfer or of occupancy; the sweep only bounds
it, at 49.9 % in the narrowest arm against 15.1 % in the widest with the payload per second flat. Which
side of the RE4 tail is responsible. And nothing about the attribute-buffer carve-out: the arms never bin
(`VSC_INPUT_TILES` 0 in all windows), so queue 35 stays parked and queue 39 asks for its re-run on the
binary this entry ships.
