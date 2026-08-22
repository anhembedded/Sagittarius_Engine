# `TableCard` — candidate `BaseCard` sub-base, NOT a real type yet

**Status: 1/2 candidates, weaker claim than `FormCard`.** No `.qml` file here. Not in
`qmldir`. Invisible to all three kit guards on purpose — this directory exists only so the
*intent* is visible to the next person (or AI session) browsing `Sagittarius/UI/`, not to
register a type.

## Hypothesis

A card that wraps tabular data. `setDisabled(true)` means "lock row selection/interaction" —
not dimming the whole table, which would make already-rendered data unreadable while a
background action runs.

## The one plausible candidate — unconfirmed, not yet coded

`AppDataTable.qml` is the obvious fit, but **it does not currently override `setDisabled` at
all** — it still uses `BaseCard`'s no-op. There is no shipped interaction (row selection,
sorting while locked, etc.) yet that this hypothesis is solving a real problem for.

## Promotion rule

Same standard as the other three: needs a **second** real table-shaped card needing the same
"lock interaction, don't dim the data" contract before becoming
`Sagittarius/UI/TableCard/TableCard.qml`. Until then, if `AppDataTable` needs *some* disabled
behaviour, implement it directly on `AppDataTable.qml` (still overriding `BaseCard`) rather
than inventing this intermediate type for a single consumer.
