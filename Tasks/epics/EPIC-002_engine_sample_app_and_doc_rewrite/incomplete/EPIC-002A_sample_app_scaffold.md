# EPIC-002A — Sample App Scaffold

**Epic:** [EPIC-002 — Engine Sample App & Doc Rewrite](../README.md)
**Status:** 🔵 Backlog
**Category:** Documentation / Developer Experience
**Priority:** P1
**Depends on:** nothing (first subtask)

---

## 🎯 Summary & Objectives

Delete-and-rebuild is done at the epic level (old `examples/student_management/` already
removed, see `ONBOARDING.md` §3, point 1). This subtask builds the replacement's skeleton: domain,
Clean Architecture layers, and engine-module registration — **without** the UI yet
(EPIC-002B's job). Getting the non-UI foundation right first means EPIC-002B builds a UI
against a stable app, not a moving one.

1. Rebuild `examples/student_management/` domain + application + infrastructure layers,
   following the same 4-layer shape `.agents/rules/architecture.md`'s "Clean Architecture
   Layers" section describes for a consuming app (entities/value objects pure; use cases as
   directories with `command.py`/`handler.py`; ports in `application/ports/` or equivalent).
2. Register the app's module(s) via `IExtension`, not `IModule` — the old sample's choice of
   the interface the engine's own code calls "legacy" is exactly what made it a bad reference.
3. Wire every engine module the domain can **honestly** justify: DI Container, Event Bus,
   Config, Logger at minimum (a real app needs all four). Persistence via the engine's
   `persistence` extension. Decide Thread Manager / CQRS / FSM / Audit on their merits — if
   the domain has no genuine use for one, **do not force it in**.
   **Fill in `MODULE_COVERAGE.md` (epic root) as you go — every top-level package and
   extension resolved to Used/Skipped/Gap, per `ONBOARDING.md` §3.** This subtask cannot move
   to `completed/` with an unresolved row. Don't defer the ledger to EPIC-002C.
4. A CLI entry point sufficient to exercise every use case without the GUI, so EPIC-002B's UI
   work has a working backend to point at from day one.
5. Tests collected by the engine's own `pytest` run (not a separate, easy-to-forget suite) —
   confirm collection with `pytest examples/student_management/ -q` from the repo root and
   verify it also shows up in a full-suite run.
6. **As each hard technical question here gets settled, write its design doc immediately** —
   see epic README's "Design docs" section. For this subtask that almost certainly means at
   least: `docs/bootstrap.md` (composition root, boot order), `docs/module_registration.md`
   (`IExtension` registration and dependency order), `docs/config_loading.md`. Each needs a
   Mermaid diagram. Do not defer these to EPIC-002C — write them while building, not after.

## 📐 Design Constraints

- No silent engine patches to route around a gap. If something needed doesn't exist or
  doesn't work as documented, verify it's a real gap (not a usage mistake), then **file a
  `TASK-XXX` immediately** per `ONBOARDING.md` §6 — don't just note it and move on.
- Match `.agents/rules/coding-style.md` and `.agents/rules/code-rule.md` as if this were
  production code — a sample with sloppy code teaches sloppy usage.

## 🧪 Verification & Test Coverage

- `pytest examples/student_management/ -q` passes.
- Every use case reachable and exercised from the CLI entry point.
- `MODULE_COVERAGE.md` has zero unresolved rows — this is a gate, not a nice-to-have.
- Any row marked "Gap" links a real, filed `TASK-XXX` — not a bare description.
