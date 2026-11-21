# 36. exp-21 returns the same tiling decision as 0014 on every create the game made; the gate's last item is closed (21.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md).

**Question.** `exp-21` is the rewrite of `0014` - the same rule about a `MUTABLE_FORMAT` image
created without a format list, expressed as one decision function instead of a special case in two
callers. Journal 33 measured the two builds against each other on the whole rig (0 differing lines
of 598) and recorded that the "94-row matrix" item copied into that gate belongs to a tiling patch
and cannot be run on this build; what stayed open was the second item, queue 3's game inventory:
does `exp-21` make the same tiling decision as the shipped `0014` on the game's own creates? The
answer is what stands between `exp-21` and patch `0016`.

**Method.** One more inventory run of RE4 with `build/out-exp21` (`d49d094a8d6e…`, `TU_IMG_INV`
present in the binary), compared with the reference inventory of journal 27 - the ship stack
*with* `0014`, build `050375a18b7b`, log `80d433927103ef02…`. Totals and class shares are what
`scripts/imginv-stats.py` and `scripts/imginv-classes.py` have always printed; the part the
question actually needs is per-create, and for that the entry adds
[`../../scripts/imginv-decisions.py`](../scripts/imginv-decisions.py): two images with the same
create signature (format, view format, extent, mip/array/sample counts, usage, flags, list length,
list content) have to agree in `tile=` and `ubwc=`, while an image present in one session and
absent in the other is scene content and is counted separately. Artifact:
[`../results/test-exp21-inventory-ab.log`](../results/test-exp21-inventory-ab.log).

## The decisions agree, create for create

Two runs of the patched build were needed to say that, and the reason is in the next section; the
second one, `exp21inv2`, is the one the gate is read from.

| | the shipped `0014` (imginv5) | `exp-21` (exp21inv2) |
|---|---|---|
| creates / bytes | 4 176 / 8 080.8 MiB | 4 169 / 8 088.6 MiB |
| `tile=tiled` | 6 449.9 MiB, 79.8 % | 6 461.0 MiB, 79.9 % |
| no-list, tiled | 1 450 creates / 2 450.3 MiB | 1 448 / 2 438.6 MiB |
| no-list, UBWC | 0 | 0 |
| create signatures in both logs | 784 | |
| **signatures with a different `tile=`/`ubwc=` verdict** | **0** | |
| signatures present in one log only | 0 | 0 |

The class split says the same thing in the units the patch is written in:

```
класс                                imginv5                  exp21inv2
8 bit                  1183.8 100.0 %    0.0u     1175.9 100.0 %    0.0u
32 bit                 1023.5   0.0 %    0.0u     1019.6   0.0 %    0.0u
64 bit                  666.4 100.0 %    0.0u      666.4 100.0 %    0.0u
16 bit                  606.7   0.0 %    0.0u      607.3   0.0 %    0.0u
BC (compressed)         600.7  99.9 %    0.0u      597.0  99.9 %    0.0u
```

The two classes `0014` refuses on purpose - 32-bit and 16-bit, whose members differ in channel
order - are at 0.0 % tiled in both logs. A rewrite that had quietly widened the rule would show up
here as a nonzero share, and this is the check that a rig cannot give: the rig has no textured
depth renderpass and no 4 176 real creates, and journal 33 said so about the matrix half of the
gate. What differs between the two sessions is only how many times the same image was recreated
(13 creates in one direction, 6 in the other), which is what a session a little further along the
same area looks like.

## The confound the first run carried, and what it says about reading a log

The first run, `exp21inv`, showed 19 creates whose signature was missing from the reference and
nothing extra - among them four `R8_UNORM 1024x1024 listn=0 tiled ubwc=0`. On its own terms that
reads as "the patched build created less", which would have been a finding. It was not: the
reference run had `MANGOHUD=1` and this one did not, and a 1024x1024 single-channel image is what
an overlay's font atlas looks like. Re-run with the overlay on, and both "only in the first" and
"only in the second" go to 0.

The rule this leaves behind: an inventory log is a *session*, and everything in the session creates
images - the driver, the game, and the overlay that was on screen. `scripts/run-game.sh` prints
`MANGOHUD=` in its header for exactly this reason, and the two columns of a comparison have to
agree in it before their create counts mean anything. The first run is kept in the artifact with
its numbers, not discarded: it is the record of how the confound was noticed, and on its own 775
shared signatures it also had 0 differing decisions.

## What this does not show

* Two sessions of one area at one timeout, not a sweep: a create the game reached in neither run
  is in neither log.
* `ubwc=0` on every no-list create is reference behaviour and patch behaviour alike. The gate says
  the rewrite did not change the UBWC answer; whether that answer should be different is the
  64-bit question (journal 31, queue 1), which this entry does not touch.
* No fps, no bandwidth, no claim about performance.
* The reference column is a log, not a driver we hold: build `050375a18b7b` is not in this
  repository, so the comparison is between decisions recorded in two game runs.

## Verdict

**Verdict.** On the creates the game actually made, `exp-21` is `0014`: 784 create signatures
present in both sessions, 0 of them with a different `tile=` or `ubwc=` verdict, the same share
tiled in every texel-block class, and the same no-list volume returned to tiling (2 438.6 MiB
against the reference 2 450.3, in a session with 7 fewer creates). The gate has no open item left: the rig half is `results/test-exp21-equiv-p14.log`, the
matrix item was recorded inapplicable in journal 33.1, and the inventory half is this entry.
Graduating `exp-21` to `patches/0016-turnip-mutable-no-list-tiling.patch` is now a decision rather
than a measurement - it needs the patch file written from `experiments/exp-21-*.patch` with a
header that cites these two artifacts, the tree moved from `0014` to `0016`, a rebuild, and the
release table moved with it. Nothing in this entry argues for or against the rewrite on any
generation other than the one on the bench.
