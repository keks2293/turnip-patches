#!/bin/bash
# Sweep the cpp=1 UBWC metadata geometry (exp-17 override, TU_8BPP_UBWC) with the
# standalone 8bpp tool: seconds per grid instead of the 20-minute harness.
#
# Needs the exp-17 build of the driver in place, because the override lives in
# fdl6_get_ubwc_blockwidth():
#   cp build/out/libvulkan_freedreno.exp17-<hash>.so build/out/libvulkan_freedreno.so
#   bash scripts/sweep-8bpp-grid.sh
#   cp build/out/libvulkan_freedreno.ship-<hash>.so build/out/libvulkan_freedreno.so
# The ship build ignores TU_8BPP_UBWC, so a sweep that shows no memreq change is a
# sweep of one and the same driver - check the memreq column before believing any
# row of this.
#
# Grids with blockheight >= 8 take the GPU down: the probe reports "texelFetch
# failed" (submit failed) and every allocation after it fails, which is
# VK_ERROR_DEVICE_LOST, not a wrong value.
set -u
cd /var/home/armada/opencode/turnip-patches
out=results/raw
ICD=/var/home/armada/opencode/build/out/freedreno_icd.json
BIN=/var/home/armada/opencode/build/tp8bpp
for g in keep 16x4 32x4 64x4 64x2 16x8 32x8 8x8 64x8 16x16 32x16 64x16 8x16 32x32; do
   TU_8BPP_UBWC=$g FD_DEV_FEATURES=has_8bpp_ubwc=1 VK_DRIVER_FILES=$ICD \
      timeout 200 "$BIN" > "$out/tp8bpp-$g.log" 2>&1
   rc=$?
   printf '%-8s exit=%-3s %s\n' "$g" "$rc" \
      "$(grep -E '^AA\[tiled\] (R8|texelFetch|i2b|.*failed)' "$out/tp8bpp-$g.log" | tr '\n' ' | ')"
done
