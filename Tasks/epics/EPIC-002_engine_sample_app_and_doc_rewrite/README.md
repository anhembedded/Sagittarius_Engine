# EPIC-002 — Engine Sample App & Doc Rewrite

**Status:** 🟡 In Progress (0/4 subtasks done)
**Category:** Documentation / Developer Experience
**Priority:** P1 — `.agents/context/` is actively misleading every AI session that loads it
**Depends on:** [EPIC-001](../EPIC-001_ui_engine_foundation/README.md) (needs a stable
`pyside_mvc` public surface and its EPIC-001D `IExtension` decision to build against)

**Start here:** [`ONBOARDING.md`](ONBOARDING.md) — read it before this file's subtask table.

---

## 🎯 Objective

Replace `.agents/context/`'s hand-written, unmaintained snapshot of the engine (16 files,
last touched 2026-08-02, now measurably wrong — see Evidence) with documentation grounded in
a real, running application that exercises the engine end-to-end, plus a mechanism that keeps
it from rotting silently again.

**The sample app is a first-class, permanent deliverable — not scaffolding thrown away after
the audit.** Its purpose is to stand as a living reference a future AI session (or human) can
read and run to learn correct engine usage directly, the same way `ui-architecture.md`'s
worked examples anchor UI decisions today. `AUDIT_REPORT.md` and the doc rewrite are downstream
of it, but the app itself is what future sessions should point to first — it must stay in
the repo, stay passing, and stay current the same way the rest of the engine's tests do.

## 📊 Evidence (measured 2026-08-23, not assumed)

| Claim in current docs | Reality |
| :--- | :--- |
| `repository.md` opening line: *"The `Sagittarius_ForkBoy` repository"* | Wrong repo name |
| `repository.md` lists `extensions/sqlalchemy` | Does not exist; real package is `persistence` |
| `repository.md` / `modules.md` omit `docs/` and `scripts/` | `docs/` alone is 388 KB, 51 files — larger than all of `.agents/context/` combined and not routed to from `.agents/ONBOARDING.md` |
| `modules.md` documents `IModule` as the module model | The engine's own code calls it *"a legacy `IModule`"* (`kernel/extension_manager.py:22`); `IExtension` (8 real implementers) is not mentioned at all |
| `.agents/context/*.md` — 16 files | All from **one commit**, `0bd461b`, 2026-08-02; 267 commits and `+7028/-430` lines have landed in `sagittarius_engine/` since, adding 9 top-level packages |
| `interfaces/i_engine_context.py:30` docstring names `AppRunner` | No such class exists anywhere in the package (confirmed the real orchestrator, `ApplicationRunner`, takes ports, never a context) |

This is not "a bit outdated" — it is wrong in ways that would send an AI session down the
wrong path with full confidence, which is exactly the failure mode `.agents/rules/
surprising-findings.md` exists to catch when it happens live. The difference here is it has
been sitting wrong for three weeks with nobody noticing, because nothing forces `.agents/
context/` to track the code.

## 🧭 Why "build an app first" instead of "rewrite the prose"

Rewriting `.agents/context/*.md` directly, from what this session currently knows about the
engine, would produce a document exactly as failure-prone as the one it replaces: correct
today, silently wrong the next time the engine moves, with nothing to catch the drift.
`ui-architecture.md`, by contrast, has stayed accurate — because it is backed by static
guards (anti-literal-colour, anti-raw-primitive, gallery-coverage) that fail CI the moment
the rule and the code disagree. This epic applies the same principle to the rest of the
engine's documentation: **build something real, let ambiguity show up as build friction, and
only write the doc once the friction is on record — then add a guard that keeps it honest.**

## 📐 Scope

- **In scope:** a real, running Student Management sample app (Clean Architecture, PySide6 +
  QML via `pyside_mvc`), built using nothing but the engine's public surface; a written audit
  of every ambiguity/gap/implicit assumption hit while building it; a rewrite of
  `.agents/context/*.md` grounded in that audit; a regression test that fails when a doc
  references a symbol or path that no longer resolves.
- **Out of scope:** modifying `sagittarius_engine/` itself to fix anything the audit finds
  (name it in the report instead — see `ONBOARDING.md` §3.5); touching
  `Sagittarius_Elite_Warrior`; rewriting `docs/` (that tree's fate is a separate decision, not
  this epic's — flag it, don't fold it in).

## 🗂️ Subtasks

| ID | Title | Status |
| :--- | :--- | :---: |
| **EPIC-002A** | Scaffold the sample app — domain, Clean Architecture layers, `IExtension`-based module registration, honest (not forced) engine-module coverage | 🔵 Backlog |
| **EPIC-002B** | Wire the full `pyside_mvc` widget kit into the sample's UI, booting it as a real `IExtension` per the EPIC-001D decision | 🔵 Backlog |
| **EPIC-002C** | Write `AUDIT_REPORT.md` from the build experience — every ambiguity, implicit assumption, and rough edge, with evidence, not impressions | 🔵 Backlog |
| **EPIC-002D** | Rewrite `.agents/context/*.md` from the audit; add a staleness-detection test; fix the 4 dangling references to the deleted old sample | 🔵 Backlog |

Sequencing is strictly `A → B → C → D` — each subtask's file lives in `incomplete/` until
done, then moves to `completed/` with its `Status:` line updated, per this repo's
`epics/README.md` convention.

## ✅ Definition of Done (epic-level)

- The sample app runs (`python -m examples.student_management` or equivalent), has passing
  tests, and is picked up by the engine's own test suite — not a parallel, uncollected one.
- `AUDIT_REPORT.md` exists, is evidence-based (every finding traceable to a file/line/command,
  per `.agents/rules/surprising-findings.md`'s standard), and each finding maps to either a
  doc fix (EPIC-002D) or an explicitly out-of-scope engine issue named for later.
- `.agents/context/*.md` no longer contains a claim this epic's own audit disproved.
- A test exists that fails if a future doc references a symbol/path that doesn't resolve —
  so this rot cannot silently repeat.
