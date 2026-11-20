# 21.11. The form of the fix: the exp-15 matrix and why mode 7 (18.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

Rig: `experiments/exp-15-b2i-sync-env-bundle.patch` (NOT FOR COMMIT),
`TU_B2I_SYNC=0..15` selects what the driver does after every
`vkCmdCopyBufferToImage`; `TU_B2I_COUNT` counts copies. `|8` is the deferred
form: do nothing at the copy, flush what has accumulated once in the setup of
the next blit in the same command buffer. Thirteen modes were run; the full
matrix (94 checks, `tests/rp6-vkd3d-sparse-test.c`, logs
`results/test-b2isync-{0..15}.log`, build `cd436fd897f2`):

| mode | what it does | MISMATCH | EXACT | verdict |
|---|---|---|---|---|
| 0 | off (the defect) | 19 | 75 | FAIL |
| 1 | `CCU_CLEAN_COLOR` + WFI per copy | 0 | 94 | PASS |
| 2 | `CCU_CLEAN_BLIT_CACHE` + WFI | 19 | 75 | FAIL |
| 3 | `CCU_CLEAN_BLIT_CACHE` | 19 | 75 | FAIL |
| 4 | `CLEAN_COLOR` + `CACHE_INVALIDATE` + WFI | 0 | 94 | PASS |
| 5 | `CLEAN_BLIT_CACHE` + `CACHE_INVALIDATE` + WFI | 19 | 75 | FAIL |
| 6 | `CLEAN_COLOR` + `CACHE_INVALIDATE`, no WFI | 0 | 94 | PASS |
| **7** | **lazy bits: `flush_bits \|= CLEAN_COLOR \| WFI`** | **0** | **94** | **PASS - chosen** |
| 15 | lazy bits without the WFI (control) | 0 | 94 | PASS |
| 9 | 1\|8 (deferred clean+WFI) | 0 | 94 | PASS |
| 12 | 4\|8 | 0 | 94 | PASS |
| 14 | 6\|8 | 0 | 94 | PASS |
| 10 | 2\|8 | 19 | 75 | FAIL |
| 13 | 5\|8 | 19 | 75 | FAIL |

What follows from it:

* **The aperture matters.** `CCU_CLEAN_COLOR` is the right one;
  `CCU_CLEAN_BLIT_CACHE` does nothing at all (2/3/5/10/13 behave exactly like
  0). The reason is that r2d writes to sysmem through CCU color, while the
  blit cache is a different mechanism (`tu_cmd_buffer.cc:5887`, the
  `CP_EVENT_WRITE::BLIT` -> GMEM-read dependency). It also explains why the
  existing `BLIT_CACHE_CLEAN` cannot "cure" the defect.
* **The WFI is needed only for a bare clean.** Mode 4 (with invalidate) passes
  without the WFI as well (6): `CACHE_INVALIDATE` orders by itself. The
  expectation "6 is the negative control" did not hold; the invalidate form is
  just more expensive (two events per copy) and is not needed for the fix.
* **Mode 7 is stable**: 94/94 over three repeats, and it is the only form that
  pays nothing in the middle of a sequence of copies. Cost:

  | form | per copy | per group |
  |---|---|---|
  | 0 (no fix) | 0 | 0 |
  | 1 (clean+WFI inline) | 1 clean + 1 WFI | N |
  | 7 (lazy bits) | 0 | 1 clean + 1 WFI |
  | 4/6 (with invalidate) | 2 events + WFI | N |

* **The `DST_FLUSH` rule is not touched.** `tu_cmd_buffer.cc:5847` -
  `DST_FLUSH(CCU_COLOR, CCU_CLEAN_COLOR, CCU_INVALIDATE_COLOR)`: when the
  barrier destination is in CCU_COLOR, i.e. it is a blit, the pending color
  clean is excluded from `ALL_CLEAN` (`& ~CCU_CLEAN_COLOR`) - "a blit does not
  read through the CCU". That is why the barrier after b2i could not flush
  anything; 0013 does not change the rule, it puts the bit straight into
  `flush_bits`, where the nearest natural flush point picks it up.
* **The "`CmdExecuteCommands` loses the lazy bits" hypothesis is refuted.**
  `tu_EndCommandBuffer` for a non-renderpass CB always does
  `tu_clean_all_pending()` + `tu_emit_cache_flush()` (and adds its own
  `CCU_CLEAN_COLOR|CCU_CLEAN_DEPTH`), and `tu_CmdExecuteCommands` does the
  same for the primary before chaining the secondaries
  (`tu_cmd_buffer.cc:6480-6487`). `WAIT_FOR_IDLE` is not in `ALL_CLEAN`, but
  0013 puts it straight into `flush_bits`, so it is executed too. No separate
  bit carry is needed; 0014 (the next section) is about something else.
