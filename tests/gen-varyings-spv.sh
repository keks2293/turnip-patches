#!/bin/bash
# Generate varyings_spv.h: five vertex/fragment pairs that differ ONLY in how many vec4 varyings
# the vertex shader exports - 1, 2, 4, 8, 16.  Queue 34 (what unit do VPC id 10 and SP id 48
# have), journal 40.36 states what the committed data already says.
#
# Run in the glslang container, the way tests/gen-vpc-attrbuf-spv.sh does:
#   podman run --rm -v "$PWD/tests:/work:Z" \
#       localhost/mesa-build-fedora44-wsi-glslang-vulkan bash -c 'cd /work && bash gen-varyings-spv.sh'
#
# Why five compiled variants instead of one shader with a loop over the outputs: the thing under
# test is the *interface*, and an interface is fixed before the pipeline exists.  On this tree the
# VPC location the fragment shader reads is an immediate inside the compiled FS binary
# (pack_inlocs rewrites `instr->srcs[0]->iim_val`, ir3_compiler_nir.c:5274-5290); a spec constant
# would change how many outputs the VS writes while the interface stayed 16 wide - the work, not
# the interface.  An indirectly indexed output is worse: nir_opt_varyings skips indirectly indexed
# slots (nir_opt_varyings.c:21-23) and ir3 asserts constant offsets for VS output stores
# (ir3_compiler_nir.c:5300).
#
# WHAT EVERY VARIANT SHARES, and what the Mesa optimizers would take away if it did not:
#   * the same nine lines of vertex data as tests/vpc_attrbuf.vert - position at location 0 and
#     seven payload attributes at 1..7, 8 x vec4 = 128 B per vertex, which is the layout
#     tests/vpc-attrbuf.c builds (NUM_ATTRIBS = 8, `vertex_t`).  All eight are read in every
#     variant, the payload folded into v0.  Without the fold the N=1 arm would read one attribute
#     and the N=16 arm eight, and VFD_NUM_ATTRIBUTES and VFD_DECODED_ATTRIBUTE_BYTES - the only
#     per-vertex denominators here that are not zero (40.36) - would differ between arms.  The
#     interface width would then not be the only variable.
#   * the same gl_Position expression, instance jitter included, so the same triangles cover the
#     same pixels in every arm.  `SP_OUTPUT_3D_PIXELS` and `TSE_OUTPUT_VISIBLE_PRIM` in
#     tools/fdperf/fdperf.cfg-varyings are what shows whether that held; the colour hash cannot,
#     because the FS sums what it is given and a different N is a different sum by construction.
#   * every output derived from an attribute, and each with a different value.  nir_opt_varyings
#     runs here with promotion limits of UINT32_MAX (tu_shader.cc:3878), which means a
#     uniform-valued output is promoted out of the interface (nir_opt_varyings.c:2889-2947) and
#     duplicate outputs are deduplicated (the same pass, doc at :86-93) - either one silently
#     changes an arm's interface.
#   * a fragment shader that reads every output, all four components, into the colour
#     unconditionally: pack_inlocs drops any component the compiled FS stops fetching
#     (ir3_compiler_nir.c:5249-5267), so a varying the FS does not read is a varying that never
#     existed as far as the hardware is concerned.
#   * and every read is multiplied by *itself* before it is summed (`v*v*c`), which is the second
#     of two traps this script fell into, both measured on 23.11 and written up as journal 42.1:
#       - a plain sum (`acc += v_i * float(i + 1)`) disassembles to ONE `bary.f` whatever N is.
#         `nir_opt_varyings` moves consumer-side arithmetic into the producer where that is legal
#         across interpolation, and `fadd`, `fsub`, `mov` always are, `fmul`/`ffma` when one side
#         is convergent - which a constant is (nir_opt_varyings.c:3738-3795,
#         `can_move_alu_across_interp`) - and the pass runs here with a budget of UINT32_MAX
#         (tu_shader.cc:3878).  A sum of varyings is therefore not N varyings: it is one, computed
#         in the vertex shader, and the counters measure an interface of 1 in every arm.
#       - `v * v` is not movable, because both sources are interpolated and neither is convergent,
#         so the fetch stays in the FS.  `fract(v)` also blocks the move, and was tried first: it
#         additionally tells the pass the value lies in [0, 1), and the interface then gets
#         *packed into 16-bit slots* - the disassembly of the 8-wide arm mixed 32-bit fetches
#         (`bary.f rD.z, (r)20`) with single-component 16-bit ones (`bary.f rD.z, 24`), so the
#         stride table below stops applying and the component count stops meaning what it said.
#     An arm is only believed when its disassembly shows N 32-bit `bary.f` pairs at offsets 0, 4,
#     8 ... 4(N-1); the command is at the end of this header.
#
# WHAT IS DELIBERATELY NOT EQUAL: the picture, and the fragment shader's own work - N `bary.f`
# and N adds against 1 of each.  That is the quantity being measured, not an artefact, and it is
# why the cfg carries `SP_FS_STAGE_BARY_INSTRUCTIONS` (42) and `SP_FS_INSTRUCTIONS` (44): the FS
# side is recorded as a moving column instead of being assumed away.  The arms are compared per
# delivered vertex (`VFD_TOTAL_VERTICES`) and per VPC RAM write (`VPC_NUM_VPCRAM_WRITE`, the flat
# denominator of 40.36).  `--loop=N` (the uLoop spec constant) is there to make the pixel side the
# limiter on purpose, which 40.36 shows id 10 does not chase.
#
# THE HARDWARE STATE EACH ARM MUST PRODUCE, so that a build can be checked rather than trusted.
# With N vec4 outputs, no psize/layer/view/clip distances, the interface is decided by
# ir3_link_shaders from the FS's inputs (tu_pipeline.cc:802; the FS owns the layout, the comment at
# ir3_shader.h:746-753), and tu6_emit_vpc writes it:
#
#   N    SP_VS_OUTPUT_CNTL.OUT    VPC_VS_CNTL.STRIDE_IN_VPC    VPC_VS_CNTL.POSITIONLOC
#   1    2                        8                            4
#   2    3                        12                           8
#   4    5                        20                           16
#   8    9                        36                           32
#   16   17                       68                           64
#
# (OUT counts POSITION as an entry too - "number of VS outputs including pos", a6xx.xml:3677-3680,
# tu_pipeline.cc:1092; STRIDE is `linkage.max_loc`, 4 components per vec4 plus 4 for position,
# tu_pipeline.cc:926-931; PC_VS_CNTL.STRIDE_IN_VPC carries the same stride again at :1043.)
# Check a built probe two ways.  The disassembler prints the FS's bary immediates - the largest
# `vappro.x + N` plus 4 is the stride:
#   IR3_SHADER_DEBUG=fs ../build/vpc-attrbuf --varyings=4 --seconds=1 2>&1 |
#       grep -o 'vappro.x + [0-9]*' | sort -u -t+ -k2 -n | tail -1
# and IR3_SHADER_DEBUG does not perturb codegen (the disasm flag is excluded from the shader cache
# key, ir3_compiler.h:379-382).  The register values themselves need a readback of the CS:
# FD_RD_DUMP=full plus cffdump -q VPC_VS_CNTL (docs/howto-measure.md).
set -euo pipefail
cd /work

SIZES="1 2 4 8 16"

# The reduction the fragment shader applies to its inputs.  `prod` is the only correct value; the
# other two exist so the two failures described above can be reproduced on demand, and they are
# what the negative controls of results/synthetics/varyings/ were built with:
#   prod   acc += v_i * v_i * c        - what every arm must be built with: v*v is not movable
#                                       across interpolation (both sources interpolated, neither
#                                       convergent) and implies no range, so all N fetches stay in
#                                       the FS and arm N really is an interface of N
#   plain  acc += v_i * c              - the first trap: nir_opt_varyings moves the sum into the VS
#                                       and the FS ends up with one fetch whatever N is
#   fract  acc += fract(v_i) * c       - the second trap: the move is blocked but the pass learns
#                                       the value lies in [0, 1) and packs part of the interface
#                                       into 16-bit slots
# Reproduce a trap, read it, then put the tree back (the header is compiled into the probe, so a
# trap needs its own build; scripts/check-varyings-arms.py reads the interface back):
#   FS_REDUCE=plain bash gen-varyings-spv.sh
#   gcc -O2 -Wall -o /tmp/probe-plain vpc-attrbuf.c -lvulkan -lm
#   VK_DRIVER_FILES=.../build/out/freedreno_icd.json \
#       scripts/check-varyings-arms.py --probe /tmp/probe-plain      # every arm "NOT ok"
#   bash gen-varyings-spv.sh && <rebuild the probe the same way>     # back to prod
FS_REDUCE="${FS_REDUCE:-prod}"
case "$FS_REDUCE" in
    prod)  red_expr() { echo "   acc += v$1 * v$1 * float($(($1 + 1)));"; } ;;
    plain) red_expr() { echo "   acc += v$1 * float($(($1 + 1)));"; } ;;
    fract) red_expr() { echo "   acc += fract(v$1) * float($(($1 + 1)));"; } ;;
    *) echo "FS_REDUCE takes prod, plain or fract, not '$FS_REDUCE'" >&2; exit 2 ;;
esac

emit() {   # $1 = spv file, $2 = C symbol
    echo "static const uint32_t $2[] = {"
    od -A n -t u4 -v "$1" | tr -s ' \t' ' ' | sed 's/^ //; s/ $//; s/ /, /g; s/$/,/' | sed '$ s/,$//'
    echo "};"
}

for n in $SIZES; do
    {
        echo "#version 450"
        echo "/* Generated by tests/gen-varyings-spv.sh: $n vec4 varyings exported.  Vertex data"
        echo " * identical to tests/vpc_attrbuf.vert - position at 0, seven payload attributes at"
        echo " * 1..7, all eight read in every variant.  Do not edit - edit the script. */"
        echo
        cat <<'EOF'
layout(location = 0) in vec4 aPos;
layout(location = 1) in vec4 a0;
layout(location = 2) in vec4 a1;
layout(location = 3) in vec4 a2;
layout(location = 4) in vec4 a3;
layout(location = 5) in vec4 a4;
layout(location = 6) in vec4 a5;
layout(location = 7) in vec4 a6;
EOF
        echo
        for ((i = 0; i < n; i++)); do
            echo "layout(location = $i) out vec4 v$i;"
        done
        echo
        echo "void main()"
        echo "{"
        # the position expression of vpc_attrbuf.vert, character for character, so coverage is
        # the same in every arm and matches the parked attribute-buffer run.
        cat <<'EOF'
   vec2 jitter = vec2(float(gl_InstanceIndex) * 0.011,
                      float(gl_InstanceIndex) * 0.017);
   gl_Position = vec4(aPos.xy + jitter, aPos.z, 1.0);
EOF
        echo
        # v0 carries the whole payload set in every arm: one expression, identical across arms,
        # and the reason VFD's per-vertex denominators are comparable between them.
        echo "   v0 = (((a0 + a1) + (a2 + a3)) + ((a4 + a5) + a6)) * 0.0009765625;"
        # every other output is attribute-derived (so nothing is promoted out of the interface)
        # and carries its index in its value (so nothing is deduplicated): no two outputs of any
        # arm can be equal by construction.
        for ((i = 1; i < n; i++)); do
            echo "   v$i = a$((i % 7)).zyxw * float($i) + a$(((i + 3) % 7)) * float($((i + 1)));"
        done
        echo "}"
    } > "/tmp/varyings_${n}.vert"

    {
        echo "#version 450"
        echo "/* Generated by tests/gen-varyings-spv.sh: reads the $n vec4 varyings of the"
        echo " * matching vertex shader and nothing else.  Do not edit. */"
        echo
        echo "layout(constant_id = 0) const uint uLoop = 0u;"
        echo
        for ((i = 0; i < n; i++)); do
            echo "layout(location = $i) in vec4 v$i;"
        done
        echo
        echo "layout(location = 0) out vec4 fragColor;"
        echo
        echo "void main()"
        echo "{"
        echo "   vec4 acc = vec4(0.0);"
        for ((i = 0; i < n; i++)); do
            red_expr "$i"
        done
        echo
        echo "   for (uint i = 0u; i < uLoop; ++i)"
        echo "      acc = fract(acc * 1.0009) + acc * 0.5;"
        echo
        echo "   fragColor = acc;"
        echo "}"
    } > "/tmp/varyings_${n}.frag"

    glslangValidator -V "/tmp/varyings_${n}.vert" -o "/tmp/varyings_${n}_vert.spv" >/dev/null
    glslangValidator -V "/tmp/varyings_${n}.frag" -o "/tmp/varyings_${n}_frag.spv" >/dev/null
done

{
    echo "/* Generated by tests/gen-varyings-spv.sh from the GLSL that script writes out"
    echo " * (glslangValidator -V; the uLoop spec constant is left unset, the probe supplies it)."
    echo " * FS_REDUCE=$FS_REDUCE - the reduction the fragment shader applies, see that script's header:"
    echo " * only 'prod' keeps N fetches in the FS, which is what makes arm N an arm of width N."
    echo " * Five interface widths - 1, 2, 4, 8, 16 vec4 - as varyingsN_vert_spv / varyingsN_frag_spv."
    echo " * All eight vertex attributes (position plus seven payload, 128 B/vertex) are read in"
    echo " * every arm; gl_Position is the expression of tests/vpc_attrbuf.vert."
    echo " * The interface each arm must produce (SP_VS_OUTPUT_CNTL.OUT / VPC_VS_CNTL.STRIDE_IN_VPC):"
    echo " * 1 -> 2/8, 2 -> 3/12, 4 -> 5/20, 8 -> 9/36, 16 -> 17/68.  Do not edit. */"
    for n in $SIZES; do
        emit "/tmp/varyings_${n}_vert.spv" "varyings${n}_vert_spv"
        emit "/tmp/varyings_${n}_frag.spv" "varyings${n}_frag_spv"
    done
} > /work/varyings_spv.h

wc -c /work/varyings_spv.h
grep -c "^static const uint32_t" /work/varyings_spv.h
