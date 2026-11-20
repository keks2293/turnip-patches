# ADR-0009: withdraw 0015 (MUTABLEEN on gen2) as a game fix

Date: 2026-11-20 (recorded 19.11)
Status: accepted

## Context

`MUTABLEEN` on gen2 breaks two independent things: the channel swap (curable with a
forced `WZYX`) and the reinterpretation of UBWC metadata (not curable - it is an a750
capability the A740 does not have). A candidate patch existed to lift only the first.

## Decision

Do not carry it as a fix for RE4. It may exist only as an upstream-shaped change for an
application that really creates `{BGRA8, RGBA8}` lists.

## Consequences

- the queue does not spend a build on it: the game creates zero lists that mix byte
  order and zero `R8G8*`-next-to-`R16*` lists, so it can neither be enabled by a
  criterion (`XV` 4/4 on a shape the game never makes) nor verified in game;
- the same inventory argument applies to the prop of ADR-0001: zero benefit, three
  regressions.

## Evidence

journal 21.4 (exp-10), 24.1; `results/raw/game-patched-imginv4.log`,
`results/raw/game-patched-imginv5.log` broken down in section 24.1.
