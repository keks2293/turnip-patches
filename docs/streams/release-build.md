# Direction: the shipped driver and its builds

**State: shipped.** `27.0.0-devel-p14`, ship `.so c17d02bcaae9a960…`; the tag and
`master` are frozen (`AGENTS.md`). The release procedure and provenance are
`docs/release.md` - this page only points at what a builder usually needs.

Believed, with the owner:

| thing | owner |
|---|---|
| what goes into a release, the checklist, how to publish | `docs/release.md` |
| the tree that must be built, the hashes to record, the chronology | `docs/release.md` |
| the rebase matrix of `0001..0014` onto Mesa 27, build cache rules, the ninja/PHONY trap | `docs/mesa-27-plan.md` |
| container, `-j2`, ccache in `/tmp`, "never while the game runs" | `AGENTS.md`, `docs/release.md` |
| build identification by `sha256sum | cut -c1-12` and why the version string cannot be used | `docs/release.md` |
| the origin of `0001..0003` (image recipe) | `patches/PATCHES.md` |
| why each shipped patch exists and what it must not do | the header of `patches/00NN-*.patch` |
| which candidates were dropped and the criterion for dropping | `patches/DROPPED.md` |

Known state that is easy to forget: `../mesa27-src` currently has `0003..0014` NOT
applied, with only `exp-14` tooling and fragments of `0001`/`0002` in the tree - the
ship `.so` is unaffected (it builds from `turnip-27.0-source-patches`), but measurement
builds cannot be made until the stack is restored by explicit file names. That is the
first blocker in `docs/plan-next-checks.md`.

On Mesa 27 the line that `0002` adds (`GPUId(chip_id=0x44050000)`) already exists
upstream, so on 27 that patch is a duplicate line and a no-op; the shipped `.so` was not
touched (effect zero, matrix 94 EXACT either way).
