#!/usr/bin/env python3
"""Counter table for a set of in-game arms, with each arm's build and environment read from
its own `meta.txt` (the queue-16/queue-26 arms of journal 40.29).

    scripts/arm-counters-table.py 0014ab-a 0014ab-b 0014ab-ship vr5-a-aliart \
        > results/games/re4/0014ab/counters.txt

Columns and parsing rules are `scripts/arm_table.py`, the same file `scripts/shadow-cache-table.py`
uses.  The driver hash, the sampler cfg and the environment are printed per arm from
`results/games/re4/<arm>/meta.txt`, so the table cannot claim a build or an env the run did not
have; the arm's `# game settings:` line, when the chain recorded one, is the settings column.
"""
import os
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from arm_table import print_table


def meta_field(arm, name):
    path = f"results/games/re4/{arm}/meta.txt"
    if not os.path.exists(path):
        return "NOT RECORDED"
    for line in open(path):
        if line.startswith(f"# {name}:"):
            return line.split(":", 1)[1].strip()
    return "NOT RECORDED"


def main():
    arms = sys.argv[1:]
    if not arms:
        sys.exit(__doc__)
    print("# Counter table for the arms named below (journal 40.29).  Registry: results/games/README.md")
    print("# sampler: tools/fdperf/fdperf.cfg-vertex, counter window t_rel 20-105 s at the pinned clock")
    print("# regenerate: scripts/arm-counters-table.py " + " ".join(arms) +
          " > results/games/re4/0014ab/counters.txt")
    print("#")
    for arm in arms:
        print(f"# {arm}: driver {meta_field(arm, 'driver')}; env {meta_field(arm, 'env')}")
    print("")
    print_table(arms)


if __name__ == "__main__":
    main()
