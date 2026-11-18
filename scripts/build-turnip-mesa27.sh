#!/bin/bash
# Mesa 27.0-devel + patches 0001-0012, turnip only (Vulkan), KMD=msm.
#
# Differences from build-turnip.sh are the "Build: rules so the SD card
# survives" rules (README.md, docs/mesa-27-plan.md):
#   1. The build directory lives on tmpfs: /out is mounted from
#      /tmp/opencode/mesa27-build.  Not a single .o lands on the SD card.
#   2. ccache is on tmpfs too: /ccache from /tmp/opencode/ccache, cap 1G.
#      The cache is lost on reboot - that is fine.
#   3. The final artifacts (.so + ICD manifest) are copied to /hostout
#      (mounted from /var/home/armada/opencode/build/out) - the only thing
#      that reaches the SD card (~5 MB).  Paths in env.sh and run-game.sh
#      do not change.
#   4. -j2 (overridable via BUILD_JOBS), not -j$(nproc): the 7.3 GiB of RAM
#      are shared with the GPU.
#   5. Do not run it together with the game: the re4.exe/wine check (same
#      as in build-turnip.sh).
#   6. Sources are /src: the Mesa 27 tree with the patches applied, on the
#      SD card (/var/home/armada/opencode/mesa27-src).  Never use
#      git checkout there - only git apply -R.
#
# The reasons for the flags are the same as in the header of build-turnip.sh
# (KMD=msm, non-empty -Dplatforms, --prefix=/usr for driconf, the copy into
# out/ for the ICD manifest).
set -euxo pipefail

JOBS="${BUILD_JOBS:-2}"
HOSTOUT="${HOSTOUT:-/hostout}"

cd /src

if pgrep -f 're4\.exe|wine|wineserver' >/dev/null 2>&1; then
    echo "WARNING: Wine/the game is already running. Build the driver when the game is closed." >&2
    exit 1
fi

# ccache (the toolchain is already in the image): tmpfs directory, cap 1G,
# reset the counter before a clean build.
export CCACHE_DIR=/ccache
export CCACHE_MAXSIZE=1G
ccache -z

rm -rf /out/build
meson setup /out/build /src \
    --buildtype=release \
    --prefix=/usr \
    -Dopengl=false \
    -Dplatforms=x11,wayland \
    -Dgallium-drivers= \
    -Dvulkan-drivers=freedreno \
    -Dfreedreno-kmds=msm \
    -Dvulkan-layers= \
    -Dshared-glapi=disabled \
    -Dllvm=disabled \
    -Dvalgrind=disabled \
    -Dlibunwind=disabled \
    -Dbuild-tests=false

ninja -C /out/build -j"$JOBS" src/freedreno/vulkan/libvulkan_freedreno.so

SO=/out/build/src/freedreno/vulkan/libvulkan_freedreno.so
# KMD diagnostics: an msm build imports drmGetVersion, a kgsl one has the
# kgsl_3d0/kgsl_bo_init strings instead.  If nm is unavailable, do not fail
# the build.
if UNDEF="$(nm -D --undefined-only "$SO" 2>/dev/null)"; then
    if [[ "$UNDEF" != *drmGetVersion* ]]; then
        echo "WARNING: no drmGetVersion import - this looks like a kgsl build, not msm" >&2
        exit 1
    fi
else
    echo "WARNING: nm is unavailable, skipping the KMD check" >&2
fi

# Artifacts -> SD card (the only write to the card): .so + ICD manifest.
# The manifest is written here rather than taken from the build: the one meson
# generates contains install paths (/usr/lib/...) that exist on the device,
# but the driver must live where env.sh points.
mkdir -p "$HOSTOUT"
cp -v "$SO" "$HOSTOUT/libvulkan_freedreno.so"
cat > "$HOSTOUT/freedreno_icd.json" <<EOF
{
    "file_format_version": "1.0.1",
    "ICD": {
        "library_path": "/var/home/armada/opencode/build/out/libvulkan_freedreno.so",
        "api_version": "1.4.354",
        "library_arch": "64"
    }
}
EOF

ls -l "$HOSTOUT/"
