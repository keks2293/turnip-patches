# 10. The cause of the rejection found: not driconf, but `prefix=/out/usr`

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

### 10.1. The run with the force confirmed the hypothesis

`VKD3D_SHADER_MODEL=6_6 scripts/run-game.sh patched 200` — **the game ran**:
the swapchain is created and recreated (`1920x1080` → `1280x800`), no window
rejection. Log — `results/games/re4/game-patched-sm66.log`.

The same run verified that the env reaches vkd3d: it prints
`d3d12_device_caps_shader_model_override: Overriding supported shader model: 6_6.`
So the non-working `VKD3D_DEBUG=trace` is a separate problem (not this run),
and environment variables reach vkd3d fine.

Separately: `VKD3D_FEATURE_LEVEL=12_0` on stock
(`results/games/re4/game-stock-flforce.log`) also gives a working game. This reproduces
"fact 1" from the document in the `rp6-vkd3d-analysis` branch already on RE4.
The level force raises `max_shader_model` only to 6_0
(`d3d12_device_caps_override`, `device.c:10888`), so the SM level in this run
stays driver-side.

### 10.2. Why `vulkaninfo` didn't show the discrepancy

The 6.2 gate in vkd3d (`device.c:9750-9765`):

```c
denorm_behavior = properties.denormBehaviorIndependence != VK_SHADER_FLOAT_CONTROLS_INDEPENDENCE_NONE;
if (denorm_behavior && properties.driverID != VK_DRIVER_ID_NVIDIA_PROPRIETARY)
    denorm_behavior = properties.shaderDenormFlushToZeroFloat32 &&
                      properties.shaderDenormPreserveFloat32;
```

On Adreno `FTZ32 = true`, `Preserve32 = false` — i.e. SM 6.0. But `Preserve32`
comes not from the hardware but from a driconf option (`tu_device.cc:1033`):

```c
/* FP32 denorm preserve has to be emulated via soft-float. ...
 * ... but vkd3d-proton cannot emulate it itself so we have to allow it
 * to use our emulation. */
p->shaderDenormPreserveFloat32 = pdevice->instance->drirc.misc.enable_softfloat32;
```

and this option is enabled **only for the vkd3d engine** —
`00-turnip-defaults.conf:42`:

```xml
<engine engine_name_match="vkd3d">
    <option name="tu_enable_softfloat32" value="true" />
</engine>
```
`engine_name_match` is a regex (`xmlconfig.c:848`), compared with the engine
name from `VkApplicationInfo`. `vulkaninfo`'s engine is not vkd3d, so **both**
drivers show `Preserve32 = false`, and the property comparison saw no
difference. This is exactly why the "SM" candidate looked disproved.

### 10.3. Our driver doesn't read driconf at all

`xmlconfig.c:1360-1380`:

```c
/* parse from either $DRIRC_CONFIGDIR or $datadir/drirc.d */
if ((configdir = os_get_option("DRIRC_CONFIGDIR"))) { ... }
else {
    parseConfigDir(&userData, DATADIR "/drirc.d");
    parseOneConfigFile(&userData, SYSCONFDIR "/drirc");
}
```

`DATADIR` comes from the `prefix`/`datadir` of our meson configuration, and it
is this: `prefix = /out/usr`, `datadir = share` → `DATADIR = /out/usr/share`.
The directory `/out/usr/share/drirc.d` does not exist, `SYSCONFDIR` for us is
also not about `/etc`, and `DRIRC_CONFIGDIR` was never set in the runs. The
upshot: **not a single turnip driconf option was read by our driver**, including
`tu_enable_softfloat32`. The packaged driver reads
`/usr/share/drirc.d/00-turnip-defaults.conf` — hence it has SM 6.6 and ours
doesn't.

Measurement (patched + a swapped-in conf, engine matching everything):

```
$ DRIRC_CONFIGDIR=/tmp/opencode/drirc-test vulkaninfo   # patched
    shaderDenormPreserveFloat32 = true      # was false
```

A clarification on the check: the `engine_name_match` pattern must be empty
(`""`) rather than `"."` — `vulkaninfo` has an empty `engineName`, and `.`
requires one character and doesn't match.

### 10.4. Where the path comes from and why it diverged

The path is not computed, it is **baked into the binary at build time**:
`src/util/meson.build:421` emits `-DDATADIR=join_paths(prefix, datadir)`, and
the only use of this macro in the whole tree is `xmlconfig.c:1375`. It can be
checked directly in the library:

```
$ grep -a -o '/usr/share/drirc\.d' /usr/lib64/libvulkan_freedreno.so
/usr/share/drirc.d
$ grep -a -o '/out/usr/share/drirc\.d' build/out/libvulkan_freedreno.so
/out/usr/share/drirc.d
```

The image's packaged build goes through `rpmbuild`
(`image-build/build.sh:70`), and in the Fedora spec `prefix=/usr` — hence
`/usr/share/drirc.d`. Our build was installed with `--prefix=/out/usr`: that is
the container's staging directory, not a real install prefix, and on the device
`/out` doesn't exist at all.

So this is neither a driver bug nor the patches' fault: a mismatch between the
build prefix and where the package is actually installed.

### 10.5. What to fix

The game's rejection is not in patches 0004–0006 and not in vkd3d. The window
appeared because of empty driconf. Three ways, all closing the same cause:

| way | where | state |
|---|---|---|
| `--prefix=/usr` in `scripts/build-turnip.sh` | build | **working, verified** |
| `DRIRC_CONFIGDIR=/usr/share/drirc.d` | `run-game.sh` | was there, **removed** (masked the cause) |
| `~/.drirc` with the same block | home directory | was there, **removed** (masked the cause) |

The correct way was chosen — `--prefix=/usr`: it removes the cause rather than
the consequence, and it works for any launch, including a normal launch of the
game from Heroic, where neither `DRIRC_CONFIGDIR` nor our script is set.

The other two ways were **removed**, not kept as a fallback: both would mask the
cause. As long as `DRIRC_CONFIGDIR` was set in `run-game.sh` and `~/.drirc`
sat in the home directory, SM 6.6 could come up from either of them, and the
next debugging session would look for the cause in the wrong place.
`run-game.sh` now does `unset DRIRC_CONFIGDIR` instead of `export` — not
"doing nothing", but so that a stray variable in the caller's environment
doesn't substitute driconf and make the run look successful for the wrong
reason. The log header keeps the line `DRIRC_CONFIGDIR=<unset>`: that is what
proves the variable was absent.

Verified by rebuilding and running: the path in the binary became
`/usr/share/drirc.d`, the patches are in place
(`sparseResidencyImage2D = true`), the game runs **without** `DRIRC_CONFIGDIR`
and **without** `~/.drirc` — SM 6.6 comes up three times, the force is applied
zero times (`results/games/re4/game-patched-prefixusr.log`, and again
`results/games/re4/game-patched-clean.log` after both crutches were removed).

The `--prefix=/usr` edit is safe because `DATADIR` is not used anywhere else in
the tree — only the path to driconf changes. `SYSCONFDIR` (same trick,
`meson.build:418`) will yield `/etc/drirc`, which also doesn't exist, but that
is `parseOneConfigFile` on an optional file, not `parseConfigDir`.

`~/.drirc` duplicates the `<engine engine_name_match="vkd3d">` block from
`/usr/share/drirc.d` and is read after the system directories, so it doesn't
affect the packaged driver. Its `vkd3d` condition is deliberately not empty:
softfloat32 is emulated and costs performance, and Mesa explicitly advises
against enabling it for everyone — so ordinary DX11 games through DXVK are not
affected.

### 10.6. How to verify

```bash
# 1. path in the library (after rebuilding)
grep -a -o '/usr/share/drirc\.d' /var/home/armada/opencode/build/out/libvulkan_freedreno.so

# 2. the option is picked up without DRIRC_CONFIGDIR
env -u DRIRC_CONFIGDIR VK_DRIVER_FILES=.../build/out/freedreno_icd.json vulkaninfo \
  | grep shaderDenormPreserveFloat32        # expect true

# 3. the game comes up without an SM force
scripts/run-game.sh patched 200
grep "Enabling support for SM 6.6" results/raw/game-patched.log
```

A caveat about step 2: `vulkaninfo` doesn't report the engine name, so the
engine block isn't applied with it and `Preserve32 = false` — that's normal,
the same as with the packaged driver. You should evaluate with a game run, not
`vulkaninfo`.
