#!/bin/bash
# One measured arm of one game: launch, one screenshot at a fixed elapsed time, an
# fdperf sample set over the steady stretch, then curate everything into
# results/games/<title>/<tag>/ together with a meta.txt that says what this arm *is*
# and how it differs from the ship stack and from the other arms of the chain.
#
#   scripts/run-arm.sh <TAG> [ENV=VALUE ...]
#
# The ENV=VALUE arguments are the delta of the arm (TU_DEBUG=..., VKD3D_CONFIG=...,
# TU_GMEM=...): they are what meta.txt records and what a later reader compares.  The
# driver is whatever build/out holds (ICD= overrides, as in run-game.sh).
#
# Curation written here, so that no arm is left half-curated:
#   results/games/<title>/<tag>/fdperf-raw.txt   the counter dump (copy of raw)
#   results/games/<title>/<tag>/meta.txt         game, driver sha256, env delta, cfg, chain
#   results/games/<title>/fps-<tag>.csv          MangoHud csv
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1

TITLE="${TITLE:-re4}"                  # one directory per measured title
OUT="results/games/$TITLE"
RAW="$OUT/raw"
TAG="${1:?usage: run-arm.sh <TAG> [ENV=VALUE ...]}"; shift || true

GAMEARGS=("$@")
mkdir -p "$RAW" "$OUT/$TAG"

env "${GAMEARGS[@]}" TAG="$TAG" HUDLOG="${HUDLOG:-180}" HUDINTERVAL="${HUDINTERVAL:-100}" \
    scripts/run-game.sh patched "${TIMEOUT:-210}" > "/tmp/opencode/run-$TAG.out" 2>&1 &
GPID=$!

echo "game launched $(date +%T)"
sleep 60
# The screenshot is recorded with the panel state it was taken in.  A powered-off output yields a
# black frame (a capture with the panel on has thousands of distinct colours, one with it off has
# 1), so without this line a black shot cannot be told apart from a black screen.
DPMS="$(cat /sys/class/drm/card*-*/dpms 2>/dev/null | paste -sd/ -)"
python3 scripts/shot.py "$RAW/shot-$TAG.png" 30 > /dev/null 2>&1
SHOT_COLS="$(python3 - "$RAW/shot-$TAG.png" <<'PY' 2>/dev/null
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGB").resize((160, 90))
px = im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata()
print(len(set(px)))
PY
)"
scripts/fdperf-sample.sh 110 1000 "$RAW/fdperf-$TAG.txt" \
    "${SAMPCFG:-tools/fdperf/fdperf.cfg-vpc}" > "/tmp/opencode/sampler-$TAG.out" 2>&1

wait "$GPID"
latest=$(ls -t /tmp/opencode/mangologs/${TITLE}_*.csv 2>/dev/null | grep -v _summary | head -1)
[ -n "$latest" ] && cp "$latest" "$OUT/fps-$TAG.csv"

cp "$RAW/fdperf-$TAG.txt" "$OUT/$TAG/fdperf-raw.txt" 2>/dev/null || true

# meta.txt: the answer to "what makes this arm different from that one".  The driver is
# identified by the sha256 prefix of the .so the ICD actually points at, not by a version.
ICD_JSON="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["ICD"]["library_path"])' \
    ../build/out/freedreno_icd.json 2>/dev/null || true)"
SO_SHA="$(sha256sum "$ICD_JSON" 2>/dev/null | cut -c1-12)"
{
  echo "# game:    $(sed -n 's/^# game: //p' "results/raw/game-patched-$TAG.log" 2>/dev/null | head -1)"
  echo "# title:   $TITLE"
  echo "# tag:     $TAG"
  echo "# date:    $(date -Is)"
  echo "# driver:  ${ICD_JSON:-<unresolved>} sha256=${SO_SHA:-unknown}"
  echo "# cfg:     ${SAMPCFG:-tools/fdperf/fdperf.cfg-vpc}"
  echo "# env:     ${GAMEARGS[*]:-<none>}   (delta against the plain ship stack)"
  echo "# shot:    $RAW/shot-$TAG.png, ${SHOT_COLS:-?} distinct colours at 160x90; panel dpms=$DPMS"
  echo "#           (a capture of this compositor with the panel off is black; the content check is"
  echo "#            counter reproduction between arms, see docs/howto-measure.md)"
  echo "# chain:   $(basename "${CHAIN:-interactive}")"
  echo "# source:  results/raw/game-patched-$TAG.log (gitignored), fps: $OUT/fps-$TAG.csv"
} > "$OUT/$TAG/meta.txt"

echo "== $TAG =="
sed -n '1,8p' "$OUT/$TAG/meta.txt"
echo "csv: $(wc -l < "$OUT/fps-$TAG.csv" 2>/dev/null) lines | samples: $(grep -c '^=== sample' "$RAW/fdperf-$TAG.txt" 2>/dev/null) | shot: $(ls -l "$RAW/shot-$TAG.png" 2>/dev/null | awk '{print $5}')"
