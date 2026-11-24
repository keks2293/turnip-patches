# 43. Nine of the ten counters that had never been read do move; one is dead, one pair is one counter, and none of them moves the frame rate (24.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules
for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or
`journal N.M`, where the number is also the start of the file name.

Bottom line: queue 37 asked for a first reading of the ten counter names that no committed dump on this
machine had ever carried, because a document cannot say "never measured" about a name it has never run.
Nine of the ten come back alive and one does not: `RBBM_PC_VSD_BUSY` reads 0 in 56 of 56 steady windows
of a running RE4 frame whose neighbouring RBBM counter is at 0.951 of the core clock. The two
`CCU_2D_RD/WR_REQ` selectors are bit-identical in every window, so the pair is not two counters and the
use this repository wanted them for - telling a 2D copy from a 3D one - is gone. `EVICTS` is alive but
has no unit and no partner, so the "L2 keeps most of the vertex bytes" figure stays an inference. One
genuinely useful thing came out: `PC_VPC_PRIMITIVES` reproduces journal 40.19's primitive count from a
counter journal 40 never selected (-1.9 %), and `RBBM_PC_DCALL_BUSY` turned out to be `PC_BUSY` to
0.007 %, which is why the analyzer's new column is not a new fact. Frame rate: p25 15.26, the ship
cluster. No lever, as `ADR-0008` expects.

## 43.1 Question, method, and the window the medians are taken over

**Question.** Queue 37: `tools/fdperf/fdperf.cfg-gaps` (written 23.11 from the budget audit of 41.1)
allocates ten names inside their block budgets, with a denominator beside each. It had never been run.
A first run can decide only whether a name moves at all, and three of the ten (`EVICTS`,
`CCHE_TPH/DPH_QUEUE_FULL`) have no unit in the XML, so they need a neighbouring counter with a known
meaning in the same scene.

**Method.** No build, no new code. Ship driver `build/out/libvulkan_freedreno.so`
sha256 `4c3cdb210082`, no environment delta; the game launched by
`scripts/run-game.sh patched 400`, sampling started 60 s later, two 140 s runs back to back in one
session - the cfg, then `fdperf.cfg-traffic` as the control:

```sh
scripts/fdperf-sample.sh 140 1000 /tmp/opencode/fdperf-gaps.txt tools/fdperf/fdperf.cfg-gaps
scripts/fdperf-sample.sh 140 1000 /tmp/opencode/fdperf-gaps-control.txt tools/fdperf/fdperf.cfg-traffic
```

65 windows for the cfg, 63 for the control (fdperf prints one window per ~2.1 s at `period_ms=1000`, so
140 s is ~65 windows and not 140), no wrapped or invalid deltas dropped.

The medians start at `t_rel` 20 s, and this is a measurement rule rather than a taste: in the first ~10
s of the sampling `EVICTS` reads 6-12 M/s against 2.81 M/s afterwards and `CCU_2D_*` 20-43 M/s against
5.0 M/s, so the scene is still arriving. Averaging the whole 140 s would blend two states; the reader
shows the transient behind `--lo 0`.

**Numbers.** `results/games/re4/gaps37/table.txt` (regenerate:
`scripts/fdperf-gaps-table.py --fps 15.57 | tee results/games/re4/gaps37/table.txt`), from
`fdperf-raw.txt` and `fdperf-traffic.txt` in the same directory, arm described by its `meta.txt`. fps
`results/games/re4/fps-gaps37.csv`. This entry quotes the verdicts, not the table.

## 43.2 The three things queue 37 said it would decide

**(a) `UCHE_EVICTS` - alive, and still not a cache measurement.** 56/56 windows non-zero, 2.81 M events/s
with the whole steady run inside 2.65-2.83 M/s, and stable against DRAM: one eviction per 348 of the same
window's 16-byte read beats. The control gives the only way to put a size on it: DRAM writes 0.28 GB/s
against reads 15.20 GB/s, so an event cannot carry more than **102 bytes** - a 64-byte line would be 62 %
of everything the machine writes, a 128-byte unit would be 125 % of it, which is impossible. That is a
bound, not a unit, and it assumes every eviction writes back. What it cannot do is answer the question it
was queued for: UCHE has an eviction counter and no fill or miss counter, so "what share of the vertex
bytes never reaches DRAM" stays what journal 40 derived it from.

**(b) `PC_VPC_PRIMITIVES` - a second name for the primitive count, and it agrees.** 254.8 M primitives/s,
6516 per context-done in the same window, and 16.37 M per frame at this run's 15.57 mean fps against the
16.69 M/frame journal 40.19 measured through `PC_IA_PRIMITIVES` - a counter this cfg does not program, so
the agreement is between two independent names for one quantity, not two readings of one. It is therefore
a usable primitive denominator when PC's eight slots have no room for IA. It is *not* the per-vertex
denominator queue 34 wanted; 42.2 settled that question without it, and this counter counts primitives.

**(c) `LRZ_LRZ_WRITE` - the mask is written.** 4421 events/s, one per 127,000 LRZ busy cycles, with LRZ
itself busy 83 % of the clock. So the depth path is not "read the mask, never write it". LRZ's units are
undescribed (journal 40 says so of `LRZ_PRIM_KILLED_BY_LRZ` and `LRZ_TOTAL_PIXEL`), so nothing more can be
said from the ratio, and nothing downstream waits for more.

## 43.3 What the other readings say, including the two that say nothing new

`CCHE_TPH_QUEUE_FULL` counts 933 M/s, **1.372 events per core cycle**: a counter that outruns the clock is
not counting cycles-when-full, and with no unit in the XML it stays a rate. Its depth-client twin counts
1.16 M/s, 1.7 events per 1000 cycles, so the depth client's queue is not where pressure lives.
`CMPDECMP_VBIF_WRITE_REQUEST` comes back at 2.15 M/s (it has no analyzer column, only this table's), and
against the read-data side the quotient is **1.71** - which is why `fdperf.cfg-gaps` no longer calls CMP
id 3 "bytes" in its header and why no average burst size for GMEM<->LLC follows from these two names.

**`RBBM_PC_VSD_BUSY` is dead on this machine.** 0 in 56/56 steady windows while the counter programmed
next to it in the same group runs at 0.951 of the core clock. It is now in the same list as
`UCHE_GMEM_*_BEATS` in `docs/fdperf-a7xx.md`. A zero cannot be told apart from "the path is never used"
without a synthetic that exercises whatever VSD dispatches, and nothing here does.

**`CCU_2D_RD_REQ` and `CCU_2D_WR_REQ` are one counter, not two.** Bit-identical in 56/56 windows, max
difference 0 - and this is not the block failing to program separate counters: the same block's
`GMEM_READ` and `GMEM_WRITE` differ by 4x in the committed `cfg-vertex` dumps. Their value, 5.04 M/s, is
96 % of the CMP read+write request count in the same windows, which is a 3D-path rate and not a
blitter's, so whatever these two are, they are not the 2D engine's read and write. The plan of using them
to tell a 2D copy from a 3D one (the 8bpp/NV12 question) is withdrawn; separating them needs a write-only
2D op, which is queue 45.

**`RBBM_PC_DCALL_BUSY` repeats a counter this cfg already programs.** Its ratio to `PERF_PC_BUSY_CYCLES`
is 1.00007 in every window - never identical, always within 0.008 %. So the analyzer's
previously-empty `RBBM_PCDC` column fills with "PC is busy", which the PC block's own counter had said in
every dump for a month. That also says something about domains, though not what a reader might want: a
selector programmed in the RBBM group agreeing with a core-domain counter to 0.008 % is not evidence
about domains, and `docs/fdperf-a7xx.md` still forbids a duty from RBBM counters, so the reader prints no
percentage for either of the two RBBM rows.

## Verdict

Queue 37 is answered and the counter-inventory line closes here: the audit's residual list in
`results/fdperf-cfg-budgets.txt` is now one name (`SP_GM_LOAD_LATENCY_CYCLES`, whose corrected id has
never been selected by a run since), every one of the ten resolves to a committed dump, and what each is
worth is written above rather than implied by its having a number. Nothing in this entry moves a frame
rate or touches `ADR-0008`: the ship frame in this run is p25 15.26 in the committed 40-50 s window,
which is the cluster, and that is the control for "the scene was the usual one", not a result.

## What this does not show

* It is not a fps measurement. One run, no interleaved base, no arm: 15.26 p25 says the scene was the
  usual one and nothing else.
* The 102-byte bound on an eviction is a bound, drawn across two runs (the two dumps' read traffic
  differ by 3 %, which is the accuracy of anything divided across them), and it assumes each eviction
  writes back. If part of the evictions are clean, the event can be larger.
* No unit for `EVICTS` or for either `*_QUEUE_FULL`: the bound is not a unit, and the reader prints rates.
* "Dead" for `RBBM_PC_VSD_BUSY` means dead in this scene under this cfg. The alternative, that the path
  is genuinely idle in RE4, is not excluded.
* Whether the `CCU_2D_*` pair is one hardware counter aliased under two selectors, or two selectors
  counting the same event, cannot be separated without traffic that is write-only in 2D.
* The primitive agreement is against journal 40.19's figure from a different session at a different clock
  policy; -1.9 % is an agreement, not a calibration.
* The two RBBM rows have no duty and no domain verdict; the cfg's `RBBM_ALWAYS_ON` denominator was kept
  and is not used, because that counter is the 19.2 MHz GMU tick (`docs/fdperf-a7xx.md`).
