# 18. NV12 + MUTABLE: `force_linear_tile` is redundant (patch 0009)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

### 18.1 What was noticed

The planar NV12 branch in `tu_image.cc` for images with
`VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT` set two restrictions at once —
`ubwc_enabled = false` **and** `force_linear_tile = true`. The second
restriction made creating NV12 + MUTABLE + SPARSE_RESIDENCY impossible: the
gate from patch 0004 rejects on create at `tile_mode != TILE6_3`, because the
sparse block addressing describes a tiled layout. This was the only path from
vkd3d into the 0004 rejection, which closed the question "is a vkd3d patch
needed for the planar branch" (sections 4 and 6).

### 18.2 Why the tiling need not be removed

The argument from reading the code, later confirmed by measurement:

- `tu_image_view_init` reinterprets NV12 plane 0 as Y8/R8, and the code comment
  names the reason as a difference in **compression**: "the 0'th plane of this
  format has a different UBWC compression". So the reinterpretation itself is
  defined as identity in terms of layout.
- The layout is built by exactly the same format: `tu6_plane_format()` returns
  `PIPE_FORMAT_Y8_UNORM` for plane 0, and that same value goes into
  `tu_image_init`. For plane 1 the base format matches (`R8_UNORM` /
  `PIPE_FORMAT_R8_UNORM`).

Only what the data is compressed with changes, not the geometry of the planes.
So `ubwc_enabled = false` is sufficient, and a separate restriction on tiling
is not.

### 18.3 Measurement

Probe **N** in `rp6-vkd3d-sparse-test.c`. The key line is N2, create
NV12 + MUTABLE + SPARSE_RESIDENCY:

| build | N2 | N1 (without MUTABLE) |
|---|---|---|
| stock 26.2.3 | SUCCESS | SUCCESS |
| 0004–0008 | `FEATURE_NOT_PRESENT` | SUCCESS |
| 0004–0008 + **0009** | **SUCCESS** | SUCCESS |

Logs: `results/test-nv12-linear-patched.log` (0004–0008) and
`results/test-nv12-keep-tiling.log` (+0009).

An indicator independent of size computation: the gate in `tu_image.cc`
rejects exactly at `tile_mode != TILE6_3`, so `SUCCESS` on N2 means TILE6_3
directly, without interpreting memreq.

### 18.4 An error in probe W, fixed along the way

Probe W was meant to be the deciding one and **did not do its job**: it printed
"linear NV12 128x128 would be 0x6000" and on both stock and 0009 it reported
`memreq 0x6000`. So tiled without UBWC gives exactly the same amount, and by
that number linearity cannot be distinguished from tiled. The caption was a
false proof; in the test it was replaced by an explicit warning, and the W
verdict was replaced with neutral reference numbers.

A second reason, recorded in the code: reading "plane 0 through an
R8_UNORM view" by copying is **inexpressible** — `vkCmdCopyImageToBuffer`
takes a `VkImage`, not a `VkImageView`, so transfer doesn't distinguish views
at all. A complete proof would require a shader sampling the R8 view; that is
separate work, it hasn't been done and isn't used in the conclusion.

### 18.5 Summary

- **vkd3d doesn't need patching.** The only path from vkd3d into the 0004
  rejection was closed on the driver side.
- NV12 + MUTABLE stops being linear. For video this is a normal configuration,
  and the demotion cost bandwidth and tiling.
- The edit is not in the per-chip gate but in common code, hence a candidate for
  upstream: a standalone `tu_image.cc` edit without a quirk gate.
- Rollback: `git apply -R patches/0009-turnip-nv12-mutable-keep-tiling.patch`.
  An incremental `scripts/rebuild-turnip-msm.sh` is needed, **but** with the
  image `mesa-build-fedora44-wsi-glslang` rather than
  `mesa-build-fedora44-full` (section 19).
