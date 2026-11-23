#!/bin/bash
# run-attrbuf-sweep.sh - does the VPC attribute-buffer carve-out do anything on A740?
#
# The arms and the reason each exists (journal 40.35, queue 35):
#
#   Raising gmem_vpc_attr_buf_size to S does two things at once: it makes
#   emit_vpc_attr_buf() write VPC_ATTR_BUF_GMEM_SIZE/_BASE and PC_ATTR_BUF_GMEM_SIZE, and
#   it takes 6*S bytes off usable GMEM (num_ccu = 6 for FD740, fd6_gmem_cache.h:108-109),
#   which changes the bin count by itself.  So every prop arm is measured twice: once with
#   the prop and once with `TU_GMEM` reduced by exactly the same number of bytes and no
#   prop.  The two have identical usable GMEM and identical CCU offsets; the only
#   difference between them is the three register writes.  prop(S) - control(S) is the
#   effect of the registers, and nothing else.
#
#   Sizes: 4096 (24 KiB carve), 0xc000 = 49152 (288 KiB, the a7xx_gen3 value and what 40.9
#   ran in-game), 0x20000 = 131072 (768 KiB, the a7xx_gen3 sysmem value).  Never above
#   0x20000: gs_vpc_adjacency_quirk records that certain VPC buffer sizes hang a750 and
#   nothing says the inverse is safe on a740, so the sweep stays inside sizes some
#   shipping a7xx GPU actually uses.
#
#   The two `*-loop64` arms repeat the pair with ALU work behind the varyings, because a
#   buffer behaves differently when the consumer drains slowly; they are the regime where
#   a real carve-out should show the largest effect, and if the effect is absent there
#   too the answer does not depend on the workload.
#
# Each arm: probe starts, warms up, fdperf samples the steady stretch, everything is
# curated into results/synthetics/attrbuf/<arm>/ (fdperf-raw.txt, run.txt, meta.txt).
# The probe prints the GMEM size the kernel reports, which is what the control arms are
# computed from; the script refuses to guess it.
#
# Usage: scripts/run-attrbuf-sweep.sh [--arms base,prop-128k,...] [--seconds 100]
#                                       [--loop-default 0] [--bin ../build/vpc-attrbuf]
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
source scripts/env.sh

OUTROOT="results/synthetics/attrbuf"
BIN="${RP6_BUILD:-../build}/vpc-attrbuf"
ICD="${ICD:-$RP6_TURNIP_ICD}"
SECONDS_ARM=100
SAMPLE=90
WARMUP=6
ONLY=""

while [ $# -gt 0 ]; do
    case "$1" in
        --arms)     ONLY="$2"; shift 2 ;;
        --seconds)  SECONDS_ARM="$2"; SAMPLE=$((SECONDS_ARM - 10)); shift 2 ;;
        --bin)      BIN="$2"; shift 2 ;;
        --icd)      ICD="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

[ -x "$BIN" ] || { echo "no $BIN - build it (tests/vpc-attrbuf.c, header of the file)" >&2; exit 1; }
[ -f "$ICD" ] || { echo "no ICD at $ICD" >&2; exit 1; }
mkdir -p /tmp/opencode "$OUTROOT"

# The driver the ICD actually points at, so meta.txt identifies the build and not a version.
SO="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["ICD"]["library_path"])' "$ICD")"
SO_SHA="$(sha256sum "$SO" 2>/dev/null | cut -c1-12)"

# ---- the kernel's GMEM, from the probe itself (2 s, no hash, no sampling) --------------
GMEM="$(VK_DRIVER_FILES="$ICD" "$BIN" --seconds=2 --no-hash 2>/dev/null |
        sed -n 's/^# gmem  *kernel reports \([0-9]*\) bytes.*/\1/p')"
case "$GMEM" in
    ''|0) echo "could not read the GMEM size from $BIN - the control arms would be meaningless" >&2; exit 1 ;;
esac
echo "kernel GMEM: $GMEM bytes ($(python3 -c "print(f'{$GMEM/1048576:.2f}')") MiB)"

NUM_CCU=6   # freedreno_devices.py:1241 (GPUId 740 / FD740 / X1-85)
carve() { echo $(( $1 * NUM_CCU )); }

# name, usable-GMEM override, extra env, probe args, what this arm is
run_arm() {
    local name="$1" gmem="$2" extra="$3" pargs="$4" what="$5"
    if [ -n "$ONLY" ] && ! echo ",$ONLY," | grep -q ",$name,"; then
        return 0
    fi
    local dir="$OUTROOT/$name"
    mkdir -p "$dir"
    echo "--- $name: $what"

    local env_args=(VK_DRIVER_FILES="$ICD")
    [ -n "$gmem" ] && env_args+=(TU_GMEM="$gmem")
    for kv in $extra; do env_args+=("$kv"); done

    # probe in the background, sampler over its steady stretch
    env "${env_args[@]}" "$BIN" --seconds="$SECONDS_ARM" $pargs \
        > "$dir/run.txt" 2>&1 &
    local pid=$!
    sleep "$WARMUP"
    scripts/fdperf-sample.sh "$SAMPLE" 1000 "$dir/fdperf-raw.txt" \
        tools/fdperf/fdperf.cfg-attrbuf > "/tmp/opencode/attrbuf-sampler-$name.out" 2>&1
    wait "$pid"

    {
        echo "arm:            $name"
        echo "what:           $what"
        echo "date:           $(date -Is)"
        echo "driver:         $SO sha256 $SO_SHA"
        echo "icd:            $ICD"
        echo "probe:          $BIN --seconds=$SECONDS_ARM $pargs"
        echo "env:            ${env_args[*]}"
        echo "gmem_kernel:    $GMEM"
        [ -n "$gmem" ] && echo "tu_gmem:        $gmem (usable GMEM $(( GMEM - gmem )) bytes below the kernel value)"
        [ -z "$gmem" ] && echo "tu_gmem:        unset (kernel GMEM)"
        echo "cfg:            tools/fdperf/fdperf.cfg-attrbuf"
        echo "sampler:        $SAMPLE s at 1000 ms, started ${WARMUP} s after the probe"
        echo "expect:         hash identical to the other arms"
    } > "$dir/meta.txt"

    local hash fps
    hash="$(sed -n 's/^hash \{0,1\}\(0x[0-9a-f]*\).*/\1/p' "$dir/run.txt")"
    fps="$(sed -n 's/^fps //p' "$dir/run.txt")"
    echo "    hash=${hash:-none} fps=${fps:-none} windows=$(grep -c '^=== sample' "$dir/fdperf-raw.txt" 2>/dev/null)"
}

# name                     usable-GMEM override              env                                                probe args   what
run_arm base                ""                                ""                                                    ""         "stock: the registers are never written"
run_arm ctrl-24k            "$(( GMEM - $(carve 4096) ))"     ""                                                    ""         "control for prop-4k: 24 KiB less GMEM, no register writes"
run_arm prop-4k             ""                                "TU_FORCE_PROPS=has_gmem_vpc_attr_buf FD_DEV_FEATURES=gmem_vpc_attr_buf_size=4096" "" "prop on, buffer 4 KiB (24 KiB carve)"
run_arm ctrl-288k           "$(( GMEM - $(carve 49152) ))"    ""                                                    ""         "control for prop-48k: 288 KiB less GMEM"
run_arm prop-48k            ""                                "TU_FORCE_PROPS=has_gmem_vpc_attr_buf FD_DEV_FEATURES=gmem_vpc_attr_buf_size=49152" "" "prop on, buffer 0xc000 (the a7xx_gen3 GMEM value, and 40.9's in-game arm)"
run_arm ctrl-768k           "$(( GMEM - $(carve 131072) ))"   ""                                                    ""         "control for prop-128k: 768 KiB less GMEM"
run_arm prop-128k           ""                                "TU_FORCE_PROPS=has_gmem_vpc_attr_buf FD_DEV_FEATURES=gmem_vpc_attr_buf_size=131072" "" "prop on, buffer 0x20000 (the a7xx_gen3 sysmem value)"
run_arm base-loop64         ""                                ""                                                    "--loop=64" "stock with ALU behind the varyings: the slow-drain regime"
run_arm prop-128k-loop64    ""                                "TU_FORCE_PROPS=has_gmem_vpc_attr_buf FD_DEV_FEATURES=gmem_vpc_attr_buf_size=131072" "--loop=64" "prop at 0x20000 in the slow-drain regime"

echo
echo "sweep done -> $OUTROOT"
echo "read it with: python3 scripts/attrbuf-table.py $OUTROOT/*/"
