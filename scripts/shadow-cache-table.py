#!/usr/bin/env python3
"""Curated evidence table for the in-game Shadow Cache A/B (journal 40.19, chain25/chain26).

    scripts/shadow-cache-table.py > results/games/re4/shadow-cache-ab.txt

The question this table answers: the 15 fps cluster of journals 38-40 was measured with the game's
`AppShadowCache=0` (the value in this install's `local_config.ini`), and chain25 changed the shadow
keys along with the cache.  Four arms separate the two: the cache is the only key that moves anything.

The columns and the parsing rules live in `scripts/arm_table.py`, shared with
`scripts/arm-counters-table.py`; this file only names the arms and the cfg.  The drop counters of
`cfg-tse3` are 3 of the 4 TSE slots (budget 4), so the reason for the drop is not in this table -
see journal 40.2.
"""
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from arm_table import print_table

ARMS = ["sh-c0", "sh-c1", "sh-q0", "sh-q3"]


def main():
    print("# Shadow Cache A/B in Resident Evil 4 Gold Edition (re4.exe), D3D12 via vkd3d-proton 3.1.0,")
    print("#       2560x1440 display mode; proton-cachyos-11.0-arm64.  Registry: results/games/README.md")
    print("# driver: build/out/libvulkan_freedreno.so sha256 4c3cdb210082 (ship stack) in all four arms;")
    print("#       the delta between arms is the game's own local_config.ini, not the driver or the env")
    print("# sampler: tools/fdperf/fdperf.cfg-tse3, counter window t_rel 20-105 s at the pinned clock")
    print("# chains: /tmp/opencode/chain25.sh (sh-q0, sh-q3), /tmp/opencode/chain26.sh (sh-c0, sh-c1)")
    print("# regenerate: scripts/shadow-cache-table.py > results/games/re4/shadow-cache-ab.txt")
    print("")
    print_table(ARMS)


if __name__ == "__main__":
    main()
