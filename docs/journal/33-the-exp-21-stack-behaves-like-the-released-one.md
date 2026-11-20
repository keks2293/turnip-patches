# 33. The exp-21 stack behaves like the released one on every probe the rig has; the matrix half of its gate cannot be run on this build (21.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md).

**Question.** Patch `0014` is part of the released stack: it makes the UBWC decision for a
`MUTABLE_FORMAT` image created without a format list once instead of twice, so that the layout
and the linear decision cannot disagree. `exp-21` is the same rule rewritten as one decision
function (`mutable_compat_class()` / `mutable_views()` in `tu_formats.cc`) rather than a
special case in two callers. Its gate, as written in queue 1, was "behaves like `0014` before
it is allowed to become patch `0016`" (`0015` is burned: ADR-0009 took the number). What
"behaves like" could mean, on this machine, with this rig, had to be settled by a run and not
by reading the two patches.

**Method.** The strongest form available here, and the one the queue now records: **one and the
same test binary against two drivers, with the FULL logs compared** - a `diff` of every line
the default run prints, not a grep of a few sections. Two drivers:

| | driver | identity | tree |
|---|---|---|---|
| A | `build/p14-shipped/libvulkan_freedreno.so` | `c17d02bcaae9a960…` | the released stack, `0001..0014` |
| B | `build/out-exp21/libvulkan_freedreno.so` | `d49d094a8d6e…` | base `6dfa32a` + `0001..0013` + `exp-14` + `exp-21`, `0014` deliberately **not** applied (8 files, +663/-80) |

```sh
source scripts/env.sh
scripts/run-test.sh build/p14-shipped/freedreno_icd_p14.json  results/raw/ceil-nolist-p14-full.log
scripts/run-test.sh build/out-exp21/freedreno_icd.json        results/raw/test-exp21-matrix-full.log
```

One caveat about run A, stated because it is a hygiene rule of this repository (journal 29)
and not a defect of the comparison: run A was taken on 20.11 and run B on 21.11, i.e. not in
one process. What that costs is bounded by the run-to-run spread measured in journal 29 for
*this* rig - the default run is a fixed sequence of creates with no wall-clock in it, so the
columns that varied between runs in journal 29 (timings, the game inventory) are not what the
diff compares.

```
lines in A: 598   lines in B: 598
diff of the two logs, minus their '=== driver:' line: 0 lines
```

| verdict word | run A | run B |
|---|---|---|
| EXACT | 116 | 116 |
| MISMATCH | 6 | 6 |
| FAIL | 6 | 6 |
| SKIPPED | 1 | 1 |
| SUCCESS | 141 | 141 |

(the words counted over the whole log, not rows: several sections print a word; the rows
themselves are compared as text by the diff, which is the claim). The 19 named sections - the
alias/cast and view-cast probes, the seven vkd3d list matrices, the NV12 planes, the trigger
matrix, `NL`, `XV`, `UBR`, `GEOM`, `CPU-FILL`, `CEIL` - are byte-equal, including the six
`MISMATCH` and six `FAIL` rows, which are the known ones: cross-byte-order views and the
8-bit class (ADR-0001, ADR-0007).

**Verdict.** On the shapes this rig creates, `exp-21` replaces `0014` without changing
anything a reader or an application can observe: no probe, no readback row and no create
distinguishes the two drivers. That is the strongest form of "behaves like" this machine can
produce without the game, and it is why the remaining gate item is a game inventory rather
than another probe run.

Artifact: [`../../results/test-exp21-equiv-p14.log`](../../results/test-exp21-equiv-p14.log),
whose header names what the equality does **not** cover.

## 33.1 21.11 - the queue's "94-row matrix" gate item is inapplicable to this build, and the wording it corrects

Queue 1 asked, as part of the `exp-21` gate, for "the 94-row byte-roundtrip matrix". That
sentence was copied from the gate of a *tiling* patch and is wrong here in a way that would
have wasted a build: the matrix is produced by `scripts/run-b2i-matrix.sh` on a driver that
carries the `exp-15` rig, and neither driver in this comparison has it -
`grep -ac TU_B2I_SYNC` over `libvulkan_freedreno.so` is `0` for A, for B and for the
`out-exp21` build. The rig's verdict table cannot be reproduced on a build without the rig,
so the item is not "pending", it does not apply to a build of this tree, and queue 1 now says
so. The same sentence is why a reader should treat the matrix as a gate for *tiling* changes
only (it moves images out of linear; `exp-21` changes no layout for any create that has a
list).

What the gate keeps, in order:

1. **the equivalence above** - met;
2. **the game inventory column** - `exp-14` *is* in driver B (`grep -ac TU_IMG_INV` = `1`), so
   a RE4 run against `out-exp21` is what closes the half the test rig cannot reach. NOT RUN as
   an inventory yet (queue 3);
3. **graduation to `0016`** only after 2, with `0014` kept until then.

## What this does not show

* Equality of two logs is equality of *observable behaviour on the shapes the test creates*.
  It says nothing about a create the test does not attempt; the test's list of shapes is not
  the game's, which is why item 2 above exists.
* It is not a statement that the two drivers run the same code: they demonstrably do not
  (`0014` vs `exp-21`). The claim is only that no probe here distinguishes them.
* It says nothing about `exp-22`, which is a rig switch and is reverted from the tree; the
  `out-exp22` build is the same tree plus that knob (journal 32).
* The matrix rig (`exp-15`) is not in any build on disk. If a future step needs it, it needs
  a build (`out-exp21` and the released stack both answer `0` to `TU_B2I_SYNC`).

Related: journal 25 (which patch produces the UBWC in the game's format), journal 27 (the
three inventories on one scale, `0014` measured), `docs/plan-next-checks.md` queue 1 and 3.
