#!/bin/bash
# fdperf-sample.sh - a background sampler of per-block GPU counters during a game run.
#
# Why it is done this way:
#  * DRM_IOCTL_MSM_PERFCNTR_CONFIG returns EPERM on the render node without
#    root (msm keeps perfctr for itself), so fdperf is started through sudo.
#  * fdperf reads fdperf.cfg from the CWD, so every iteration chdirs into the
#    working directory that holds the binary and the config (see tools/fdperf/).
#  * -d is one period (-r ms) and a dump; the loop produces a time series that
#    is later matched against the MangoHud CSV by elapsed.
#  * The counters are GPU-global (CP perf): they measure the whole GPU load
#    while RE4 renders.  Do NOT run it together with
#    TU_AUTOTUNE_FLAGS=preempt_optimize - that one takes the last two CP
#    counters.
#
# Usage:
#   scripts/fdperf-sample.sh [duration-sec] [period-ms] [out-file] [cfg]
#   duration-sec  how long to sample (default 120)
#   period-ms     the window of one sample (default 1000)
#   out-file      where to write (default /tmp/opencode/fdperf-samples.txt)
#   cfg           the fdperf config (default tools/fdperf/fdperf.cfg;
#                 vertex run: tools/fdperf/fdperf.cfg-vertex - see its
#                 header about hw budgets)
#
# Start it AFTER the game is up and already in the scene (the warm-up title
# screen is not needed but does no harm: every sample carries a timestamp).
set -euo pipefail

DUR="${1:-120}"
PERIOD="${2:-1000}"
OUT="${3:-/tmp/opencode/fdperf-samples.txt}"
CFG="${4:-$REPO/tools/fdperf/fdperf.cfg}"

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
FDPERF="$REPO/../build/out/fdperf"

[ -x "$FDPERF" ] || { echo "no $FDPERF (build it: see docs/mesa-27-plan.md)" >&2; exit 1; }
[ -f "$CFG" ] || { echo "no $CFG" >&2; exit 1; }

WORK="$(mktemp -d /tmp/opencode/fdperf.XXXXXX)"
cp "$FDPERF" "$WORK/fdperf"
cp "$CFG" "$WORK/fdperf.cfg"
trap 'rm -rf "$WORK"' EXIT

: > "$OUT"
echo "# period_ms=$PERIOD  duration_s=$DUR  start=$(date -Is)" >> "$OUT"

end=$(( $(date +%s) + DUR ))
while [ "$(date +%s)" -lt "$end" ]; do
    {
        echo "=== sample $(date +%s.%3N) ==="
        echo "armada" | sudo -S -p '' bash -c \
            "cd '$WORK' && ./fdperf -r $PERIOD -d" 2>/dev/null
    } >> "$OUT" || echo "=== fdperf failed at $(date +%s) ===" >> "$OUT"
done

echo "# end=$(date -Is)" >> "$OUT"
echo "sampler finished: $OUT ($(grep -c '^=== sample' "$OUT") samples)"
