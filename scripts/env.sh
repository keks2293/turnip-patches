# Paths needed to run the test on the patched turnip.
# /usr must not be touched (journal 7 of docs/analysis.md), and sudo on the device
# requires a password, so the driver is handed to the Vulkan loader via
# an environment variable, without bind-mount.
#
# Checked 20.11: the three paths below exist. The Mesa tree is the Mesa 27 one -
# the Mesa 26 tree this file used to name (build/mesa-rp6) no longer exists, and the
# repository was renamed from turnip-a7xx-dx12 to turnip-patches.

# ICD manifest: points the loader at our .so instead of the system one.
export VK_DRIVER_FILES=/var/home/armada/opencode/build/out/freedreno_icd.json

# Built driver and manifest:
export RP6_TURNIP_SO=/var/home/armada/opencode/build/out/libvulkan_freedreno.so
export RP6_TURNIP_ICD=/var/home/armada/opencode/build/out/freedreno_icd.json

# Sources with the patches applied and the patches from this same repository:
export RP6_MESA_SRC=/var/home/armada/opencode/mesa27-src
export RP6_PATCHES=/var/home/armada/opencode/turnip-patches/patches

# Test:
export RP6_TEST_SRC=/var/home/armada/opencode/turnip-patches/tests
export RP6_TEST_BIN=/var/home/armada/opencode/build/rp6-vkd3d-sparse-test
