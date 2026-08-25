# EPIC-006E — `sagittarius-doctor`, generated wiring document, docs

**Epic:** [EPIC-006 — Wiring & Readiness Diagnostics](../README.md)
**Status:** 🔵 Backlog
**Category:** Tooling / Developer Experience
**Priority:** P2
**Depends on:** EPIC-006C (needs a readiness milestone to inspect at)

---

## 🎯 Objective

Make the inspection reachable without writing code, and reviewable in a diff.

`EPIC-006B` produces a `WiringReport`; everything here is a rendering of it.

## Requirements

1. **`sagittarius-doctor`** — boots the application, prints the report, exits non-zero on
   errors. CI is where it earns most of its value: a mis-wiring becomes a red build rather than
   a runtime surprise.
2. **A generated wiring document**, in the shape `EVENT_CATALOG.md` already establishes:
   committed, diffable, and guarded by a test. An unintended change to the wiring then shows up
   in review, which is a different and often earlier signal than a failing check.
3. `.agents/context/` updated. Per `doc-code-sync.md` this is not optional.

## Constraint carried from `TASK-039`

The wheel guard now resolves every declared console script and asserts it is callable. This
entry point is covered by it from the moment it is declared — which is the reason `TASK-039` was
done ahead of this epic rather than alongside it.

`sagittarius-audit` is the cautionary tale: it shipped in `v2.1.0` and `v2.2.0` advertising a
command that had never run, in three independent ways at once.

## Open question

Does this justify a **second** console script alongside the one `EPIC-005` Milestone D will
re-add, or should there be a single `sagittarius` command with subcommands? Two scripts is the
smaller change now; one command with subcommands is the smaller surface later. Decide before
either ships, because the entry point is published metadata and consumers pin to it.
