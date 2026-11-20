# 23. The `ubwc_coherency_quirk` has no case on gen2 (19.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

**Question.** `supports_uav_ubwc = True` is set in `a7xx_gen2`
(`freedreno_devices.py:818`) while the guard `ubwc_coherency_quirk` is set only in
`a7xx_gen3` (`:863`). So UBWC-storage images are legal on the A740 with no guard
around them. Was there a case for the guard that no probe had touched? The earlier
note "the quirk changes nothing" was obtained in a combo with
`ubwc_all_formats_compatible`, so it was an empty result, not a measurement.

**Method.** Form taken from the driver's own comment (`tu_cmd_buffer.cc:10709-10722`):
a compute shader writes a UBWC image, a later read returns the fast-clear color,
`CACHE_CLEAN` fixes it. Barrier `COMPUTE -> COMPUTE`, which satisfies the guard's
own condition (it checks only that the src stage is a shader stage, it does not
check UBWC). UBWC in the test tube is really on: `0x102000` against `0x100000` for
the linear image. Same test binary, driver = the ship build
(`build/p14-shipped/libvulkan_freedreno.so`, sha256 `c17d02bcaae9a960…`), the prop
turned on with `TU_FORCE_PROPS=ubwc_coherency_quirk`.

| variant | what it asks | result (quirk off / on) |
|---|---|---|
| `same_blit` | blit + fast clear + write + barrier + read in one submit - the form from the comment | `bad=0/262144` both readers / same |
| `same_noblit` | the same without the blit, so a failure could be blamed on the blit | `bad=0/262144` / same |
| `split_blit` | control: write at the end of the submit, read in the next one (the submit boundary flushes by itself) | `bad=0/262144` / same |
| `clear_only` | positive control: no write at all, the read MUST return the clear color | `262144/262144` equal to `0xff00ff00`, both readers (`texelFetch` and `imageLoad`) |

The last row is what makes the other three mean anything: without it the bug had
nothing to return. It also shows the clear really was fast - `0` of 262144 words in
the tile data equal the clear color, while metadata is written (`nz meta = 224` of
`0x2000`), so the clear never touched the data.

Logs: `results/test-uq-quirk-off.log`, `results/test-uq-quirk-on.log`; delete the
`TU_FORCE_PROPS` line and the two files are byte-identical.

**Verdict.** In the tested form there is no bug on the A740, and the form was
observable. There is nothing to give `a7xx_gen2` the flag for; with the flag on it
would cost one `CACHE_CLEAN` per barrier whose src stage is a shader stage.

**What this does not show.** One form, 512x512 RGBA8 in `GENERAL`, no GMEM
renderpass after the blit, no reading of a UBWC image as a blit *source*,
`dEQP-VK.image.load_store.with_format.2d.*` was not run here, and gen3 cannot be
checked on this device.

**Artifact status.** The probe (`probe_ubwc_coherency`, two `.comp` files, the
generator) was removed from the tree, like every other retired experiment; what
remains are the two logs and this section. Removal verified: the test rebuilt
without the probe, on the same p14 driver, produced `results/test-uq-after-removal.log`,
byte-identical to `test-uq-quirk-off.log` except the `UQ` block and one blank line
before it. Row 24 of `docs/a7xx-gen-props.md` was corrected: the `gen1/gen2/gen3`
columns were right (`- | - | True`), the wrong part was the conclusion column.
