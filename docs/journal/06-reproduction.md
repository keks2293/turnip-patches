# 6. Reproduction

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

`tests/rp6-vkd3d-sparse-test.c` — the test on which all the results above were
obtained. Key probes: **A** — sparse machinery working; **S** — the hole (on
stock the data is corrupted, on 0004 create is rejected, on 0005 both views are
exact); **S2** — the boundary (mixed-swap and the NULL list stay rejected);
**T** — P6; **N** — planar NV12 with and without MUTABLE; **V** — enumeration of
all 70 compatibility lists that vkd3d can possibly build; **G** and **M** — UBWC
controls (with metadata / without). The full matrix and verdict are in the file
header.

The class list for probe V is generated from the vkd3d sources rather than
enumerated by hand, and when vkd3d is updated it needs to be regenerated:

```sh
scripts/gen-vkd3d-lists.py /path/to/vkd3d-proton > tests/vkd3d-fmt-classes.h
```

Procedure:

```sh
# 1. toolchain (the device has no compiler, everything runs in podman)
podman run --name mesa localhost/fedora:44 \
    dnf install -y meson ninja-build gcc gcc-c++ python3-mako ...
podman commit mesa localhost/mesa-build-fedora44-full

# 2. Mesa 26.2.3 + patches 0001-0006
scripts/build-turnip.sh          # meson setup + ninja in the container
scripts/rebuild-turnip-msm.sh    # incrementally, if flags changed

# 3. test
scripts/build-test.sh
scripts/run-test.sh ""                          results/test-stock.log
scripts/run-test.sh .../freedreno_icd.json      results/test-patched.log
```

A run takes about a second, so there is no point in filtering probes — the full
log is more useful. Ready logs of both runs are in `results/`.

### Two mistakes the build went through

Both are reproducible, and both give an equally vague symptom —
`vkEnumeratePhysicalDevices` returns 0 devices and the test prints
`find turnip -> -3`.

1. **`-Dfreedreno-kmds=kgsl` (the Mesa default is `msm`).** The device has no
   `/sys/class/kgsl`, and the enumeration path for kgsl —
   `open("/dev/kgsl-3d0")` (`tu_knl.cc:343`) — silently returns
   `VK_ERROR_INCOMPATIBLE_DRIVER`. Signs: the `.so` contains the strings
   `kgsl_3d0`/`kgsl_bo_init`, while there is no `drmGetVersion` import.
2. **Where the result gets copied.** The container mounts `/out` at the root of
   `build/`, while the ICD manifest points to `build/out/`. If you copy into
   `/out/`, the loader picks up the old binary, and the result looks like "the
   patches didn't apply". You should check both copies with `ls -l` rather than
   trusting `EXIT=0`.

Diagnostics that came in handy: `TU_DEBUG=startup` (is there an instance),
`VK_LOADER_DEBUG=all` (did the loader find the ICD),
`objdump -p | grep NEEDED` and
`nm -D --undefined-only | grep drmGetVersion` (was the msm-KMD compiled in).

### Where 0004 turns into a rejection for vkd3d

The rejection is correct, but vkd3d has no degradation path: `resource.c:1207`
on `vkCreateImage` failure writes a WARN and returns the HRESULT outward, with
no retry and no fallback to another path. Therefore it matters which exact set
of combinations is actually unreachable.

Analysis of `vkd3d_get_format_compatibility_list` (`resource.c`):

- **regular formats** — there is always a list, the ready-made
  `device->format_compatibility_lists[Format]`, and for typeless-32-bit
  additionally `R32_{UINT,SINT,SFLOAT}` (D3D11 spec 5.3.9.5).
  `MUTABLE_FORMAT_BIT` is set only after
  `if (list->format_count < 2) return false;`, i.e. MUTABLE and the list go
  together: no list — no MUTABLE. No conflict.
- **the branch with a zeroed list** (`resource.c:826-827`, MUTABLE under
  `memset(compat_list, 0, ...)`) requires `DISABLE_UAV_COMPRESSION` /
  `DISABLE_COLOR_COMPRESSION` / `DISABLE_SIMULTANEOUS_UAV_COMPRESSION` —
  off by default, not encountered in a normal game.
- **planar formats** — the only default case where MUTABLE is set without a
  list:
  ```c
  if (format->vk_aspect_mask & VK_IMAGE_ASPECT_PLANE_0_BIT) {
      *vk_flags |= VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT;
      return false;
  }
  ```

This connects with `sparse_resource = !heap_properties` (`resource.c:732`): all
`CreateReservedResource` (`resource.c:4916` passes `NULL`) and any
`CreateCommittedResource` without a heap get
`SPARSE_BINDING|RESIDENCY|ALIASED`. The upshot: **NV12 on the default/reserved
heap** gives MUTABLE + SPARSE + no list, i.e. exactly the 0004 rejection.

### NV12: measured, the isolation works

Probe **N** (added to the test) — planar NV12 with sparse, with and without
MUTABLE:

| | stock | 0004–0006 |
|---|---|---|
| N1: NV12 + sparse, **without** MUTABLE | SUCCESS | **SUCCESS** |
| N2: NV12 + sparse, **with** MUTABLE | SUCCESS | `FEATURE_NOT_PRESENT` |
| N3: query NV12 + sparse, both variants | `FORMAT_NOT_SUPPORTED` | `FORMAT_NOT_SUPPORTED` |

N1 is exactly the prediction confirmed by measurement: without MUTABLE the
"NV12 is always linear" branch is not executed at all, `force_linear_tile` is
not set, `tile_mode` stays `TILE6_3`. That it is tiled rather than linear
follows from 0004 itself: it rejects any sparse image with
`tile_mode != TILE6_3`, so on the patched driver a successful sparse-create
cannot be linear.

N3 is not a regression: the same `FORMAT_NOT_SUPPORTED` exists on stock, the
cause is upstream (`tu_formats.cc:730-732`,
`/* Don't support multi-planar formats with sparse yet */`). Inside the driver
there is a discrepancy here — create allows, query rejects — but it doesn't
affect vkd3d: `utils.c:686` returns before the query for planar formats ("Planar
and depth-stencil formats do not support sparse in D3D12").

**Conclusion: MUTABLE and SPARSE are not obliged to combine, and the decoupling
is one line in vkd3d.** MUTABLE is functionally unnecessary for planar, as the
comment next to it admits: "Just be conservative here". The proposed edit:

```c
if (format->vk_aspect_mask & VK_IMAGE_ASPECT_PLANE_0_BIT) {
    if (!sparse_resource)                 /* NV12 + sparse is linear anyway */
        *vk_flags |= VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT;
    return false;
}
```

0004 should **not** be weakened for this: a NULL list means the application may
reinterpret into any compatible format, and safety cannot be proven for such a
list in principle — the helper says outright "presumably one would have the swap
set". The decoupling belongs on the vkd3d side.

### Enumeration of all lists vkd3d can possibly build

The question "will a list built by vkd3d itself ever reach the rejection" is
settled not by reasoning but by enumeration. Both tables that vkd3d uses for
this are static:

- `libs/vkd3d/utils.c: vkd3d_formats[]` — DXGI → VkFormat map;
- `libs/vkd3d/utils.c: dxgi_format_compatibility_list[]` — the lists
  (`image_format` + `view_formats`) from which
  `vkd3d_init_format_compatibility_lists` assembles
  `device->format_compatibility_lists[]`.

From these, `tests/vkd3d-fmt-classes.h` is generated
(`scripts/gen-vkd3d-lists.py`) — 72 classes whose list has ≥ 2 formats (two of
them were added later, journal 21.3). The counts in the sections below, made on the
first 70 classes, are left as they were.
This condition is exactly what decides everything: `MUTABLE_FORMAT_BIT` is set
only after `if (list->format_count < 2) return false;`, so **MUTABLE always
comes with a list**, and the "MUTABLE without a list" case on non-planar formats
is unreachable.

The enumeration zone is narrowed by two facts, both from the code:

- a sparse resource in vkd3d is exactly `CreateReservedResource`:
  `d3d12_resource_create_vk_resource` passes
  `heap_properties = resource->flags & VKD3D_RESOURCE_RESERVED ? NULL : &resource->heap_properties;`,
  so `sparse_resource = !heap_properties` is true only for reserved.
  Fallback goes to `d3d12_resource_create_committed`, i.e. **not** sparse.

Probe **V** asks the driver about each class three times — `SPARSE+MUTABLE`
with a list (exactly what vkd3d does for reserved), `MUTABLE` without sparse,
and `sparse` without mutable and without a list — under two usage sets: full
(`SAMPLED|STORAGE|TRANSFER`) and the one vkd3d itself uses to query sparse
support (`TRANSFER_SRC|TRANSFER_DST`, `utils.c`). For those that pass the query,
`vkCreateImage` is done: the query is only a necessary condition; the whole
point of 0004 is that query and create disagreed.

| usage | accepted | rejections by the `sparse × mutable` gate | query/create gaps | rejections not due to sparse |
|---|---|---|---|---|
| full | 49/70 | **0** | **0** | 21 |
| vkd3d's | 64/70 | **0** | **0** | 6 |

**No list that vkd3d is capable of building is rejected by the 0004 gate.** All
rejections are "sparse itself is forbidden" or "format+usage not supported at
all" (BC*, NV12/P010/P016, R32G32B32*), and these are long-standing upstream
limitations. The V block on stock and on the patches is **byte-identical**,
i.e. 0004–0006 changed not a single verdict for real vkd3d lists.

Two consequences:

1. The 0004 rejection is **unreachable** from the normal vkd3d path. The only
   path that lands in it is the planar branch without a list (probe N2), and
   there the fix is one line, described above.
2. The E/F hole that 0004 closes (silent linear+sparse) is **unreachable from
   vkd3d as well**: E is the list `{RGBA8, BGRA8}`, F is the NULL list, and
   vkd3d builds neither of them. So 0004 closes a real bug without changing
   behavior for any real consumer. This is the answer to the question that
   remained open: there is no risk to games, and there are no grounds for
   dropping 0004 either.
