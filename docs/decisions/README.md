# Decision records

One decision per file, ~15 lines, immutable once accepted: `Status`, `Context`,
`Decision`, `Consequences`, `Evidence`. A changed verdict is a new ADR that supersedes
the old one, not an edit of it (the rules are in `AGENTS.md`).

These records used to live in four places at once - a topic section, a journal section,
a queue bullet and a plan file - which is how a correction failed to reach all of them.

| id | decision | status |
|---|---|---|
| [ADR-0001](ADR-0001-keep-ubwc-all-formats-compatible-off.md) | `ubwc_all_formats_compatible` stays off on a7xx gen2 | accepted |
| [ADR-0002](ADR-0002-sparse-gate-lift-with-create-time-refusal.md) | sparse gate lifted, sparse+MUTABLE without a list refused at create | accepted |
| [ADR-0003](ADR-0003-tiled-layout-depends-on-block-size.md) | the tiled layout is a function of the block size; 0005/0006/0010/0011/0012 stay | accepted |
| [ADR-0004](ADR-0004-bc-ubwc-is-not-a-perf-lever.md) | BC + UBWC is not an RE4 performance lever | accepted |
| [ADR-0005](ADR-0005-r2d-fix-is-lazy-ccu-bits.md) | the r2d readback fix is deferred CCU bits (0013, exp-15 mode 7) | accepted |
| [ADR-0006](ADR-0006-mutable-no-list-synthesize-the-compat-class.md) | mutable with no list: synthesize the class (0014 v1); v2 dropped | accepted |
| [ADR-0007](ADR-0007-keep-has-8bpp-ubwc-false.md) | `has_8bpp_ubwc` stays False, no 8bpp patch | accepted |
| [ADR-0008](ADR-0008-no-driver-side-fps-lever-for-re4.md) | no driver-side fps lever for RE4 on this device | accepted |
| [ADR-0009](ADR-0009-withdraw-0015-mutableen-on-gen2.md) | 0015 (MUTABLEEN on gen2) withdrawn as a game fix | accepted |
| [ADR-0010](ADR-0010-no-ubwc-coherency-quirk-on-gen2.md) | `ubwc_coherency_quirk` not set on gen2 | accepted |
| [ADR-0011](ADR-0011-feature-level-ceiling.md) | 12_0 through the tiling tier; 12_1 out of reach | accepted |
| [ADR-0012](ADR-0012-lrz-is-not-a-lever-and-its-busy-counter-is-not-a-cost.md) | LRZ is not an RE4 lever; its busy/stall counters are not a cost meter | accepted |

Every ADR points at the journal section that owns the numbers; it does not restate a
measurement that the journal already carries.
