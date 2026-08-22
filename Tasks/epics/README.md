# Epics — Sagittarius Engine

Convention adopted 2026-08-22, ported from `Sagittarius_Elite_Warrior`'s
`Tasks/epics/` convention: a multi-task program gets **its own directory**, not a single
flat file in `Tasks/backlog/`. A program with several subtasks and several rounds of status
updates makes both a flat file and the main Kanban table hard to read — same reasoning that
already justifies keeping `Tasks/issue-report/` separate from `Tasks/README.md`.

## Layout

```text
Tasks/epics/
├── README.md                          # This file
└── EPIC-XXX_short_slug/
    ├── README.md                      # Epic overview: objective, context, subtask table
    ├── incomplete/                    # Subtasks NOT yet done — new subtasks always start here
    │   └── EPIC-XXXA_name.md
    └── completed/                     # Subtasks done, moved from incomplete/
        └── EPIC-XXXB_name.md
```

- **Epic ID**: `EPIC-XXX` — its own incrementing pool, independent of `TASK-XXX`. The next
  epic takes the highest existing number in `Tasks/epics/` + 1.
- **Subtask ID**: `EPIC-XXX` + letter (`EPIC-001A`, `EPIC-001B`, …), self-contained within
  its own epic directory — no separate registration needed elsewhere.
- **When a subtask finishes**: move the file `incomplete/` → `completed/`, update its
  `Status`, update the corresponding row in the epic's own `README.md`.
- **`Tasks/README.md` keeps only a one-line link** to the epic's `README.md` — no content is
  duplicated there. Open the epic file directly for detail.
- Plain `TASK-XXX` tasks in `Tasks/backlog/`/`Tasks/completed/` are **not** retroactively
  moved into this structure — this convention applies to new multi-task programs going
  forward.

## Epics in progress

| ID | Name | Status |
| :--- | :--- | :---: |
| **[EPIC-001](EPIC-001_ui_engine_foundation/README.md)** ([onboarding](EPIC-001_ui_engine_foundation/ONBOARDING.md)) | UI Engine Foundation — tokens, widget kit, composition runtime for `pyside_mvc` | 🟡 In Progress (3/4 subtasks done) |
