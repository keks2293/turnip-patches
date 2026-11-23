#!/bin/bash
# Negative controls for the --varyings arms: build the probe from the two wrong fragment-shader
# forms and show that scripts/check-varyings-arms.py reports them, instead of trusting the note in
# tests/gen-varyings-spv.sh's header.  Journal 42.1.
#
#   podman run ... bash scripts/check-varyings-controls.sh | tee \
#       results/synthetics/varyings/negative-controls.txt
# (run from the repository root, on the device: reading an interface means running the probe, and
# the probe needs the GPU.  The container is used only to compile.)
#
# Why controls at all: a plain sum of varyings gives a pipeline that renders and counters that move;
# only the interface is wrong, because nir_opt_varyings moves the adds up into the vertex shader
# (can_move_alu_across_interp(), nir/nir_opt_varyings.c:3738-3795, with the unlimited budget
# tu_shader.cc:3878 gives the pass). An arm that silently has an interface of 1 in every arm would
# produce a clean, smooth, meaningless sweep of PERF_VPC_SP_COMPONENTS and PERF_SP_EXPORT_VPC_TRANS,
# which is exactly what a counter sweep cannot reveal about itself.
#
# The `fract` table is not a defect. Wrapping each varying in fract() is a form the pass does not
# move, so it reads `ok`, like the production form; it is run here because the claim when the rig was
# written was that fract() makes the pass pack slots to 16 bits, and this script is where a reader can
# see that claim tested instead of taken (journal 42.1).
#
# The `attrbuf` row of each table is the rig's own default pair (tests/vpc_attrbuf.{vert,frag}), which
# FS_REDUCE does not touch. It reads ok in all three tables, which is the control saying the collapse
# belongs to the form of the shader and not to the binary around it.
#
# Leaves the tree as it found it: tests/varyings_spv.h and ../build/vpc-attrbuf are regenerated from
# the default (prod) form at the end, built with the command of tests/vpc-attrbuf.c's header so the
# binary left behind is the one the documented recipe produces, and the check runs once more so the
# artifact ends with the arms the counter run of journal 42.2 actually used.
set -uo pipefail
cd "$(dirname "$0")/.."
REPO=$PWD
IMAGE=localhost/mesa-build-fedora44-wsi-glslang-vulkan
ICD=$REPO/../build/out/freedreno_icd.json

build() {   # $1 = FS_REDUCE form, $2 = output path for the probe
    podman run --rm --userns=keep-id -v "$REPO/tests:/work:Z" -v "$REPO/../build:/out:Z" "$IMAGE" \
        bash -c "cd /work && FS_REDUCE=$1 bash gen-varyings-spv.sh >/dev/null &&
                 gcc -O2 -Wall -o $2 vpc-attrbuf.c -lvulkan -lm" >&2
}

echo "# Negative controls for the --varyings arms: what the check script says about the two wrong"
echo "# fragment-shader forms, and about the right one."
echo "# regenerate: scripts/check-varyings-controls.sh | tee results/synthetics/varyings/"
echo "# negative-controls.txt"
echo "# form:       the FS_REDUCE of tests/gen-varyings-spv.sh that produced the shader pairs"
echo "#               compiled into the probe that was then read.  prod is the only correct form:"
echo "#               'acc += v_i * v_i * c'.  plain and fract are the two wrong ones."
echo "# each table below is scripts/check-varyings-arms.py run against one probe; its own header"
echo "# says what is read and what an arm must show."
for form in plain fract; do
    build "$form" "/out/probe-$form"
    echo
    echo "================================================================================"
    echo "FS_REDUCE=$form  (probe ../build/probe-$form)"
    echo "================================================================================"
    VK_DRIVER_FILES=$ICD python3 scripts/check-varyings-arms.py --probe "../build/probe-$form"
    rm -f "$REPO/../build/probe-$form"
done

build prod "/out/vpc-attrbuf"
echo
echo "================================================================================"
echo "FS_REDUCE=prod  (the probe the counter run of journal 42.2 used, ../build/vpc-attrbuf)"
echo "================================================================================"
VK_DRIVER_FILES=$ICD python3 scripts/check-varyings-arms.py --probe "../build/vpc-attrbuf"
