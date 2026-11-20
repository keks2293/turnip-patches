# 21.10. Root cause of the r2d readback zero-windows (18.11): missing CCU clean on A7XX

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

Closed the same evening as 21.8/21.9. The bug is neither BC, nor addressing, nor
engine-specific - it is **in-submit memory visibility**. On A7XX the CP_BLIT writes
of `CmdCopyBufferToImage` land in the CCU; `tu_copy_buffer_to_image` and
`tu_copy_image_to_buffer` emit no cache operations (empty `r2d_teardown`), and an
outside-renderpass pipeline barrier inserts nothing into the CS (its flush bits
collapse onto the batch). The next reader in the same submit - our readback, but
in general any UCHE read - may see pre-copy memory. The decisive A/B (`TU_I2B_SYNC`,
one line of `FD_CCU_CLEAN_COLOR` + WFI before the readback): 91/91 EXACT, every
GEOM/BC failure in the matrix disappears; `=2` (invalidate only) and `=4` (clean
without WFI) still fail; the no-env control still fails. Turnip already documents
the rule it violates ("On A7XX, blit cache flushes are required to ensure blit
writes are visible via UCHE. This isn't necessary on A6XX, all writes should be
visible implicitly") - and applies it in `store_3d_blit` and in the
`tu_copy_image_to_image` staging path, only the public copy commands skip it. This
is exactly the "works on 6xx" asymmetry, and mesa main has the same gap (verified
against gitlab main 18.11), so it is an upstream correctness find, not our lag:
vkd3d `CopyTextureRegion` texture->buffer in one command list hits it, and the
"first fill writes ~2% zeros" quirk is plausibly the same phenomenon. The earlier
signals all re-read consistently: WFI after the fill does nothing (drain is not a
CCU clean); r3d moves cases without fixing the class (same missing sync); the
per-row path keeps the windows only in the first rows (traversal starts before the
CCU has drained); CPU-FILL sees clean DRAM (the data does land - only the GPU read
is too early). Fix candidate and the full evidence chain: `docs/bugs-found.md`
final section, `experiments/exp-13b-b2i-ccu-clean-candidate.patch`, logs
`results/test-BCcopy-i2b*.log` and `results/test-BCcopy-0013cand*.log` (both the
raw event-write form and the idiomatic `flush_bits |= CCU_CLEAN_COLOR |
WAIT_FOR_IDLE; tu_emit_cache_flush()` form give 91/91). Closed without a game
A/B: games/vkd3d-proton submit between the copy and its use, RE4 never executes
the in-submit chain - which is why the game always looked fine.

Shipped anyway, as `patches/0013-turnip-b2i-ccu-clean.patch`, in the form
chosen by the exp-15 matrix (journal 21.11): lazy bits, no command at the copy. The
game A/B was not needed to justify it - it adds no work to a submit that does
not already end in a flush point, and it closes a real in-submit hole that
vkd3d `CopyTextureRegion` texture->buffer can hit. The upstream-shaped patch is
the model form (a separate blit-write access bit); 0013 is the two-line local
form for this stack.
