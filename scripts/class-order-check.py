#!/usr/bin/env python3
"""Run the driver's own no-list predicates over the whole compatibility class of each base format.

Journal 39 had to answer one question before any new tiling predicate could be written: for an image
created with VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT and **no** VkImageFormatListCreateInfo, which formats
may the application view it as?  Not the base format and not the application's habits - the class.
Both halves of that are in the tree this repository builds against:

  * the class, as the spec groups it: the `class` attribute of every <format> in
    src/vulkan/registry/vk.xml ("Uncompressed color formats are compatible with each other if they
    occupy the same number of bits per texel block"), already extracted into
    tests/vk-fmt-classes.json by scripts/gen-vk-fmt-classes.py;
  * the predicates that decide the layout, src/freedreno/vulkan/tu_formats.cc:115-176:
      tu6_format_list_has_swaps()                 -> any member whose
                                                    tu6_format_texture(fmt, TILE6_LINEAR, false).swap
                                                    is non-zero
      tu6_format_list_reinterprets_r8g8_r16()     -> a 2-byte base (tu_is_r8g8_compatible:
                                                    blocksize == 2, not depth/stencil) together with a
                                                    member that is not tu_is_r8g8
      both are answered with the worst case when the list is NULL, and patches/0014 replaces that NULL
      with the class (tu6_mutable_compat_class()), which is what this script reproduces offline.

So the question is not "is this base swapped" but "does the base's class contain a member with another
swap, or another 2-byte geometry".  A class that does cannot be tiled on a chip where the tiled path
forces WZYX for every format (`fd6_pipe2swap()` when `tile_mode && !is_mutable`,
src/freedreno/fdl/fd6_format_table.c:399-404, and `is_mutable` stays false without
ubwc_all_formats_compatible).

Swap values are read from fd6_format_table.c, the same table the driver compiles, with the same
macro scan scripts/fmt-list-gate-check.py uses.

Run:
  scripts/class-order-check.py [PIPE_FORMAT ...]     # default: the no-list residue of 0014 v1
"""

import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLASSES = os.path.join(REPO, "tests", "vk-fmt-classes.json")
TABLE = "/var/home/armada/opencode/mesa27-src/src/freedreno/fdl/fd6_format_table.c"

# The pipe formats 0014 v1 leaves in linear in the RE4 run (results/nolist-residue-p14.log); command
# line arguments replace this list.
DEFAULT_PIPE = [
    "R8G8_UNORM", "R11G11B10_FLOAT", "R32_UINT", "R32_FLOAT", "R8G8B8A8_SNORM", "R16G16_FLOAT",
    "R8G8B8A8_SRGB", "R8G8B8A8_UNORM", "R16_UNORM", "R16_FLOAT", "R10G10B10A2_UNORM", "R16_SNORM",
    "R16G16B16A16_FLOAT", "R32G32_FLOAT", "R8_UINT", "R8_UNORM", "R8G8B8A8_UINT", "BPTC_UNORM",
]

COMPONENTS = re.compile(r"^([RGBA])(\d+)")


ROW = re.compile(r"^\s*(FMT|VTC|_TC|_T_|VT_|V_|V__)\((.*)\),\s*$")


def load_swap(path):
    """pipe_format -> swap, from the rows the driver compiles.

    Every row of the table ends with its swap: `FMT(pipe, vtxfmt, texfmt, rbfmt, swap)` and the
    shorthands built on it (VTC/_TC/_T_/VT_/V_/V__, fd6_format_table.c:27-39).  Taking the last
    argument is what makes the read independent of which shorthand a format happens to use.
    """
    swap = {}
    for line in open(path):
        m = ROW.match(line)
        if not m:
            continue
        args = [a.strip() for a in m.group(2).split(",")]
        if len(args) < 2:
            continue
        swap.setdefault(args[0], args[-1])
    return swap


def comp_seq(vk_name):
    """[(R,8),(G,8),(G,8),(A,8)]-style component sequence, or None if the name is not a plain list."""
    comps, rest = [], vk_name
    while True:
        m = COMPONENTS.match(rest)
        if not m:
            break
        comps.append((m.group(1), int(m.group(2))))
        rest = rest[m.end():]
    if not comps or not re.match(r"^(UNORM|SNORM|UINT|SINT|SFLOAT|UFLOAT|SSCALED|USCALED|SRGB)"
                                 r"(_PACK\d+)?(_2PACK16|_3PACK16|_4PACK16)?$", rest.lstrip("_")):
        return None
    return comps


def is_r8g8(seq, block_size):
    """tu_is_r8g8() (tu_formats.cc:101-105): blocksize == 2 and nr_components == 2.

    The driver asks the pipe format's component count; here it is the component sequence of the
    Vulkan name, and the block size comes from vk.xml's blockSize, which is what the class is built
    from anyway.
    """
    return seq is not None and len(seq) == 2 and block_size == 2


def main():
    swap = load_swap(TABLE)
    data = json.load(open(CLASSES))
    fmts, classes = data["formats"], data["classes"]
    vk_of_pipe = {}
    for vk, rec in fmts.items():
        if rec.get("pipe"):
            vk_of_pipe.setdefault(rec["pipe"], []).append(vk)

    print("class table : %s" % CLASSES)
    for k, v in data["provenance"].items():
        print("              %-12s %s" % (k, v))
    print("swap table  : %s (%d rows, the values the driver compiles)" % (TABLE, len(swap)))
    plain = {c: m for c, m in classes.items() if c[0].isdigit()}
    print("classes     : %s" % ", ".join(
        "%s=%d/%d" % (c, len(m), sum(1 for x in m if fmts[x].get("pipe")))
        for c, m in sorted(plain.items(), key=lambda kv: -int(kv[0].split("-")[0]))))
    print("              plus %d compressed / depth-stencil classes in the table" %
          (len(classes) - len(plain)))
    print("              (members with a VK-to-PIPE mapping over total members; vk.xml keeps the alpha")
    print("              exception of the spec rule as its own class - `8-bit alpha` is A8_UNORM alone,")
    print("              vk.xml:32838 - so this table does not merge A8 with R8)")
    print()
    print("For each base format: its class, and inside that class the members the driver's own")
    print("predicates object to - a member with a different swap value (`swap-diff`) or, for a 2-byte")
    print("base, a member that is not R8G8 (`r8g8-r16`).  Either one forces linear; both are the whole")
    print("reason the residue is linear, so no predicate on the base format can remove it.")
    print()
    hdr = "  %-22s %-8s %4s %5s %9s %10s %6s  %-26s %s" % (
        "pipe base", "class", "mbr", "b-swap", "swap-diff", "r8g8-r16", "no-row", "verdict",
        "first offending members")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))

    for pipe in (sys.argv[1:] or DEFAULT_PIPE):
        vks = vk_of_pipe.get(pipe)
        if not vks:
            print("  %-22s (no VK_FORMAT_* maps to it in the class table)" % pipe)
            continue
        base_vk = vks[0]
        cls = fmts[base_vk]["class"]
        members = [v for v in classes[cls] if fmts[v].get("pipe")]
        bseq = comp_seq(base_vk)
        bswap = swap.get(fmts[base_vk]["pipe"])
        diff, r16, norow, examples = 0, 0, 0, []
        for v in members:
            p = fmts[v]["pipe"]
            seq = comp_seq(v)
            mswap = swap.get(p)
            if bswap is None or mswap is None:
                norow += 1
            elif mswap != bswap:
                diff += 1
                if len(examples) < 3:
                    examples.append("%s(%s)" % (v, mswap))
            if is_r8g8(bseq, fmts[base_vk]["blockSize"]) and not is_r8g8(seq, fmts[v]["blockSize"]):
                r16 += 1
        verdict = "UNKNOWN (base has no row)" if bswap is None else (
            "linear required" if (diff or r16) else "class homogeneous")
        print("  %-22s %-8s %4d %5s %9d %10d %6d  %-26s %s" %
              (pipe, cls, len(members), bswap or "?", diff, r16, norow, verdict,
               ", ".join(examples) if examples else "-"))

    print()
    print("What is measured and what is arithmetic here:")
    print("  * swap-diff > 0 is measured damage.  On the 0014 v2 build an R8G8B8A8_UNORM image tiled and")
    print("    viewed as B8G8R8A8_UNORM came back 250000/250000 with R and B exchanged")
    print("    (results/test-0014v2-matrix.log, XV[RGBA8_as_BGRA8]); on the shipped stack the same")
    print("    check is OK because the image is linear (results/test-p14-base.log).")
    print("  * r8g8-r16 is the pair the driver names itself (tu6_format_list_reinterprets_r8g8_r16 and")
    print("    journal 22 / ADR-0007).  A content read of an R16 view of a tiled R8G8 image has never")
    print("    been done: the probe guard only compares layout verdicts (XV[GUARD_R8G8_as_R16],")
    print("    \"content not judged\"), so this column is the rule, not a pixel count.")
    print("  * swap values come from the tree; a pipe format with no TC row prints `?` and is not")
    print("    counted as a difference.")


if __name__ == "__main__":
    main()
