"""What the props generator actually hands to C for each a7xx chip id.

    podman run --rm -v <mesa>/src:/src:Z -v <repo>/scripts/pystub:/stub:Z \
        -v <repo>/scripts:/hostscripts:Z \
        -e PYTHONPATH=/stub:/src/freedreno/common \
        -e MESA_FREEDRENO_COMMON=/src/freedreno/common \
        localhost/mesa-build-fedora44-wsi-glslang-vulkan \
        python3 /hostscripts/props-for-chip.py -p /stub -q

Two things the container needs that the device does not have:

* `mako` and `yaml`, because `freedreno_dev_info.py` imports them at module scope, and
  `a6xx`, the register module meson generates from `a6xx.xml` into the build directory
  (this checkout has no build directory).  They are stubbed in `scripts/pystub/`:
  `Template` is only used inside `main()`, `yaml` only in the quirk report, and
  `freedreno_devices.py` merely stores `A6XXRegs.REG_*` in its regtables, so a chainable
  proxy is enough.  Nothing numeric comes out of them - which is why this script prints
  props and never a register encoding.
* the trailing `-p … -q`: `freedreno_dev_info.py` parses sys.argv at import time (its own
  argparse, line 17), because it is written to be run as the generator.  Without them the
  import aborts with "the following arguments are required".

Why the question needs the merged object at all: in `freedreno_devices.py` a chip's props
are merged in order (`[a7xx_base, a7xx_gen2]`), so a prop written once in `a7xx_base`
really is inherited by every block that names it - and the FD740 entry then says nothing
about it.  Grep near the FD740 entry cannot answer "is it 0 or inherited"; this does,
because it reads the same merged dict the generator stringifies into the C table.
"""
import os
import sys

sys.path.insert(0, os.environ.get("MESA_FREEDRENO_COMMON", "/src/freedreno/common"))
import freedreno_devices as d  # noqa: E402

NAMES = (
    "has_gmem_vpc_attr_buf",
    "sysmem_vpc_attr_buf_size",
    "gmem_vpc_attr_buf_size",
    "sysmem_per_ccu_depth_cache_size",
    "sysmem_per_ccu_color_cache_size",
    "gmem_ccu_color_cache_fraction",
    "gmem_ccu_depth_cache_fraction",
)

props_blocks = [(name, obj) for name, obj in ((n, getattr(d, n)) for n in dir(d))
                if isinstance(obj, dict) and name.endswith(("base", "gen1", "gen2", "gen3"))]

print("=== which GPUProps block defines each name (a7xx_base included) ===")
for n in NAMES:
    hits = [f"{name}={obj[n]}" for name, obj in props_blocks if n in obj]
    print(f"{n:34s} " + (", ".join(hits) if hits else "(in no block of the family -> 0 in C)"))

WANT = {0x43050A01: "FD740 (this rig)", 0xFFFF43050C01: "X1-85", 0x43050D01: "0x43050d01",
        0x43020000: "FD720", 0x43020100: "Adreno 722", 0x07010000: "FD710"}

print("\n=== the merged props of those chip ids, as the generator sees them ===")
seen = {}
for gid, info in d.s.gpus.items():
    if gid.chip_id in WANT and gid.chip_id not in seen:
        seen[gid.chip_id] = (gid, info)

for cid, label in WANT.items():
    if cid not in seen:
        print(f"0x{cid:08x} {label:18s} not in Mesa's catalog")
        continue
    gid, info = seen[cid]
    props = getattr(info, "props", {})

    def show(n):
        if isinstance(props, dict):
            return props[n] if n in props else "(unset -> 0 in C)"
        return getattr(props, n, "(unset -> 0 in C)")

    print(f"0x{cid:08x} {label:18s} name={gid.name!r} num_ccu={getattr(info, 'num_ccu', '?')} "
          f"tile_align={getattr(info, 'tile_align_w', '?')}x{getattr(info, 'tile_align_h', '?')}")
    for n in NAMES:
        print(f"    {n:34s} {show(n)}")

print("\n=== every catalog entry the flag is on, and the family it is off for ===")
on, off = [], 0
for gid, info in d.s.gpus.items():
    props = getattr(info, "props", {})
    flag = props.get("has_gmem_vpc_attr_buf", False) if isinstance(props, dict) \
        else getattr(props, "has_gmem_vpc_attr_buf", False)
    if flag:
        on.append((gid, info))
    else:
        off += 1
for gid, info in on:
    props = info.props
    get = (lambda n: props.get(n, 0)) if isinstance(props, dict) else (lambda n: getattr(props, n, 0))
    print(f"    ON  0x{gid.chip_id:08x} {gid.name!r:24s} num_ccu={getattr(info, 'num_ccu', '?')} "
          f"sysmem=0x{get('sysmem_vpc_attr_buf_size'):x} gmem=0x{get('gmem_vpc_attr_buf_size'):x}")
print(f"    OFF {off} entries, including every a7xx_gen1 and a7xx_gen2 chip")

print("\n(0 in C means: never written to GMEM and never consulted - the layout branch and")
print(" emit_vpc_attr_buf are both gated on has_gmem_vpc_attr_buf, journal 40.34)")
