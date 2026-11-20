# AGENTS.md - how work is done in this repository

Instructions for anyone (agent or human) editing this repo. The documentation
rules - what goes where, and in what language - are in the second half.

## Language

* **Documents, patch headers, commit messages, code comments: English.** New text is
  English; if you touch a non-English passage outside the archive, rewrite that passage
  in English in the same commit. Quoted device output, log lines and upstream commit
  titles stay as they are. The one exception was the 19.11 report; it is dissolved and
  archived as `docs/archive/2026-11-19-consolidated-report.md` (last section here), so
  Russian now exists only in the archive and in quoted output.
* Conversation with the operator: Russian, unless they switch.

## Working rules, each earned by an incident

* Work on branch `test`. `master` and the tag `27.0.0-devel-p14` are the shipped
  state: no commit, no rebase, no file edit there. Shipped `.so`
  (`c17d02bcaae9a960…`) and every recorded hash stay valid forever.
* Keep `test` pushed: work that is not on `origin/test` does not exist.
* The Mesa tree (`../mesa27-src`) is a working tree with patches applied by hand; there
  is no Mesa 26 tree on this machine, only the Mesa 26 twin of a patch file
  (`patches/0002-add-a830-chip-id-mesa26.patch`, which `ls | head -1` picks before the
  Mesa 27 form). **Never `git checkout`/`git restore` there** - it once dropped
  a hunk of `0008`. Apply and revert with `git apply` / `git apply -R` and
  **explicit file names**.
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
  (journal 22.1, 22.2).

## Where to look first

| you need | open |
|---|---|
| is this question already answered, and where | [`docs/analysis.md`](docs/analysis.md) - the journal index (status column tells you whether to read at all), or `docs/journal/manifest.json` for a machine-readable version |
| the verdict on a closed branch | [`docs/decisions/`](docs/decisions/) |
| where a direction stands today | [`docs/streams/`](docs/streams/) |
| a command: build, run, measure | [`docs/howto-measure.md`](docs/howto-measure.md), README `Build and tests` |
| a hash, a version, what shipped | [`docs/release.md`](docs/release.md) |
| what a file in this repo is for | [`docs/artifacts.md`](docs/artifacts.md) |
| what to do next | [`docs/plan-next-checks.md`](docs/plan-next-checks.md) |

## Documentation rules

Written 20.11 after two files started carrying the same numbers twice
(`docs/analysis.md` and the 19.11 report, now archived) and after one measurement was
published here in a stronger form than the data supported (journal 22.1 - the counter
printed the number of *wrong* elements, the summary printed it as "readable").

Borrowed from: Diataxis (separate reference from explanation), ADR/MADR (a
decision is a small immutable record with a status, superseded rather than
edited), Linux kernel practice (the rationale for a patch lives in the patch
header and the commit message, not in a parallel document), reproducible-research
practice (a claim ships with its command and its raw output, or it is marked as
not reproduced).

### One fact, one home

Every number, hash and verdict has exactly one owning file. Anywhere else it is a
pointer, not a copy - and a pointer names its owner ("measured in journal 22.3"), so a
correction has one place to land. Two live copies of one number is the failure this
repository already had once (journal 22.1).

| kind of fact | owner | what everyone else writes |
|---|---|---|
| what an experiment asked, how it was run, what came back | `docs/journal/NN-<slug>.md`, one entry per experiment, append-only | `journal NN` or `journal NN.M` |
| which entry answers a question, and whether it is still live | `docs/analysis.md` (generated index) and `docs/journal/manifest.json` | a link to the entry |
| a verdict that closes a branch ("keep X off", "drop patch Y") | `docs/decisions/ADR-NNNN-<slug>.md` | `ADR-NNNN` |
| why patch N exists and what it must not do | the header of `patches/00NN-*.patch` | the patch number |
| shipped code, hashes, reference builds, versions, chronology | `docs/release.md` | "ship build `<hash>`" |
| what a tool, script or log is for and what it proves | `docs/artifacts.md` | the file name |
| how to build, run, measure | `docs/howto-measure.md`, README `Build and tests`, script headers | the command |
| what to do next, what is unexplained | `docs/plan-next-checks.md`, `docs/mesa-27-plan.md` | the queue item |
| where a direction stands right now | `docs/streams/<direction>.md` | links, never new numbers |

### Document types

1. **Journal** - `docs/journal/`, one file per experiment, `NN-<slug>.md`, the number
   stable forever and never reused. An entry holds: question, method, the exact command,
   numbers, verdict, artifact paths, and "what this does not show". Corrections are added
   as a dated paragraph *inside* the entry and the superseded sentence stays visible: the
   value of a journal is that a later reader sees how the conclusion moved.
   `docs/analysis.md` and `docs/journal/manifest.json` are generated from the entries by
   `scripts/gen-journal-index.py` - never edit them by hand.
2. **Decision record** - `docs/decisions/ADR-NNNN-<slug>.md`, one page: `Status`
   (accepted / superseded by ADR-x), `Context`, `Decision`, `Consequences`, `Evidence`.
   Immutable once accepted; a changed verdict is a new ADR that supersedes the old one,
   which keeps its number. Index: `docs/decisions/README.md`.
3. **Direction page** - `docs/streams/<direction>.md`: what is believed, what is open,
   which patches/experiments/decisions belong to it, what the next measurement is. One or
   two screens, rewritten freely, cites the journal instead of repeating it.
4. **Reference** - tables without prose: `docs/artifacts.md`, `docs/a7xx-gen-props.md`,
   the patch list, the hash list.
5. **How-to** - commands that reproduce an environment or a measurement
   (`docs/howto-measure.md`, README, script headers).
6. **Archive** - `docs/archive/<date>-<name>.md`: frozen reports and superseded plans,
   with a banner naming where the content went. An archive page is never cited as
   evidence.

Directions in use: `ubwc-format-lists`, `r2d-ccu-clean`, `mutable-lazy-deposition`,
`8bpp-ubwc`, `re4-perf`, `measurement-tooling`, `release-build`.

### Writing for a reader who does not skim

An agent reads this repository one file at a time, in whatever order a search returns.
So:

* an entry is self-contained enough to quote without opening a neighbour, and starts with
  a link back to the index;
* the number is the address: `journal 22.3` must resolve to a file and a heading without
  searching. Renumbering is forbidden; adding `22.4` is not;
* a reader must be able to tell "settled" from "still live" without reading the body -
  that is what the `status` column in the index and `STATUS` in
  `scripts/gen-journal-index.py` are for;
* headings are complete sentences in English (`Google style guide`: one page one topic,
  one H1, unique heading names); no in-file anchors that depend on scroll position;
* a claim names its artifact in the same paragraph as the number, so a copied sentence
  still carries its provenance;
* tables beat prose for numbers; prose beats tables for causes.

### Naming

* journal entry: `docs/journal/NN-<slug>.md` (and `NN-M-<slug>.md` when a numbered part
  was later promoted to an entry of its own, as `21-10` was);
* experiment: `experiments/exp-NN-<slug>.patch`, cited together with its entry;
* decision: `docs/decisions/ADR-NNNN-<slug>.md`;
* curated log: `results/<direction>-<what>.log`, with a header naming the tool, the
  driver build hash, the environment and how to regenerate it;
* raw logs stay in `results/raw/` (gitignored) - a curated file is what git sees and what
  a claim may cite.

### Honesty rules, all of them learned the expensive way

* A number points at a committed artifact. If the artifact is not in git, the file says
  where it is and how to regenerate it.
* `NOT BUILT` / `NOT MEASURED` are valid sentences and must be used instead of a
  plausible value.
* A driver allocation is not a statement about hardware. `+0x2000` in `memreq` means the
  driver reserved a metadata plane (journal 21.7); it does not mean the chip compressed
  anything (journal 22.2).
* A round-trip proves the mode that actually received the feature, and only the path it
  was read through. Say which reader and which engine, and name the control run
  (journal 22.1, and the `clear_only` row of journal 23 as the model of a control).
* A tool's counter semantics are read in the tool's source before its output is quoted
  (journal 22.1: `tp8bpp` prints wrong elements, a summary printed them as readable).
* When a claim is corrected, the correction names the wording it corrects.
* A vendor document that is not in this repository is corroboration, never an "artifact":
  say which table it is and that it is not committed (the 80-78185-2 surface-format
  table, journal 22 / `docs/streams/8bpp-ubwc.md`).

## The 19.11 consolidated report (done)

`docs/findings-2026-11-19.md` was a ship snapshot that grew a second copy of the
experiment narrative; on 20.11 it was dissolved and moved to
`docs/archive/2026-11-19-consolidated-report.md` with a banner. The stand and the
reference builds went to `docs/release.md`, the methodology and its artefacts to journal
29 and `docs/howto-measure.md`, the 19-20.11 measurements that existed only there to
journal 23-28, the verdicts to `docs/decisions/`, the live state to `docs/streams/`, the
registry to `docs/artifacts.md`, the queue and open questions to
`docs/plan-next-checks.md`, the chronology to `docs/release.md`.

It is kept in the archive instead of deleted because it is the frozen record of what was
believed on that evening, and deleting the only copy of some wording would make the
corrections unverifiable. It owns nothing and cites nothing.
