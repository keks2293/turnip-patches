# 19. The build image: `mesa-build-fedora44-full` is stale

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

### 19.1 Symptom

Incremental rebuild (`scripts/rebuild-turnip-msm.sh`) failed at link time,
listing missing libraries one after another:

```
ninja: error: '/usr/lib64/libX11-xcb.so', needed by
  'src/freedreno/vulkan/libvulkan_freedreno.so', missing and no known rule
```

### 19.2 Cause

`docs/analysis.md` prescribes making the image via
`podman commit mesa localhost/mesa-build-fedora44-full` — the image is not
rebuilt, and `commit` freezes the container in whatever state it ended up in.
Measured contents:

| image | date | of the 6 WSI-devel packages |
|---|---|---|
| `mesa-build-fedora44-full` | 27.09 | **0** |
| `mesa-build-fedora44-wsi-glslang` | 29.09 | **6** |

All six packages (`libxcb-devel libX11-devel libXrandr-devel
libxshmfence-devel xcb-util-keysyms-devel wayland-devel`) are listed explicitly
in `container/Containerfile.mesa-build`, together with the note about name
casing. So **the documentation is correct — the image merely fell behind it**:
the commit was made before the WSI block was added to the Containerfile.

Why it wasn't caught immediately: a full rebuild (`scripts/build-turnip.sh`
with `rm -rf build`) recreates the directory and `meson setup` finds the
dependencies itself. An incremental rebuild reuses the existing `build/`, where
meson has already written absolute paths of the form
`/usr/lib64/libX11-xcb.so`. Those paths haven't gone anywhere, but the packages
aren't in the image.

### 19.3 What to do

Take `localhost/mesa-build-fedora44-wsi-glslang` for any rebuild. Or rebuild
the image from `container/Containerfile.mesa-build` so that it cannot diverge
from the Containerfile again.

Separately: `podman run --rm` discards what was installed, so "install the
packages once into the image" doesn't work in principle — if the image isn't
rebuilt, the dependencies are installed in the same run. And `dnf` rolls back
**the entire** transaction on any wrong package name, silently going into
`>/dev/null`, so the list must be exact (in Fedora it is `libXrandr-devel`, not
`libxrandr-devel`; there is no `libxcb-present` or the like — everything is in
`libxcb-devel`).

### 19.4 What was measured

| package | `-full` | `-wsi-glslang` |
|---|---|---|
| `libX11-devel` | no | yes |
| `libXrandr-devel` | no | yes |
| `libxshmfence-devel` | no | yes |
| `xcb-util-keysyms-devel` | no | yes |
| `libxcb-devel` | no | yes |
| `wayland-devel` | no | yes |

Check with one command:

```sh
podman run --rm localhost/<image> bash -c \
  'for p in libX11-devel libXrandr-devel libxshmfence-devel \
            xcb-util-keysyms-devel libxcb-devel wayland-devel; do
     rpm -q $p >/dev/null 2>&1 && echo "yes $p" || echo "NO   $p"
   done'
```

Casing matters in `rpm -q`: `libxrandr-devel` will return "no" even where the
package is installed — the name is `libXrandr-devel`.
---
