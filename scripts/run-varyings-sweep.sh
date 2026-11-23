#!/bin/bash
# run-varyings-sweep.sh - what do the two export counters count?  Sweep the VS/FS interface width.
#
# Queue 34 (journal 40.36).  PERF_VPC_SP_COMPONENTS (VPC selector 10) and PERF_SP_EXPORT_VPC_TRANS
# (SP selector 48) are not one signal window by window, and no committed in-game dump knows how many
# vec4 varyings cross the interface, which is the one variable that would give them a unit.  This
# rig knows: tests/vpc-attrbuf.c --varyings=N draws the same 24576 x 8 mesh into the same 768x768
# target with an interface of N vec4, N in 1, 2, 4, 8, 16.
#
# Before any arm is sampled the interface of the binary is read back from the driver's own
# disassembly (scripts/check-varyings-arms.py).  An arm whose shader pair collapsed to one fetch -
# which is what a plain sum of varyings does, journal 42.1 - would produce a perfectly smooth,
# perfectly meaningless sweep, so the run refuses to start unless the check says every requested
# arm is N wide for the binary it is about to sample.
#
# Each arm: probe in the background, sampler over its steady stretch, everything curated into
# results/synthetics/varyings/varyings<N>/ (fdperf-raw.txt, run.txt, meta.txt).  meta.txt carries
# the probe's sha256 and the expected SP_VS_OUTPUT_CNTL.OUT / VPC_VS_CNTL.STRIDE_IN_VPC of the arm,
# so a later reader can tell which binary and which interface produced the numbers.
#
# An arm may also be named `attrbuf`: the rig's own default pair (tests/vpc_attrbuf.{vert,frag}),
# sixteen vec4 wide on the same mesh since journal 42.1 corrected its fragment shader.  It is the arm
# that joins this sweep to the attribute-buffer question of journal 40.35, whose arms ran with a
# one-varying interface and have to be re-measured with this binary (queue 39).
#
# Usage: scripts/run-varyings-sweep.sh [--arms 1,2,4,8,16] [--seconds 60] [--bin ../build/vpc-attrbuf]
#        scripts/run-varyings-sweep.sh --arms attrbuf          # the default pair, 16 wide
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
source scripts/env.sh

OUTROOT="results/synthetics/varyings"
BIN="${RP6_BUILD:-../build}/vpc-attrbuf"
ICD="${ICD:-$RP6_TURNIP_ICD}"
CFG="tools/fdperf/fdperf.cfg-varyings"
SECONDS_ARM=60
SAMPLE=45
WARMUP=10
ONLY="1,2,4,8,16"

while [ $# -gt 0 ]; do
    case "$1" in
        --arms)     ONLY="$2"; shift 2 ;;
        --seconds)  SECONDS_ARM="$2"; SAMPLE=$((SECONDS_ARM - 15)); shift 2 ;;
        --bin)      BIN="$2"; shift 2 ;;
        --icd)      ICD="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

[ -x "$BIN" ] || { echo "no $BIN - build it (tests/vpc-attrbuf.c, header of the file)" >&2; exit 1; }
[ -f "$ICD" ] || { echo "no ICD at $ICD" >&2; exit 1; }
[ -f "$CFG" ] || { echo "no $CFG" >&2; exit 1; }
mkdir -p /tmp/opencode "$OUTROOT"

# ---- the gate: every requested arm must be the interface width it asks for -----------------------
# The gate's own output is a committed artifact, not scratch: each arm's meta.txt points at it, so a
# reader can see the interface the run was gated on. Same path `scripts/check-varyings-arms.py` is
# documented to write (results/synthetics/varyings/interface-check.txt).
CHECK="$OUTROOT/interface-check.txt"
VK_DRIVER_FILES="$ICD" python3 scripts/check-varyings-arms.py --probe "$BIN" --arms "$ONLY" \
    > "$CHECK" 2>&1
if [ $? -ne 0 ]; then
    echo "the interface check failed for $BIN - the arms are not what they ask for:" >&2
    sed -n '/^arm  *fps/,$p' "$CHECK" >&2
    exit 1
fi
PROBE_SHA="$(sha256sum "$BIN" | cut -c1-12)"
echo "interface verified for $(basename "$BIN") sha256=$PROBE_SHA: $(grep -c '  ok$' "$CHECK") arms ok"

SO="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["ICD"]["library_path"])' "$ICD")"
SO_SHA="$(sha256sum "$SO" 2>/dev/null | cut -c1-12)"

run_arm() {   # $1 = N
    local n="$1" dir="$OUTROOT/$1"
    # what the driver has to write for an interface of n vec4 (tests/gen-varyings-spv.sh's table);
    # the default pair is sixteen wide whatever its name
    local w=$n; [ "$n" = "attrbuf" ] && w=16
    local out=$((w + 1)) stride=$((4 * w + 4))
    mkdir -p "$dir"
    echo "--- $n: interface of $w vec4, SP_VS_OUTPUT_CNTL.OUT=$out VPC_VS_CNTL.STRIDE_IN_VPC=$stride"

    local extra=(--varyings="$n")
    [ "$n" = "attrbuf" ] && extra=()      # the rig's default pair takes no --varyings
    env VK_DRIVER_FILES="$ICD" "$BIN" --seconds="$SECONDS_ARM" "${extra[@]}" \
        > "$dir/run.txt" 2>&1 &
    local pid=$!
    sleep "$WARMUP"
    scripts/fdperf-sample.sh "$SAMPLE" 1000 "$dir/fdperf-raw.txt" "$CFG" \
        > "/tmp/opencode/varyings-sampler-$n.out" 2>&1
    wait "$pid"

    {
        echo "arm:            $n"
        echo "what:           the VS/FS interface is $w vec4 wide; everything else is the same probe"
        echo "date:           $(date -Is)"
        echo "driver:         $SO sha256 $SO_SHA"
        echo "probe:          $BIN --seconds=$SECONDS_ARM ${extra[*]}   (sha256 $PROBE_SHA)"
        echo "icd:            $ICD"
        echo "env:            VK_DRIVER_FILES only; TU_GMEM, TU_FORCE_PROPS, FD_DEV_FEATURES,"
        echo "                TU_DEBUG, IR3_SHADER_DEBUG, MESA_SHADER_CACHE_DISABLE all unset"
        echo "interface:      SP_VS_OUTPUT_CNTL.OUT=$out, VPC_VS_CNTL.STRIDE_IN_VPC=$stride, expected"
        echo "                from n (tu_pipeline.cc:1092 and :926-931); read back as $w VAR slots at"
        echo "                il = 0,4,...,$((4 * (w - 1))) in the driver's disassembly before this run"
        echo "                (scripts/check-varyings-arms.py; $CHECK)"
        echo "cfg:            $CFG"
        echo "sampler:        $SAMPLE s at 1000 ms, started ${WARMUP} s after the probe"
        echo "expect:         VFD_TOTAL_VERTICES, TSE_INPUT_PRIM, SP_PIXELS and CCU_COLOR_BLOCKS equal"
        echo "                to the other arms; VPC_SP_COMPONENTS the column that moves with n"
    } > "$dir/meta.txt"

    echo "    hash=$(sed -n 's/^hash \{0,1\}\(0x[0-9a-f]*\).*/\1/p' "$dir/run.txt") fps=$(sed -n 's/^fps //p' "$dir/run.txt") windows=$(grep -c '^=== sample' "$dir/fdperf-raw.txt" 2>/dev/null)"
}

for n in ${ONLY//,/ }; do
    case "$n" in
        attrbuf|1|2|4|8|16) ;;
        *) echo "no arm $n (known: attrbuf 1 2 4 8 16)" >&2; exit 2 ;;
    esac
    run_arm "$n"
done

echo
echo "sweep done -> $OUTROOT (probe sha256 $PROBE_SHA)"
echo "read it with: python3 scripts/varyings-table.py $OUTROOT/varyings*/"
