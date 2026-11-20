# Direction: how anything here is measured

**State: permanent.** This page is the "what we believe about our own stand" page; the
runnable protocols are `docs/howto-measure.md`, the incidents that produced them are
`analysis` 29, and the honesty rules are `AGENTS.md`.

The nine classes of measurement error, as one line each (each one is a section of the
journal): unit of the CSV time column, log directory recreation, a game that survives
its timeout, the cold first fill, a green round trip measured in linear, b2i -> i2b in
one submit, a rebuild that invalidates the pipeline cache, swap exhaustion with zombie
wines, and a stale baseline. Full table: `analysis` 29.

Standing rules, in the order they bite:

1. content before numbers - any change that touches memory or layout is first checked by
   a round trip in the mode that actually turned on (`analysis` 21.10, `AGENTS.md`);
2. name the reader and the engine: `texelFetch`, `i2b` and `imageLoad` are three paths and
   they do not all fail together; `i2b` is the reader whose linear control is EXACT at
   every size tested (`analysis` 22.1);
3. name the control run. A round trip proves the mode that received the feature and the
   path it was read through (`analysis` 22.2, 24.1's `clear_only` row is the model);
4. stack identity is proven by the matrix, not by a hash: rebuilding the same stack is
   not bit-for-bit (`analysis` 24.3);
5. sessions differ in length by ~7 %, so compare shares and classes, never absolute MiB
   (`analysis` 27);
6. an allocation is not a hardware claim (`+0x2000` in `memreq` = the driver reserved a
   metadata plane, `analysis` 21.7, 22.2);
7. a probe defect must be excluded before it is reported as behaviour: the tool prints
   the count of WRONG elements, which is how "reads back a quarter" was first published
   as "reads back 75 %" (`analysis` 22.1).

Open tooling gaps: `probe T`-style probes test mechanisms and are not workload shapes
(`analysis` 25); the inventory tooling's `mutable=` field changed meaning between
revisions, so `flags & 0x8` is the source of truth (`analysis` 27); the honest bare base
(stock, no patches, no prop, with the inventory) is built but NOT RUN (`analysis` 27).

Artifacts: `tests/rp6-vkd3d-sparse-test.c`, `tests/tp8bpp.c`, `scripts/run-test.sh`,
`scripts/run-b2i-matrix.sh`, `scripts/run-game.sh`, `scripts/fps-window.py`,
`scripts/imginv-*.py`, `scripts/ubwc-dump-analyze.py`, `scripts/fdperf-*.py`.
