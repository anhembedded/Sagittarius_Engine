# Decisions — Architecture Decision Records

Convention adopted 2026-08-27. An **ADR** records one architectural decision, the
context that forced it, and the consequences accepted with it — written *before* the
work, so the reasoning is on record while it is still a choice rather than
reconstructed afterwards from what shipped.

## Why this directory exists

The reasoning behind big decisions in this repository currently lives inside epic
`README.md` files — `EPIC-005` §5 ("build the recorder, borrow the viewer") and
`EPIC-006` §1.2 ("wiring correctness before execution cost") are both real ADRs
written in the middle of a work-tracking document. That works while the decision and
the work have the same lifetime. It fails in two cases:

1. **A decision precedes any epic.** There is nowhere to put it, so it gets made in a
   chat and lost.
2. **A decision outlives its epic.** `EPIC-005` is closed; its §5 ruling on viewers
   still governs anything proposed today. A closed epic is the wrong place to look up
   a live constraint.

`Sagittarius_Elite_Warrior` already keeps standalone decision files
(`DECISION_2026-08-24_widget_architecture.md`, cited by `TASK-038`). This is the same
idea with a stable ID pool.

## Layout

```text
Tasks/decisions/
├── README.md                       # This file — the index below is the register
└── ADR-XXX_short_slug.md
```

- **ID**: `ADR-XXX`, its own incrementing pool, independent of `TASK-XXX` / `EPIC-XXX` /
  `BUG-XXX`. Next ADR takes the highest existing number + 1.
- **Status**: `Proposed` → `Accepted` → (later) `Superseded by ADR-YYY` or `Deprecated`.
  **An ADR is never edited to say something different once accepted** — that erases the
  record. It is superseded by a new one that names it.
- **One decision per record.** If a document contains two decisions with different
  lifetimes — they could be revisited independently — it is two ADRs. That is why
  `ADR-001` and `ADR-002` below are separate: the console's data model can stand while
  its renderer is reconsidered.
- An ADR is **not** a task. It does not track progress and has no acceptance criteria;
  it states a decision. The work that follows from it is a `TASK-XXX` or an `EPIC-XXX`
  that links back here.

## Register

| ID | Decision | Status | Date |
| :--- | :--- | :--- | :--- |
| **[ADR-001](ADR-001_runtime_state_console_scope_and_transport.md)** | The runtime dashboard is a **state console**, not a second timeline — and it rides the trace protocol's unused `SNAPSHOT` message rather than a transport of its own | 🟠 Proposed | 2026-08-27 |
| **[ADR-002](ADR-002_state_console_client_ui_framework.md)** | The state console's client is **PySide6 + QML** — chosen with the framework field deliberately re-opened, over Textual and a browser client | 🟠 Proposed | 2026-08-27 |
