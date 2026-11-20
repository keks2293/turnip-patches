# Direction: UBWC and mutable format lists

**State: shipped, one open measurement (`exp-20`), no open decision.** The patches that
belong to this direction
(`0005`, `0006`, `0009`, `0010`, `0011`, `0012`) are in the release; the alternative
that would have replaced them - the `ubwc_all_formats_compatible` prop - was measured
and rejected.

Believed, with the section that owns the evidence:

- the refusal to tile or compress a format list is derived from comparisons that
  cannot describe the same memory; the axis is the texel block
  (journal 2.1, 21.1-21.6, ADR-0003);
- the ceiling of UBWC for a given shape is measured with three images - linear, with
  a list, without a list - which is the only way to tell "the gate ate it" from "the
  hardware cannot" (journal 21.6.2 method, probes `CEIL`);
- inside RE4's real lists, the volume that comes from `0011` and `0012` is separated
  from the volume that rides on an upstream prop, per "base -> list" combo
  (journal 25);
- the prop is not a superset of the patches: removing the five under the prop breaks
  probes `S` and `T` (journal 24.3, ADR-0001);
- a UBWC compat mode is part of a resource's layout, not an on/off switch - the single
  sentence that explains most of this direction;
- a no-list mutable image cannot be judged by its **base** format, only by its class: the
  32-bit class holds `B8G8R8A8_UNORM`, `R8G8B8A8_UNORM` and `R32_UINT` at once
  (journal 24.4), which is the argument behind the two failures in journal 24.1, and
  behind rejecting the same base-format rule when it arrives from outside
  (journal 30).

Open: one measurement, `exp-20` (queue 10) - whether RE4 ever creates a view whose
format differs from the base within one compatibility class. It is the last gap in
journal 24.1's argument that the prop's broken shape is never created here: a no-list
`MUTABLE_FORMAT` image is reinterpretable without a list (journal 24.4,
`tests/vk-fmt-classes.json`), and the inventories only record creates. It reopens no
verdict - the prop frees no patch and adds no compression. The 8-bit hole in
`fd6_ubwc_compat_mode()` is not part of this direction -
it is closed by `streams/8bpp-ubwc.md`, and its cause sits earlier than the table.

Decisions: ADR-0001, ADR-0003, ADR-0009, ADR-0010.
Artifacts: `results/test-CEIL-*.log`, `results/test-gen2flag-*.log`,
`results/test-stock-*matrix.log`, `results/imginv-3variants.txt`,
`scripts/fmt-list-gate-check.py`, `tests/vk-fmt-classes.json`.
Next measurement: `exp-20` (view-format logging over one game run), which settles the
last gap in journal 24.1. A workload that creates lists mixing byte orders would also
reopen the direction.
