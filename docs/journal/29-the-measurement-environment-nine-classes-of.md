# 29. The measurement environment: nine classes of error and two artefacts (19.11)

One entry of this repository's journal. Index: [`docs/analysis.md`](../analysis.md) (generated); rules for reading and writing: [`../../AGENTS.md`](../../AGENTS.md). Cite this entry as `journal N` or `journal N.M`, where the number is also the start of the file name.

The most practical result of this work: almost every "finding" on the way turned out
first to be an artefact of the stand. Recorded here because each one cost a day and
each is now closed by a rule (the runnable protocols are in `docs/howto-measure.md`).

| # | artefact | symptom | how it was caught / the cure |
|---|---|---|---|
| 1 | `elapsed` in the MangoHud CSV is nanoseconds | a 40-50 s window comes back empty | the parser filtered it as seconds; divide by 1e9 |
| 2 | `HUDLOG` recreates the directory | the CSV disappears after the next run | copy the CSV right after the run starts |
| 3 | `timeout --signal=INT` does not kill the game | `re4.exe`/`wineserver` survive, the next run stacks on top of them | `pgrep -f 're4\.exe'` + SIGTERM -> SIGKILL, in `scripts/run-game.sh` |
| 4 | cold first fill | ~2 % of zeros in a fresh image, the second fill is clean | `tests/repro-first-fill.c`, warm up before measuring (section 20) |
| 5 | "EXACT" with the gate lifted | the round trip is green because what was measured was linear | check that the mode really got UBWC: `nonmut/list > lin` |
| 6 | b2i -> i2b in one submit | the readback returns the pre-copy content | `RK_SPLIT_SUBMITS=1`; section 21.10 |
| 7 | rebuilding the driver | cold start, `Pipeline … does not exist` | `pipelineCacheUUID` changes, see below |
| 8 | swap exhaustion + zombie wines | fps frozen at 1.86, GPU at 220 MHz | see below |
| 9 | a stale baseline | "-60 %" out of nowhere | new baseline on the same binary, interleaved runs |

**How a rebuild invalidates the pipeline cache.** `tu_device_get_cache_uuid()`
(`tu_device.cc:108`) hashes with blake3 over: `build_id`
(`disk_cache_get_function_identifier` -> the ELF build-id note), `chip_id`,
`uche_trap_base`, `compiler_options`. On Linux with `HAVE_BUILD_ID`,
`disk_cache_get_function_identifier` hashes the GNU build-id note
(`src/util/disk_cache.h:107-120`), and the build-id changes whenever the contents of
the `.so` change. Therefore **any rebuild of the driver changes
`pipelineCacheUUID`**, and `vkd3d-proton.cache` (mtime 17.11) becomes invalid: a slow
first run, shader compilation inside the measurement window, and `Pipeline "…" does
not exist` warnings. Rule: after a rebuild, one warm-up run first, then measure; in
an A/B compare only warm runs, and only inside one build.

**The "1.86 fps" artefact (19.11).** The same binary `c9dad346` that gave p25 =
14.94-15.09 in the morning produced, in the afternoon:

```
fps = 1.857 (min = max = 1.857), frametime = 538.5 ms,
gpu_core_clock = 220 MHz, gpu_load = 9 %,
ram_used = 6.98 GiB, swap_used = 7.32 GiB of 7.49 GiB, cpu_load = 45 %
```

The value does not move by a single frame over 100 s - that is not a slow game, that
is the environment: swap almost fully used, wine processes from the previous day still
in the system (`winedevice.exe` from 18.11 17:28 and 23:31, `xalia.exe`), and the GPU
at its minimum clock almost idle (9 %). After removing the zombies, swap dropped from
~7.3 to ~5.5 GiB. Practical rule: **before every window** check `free -m`, the presence
of `re4.exe`/`wine*`, `cur_freq` and `gpu_load`. The signature of a poisoned run is
`min == max` for fps - frames are paced by a fixed timeout, not by rendering.
