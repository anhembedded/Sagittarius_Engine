# BUG-013 — `AppDataTable` renders a right-aligned column and the left-aligned column after it with zero visual gap

**Reported date:** 2026-08-27
**Severity:** Low (cosmetic — data is still correct and readable once a viewer knows to look, but two values can render as one fused string)
**Status:** 🔴 Open
**Found by:** `EPIC-007E`, smoke-testing the runtime state console's Events & wiring screen against a real server

---

## What is wrong

`AppDataTable.qml`'s header row (`Row { spacing: 0 }`, `AppDataTable.qml:168`) and each data row
(`Row { anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12 }`,
`AppDataTable.qml:314`) lay columns out edge-to-edge with **no per-cell padding** — a cell's
`Text` fills exactly `_effectiveColumnWidths()[index]` and nothing more
(`AppDataTable.qml:184`/`327`). Horizontal alignment is per-column
(`modelData.align`, default `Text.AlignLeft`).

When a column aligned `Text.AlignRight` is immediately followed by a column that is
`Text.AlignLeft` (the default — most columns never set `align` at all), the first column's text
hugs its own right edge and the second column's text hugs its own left edge. Those two edges are
the same pixel, with zero gutter between them, so the two values render as one fused string.

## Reproduction

`tools/state_console/presentation/events/qml/EventsScreen.qml`'s original column list:

```qml
readonly property var eventColumns: [
    { key: "name", title: "Event", weight: 3 },
    { key: "module", title: "Module", weight: 3 },
    { key: "handlerCount", title: "Handlers", weight: 1, align: Text.AlignRight },
    { key: "emits", title: "Emits", weight: 1, align: Text.AlignRight },
    { key: "failures", title: "Failures", weight: 1, align: Text.AlignRight },
    {
        key: "registered", title: "Registered", weight: 1,
        formatter: function(v) { return v ? "yes" : "NO" }
    }
]
```

`failures` (right-aligned) is immediately followed by `registered` (left-aligned, the default).
Screenshotted against a real running server (`examples/student_management/console.py
--demo-faults`), the header renders as one string `"FailuresRegistered"` and every data row
renders as `"0yes"` / `"0NO"` instead of two legible columns.

This is not new to this screen: `examples/student_management/presentation/roster/qml/
RosterScreen.qml:24` has the identical shape — `gpa` (`Text.AlignRight`) immediately followed by
`enrolledAt` (default, left) — so `RosterScreen` renders the same fused-text defect whenever a
GPA value and the next row are both visible; it went unnoticed because nothing in
`test_roster_screen.py` asserts on rendered column *gaps*, only on data values and warning
absence.

## Why it is worth fixing rather than ignoring

The bug is silent in the same shape `BUG-007` describes for a different subsystem: nothing
raises, nothing logs, the values are individually correct — the display alone merges two
columns into an illegible run of characters. Any new screen composing this shape (a numeric
right-aligned column immediately before a left-aligned one) reproduces it by construction; a
column-list author has no signal from `AppDataTable`'s own API that this combination is unsafe.

## Requirements

1. Give `AppDataTable` a real per-cell horizontal gutter (a `columnSpacing`-style property, or
   fixed inner padding, applied consistently regardless of alignment) so adjacent columns never
   share a pixel — the "why" a reader would otherwise have to reconstruct: alignment-only
   layout with `spacing: 0` was fine as long as no consumer alternated alignments, but nothing
   enforces that invariant.
2. Regression test: two adjacent columns, one `Text.AlignRight` then one default-left, with
   values chosen so a fused string is visually/positionally distinguishable from two separate
   ones (e.g. assert the rendered `x` of the second cell's text is not less than the rendered
   `x + width` of the first cell's text, or an equivalent geometry assertion — a value-only
   assertion would not have caught this). Must fail against today's `AppDataTable.qml`.
3. `pwsh ./scripts/ci-local.ps1` green — paste the `===CI_LOCAL_RESULT===` block and the log path.

## Deliberately not fixed inside `EPIC-007E`

`EPIC-007E`'s two affected screens (Events & wiring, Tasks & threads) were reordered/realigned
locally to avoid the adjacency rather than touching the shared `AppDataTable.qml` kit component —
a kit-wide layout change is a distinct, higher-blast-radius fix (it also touches the already-
shipped `RosterScreen`) that deserves its own change and its own review, not a drive-by inside an
unrelated epic (`design-discipline.md`: "prefer leaving something undone and named over done and
wrong").
