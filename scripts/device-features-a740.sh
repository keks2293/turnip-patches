#!/bin/bash
# What the driver under test actually exposes on this machine, for the questions the operator raised
# on 22.11 about features "locked behind a7xx_gen3 / A8XX" (sparse residency classes, the raster and
# descriptor extensions, the denorm/float-controls pair, ray tracing).
#
# Two runs, same command, different ICD:
#   system - the distribution's Turnip (/usr/lib64/libvulkan_freedreno.so, Mesa 27 base, no patches)
#   ours   - the ship stack via VK_ICD_FILENAMES=build/out/freedreno_icd.json, sha256 4c3cdb210082
# The pair is the control: a row that differs between them is a row one of our patches moved, and a
# row that is equal in both is the upstream state, which is what the "locked behind gen3" claims are
# about.
#
# Limits of this artifact. It is `vulkaninfo`, an instance created by a loader in a shell: no game, no
# wine, no vkd3d-proton. It says what the driver offers, not what the game asks for (a feature can be
# exposed and still unused by RE4, and vkd3d's D3D12 feature level is derived from a list of
# extensions, not from this output). It also reads the device-level state only: per-image decisions
# (UBWC, tiling, LRZ) are journals 21-24 and 40, not this file.
set -uo pipefail
OUT=/var/home/armada/opencode/turnip-patches/results/device-features-a740.txt
SHIP_ICD=/var/home/armada/opencode/build/out/freedreno_icd.json
SHIP_SHA=$(sha256sum /var/home/armada/opencode/build/out/libvulkan_freedreno.so | cut -c1-12)

EXT_RE='VK_(KHR|EXT)_(fragment_shader_barycentric|post_depth_coverage|descriptor_buffer|attachment_feedback_loop(_layout|_dynamic_state)?|ray_tracing_pipeline|ray_query|acceleration_structure|shader_float_controls|fragment_shader_interlock|fragment_shading_rate|sparse_binding|sparse_buffer|shader_object_controls)'
FEAT_RE='sparseResidency[A-Za-z0-9]*|shaderDenormPreserveFloat32|shaderDenormFlushToZeroFloat32|shaderSignedZeroInfNanPreserveFloat32|shaderResourceResidency[A-Za-z0-9]*|fragmentShaderBarycentric|postDepthCoverage|descriptorBuffer|rayTracingPipeline|rayQuery|fragmentShaderInterlock'

{
    echo "# What Turnip exposes on this Adreno A740 (FD740, a7xx_gen2): extensions and features"
    echo "# date: $(date -Is)"
    echo "# regenerate: scripts/device-features-a740.sh > results/device-features-a740.txt"
    echo "# command in both runs: vulkaninfo --show-all (text), grepped for the rows named below"
    echo "# run 'system': the distribution's driver   $(basename "$(readlink -f /usr/lib64/libvulkan_freedreno.so 2>/dev/null || echo /usr/lib64/libvulkan_freedreno.so)")"
    echo "# run 'ours'  : VK_ICD_FILENAMES=$SHIP_ICD  (ship stack sha256 $SHIP_SHA)"
    echo

    for drv in system ours; do
        if [ "$drv" = ours ]; then
            export VK_ICD_FILENAMES="$SHIP_ICD"
        else
            unset VK_ICD_FILENAMES
        fi
        echo "## $drv"
        dump=$(timeout 120 vulkaninfo --show-all 2>/dev/null)
        echo "\$ vulkaninfo --show-all | grep -E '$EXT_RE'   (device extension lines)"
        echo "$dump" | grep -aE "^\s*$EXT_RE" | sed 's/^\s*//' | sort -u
        echo
        echo "\$ vulkaninfo --show-all | grep -E '$FEAT_RE'"
        echo "$dump" | grep -aE "^\s*($FEAT_RE)\s*=" | sed 's/^\s*//' | sort -u
        echo
    done

    echo "## Reading"
    echo "- Equal rows in both runs are upstream's state; a row that differs is one of our patches."
    echo "- A missing extension line means it is not offered at all for this device."
    echo "- Nothing here says the game uses or could use the feature; RE4's own requests are in the"
    echo "  vkd3d-proton logs (docs/journal/, queue for the feature-level story)."
} > "$OUT"
