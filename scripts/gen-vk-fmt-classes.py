#!/usr/bin/env python3
"""Generate the Vulkan format compatibility class table as JSON.

Two inputs, both machine-readable and both authoritative for their half:

  vk.xml   (KhronosGroup/Vulkan-Docs)  - every VkFormat with its `class` attribute.
        The spec says (chapters/formats.adoc, "Format Compatibility Classes"):
        uncompressed color formats are compatible when they occupy the same number
        of bits per texel block; compressed formats are compatible when the only
        difference is the numeric format of the uncompressed texels; each
        depth/stencil format is only compatible with itself.  vk.xml encodes
        exactly that as the `class` attribute: all formats of one class form one
        row of the spec's "Compatible Formats" table, so "same class" ==
        "compatible view" and nothing else has to be derived by hand.
  vk_format.c (mesa src/vulkan/util)   - the VK_FORMAT_* -> PIPE_FORMAT_* map the
        driver actually uses, both directions.  Needed because the names are not
        the same: VK_FORMAT_B10G11R11_UFLOAT_PACK32 is PIPE_FORMAT_R11G11B10_FLOAT,
        VK_FORMAT_A2B10G10R10_UNORM_PACK32 is PIPE_FORMAT_R10G10B10A2_UNORM, and
        the packed 16-bit pairs are swapped.  A channel-order question cannot be
        answered from the Vulkan name.

Formats with no pipe equivalent (PIPE_FORMAT_NONE, e.g. the *_USCALED ones) are
kept in the class but marked pipe=null: turnip cannot build a view for them, so
the layout predicates have nothing to compare there.

Usage: gen-vk-fmt-classes.py /path/to/vk.xml /path/to/vk_format.c [--sha SHA] > tests/vk-fmt-classes.json
"""

import argparse
import json
import re
import sys

FORMAT_TAG = re.compile(r"<format\s+([^>/]*)>")
ATTRS = re.compile(r'(\w+)="([^"]*)"')
VK_TO_PIPE = re.compile(r"\[VK_FORMAT_([A-Z0-9_]+)\]\s*=\s*PIPE_FORMAT_([A-Z0-9_]+)")
PIPE_TO_VK = re.compile(r"\[PIPE_FORMAT_([A-Z0-9_]+)\]\s*=\s*VK_FORMAT_([A-Z0-9_]+)")

# Classes that are not "one row of the compatibility table" in the ordinary sense:
# multi-planar YUV formats are handled by their own code paths in the driver.
PLANAR = re.compile(r"^\d+PLANE|_2PLANE_|_3PLANE_")


def parse_vk_formats(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        m = FORMAT_TAG.search(line)
        if not m:
            continue
        a = dict(ATTRS.findall(m.group(1)))
        name = a.get("name")
        if not name or not name.startswith("VK_FORMAT_"):
            continue
        out[name[len("VK_FORMAT_"):]] = {
            "class": a.get("class"),
            "blockSize": int(a["blockSize"]) if "blockSize" in a else None,
            "blockExtent": [int(x) for x in a["blockExtent"].split(",")]
                           if "blockExtent" in a else [1, 1, 1],
            "texelsPerBlock": int(a["texelsPerBlock"]) if "texelsPerBlock" in a else 1,
            "packed": a.get("packed"),
            "compressed": a.get("compressed"),
            "chroma": a.get("chroma"),
        }
    return out


def parse_vk_format_c(path):
    src = open(path, encoding="utf-8").read()
    v2p = {v: p for v, p in VK_TO_PIPE.findall(src)}
    p2v = {}
    for p, v in PIPE_TO_VK.findall(src):
        p2v.setdefault(p, v)
    return v2p, p2v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vkxml")
    ap.add_argument("vk_format_c")
    ap.add_argument("--sha", default=None, help="Vulkan-Docs commit the vk.xml came from")
    ap.add_argument("--mesa", default=None, help="mesa commit of vk_format.c")
    args = ap.parse_args()

    fmts = parse_vk_formats(args.vkxml)
    v2p, p2v = parse_vk_format_c(args.vk_format_c)
    if not fmts or not v2p:
        sys.exit("nothing parsed: check the input paths")

    formats = {}
    for name, info in sorted(fmts.items()):
        if PLANAR.search(name) or (info["chroma"] or "") == "chroma":
            kind = "multi-planar"
        elif (info["compressed"] or "") in ("BC", "ETC2", "ASTC", "PVRTC"):
            kind = "compressed"
        elif re.match(r"^(D|S)\d|_D\d|_S8|X8_D24|X8_D32", name) or \
                (v2p.get(name, "").startswith(("D", "S8", "Z", "X24"))):
            kind = "depth-stencil"
        else:
            kind = "color"
        formats[name] = {
            "class": info["class"],
            "kind": kind,
            "blockSize": info["blockSize"],
            "blockExtent": info["blockExtent"],
            "compressed": info["compressed"],
            "packed": info["packed"],
            "pipe": v2p.get(name),
        }

    classes = {}
    for name, info in sorted(formats.items()):
        if info["kind"] == "multi-planar":
            continue
        classes.setdefault(info["class"], []).append(name)

    json.dump({
        "provenance": {
            "vk.xml": "KhronosGroup/Vulkan-Docs" + (f" @{args.sha}" if args.sha else ""),
            "vk_format.c": "mesa" + (f" @{args.mesa}" if args.mesa else ""),
            "generator": "scripts/gen-vk-fmt-classes.py",
        },
        "formats": formats,
        "classes": classes,
        "pipe_to_vk": p2v,
    }, sys.stdout, indent=1, sort_keys=True)
    print()


if __name__ == "__main__":
    main()
