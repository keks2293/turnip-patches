#!/bin/bash
# Experiment 15: the cheapest form of the CP_BLIT (r2d) write-visibility fix on
# A7XX (docs/analysis.md 21.10, docs/bugs-found.md Bug 1).
#
#   scripts/run-b2i-matrix.sh out/freedreno_icd_exp15.json ["0 1 2 3 4 5 6 9 10 11 12 13 14"]
#
# Runs rp6-vkd3d-sparse-test once per TU_B2I_SYNC mode and prints the verdict of
# the byte roundtrips (the U matrix).  The driver must contain the experiment
# rig: tu_clear_blit.cc, b2i_sync_mode().
#
# TU_B2I_SYNC modes (| 8 = deferred: pay once per group of copies, in the setup
# of the next blit of the same command buffer):
#   0  off (the defect: the b2i -> i2b chain reads pre-copy memory)
#   1  FD_CCU_CLEAN_COLOR + WFI                       (the validated reference)
#   2  FD_CCU_CLEAN_BLIT_CACHE + WFI
#   3  FD_CCU_CLEAN_BLIT_CACHE alone
#   4  CCU_CLEAN_COLOR + CACHE_INVALIDATE + WFI       (also for UCHE readers)
#   5  CCU_CLEAN_BLIT_CACHE + CACHE_INVALIDATE + WFI
#   6  CCU_CLEAN_COLOR + CACHE_INVALIDATE, no WFI     (negative control)
#   7  lazy bits (flush_bits |= CCU_CLEAN_COLOR|WFI, executed at the next
#      natural flush point) - one clean+WFI per group of copies
#   15 the lazy bits without the WFI                   (negative control)
set -uo pipefail

cd "$(dirname "$0")/.."

ICD="${1:?usage: $0 <icd manifest> [modes]}"
MODES="${2:-0 1 2 3 4 5 6 9 10 11 12 13 14}"
DRIVER="$(python3 -c "import json,sys;print(json.load(open('$ICD'))['ICD']['library_path'])" 2>/dev/null)"
if [ -n "$DRIVER" ]; then
    echo "driver: $DRIVER sha256=$(sha256sum "$DRIVER" | cut -c1-12)"
fi

printf '%-5s %-7s %-9s %s\n' mode MISMATCH EXACT verdict
for m in $MODES; do
    out="results/test-b2isync-$m.log"
    TU_B2I_SYNC="$m" scripts/run-test.sh "$ICD" "$out" >/dev/null 2>&1
    bad=$(grep -c 'MISMATCH' "$out")
    ok=$(grep -c 'EXACT' "$out")
    verdict=PASS
    [ "$bad" = 0 ] || verdict=FAIL
    [ -s "$out" ] || verdict="NO LOG"
    printf '%-5s %-7s %-9s %s\n' "$m" "$bad" "$ok" "$verdict"
done
