# 30. Two outside Turnip patch stacks reviewed: neither carries the A740 fast-path, and the two closest patches are verdicts this repository already has (20.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

**Question.** The operator pointed at two outside patch sets: a "Turnip-Z" patch
collection (files numbered 01, 15, 16, 17, 25, 30, 33, 34, 35, 36, 37) and the repository
`sherft2607/turnip-adreno722-duo`, whose builder applies a subset of them by file name.
The question is narrow: does any of them already contain what queue item 8 (exp-18) asks
for - keep a `VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT` image *tiled* when the application gave
no `VkImageFormatListCreateInfo`, on a chip with `ubwc_unorm_snorm_int_compatible`? A
second version of the same proposal, written by the operator, asked to go further and keep
UBWC on in that case by filtering on the base format.

**Method.** Three steps, none of which touches the Mesa tree or the GPU.

1. The file list with byte sizes, and which files that builder applies, was captured from
   the GitHub tree API into `results/external/sherft2607-turnip-adreno722-duo/repo-tree.txt`
   (tree `766b5ef7034f9425f52054f8e69bdafb0cdc8118`). Their convention, quoted there: a
   file renamed to `*.py.off` is switched off, and a script that runs but changes nothing
   only produces a warning while the build continues.
2. The five mutable/BGRA-related scripts (30, 33, 34, 35, 37) were captured byte-for-byte
   with `curl` into the same folder; the sizes match the ones the API reports.
3. All five were dry-run in a copy of six source files from `../mesa27-src` at commit
   `9845cfb` (base `6dfa32a85f91` + `0001` + `0002`; neither commit touches those six
   files), which is where each script's own anchor matching shows whether it would land.
   The command and the output are `results/external/sherft2607-turnip-adreno722-duo/apply-check.txt`.

Of the whole stack, ten files are applied (`01, 15, 16, 17, 25, 30, 36, 56, 57, 58`) and
the rest carry `.off`; of the mutable/BGRA group, only 30 is applied. The applied set is
Android-side work (gralloc, `AHardwareBuffer`, swapchain usage, per-chip register blobs
for A722) plus sysmem rendering: `repo-tree.txt` groups it by kind.

**Mapping, file by file.** "Here" names the entry or decision that already owns the same
question - which is the point of this entry: none of the candidates opens a new branch.

| external file | what it does, in its own docstring | the same question here | state here |
|---|---|---|---|
| `30-tu-z-mutable.py` (applied) | clears `force_linear_tile` and sets `tile_mode = TILE6_3` **only** inside `if (modifier == DRM_FORMAT_MOD_QCOM_COMPRESSED)`; states that it "leaves 100% of game-internal `VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT` handling untouched" | there is nothing to fix on this stand: no gralloc-imported image arrives with that modifier. The no-list case is answered by the compatibility class in `0014` (journal 21.12) | applies, and is a no-op here (`apply-check.txt`); does not propose UBWC for a no-list image |
| `34-tu-z-mutable-swap.py` (`.off`) | sets `is_mutable = true` for swapped lists on a7xx without `ubwc_all_formats_compatible`, so `fdl` emits the per-view swap and `MUTABLEEN` | exp-10, journal 21.4, and ADR-0009 | measured "no": the goal was not reached (the `R32_UINT` view did not change by one byte) and the BGRA side broke, `261119/262144` `MISMATCH`, the swap applied once instead of twice. It also does not apply to this tree at all (`apply-check.txt`) |
| `35-tu-z-mutable-safe.py` (`.off`) | keep tiled and turn UBWC off when every swapped format in the list is `B8G8R8A8_UNORM`/`_SRGB`; with no list the predicates return "worst case", so its rule leaves such an image tiled with UBWC off | journal 21.12 and patch `0014`, which answer the same predicate with the whole texel-compatibility class instead of a BGRA8 exception, and journal 24.4 for why UBWC stays off there | the same direction, already shipped in a stronger form; does not apply (`apply-check.txt`) |
| `33-tu-z-bgra-swap.py` + `37-tu-z-bgra-companion.py` (both `.off`) | give `B8G8R8A8_UNORM`/`_SRGB` their table swap (`WXYZ`) on every path, then rewrite the channel order everywhere so the memory really holds B,G,R,A: a NIR pass on fragment `store_output`, the colour write mask, three clear-value paths, the blit source swap, `copy_format()` | nothing in this game asks for it - the ship stack's inventory shows zero lists mixing byte order (ADR-0009) and the cross-order no-list classes are the ones `0014` deliberately leaves linear (journal 24.4, 1630.2 MiB), where `fd6_pipe2swap()` does not force `WZYX` at all | applies cleanly (33 matches `fd6_format_table.c:403-404`, all 13 anchors of 37 match), `NOT MEASURED`, not carried |

The two facts worth keeping from the dry run, both verifiable in `apply-check.txt`:

* 34 and 35 anchor on `if (r8g8_r16 || (fmt_list_has_swaps && z_mutable < 1)) {`. That
  line is produced by an older form of 30; the 30 currently in the repository defines no
  `TU_Z_MUTABLE` and never edits that line, and Mesa 27 reads
  `if (r8g8_r16 || fmt_list_has_swaps) {` (`tu_image.cc:659`). So the two files that come
  closest to exp-18 are dead code in that stack - and because their builder only warns on
  a no-op, they would be missing from a release even if they were switched on.
* 33 and 37 are the only mutable-adjacent files that would land on Mesa 27.0-devel here,
  and they are the pair that changes channel semantics on every write path. That is the
  opposite of this repository's rule that a tiling patch may only pull images out of
  linear (`AGENTS.md`, working rules): it is a colour fix, not a layout fix, and it has no
  observed defect to fix in RE4.

**Verdict.** Nothing to merge, and no queue item changes. The specific rule the operator
proposed - when there is no list, keep UBWC if the *base* format is not a swizzled format
and belongs to the UNORM/SNORM/INT group - cannot be made safe by looking at the base
format, because the whole point of a list-less mutable image is that a view may pick any
format of the class: the 32-bit class contains `B8G8R8A8_UNORM`, `R8G8B8A8_UNORM` and
`R32_UINT` at once (journal 24.4, `tests/vk-fmt-classes.json`), which are precisely the
two shapes the flag broke in journal 24.1 (`XV[BGRA8_as_RGBA8]` and `U[B8G8R8A8_UAVLIST]`).
The unit of the decision has to be the class, not the base format - which is what `0014`
already does for tiling, and what exp-18(b) is about for UBWC.

**What this does not show.** Nothing from either stack was built or run, so no statement
here is about what those patches do on hardware; the claim is only about what their
scripts edit. The other 37 files of that repository, the `WinNative-Emu/Drivers` scripts
they are ports of, and the release pages the operator cited (`Vauzi-17/710`,
Mesa release notes) were not captured and are not reviewed here, except that the applied
set's kinds are listed in `repo-tree.txt`. `17-wn-apply-perf-variant.py` (a per-chip
register blob, 13 KB) is the one applied file whose subject this repository has not
measured in that form; journal 13 and ADR-0008 say RE4's frame time does not respond to
driver levers, which is a reason not to spend a build on it, not a measurement of it.

**Artifact status.** Committed under `results/external/sherft2607-turnip-adreno722-duo/`:
`repo-tree.txt`, `apply-check.txt`, and the five scripts as captured
(`30-tu-z-mutable.py` 2348 B, `33-tu-z-bgra-swap.py.off` 2479 B,
`34-tu-z-mutable-swap.py.off` 2925 B, `35-tu-z-mutable-safe.py.off` 3647 B,
`37-tu-z-bgra-companion.py.off` 11818 B). They are evidence about somebody else's work, not
artifacts of a measurement: no build hash and no device is involved. Nothing under
`patches/`, `experiments/` or `build/` changed, and `../mesa27-src` was not written to.
