# TASK-035: `AppDataTable`'s columns render with no gap between them

## Description

`AppDataTable.qml`'s header row and each data row lay out their column cells using a plain
`Row` with no `spacing` set:

```qml
Row {
    id: headerRow
    anchors.fill: parent
    anchors.leftMargin: 12
    anchors.rightMargin: 12
    Repeater { ... }   // each delegate's own width: (weight / weightSum) * headerRow.width
}
```

Same shape for the data-row delegate's `cellsRow`. Each column's `Text` fills exactly its
weighted share of the row's width with no margin between adjacent columns. A right-aligned
column immediately followed by a left-aligned column therefore renders with the two touching —
visually the two values run together with no visible gap.

## How this was found

Found 2026-08-23 verifying `examples/student_management`'s new `enrolledAt` column (added this
session) by actually launching the GUI and grabbing a screenshot. The GPA column
(`align: Text.AlignRight`) sits immediately before the Enrolled column (left-aligned), and the
rendered header read `GPAEnrolled` with no space, and data rows read e.g. `3.702026-08-23 12:48`.
Confirmed this is structural to `AppDataTable.qml` itself (`Row` with no `spacing:`), not
specific to `RosterScreen.qml`'s column list — any consumer with a right-aligned column
immediately followed by another column will hit the same thing, it's just unusually visible here
because the two touching values are both dense strings (a number and a date) with no natural
word-break between them.

## Why it might matter

Purely cosmetic — no functional breakage, `AppDataTable` still renders correct data in the
correct columns. But it's a real, user-visible defect in a shared widget-kit component (not just
this one sample app), and it's a poor first impression for anyone using `AppDataTable` with a
right-aligned numeric column that isn't the last one.

## Requirements

1. Add a small `spacing` to both `headerRow` and `cellsRow` in `AppDataTable.qml`.
2. Re-derive each column's width formula to account for the added spacing (currently
   `(weight / weightSum) * headerRow.width`; if `Row.spacing` grows the total content width by
   `(columns.length - 1) * spacing`, the width formula needs to divide the reduced usable width,
   not `headerRow.width` verbatim, or the last column will overflow the card's own bounds).
3. Verify against the widget-kit gallery (`Gallery.qml`'s own `AppDataTable` usage) and
   `student_management`'s roster screen — both should still have their columns sum to the full
   available width with no overflow/clipping, just a visible gap between adjacent cells.
4. Add or extend a regression test if a reasonable one exists for this (e.g. asserting adjacent
   header cells' x + width for one delegate is strictly less than the next delegate's x).

## Priority

P3 — cosmetic only, not a functional defect, and workaroundable per-consumer today (e.g. adding
manual padding into a formatter's returned string).

## Category

UI / Widget Kit (`pyside_mvc`)

## Related

- None — found independently while verifying `examples/student_management`'s card-usage feature
  work, not tied to any existing task.
