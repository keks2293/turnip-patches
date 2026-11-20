# 12. Defect of run-game.sh: the game outlives the timeout

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

`timeout --signal=INT` kills proton but not the game: `re4.exe` and
`wineserver` stay alive. The next run starts on top of them, in the same
wineserver, and the measurements come out mixed. Discovered on the DX11 attempt,
where a live `re4.exe` was present before launch.

The script now checks `pgrep -f 're4\.exe'` after the timeout, reports it on
stdout and kills the processes (first `SIGTERM`, then `SIGTERM` to wineserver,
then `SIGKILL` for the leftovers).

The number of `d3d12_device_create` lines in the log is deceptive: seven lines
are **one** device plus six warnings from `d3d12_device_create_vkd3d_queues`
about failed OOB queues for families 0 and 5, not seven devices.
