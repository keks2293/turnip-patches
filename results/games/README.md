# `results/games/` - one directory per measured title

Everything a number in this repository's journal rests on lives under the directory of the game it
was measured in, and nothing is measured across titles: a counter from RE4 and a counter from another
game are never put in one table.

| directory | title | how it is launched | what is in it |
|---|---|---|---|
| `re4/` | **Resident Evil 4 Gold Edition** (InsaneRamZes build, `re4.exe`), D3D12 through vkd3d-proton 3.1.0 (`vkd3d-1.1-5641-g44cf7c2`) under `proton-cachyos-11.0-arm64`, prefix `~/Games/Heroic/Prefixes/re4`, 2560x1440, in-game FPS counter off, MangoHud recording | `scripts/run-game.sh patched` / `stock` | `<tag>/fdperf-raw.txt` (counter dumps, one directory per arm; the `fdperf-` prefix on the directory was
dropped in practice - `0014ab-a/`, `vpc-cacheon/`, `cb21-h1/`), `fps-<tag>.csv` (MangoHud),
`game-<mode>[-<tag>].log` (curated turnip lines), `<batch>/fps.txt` (a generated fps table for a group of
arms, e.g. `cb21/fps.txt`), `dbg-flip-and-messages.txt` (journal 40.16), `traffic-ubwc-ab.txt` (journal 40.17) |

`results/raw/` is the gitignored scratch of the same runs (`game-patched-<tag>.log` in full,
`fdperf-<tag>.txt` before curation, `shot-<tag>.png`); it is not per-game because it is deleted and
regenerated, and the curated copy under `games/<title>/` is what a claim cites.

Everything else directly in `results/` is not a game measurement: `test-*.log` and the probe dumps
(`imginv-*`, `tp8bpp-*`, `sparse-*`, `xr64-*`) come from `turnip-test` on the rig, `vkmark-*` from the
vkmark benchmark, `vulkaninfo-*` from device enumeration. A rig result is never quoted as "the game
does X".

Naming for new work: `results/games/<title>/<direction>-<what>.log`, `fdperf-<tag>/`, `fps-<tag>.csv`,
where `<tag>` is the tag `scripts/run-game.sh` was given. The title is therefore part of the path, and
a citation cannot lose it. History: on 22.11 the RE4 material was moved here from the flat `results/`
by `git mv` and the 34 documents/scripts that cite it were rewritten in the same commit, so every
`results/fdperf-*` path in an older commit is `results/games/re4/fdperf-*` today.
