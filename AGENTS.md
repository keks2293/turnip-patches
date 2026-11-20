# AGENTS.md - how work is done in this repository

Instructions for anyone (agent or human) editing this repo. The documentation
rules - what goes where, and in what language - are in the second half.

## Language

* **Documents, patch headers, commit messages, code comments: English.** The repo
  was English from the first commit; `docs/findings-2026-11-19.md` was the only
  exception and is being dissolved (see the last section here). New text is
  English; if you touch a non-English passage, rewrite that passage in English in
  the same commit. Quoted device output, log lines and upstream commit titles
  stay as they are.
* Conversation with the operator: Russian, unless they switch.

## Working rules, each earned by an incident

* Work on branch `test`. `master` and the tag `27.0.0-devel-p14` are the shipped
  state: no commit, no rebase, no file edit there. Shipped `.so`
  (`c17d02bcaae9a960…`) and every recorded hash stay valid forever.
* Keep `test` pushed: work that is not on `origin/test` does not exist.
* The Mesa trees (`../mesa27-src`, `../mesa26-src`) are working trees with patches
  applied by hand. **Never `git checkout`/`git restore` there** - it once dropped
  a hunk of `0008`. Apply and revert with `git apply` / `git apply -R` and
  **explicit file names**; `ls | head -1` picks the mesa26 twin of a patch.
  `git log -S` is useless in the shallow clone: use
  `https://gitlab.freedesktop.org/mesa/mesa/-/raw/main/<path>` and
  `/-/commit/<sha>.patch` for upstream lookups (the MR discussion API is not
  readable).
* Minimal patch footprint ("nothing extra"): a new prop or gate is scoped to the
  generation that needs it, and a tiling patch may only pull images out of linear,
  never push them into it.
* A driver build runs in the container, `-j2`, ccache under `/tmp`, never while the
  game is running. Builds are identified by `sha256sum ... | cut -c1-12`, not by
  version (`MESA_GIT_SHA1` is not embedded).
* Before writing "the hardware can/cannot": re-read the tool source and the raw
  log. Two published conclusions this month were wrong in exactly that place
  (analysis §22.1, §22.2).

## Documentation rules

What goes where. Written 20.11 after two files started

carrying the same numbers twice (`docs/analysis.md` and
`docs/findings-2026-11-19.md`) and after one measurement was published here in a
stronger form than the data supported (analysis §22.1 - the counter printed the
number of *wrong* elements, the summary printed it as "readable").

Borrowed from: Diataxis (separate reference from explanation), ADR/MADR (a
decision is a small immutable record with a status, superseded rather than
edited), Linux kernel practice (the rationale for a patch lives in the patch
header and the commit message, not in a parallel document), reproducible-research
practice (a claim ships with its command and its raw output, or it is marked as
not reproduced).

### One fact, one home

Every number, hash and verdict has exactly one owning file. Anywhere else it is
a pointer, not a copy. If a second copy is needed for reading comfort, it must
name the owner ("measured in analysis §22.3") so a correction has one place to
land.

| kind of fact | owner | what everyone else writes |
|---|---|---|
| what an experiment asked, how it was run, what came back | `docs/analysis.md`, one `## NN` section per experiment, append-only | `see analysis §NN` |
| a verdict that closes a branch ("keep X off", "drop patch Y") | `docs/decisions/ADR-NNNN-*.md` | the status line + link |
| why patch N exists, what it must not do | the patch header in `patches/00NN-*.patch` | link to the patch |
| shipped code, hashes, matrix counts, versions | `docs/release.md` (provenance) | "ship build `<hash>`" |
| artifacts: tools, scripts, logs, what each proves | `results/` registry table in README (`What's here`) / file header | the file name |
| how to build / run / measure | README `Build and tests`, `docs/release.md`, script headers | the command |
| what to do next | `docs/plan-next-checks.md`, `docs/mesa-27-plan.md` | queue item + link |
| state of a workstream right now | `docs/streams/<direction>.md` | links, never new numbers |

### Document types

1. **Journal** - `docs/analysis.md`. One section per experiment, in the order the
   experiments happened. Contents of a section: question, method, exact command,
   numbers, verdict, artifact paths, and "what this does not show". Corrections
   are added as a dated paragraph inside the section; the wrong sentence stays
   visible with a strike or a "retracted" note, because the point of a journal is
   that a later reader can see how the conclusion moved.
2. **Decision record** - `docs/decisions/ADR-NNNN-<slug>.md`, ~15 lines:
   `Status` (accepted / superseded by ADR-x), `Context`, `Decision`,
   `Consequences`, `Evidence` (artifact paths, upstream commit ids). Immutable
   once accepted. These are the records that today are buried in four places at
   once (a topic section, a journal section, a queue bullet and a plan file).
3. **Direction page** - `docs/streams/<direction>.md`. The current state of one
   workstream: what is believed, what is open, which patches/experiments/decisions
   belong to it, what the next measurement is. Short (a screen or two), rewritten
   freely, cites the journal rather than repeating it.
4. **Reference** - tables with no prose: patch list, hashes, artifact registry,
   device property tables (`docs/a7xx-gen-props.md`).
5. **How-to** - commands to reproduce an environment or a measurement.
6. **Archive** - frozen reports and superseded plans. Dated file names, no
   further edits.

Directions currently in use: `ubwc-format-lists`, `r2d-ccu-clean`,
`mutable-lazy-deposition`, `8bpp-ubwc`, `re4-perf`, `measurement-tooling`,
`release-build`.

### Naming

* experiment: `experiments/exp-NN-<slug>.patch` (+ its section in the journal);
* decision: `docs/decisions/ADR-NNNN-<slug>.md`;
* curated log: `results/<direction>-<what>.log`, header must state the tool, the
  driver build hash, the environment, and how to regenerate it;
* raw logs stay in `results/raw/` (gitignored) - a curated file is what git sees.

### Honesty rules, all of them learned the expensive way

* A number points at a committed artifact. If the artifact is not in git, the
  file says where it is and how to regenerate it.
* `NOT BUILT` / `NOT MEASURED` are valid sentences and must be used instead of a
  plausible value.
* A driver allocation is not a statement about hardware. `+0x2000` in `memreq`
  means the driver reserved a metadata plane (analysis §21.7); it does not mean
  the chip compressed anything (analysis §22.2).
* A round-trip proves the mode that actually received the feature, and only the
  path it was read through. Say which reader and which engine, and name the
  control run (analysis §22.1).
* When a claim is corrected, the correction names the old wording.

## Dissolving `docs/findings-2026-11-19.md`

The 19.11 consolidated report was written as a ship snapshot and grew a second
copy of the experiment narrative. Target:

| section of that file | where it goes |
|---|---|
| stand, versions, build identification | `docs/release.md` (provenance) |
| measurement methodology, the nine classes of measurement error, the pipeline-cache and "1.86 fps" artifacts | `docs/streams/measurement-tooling.md` + README how-to |
| per-topic experiment narrative (feature level, UBWC lists, r2d, lazy deposition, 8bpp, perf) | already in `docs/analysis.md` sections; only the verdicts move, to `docs/decisions/` and `docs/streams/` |
| artifact registry, open questions, next steps, queue | README table, `docs/plan-next-checks.md` |
| chronology, summary-of-numbers appendix | `docs/release.md` history / `docs/archive/` |

After that the file is deleted, not renamed: the ship record it was written for
already exists as `docs/release.md`, and a second "report" file is how the
duplication started.
