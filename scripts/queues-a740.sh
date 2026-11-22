#!/bin/bash
# Can an application on this device get a second, independent queue? Journal 40.25 asks this because
# an outside note proposed porting RADV's async-compute layout (separate compute queue -> separate
# kernel ring -> ACE engines) into Turnip for RE4.
#
# What this captures, for both drivers (the distribution's Turnip and the ship stack):
#   * VkQueueFamilyProperties, i.e. how many families, how many queues each, and which bits each family
#     carries - a D3D12 "compute queue" in vkd3d-proton needs a family that is not the graphics family;
#   * which device nodes the driver talks to, and whether the legacy kgsl node the note assumes exists
#     on this machine at all.
#
# It says nothing about whether two queues would overlap on the GPU: that is scheduler and firmware
# behaviour, and this artifact only records what the driver offers to an application.
#
# usage: scripts/queues-a740.sh > results/queues-a740.txt
set -uo pipefail
SHIP_ICD=/var/home/armada/opencode/build/out/freedreno_icd.json
SHIP_SHA=$(sha256sum /var/home/armada/opencode/build/out/libvulkan_freedreno.so | cut -c1-12)

echo "# Queue families and command submission on this Adreno A740 (FD740, a7xx_gen2)"
echo "# date: $(date -Is)"
echo "# regenerate: scripts/queues-a740.sh > results/queues-a740.txt"
echo "# run 'system': the distribution's driver   $(basename "$(readlink -f /usr/lib64/libvulkan_freedreno.so 2>/dev/null || echo /usr/lib64/libvulkan_freedreno.so)")"
echo "# run 'ours'  : VK_ICD_FILENAMES=$SHIP_ICD  (ship stack sha256 $SHIP_SHA)"
echo "# note: 'vulkaninfo --show-all' on this machine dies with SIGSEGV part way through its own dump"
echo "#       (exit 139, same with both drivers, and at a different line each run), so it is run here"
echo "#       through a pipe and its stdout is taken as far as it goes. The queue-family section always"
echo "#       lands: it is early, and it ends at VkPhysicalDeviceMemoryProperties. Nothing below this"
echo "#       script's own section headers comes from the crashing tool."
echo

echo
for drv in system ours; do
    if [ "$drv" = ours ]; then
        export VK_ICD_FILENAMES="$SHIP_ICD"
    else
        unset VK_ICD_FILENAMES
    fi
    echo "=== $drv"
    { vulkaninfo --show-all 2>/dev/null | awk '
        /^VkQueueFamilyProperties:/ {inq = 1; next}
        /^VkPhysicalDevice/         {inq = 0}
        inq && /queueProperties|queueCount|queueFlags|timestampValidBits/ {print $0}
    ' | sed 's/^[ \t]*/    /'; } 2>/dev/null
    echo
done

echo "=== kernel interfaces available to the driver"
for n in /dev/dri/renderD128 /dev/dri/card0 /dev/kgsl-3d0; do
    printf "    %-22s %s\n" "$n" "$(ls "$n" 2>/dev/null || echo absent)"
done
echo "    DRM driver name: $(echo armada | sudo -S -p '' cat /sys/kernel/debug/dri/0/name 2>/dev/null | head -1)"
echo "    driver backend in use: tu_knl_drm_msm.cc (DRM/msm); tu_knl_kgsl.cc needs /dev/kgsl-3d0"
