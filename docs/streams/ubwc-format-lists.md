# Direction: UBWC and mutable format lists

**State: shipped, two open measurements (`exp-18`, `exp-20`), no open decision.** The
patches that
belong to this direction
(`0005`, `0006`, `0009`, `0010`, `0011`, `0012`) are in the release; the alternative
that would have replaced them - the `ubwc_all_formats_compatible` prop - was measured
and rejected.

Believed, with the section that owns the evidence:

- the refusal to tile or compress a format list is derived from comparisons that
  cannot describe the same memory; the axis is the texel block
  (journal 2.1, 21.1-21.6, ADR-0003);
- the ceiling of UBWC for a given shape is measured with four images - linear, without
  `MUTABLE`, with a list, and with `MUTABLE` but no list - which is the only way to tell
  "the gate ate it" from "the hardware cannot", and the fourth image is what separates
  "our stack refuses it" from "Mesa refuses it" (journal 21.6.2 method, extended and
  measured on the bare base in journal 31, probes `CEIL`);
- inside RE4's real lists, the volume that comes from `0011` and `0012` is separated
  from the volume that rides on an upstream prop, per "base -> list" combo
  (journal 25);
- the prop is not a superset of the patches: removing the five under the prop breaks
  probes `S` and `T` (journal 24.3, ADR-0001);
- a UBWC compat mode is part of a resource's layout, not an on/off switch - the single
  sentence that explains most of this direction;
- the two 64-bit compat labels of `fd6_ubwc_compat_mode()` are one cell of the compressor
  on this chip in the paths a copy-in and a compute `texelFetch` exercise, and the enum is
  read nowhere but the mutable-list gate and the query that mirrors it - so it is upstream's
  summary of observed behaviour, testable and here tested (journal 32);
- a no-list mutable image cannot be judged by its **base** format, only by its class: the
  32-bit class holds `B8G8R8A8_UNORM`, `R8G8B8A8_UNORM` and `R32_UINT` at once
  (journal 24.4), which is the argument behind the two failures in journal 24.1, and
  behind rejecting the same base-format rule when it arrives from outside
  (journal 30).

Open: two measurements. The first is `exp-18` (queue 1) - give compression back to a
no-list `MUTABLE` image by answering the UBWC question with the **strict** Vulkan class
instead of refusing `NULL`, which is the `TODO: limit based on compatiblity class` that
upstream still carries. Journal 31 measured the two facts that gated it (the class has a
ceiling; the refusal is upstream's and identical on the base and on the shipped stack), and
journal 32 did the two things that were left between that and a rule: it **modelled** the
strict class over all 23 classes (`results/model-strict-class-nolist.txt`, a Python port of
the three predicates - what it grants, and which single line refuses the rest), and it
**measured** the one compat claim the model still had to take on trust - the two labels of
the 64-bit class behave as one cell on this chip
(`results/test-xmc-64bit-compat.log`, probe `XMC`, the `exp-22` knob). So the shape of a
rule is now known rather than guessed, and it is narrower than the direction's earlier
guesses: two classes, not a class list. What stops it being written is the gap journal 32
states as what it does not show - the `R64_*` members that `STORAGE` makes reachable and
that `ubwc_possible()` refuses for its own reasons (open question 14), one geometry, one
reader, and no direct evidence of compressed bytes (open question 15). The bar is also
higher than for a driver-local fix, because the default it reverses is deliberate and
current. The second open measurement is `exp-20` (queue 10) - whether RE4 ever creates a view whose
format differs from the base within one compatibility class. It is the last gap in
journal 24.1's argument that the prop's broken shape is never created here: a no-list
`MUTABLE_FORMAT` image is reinterpretable without a list (journal 24.4,
`tests/vk-fmt-classes.json`), and the inventories only record creates. It reopens no
verdict - the prop frees no patch and adds no compression. A third thing is open in this
direction but is not a measurement: a replacement for `0014` that keeps its rule and
removes its duplication - `exp-21` (queue 11, graduation number `0016`) moves the class
synthesis and the layout decision into
`tu6_mutable_format_list_forces_linear()` and lets `tu_image_init()` call it, instead of
the create path carrying a copy of both. Built and measured 21.11: it is indistinguishable
from the released stack on every probe the rig had at the time - journal 33,
`results/test-exp21-equiv-p14.log`, the same binary against two drivers and the full logs
compared. Its gate has one column left, the game inventory (queue 3), and the "94-row
matrix" item that used to be in that gate is recorded in queue 11 as inapplicable to a
build without the `exp-15` rig. It does not reopen ADR-0006, which is about the rule, not
about where the rule is written.
It is also the seam `exp-18` would sit on: with one decision function, the class that
answers the layout and the class that answers the compression are two arguments rather
than one shadowed pointer.
The 8-bit hole in
`fd6_ubwc_compat_mode()` is not part of this direction -
it is closed by `streams/8bpp-ubwc.md`, and its cause sits earlier than the table.

Decisions: ADR-0001, ADR-0003, ADR-0009, ADR-0010.
Artifacts: `results/test-CEIL-*.log`, `results/test-CEIL-nolist-*.log`,
`results/test-gen2flag-*.log`,
`results/test-stock-*matrix.log`, `results/imginv-3variants.txt`,
`scripts/fmt-list-gate-check.py`, `tests/vk-fmt-classes.json`,
`results/model-strict-class-nolist.txt` (the strict class rule, modelled),
`results/test-xmc-64bit-compat.log` (the two 64-bit compat labels, measured),
`experiments/exp-22-ubwc-64b-mix-knob.patch` (the rig that asked it, not for ship),
`experiments/exp-21-mutable-one-decision.patch` (the candidate for `0014`),
`results/test-exp21-equiv-p14.log` (that candidate against the released stack).
Next measurement: the game inventory against `build/out-exp21` (queue 3) is the run that
closes `exp-21`'s gate and gives this direction a refactored `0014`; the rule for
`exp-21`-plus-class is then a patch file with a known shape and a known gap, and the probe
column it reads off already exists (the fourth image of `CEIL`, journal 31). `exp-20`
(view-format logging over one game run) settles the last gap in journal 24.1 and reopens
nothing - and it is also the run that would say whether the `R64_*` gap of open question 14
is ever reached in practice. A workload that creates lists mixing byte orders would also
reopen the direction.
