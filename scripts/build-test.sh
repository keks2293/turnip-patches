#!/bin/bash
# Build rp6-vkd3d-sparse-test in the container (there is no compiler on the device).
set -euxo pipefail

# The install is here for images that lack the toolchain. It is skipped when
# gcc, the Vulkan headers and the loader link name are already present, which
# they are in localhost/mesa-build-fedora44-wsi-glslang-vulkan: on 20.11 the
# Fedora mirror metadata failed mid-download and `set -e` turned that into a
# build failure even though nothing was missing.
if ! command -v gcc >/dev/null 2>&1 || [ ! -e /usr/include/vulkan/vulkan.h ] ||
   ! ldconfig -p 2>/dev/null | grep -q "libvulkan\.so\b"; then
    dnf -y install gcc vulkan-headers vulkan-loader-devel
fi

cd /work
gcc -O2 -Wall -o /out/rp6-vkd3d-sparse-test rp6-vkd3d-sparse-test.c -lvulkan
ls -l /out/rp6-vkd3d-sparse-test
