#!/bin/bash
# build-tree-stamp.sh - what a driver build actually is, when the Mesa tree is not committed anywhere.
#
#   scripts/build-tree-stamp.sh <mesa-tree> [<.so> ...]
#
# docs/release.md, checklist item 4, asks for three things per build: the .so sha256, the Mesa base
# commit, and "sha256 of git diff <base>" over the applied tree, because ../mesa27-src is a working
# tree with patches applied by hand and its source exists nowhere else. Until now nothing printed
# those together, so a build was identified by the .so hash alone - and the hash says nothing about
# the tree: docs/release.md's own reproducibility rule ("rebuild the same tree twice, the hash is
# identical") means a different hash is a different SOURCE, which is exactly the question you want to
# be able to answer about an experiment build.
#
# What it prints, in this order:
#   * the tree's HEAD (the Mesa base commit; `git rev-parse --short=12`), and that HEAD's subject;
#   * the sha256 of `git diff` (the uncommitted part = the applied patches, since 0001/0002 are
#     committed here) and how many files and lines it covers;
#   * the same for `git diff` restricted to src/freedreno, which is what a Turnip build reads;
#   * the tree state the build script reads (env/exp hooks that are not part of the patch set are
#     counted by name, because a rig in the tree is exactly what checklist item 1 forbids in a ship
#     build and what makes two trees of the same patch set differ);
#   * one line per .so: its sha256 prefix and size.
#
# Read it as: two trees with the same diff-hash are the same source, whatever their .so says; two
# trees with different diff-hashes are different sources, and the difference between them is whatever
# `diff -r` - not the .so - reports.
set -uo pipefail

TREE="${1:?usage: build-tree-stamp.sh <mesa-tree> [<.so> ...]}"; shift || true
[ -d "$TREE/.git" ] || [ -f "$TREE/.git" ] || { echo "not a git tree: $TREE" >&2; exit 1; }

soFar() { cd "$TREE" && git diff | sha256sum | cut -c1-12; }

echo "# tree: $TREE"
echo "# regenerate: scripts/build-tree-stamp.sh $TREE $*"
echo "# date:   $(date -Is)"
echo "HEAD        $(cd "$TREE" && git rev-parse --short=12 HEAD)  $(cd "$TREE" && git log -1 --format=%s | cut -c1-72)"
echo "diff/all    $(soFar)  ($(cd "$TREE" && git diff --shortstat | sed 's/^ *//'))"
cd "$TREE" && git diff -- src/freedreno > /tmp/opencode/.bts-fd.diff
echo "diff/freedreno $(sha256sum /tmp/opencode/.bts-fd.diff | cut -c1-12)  ($(git diff --shortstat -- src/freedreno | sed 's/^ *//'))"

# Hooks that are experiment rigs and not patches: named here because "is measurement code in this
# build?" cannot be answered from the patch set. The list is what this repository has ever written.
echo -n "hooks       "
for knob in TU_IMG_INV TU_B2I_SYNC TU_DBG_RM_HIST TU_MAX_DRAW_STATES TU_CMD_FLAG_CCU_CLEAN_COLOR; do
    n=$(grep -rl -- "$knob" src/freedreno 2>/dev/null | wc -l)
    [ "$n" != 0 ] && printf "%s(%s files) " "$knob" "$n"
done
echo ""
echo -n "props forced by a device entry that gen3 also sets (audit of journal 40.24): "
grep -c "has_alias_rt = True" src/freedreno/common/freedreno_devices.py | sed 's/^/has_alias_rt entries=/'
echo ""
for so in "$@"; do
    [ -r "$so" ] || { echo "so          $so NOT READABLE"; continue; }
    printf 'so          %s  %10s B  %s\n' "$(sha256sum "$so" | cut -c1-12)" "$(stat -c %s "$so")" "$so"
done
