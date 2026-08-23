# Module Coverage Ledger

**Owner subtask:** [EPIC-002A](incomplete/EPIC-002A_sample_app_scaffold.md) (extended by
EPIC-002B for `pyside_mvc`). **Gate, not a nice-to-have:** EPIC-002A cannot move to
`completed/` while any row below reads "TBD."

Why this file exists: prose claims of "honest module coverage" aren't verifiable — see
`ONBOARDING.md` §3's "not a promise, it's checked against a ledger." Every top-level
`sagittarius_engine/` package and every shipped extension gets exactly one row, resolved to
one of three states:

- **Used** — cite the file/line in `examples/student_management/` that proves it.
- **Skipped** — the domain-specific reason it has no genuine use here.
- **Gap** — the module doesn't do what the sample needs; cite the filed `TASK-XXX`
  (per `ONBOARDING.md` §6, a gap gets a task immediately, not just a description here).

This list is exhaustive — generated from `ls sagittarius_engine/` and
`ls sagittarius_engine/extensions/` on 2026-08-23. If a new top-level package or extension is
added to the engine after this table is filled in, add a row; don't let the table go stale
the way `.agents/context/` did.

## Top-level packages

| Package | Status | Evidence / Reason |
| :--- | :--- | :--- |
| `adapters/` | TBD | |
| `base/` | TBD | |
| `domain/` | TBD | |
| `exceptions.py` | TBD | |
| `infrastructure/` | TBD | |
| `interfaces/` | TBD | |
| `kernel/` | TBD | |
| `middleware/` | TBD | |
| `runtime/` | TBD | |
| `sdk/` | TBD | |
| `utils/` | TBD | |

## Extensions (`sagittarius_engine/extensions/`)

| Extension | Status | Evidence / Reason |
| :--- | :--- | :--- |
| `audit` | TBD | |
| `cqrs` | TBD | |
| `fsm` | TBD | |
| `health` | TBD | |
| `logger` | TBD | |
| `persistence` | TBD | |
| `pyside_mvc` | TBD | Owned by EPIC-002B — must resolve to **Used**, not Skipped. Two prior sample apps in this repo (`student_management`, `tools/audit_dashboard`) both skipped it in favor of plain `QtWidgets`; that precedent is exactly what this ledger exists to prevent repeating. |
| `thread_manager` | TBD | |
