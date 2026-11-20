# 7. Swapping the driver on the device

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

Edits to files under `/usr` on the device are not made. An edited file in
`/usr` is a divergence from the installed package: it breaks install
verification and, after a build image update, resurfaces as system corruption —
and not at the moment of the edit, but later and in a different update, so the
link to the cause is lost.

So the driver is swapped by **temporary mounting**: the patched file lives
outside `/usr` (e.g. in `/var/lib/rp6-mesa/`), and a bind-mount is placed over
the packaged one. The mount point does not survive a reboot — after a reboot
the system is stock again, nothing needs to be cleaned up, and the update goes
through cleanly.

```sh
sudo mount --bind /var/lib/rp6-mesa/libvulkan_freedreno.so \
  /usr/lib64/libvulkan_freedreno.so   # after reboot the mount is gone
```

If the swap needs to persist within a session, the mount is set up as a unit in
`/etc/systemd/system` — `/usr` is again untouched in the process. For
vkd3d-proton, if a library swap is needed, the same trick applies: the file
lives outside the prefix and is mounted in place.
