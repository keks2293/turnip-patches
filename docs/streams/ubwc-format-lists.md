# Direction: UBWC and mutable format lists

**State: shipped, no open item.** The patches that belong to this direction
(`0005`, `0006`, `0009`, `0010`, `0011`, `0012`) are in the release; the alternative
that would have replaced them - the `ubwc_all_formats_compatible` prop - was measured
and rejected.

Believed, with the section that owns the evidence:

- the refusal to tile or compress a format list is derived from comparisons that
  cannot describe the same memory; the axis is the texel block
  (`analysis` 2.1, 21.1-21.6, ADR-0003);
- the ceiling of UBWC for a given shape is measured with three images - linear, with
  a list, without a list - which is the only way to tell "the gate ate it" from "the
  hardware cannot" (`analysis` 4.2 method, probes `CEIL`);
- inside RE4's real lists, the volume that comes from `0011` and `0012` is separated
  from the volume that rides on an upstream prop, per "base -> list" combo
  (`analysis` 25);
- the prop is not a superset of the patches: removing the five under the prop breaks
  probes `S` and `T` (`analysis` 24.3, ADR-0001);
- a UBWC compat mode is part of a resource's layout, not an on/off switch - the single
  sentence that explains most of this direction.

Open: none. The 8-bit hole in `fd6_ubwc_compat_mode()` is not part of this direction -
it is closed by `streams/8bpp-ubwc.md`, and its cause sits earlier than the table.

Decisions: ADR-0001, ADR-0003, ADR-0009, ADR-0010.
Artifacts: `results/test-CEIL-*.log`, `results/test-gen2flag-*.log`,
`results/test-stock-*matrix.log`, `results/imginv-3variants.txt`,
`scripts/fmt-list-gate-check.py`, `tests/vk-fmt-classes.json`.
Next measurement: none planned; the direction reopens only for a workload that creates
lists mixing byte orders.
