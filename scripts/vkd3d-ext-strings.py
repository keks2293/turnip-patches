#!/usr/bin/env python3
"""Which Vulkan extension names the shipped D3D12 layer actually contains.

Journal 40.25 needs this to answer "implement VK_EXT_descriptor_heap / DGC in Turnip and RE4 gets
faster": a driver-side feature can only help a game if the translation layer in front of it asks for
it. The files below are the vkd3d-proton build this stand runs (the same tree the game is launched
from), so a name that does not occur in them is not reachable from D3D12 on this machine, whatever a
driver does with it.

Method and its limit: a byte search over the binaries, ASCII and UTF-16LE. It finds the extension
names the layer stores as strings, and it cannot tell a queried extension from a name mentioned once
in a log format string. An absent name is strong (the layer has to name what it enables), a present
name is only "this layer knows this name".

Usage: python3 scripts/vkd3d-ext-strings.py > results/vkd3d-ext-strings.txt
"""
import glob
import os
import sys

ROOT = "/var/home/armada/opencode/proton-patched/files"
NAMES = [
    "VK_EXT_descriptor_heap",
    "VK_EXT_descriptor_buffer",
    "VK_EXT_device_generated_commands",
    "VK_EXT_mutable_descriptor_type",
    "VK_EXT_shader_object",
    "VK_KHR_driver_properties",
    "sparseResidencyImage3D",
    "sparseResidencyImage2D",
]


def main() -> int:
    print("# Extension and feature names present in the shipped vkd3d-proton / vkd3d binaries")
    print("# regenerate: python3 scripts/vkd3d-ext-strings.py > results/vkd3d-ext-strings.txt")
    print(f"# searched: every regular file under {ROOT}/lib*/{{vkd3d,wine/vkd3d-proton}}/**")
    print("# method: byte search for the ASCII and UTF-16LE form of each name; see the script header")
    print("# for what a hit and a miss each mean")
    files = []
    for sub in ("lib/vkd3d", "lib64/vkd3d", "lib/wine/vkd3d-proton", "lib64/wine/vkd3d-proton"):
        files += [f for f in glob.glob(os.path.join(ROOT, sub, "**", "*"), recursive=True)
                  if os.path.isfile(f)]
    files = [f for f in files if os.path.getsize(f) > 1024]
    print(f"# {len(files)} files, {sum(os.path.getsize(f) for f in files) // (1024 * 1024)} MiB total")

    table = {}
    for path in files:
        data = open(path, "rb").read()
        key = path.split("/files/")[-1]
        table[key] = {n: (data.count(n.encode()) + data.count(n.encode("utf-16-le"))) for n in NAMES}

    short = [n.split("_", 2)[-1] for n in NAMES[:5]]
    width = max(len(k) for k in table) + 2
    print("\n" + " " * width + "".join(f"{s:<26}" for s in short))
    for key in sorted(table):
        row = table[key]
        print(f"{key:<{width}}" + "".join(f"{row[n]:<26}" for n in NAMES[:5]))

    print("\n# other names, same table, printed only where non-zero:")
    for key in sorted(table):
        for n in NAMES[5:]:
            if table[key][n]:
                print(f"   {key}  {n} = {table[key][n]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
