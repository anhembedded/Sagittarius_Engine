# EPIC-002A — Sample App Scaffold

**Epic:** [EPIC-002 — Engine Sample App & Doc Rewrite](../README.md)
**Status:** 🔵 Backlog
**Category:** Documentation / Developer Experience
**Priority:** P1
**Depends on:** nothing (first subtask)

---

## 🎯 Summary & Objectives

Delete-and-rebuild is done at the epic level (old `examples/student_management/` already
removed, see `ONBOARDING.md` §3.1). This subtask builds the replacement's skeleton: domain,
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
   the domain has no genuine use for one, **do not force it in**; write down why it was
   skipped for EPIC-002C to fold into the audit report.
4. A CLI entry point sufficient to exercise every use case without the GUI, so EPIC-002B's UI
   work has a working backend to point at from day one.
5. Tests collected by the engine's own `pytest` run (not a separate, easy-to-forget suite) —
   confirm collection with `pytest examples/student_management/ -q` from the repo root and
   verify it also shows up in a full-suite run.

## 📐 Design Constraints

- No engine source changes. If something needed for a correct implementation doesn't exist or
  doesn't work as documented, that is a finding for `AUDIT_REPORT.md` (EPIC-002C), not a
  same-session engine patch — see `ONBOARDING.md` §3.5.
- Match `.agents/rules/coding-style.md` and `.agents/rules/code-rule.md` as if this were
  production code — a sample with sloppy code teaches sloppy usage.

## 🧪 Verification & Test Coverage

- `pytest examples/student_management/ -q` passes.
- Every use case reachable and exercised from the CLI entry point.
- A short note (can live in this file's own "Notes" section once done) listing which engine
  modules were used, which were deliberately skipped, and why — EPIC-002C consumes this
  directly rather than re-deriving it.
