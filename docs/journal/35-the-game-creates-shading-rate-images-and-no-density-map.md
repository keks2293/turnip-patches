# 35. The game creates 22 shading-rate images, no density-map image, and the VRS path has no driver knob (21.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md).

**Question.** Journal 34.2 listed five driconf options that this device had never run with, and the
one carrying upstream's own number ("Improves performance up to 4% on A7XX") was
`tu_disable_conservative_fdm_binning`. Reading that option's code in full shows it is gated on
`pass->has_fdm` at both of its sites - `tu_cmd_buffer.cc:3673` and `tu_pipeline.cc:3487-3489` - and
`has_fdm` is set only when the application hands the driver a fragment density map
(`tu_pass.cc:1202-1216` for a render pass, `:1765-1782` for dynamic rendering; `TU_DEBUG=FDM` forces
it, which is a probe and not a detector). So the question split in two, and both halves are
answerable without the game:

1. does anything in this stack ever ask for a fragment density map or a shading-rate attachment, and
   at what cost in images;
2. if a shading-rate map is attached, what does Turnip itself do with it - is there a knob, a
   fallback, a cost.

Neither the existing inventory statistics nor any journal had looked at the `usage=` mask, which is
the only place those paths announce themselves.

## 35.1 The usage census: 22 shading-rate images, zero density maps

`results/imginv-3variants.txt` counts tiling, UBWC and MUTABLE lists, and ignores `usage=`. A
census over the same three logs (`scripts/imginv-usage-bits.py`, new here) gives, per log, the
images with each usage bit and, for the two interesting bits, a breakdown by format, size, tiling
and UBWC. Artifact: [`../../results/imginv-usage-bits.log`](../../results/imginv-usage-bits.log).

| log (build) | creates | `0x100` shading rate | `0x200` density map |
|---|---|---|---|
| `game-patched-imginv4.log` (ship stack without 0014) | 3638 | 21 images, 11.8 MiB | 0 |
| `game-patched-imginv5.log` (ship stack with 0014) | 4176 | 22 images, 12.0 MiB | 0 |
| `game-patched-stockflaginv.log` (stock 6dfa32a + exp-14 + one flag) | 4170 | 22 images, 12.0 MiB | 0 |

Every one of the shading-rate images is `PIPE_FORMAT_R8_UINT`, `tile=tiled`, `ubwc=0`, in the five
sizes 1280x800, 1280x720, 853x480, 640x400, 426x240 - the window and the game's own reduced render
resolutions - and created in groups of three per size with `VK_IMAGE_CREATE_ALIAS_BIT |
VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT` on two of the three and mutable-format alone on the third. The
triple pattern is what a per-resolution ring of aliased resources looks like; that reading is an
inference from the flags, not a measurement, and nothing in the log says which of the three is
attached anywhere.

Two consequences, both cheap:

- **the FDM option cannot fire in these scenes.** It needs an image created with the density-map bit
  to attach, and there is not a single one in 11 984 creates across three builds. That demotes the
  "first candidate" of journal 34.3 before anyone spends a game session on it: in the inventory
  window it is a no-op, and what remains unmeasured is only whether a render pass created later
  attaches a map that was not created in that window.
- **the shading-rate path is real and is already in use.** The same three logs are a control on the
  UBWC patches, and the count does not move with them (21 against 22 - the one-image difference is
  the extra create that imginv4 never reached, consistent with the rest of that log).

## 35.2 What the driver exposes for that path

The capability is not per-chip: `has_attachment_shading_rate` is set in `a7xx_base`
(`freedreno_devices.py:783`), the block that a740 composes from
(`freedreno_devices.py:1239`, `[a7xx_base, a7xx_gen2]`), and it gates the extension, the features and
the per-subpass register write (`tu_device.cc:246`, `:619-621`, `:1366`;
`tu_cmd_buffer.cc:2235`). Measured on the released driver (`c17d02bcaae9a960…`), verbatim in
[`../../results/vulkaninfo-vrs.log`](../../results/vulkaninfo-vrs.log):

| property | value |
|---|---|
| extension | `VK_KHR_fragment_shading_rate`, revision 2 |
| attachment texel size | 8x8, minimum == maximum |
| largest fragment size | 4x4 (`maxFragmentSizeAspectRatio` 4) |
| coverage samples / rasterization samples | 16 / `SAMPLE_COUNT_4_BIT` |
| layered attachments, interlock | `false`, `false` |
| trivial combiner, strict multiply | `fragmentShadingRateNonTrivialCombinerOps = true`, `fragmentShadingRateStrictMultiplyCombiner = true` |

So one map per subpass, 8x8 texels, up to a sixteenth of the fragment work in a covered region -
the ceiling the application is choosing rates under.

## 35.3 What Turnip does with an attached map

`tu7_emit_subpass_shading_rate()` (`tu_cmd_buffer.cc:6963-7000`) emits four register groups per
subpass - `GRAS_QUALITY_BUFFER_INFO` (with `layered = true` and the image's own tile mode),
`_DIMENSION`, `_PITCH`, `_BASE` - and one `LRZ_Q_CACHE_INVALIDATE` event; switching back to no map
emits the same registers with default values plus the same invalidate, once. The format is
`assert(iview->vk.format == VK_FORMAT_R8_UINT)`. That is the whole cost: state per subpass, no
per-image resolve, no copy, and no interaction with tiling or LRZ - `fsr_attachment` appears in
`tu_pass.*`, `tu_cmd_buffer.cc` and `tu_pipeline.cc` only, never in the tiling config
(`tu_util.cc`), the LRZ code or the clear/blit paths.

There is no driver-side option, debug bit or driconf entry anywhere near this path: the rates are
the application's, the map is the application's, and the driver's only choice is how to write four
registers. So "measure the VRS path" cannot mean "A/B a knob" - there is no knob, in this tree.

## 35.4 The bit order I got wrong first, stated so the artifact carries the correction

The first pass over the logs, before it was written down, read `0x100` as the density-map bit and
`0x200` as shading rate, and reported "22 density maps, 0 shading-rate images" - the opposite
conclusion. The header the tree builds against has it the other way round:
`FRAGMENT_SHADING_RATE_ATTACHMENT_BIT_KHR = 0x00000100` and
`FRAGMENT_DENSITY_MAP_BIT_EXT = 0x00000200` (`include/vulkan/vulkan_core.h:2819-2820` at
`6dfa32a`). `scripts/imginv-usage-bits.py` prints both bits side by side, by name, precisely because
they are adjacent and easy to swap from memory; the census above is the corrected reading, and the
`0x100`/`0x200` labels in `results/imginv-usage-bits.log` come from those two header lines.

## What this does not show

- **No proof of attachment.** A usage bit is a declaration; nothing in these logs says a render pass
  actually passed one of the 22 images as a shading-rate attachment, or which rates the game sets.
  The check that would settle it is one line in the driver - log when
  `subpass->fsr_attachment != VK_ATTACHMENT_UNUSED` - and a game run, i.e. queue 12's rig, which is
  blocked on memory (the machine had ~0.4 GiB free when this was written).
- **No fps number, and none implied.** VRS reduces fragment work by construction, and the game
  already asks for it; there is no lever here to gain from, only a path to stop suspecting. ADR-0008
  stands: `UCHE` pressure at ~90 % is what this game hits, and VRS is a fragment-side mechanism.
- **No statement about 8-bit UBWC.** The maps are `R8_UINT` and `ubwc=0`; whether they could be
  UBWC-compressed is the closed `has_8bpp_ubwc = False` branch, not a new question, and the total
  footprint at stake is 12.0 MiB.
- **Nothing about scenes other than the inventoried ones**, and the known caveat applies: 1/1/9
  inventory lines were cut by foreign stderr in these logs and are skipped, as in
  `results/imginv-3variants.txt`.

**Verdict.** The new lead of journal 34.3 resolves to a capability that is on for every a7xx and
that this stack uses at the image level, with no driver-side lever attached: the shading-rate path
is app-owned, its images cost 12.0 MiB, and the driver's entire involvement is four register groups
and a cache invalidate per subpass. The FDM option, meanwhile, has nothing to attach to in the
inventoried scenes, so it leaves the "first candidate" position until an attachment is observed.
The three remaining candidates of journal 34.2 are untouched by this entry.
