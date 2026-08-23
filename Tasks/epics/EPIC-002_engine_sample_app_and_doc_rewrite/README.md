# EPIC-002 — Engine Sample App & Doc Rewrite

**Status:** ✅ Completed 2026-08-23 (4/4 subtasks done)
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
| `repository.md` / `modules.md` omit `docs/` and `scripts/` | `docs/` alone is 388 KB, 51 files — larger than all of `.agents/context/` combined and not routed to from `.agents/ONBOARDING.md` **— superseded: `docs/` was deleted entirely (53 files) in commit `a338d42`, later the same day this was written. Kept as written to preserve the record; see EPIC-002D's outcome notes.** |
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

## 📝 Design docs — one per hard technical topic, written when you hit it

Every real app has its own set of genuinely hard technical questions — how it boots, which
modules it registers and in what order, how it loads config, how its UI lifecycle ties into
the engine's, how persistence is wired. **The moment EPIC-002A/B settles one of these
questions, write it up as its own design doc — right then, not batched at the end of the
subtask.** User's instruction, 2026-08-23: *"làm tới vấn đề nào thì gen luôn design doc của
vấn đề đó, có mermaid diagram"* (whichever topic you reach, generate that topic's design doc
immediately, with a mermaid diagram).

- **Location:** `examples/student_management/docs/` — next to the app, not in this epic's own
  directory. The app is the permanent reference (see Objective above); a future reader opening
  it should find "how this boots" right there, not have to know EPIC-002 ever existed. (The
  deleted old sample already had this instinct — `docs/doc.mermaid`, `docs/gen.md` — this
  formalizes it as a per-topic convention instead of one grab-bag file.)
- **One file per topic**, named for the topic (`bootstrap.md`, `module_registration.md`,
  `config_loading.md`, `ui_extension_lifecycle.md`, …) — not one giant file covering
  everything, for the same reason `rules/` is split by topic instead of one mega-rule file.
- **Every file has a Mermaid diagram** — sequence diagram for a flow (boot order, request
  path), flowchart for a decision/branch, whichever fits the topic.
- **Written at the moment the topic is settled**, while the reasoning and any friction hit are
  still fresh — not reconstructed from memory during EPIC-002C. EPIC-002C's job becomes
  *consolidating* these into `AUDIT_REPORT.md`, not discovering them cold.
- Candidate topics already visible from scope: for EPIC-002A — composition root/bootstrap
  sequence, `IExtension` registration order, DI container wiring, event bus wiring, config
  loading; for EPIC-002B — `pyside_mvc` boot ordering as a real `IExtension` (the
  `QApplication`-must-exist-first constraint from EPIC-001D), token/theme wiring, screen
  composition. Not exhaustive — write one for any topic that turns out to be a real decision,
  skip topics that turned out trivial.

## 📐 Scope

- **In scope:** a real, running Student Management sample app (Clean Architecture, PySide6 +
  QML via `pyside_mvc`), built using nothing but the engine's public surface; a written audit
  of every ambiguity/gap/implicit assumption hit while building it; a rewrite of
  `.agents/context/*.md` grounded in that audit; a regression test that fails when a doc
  references a symbol or path that no longer resolves.
- **Out of scope:** modifying `sagittarius_engine/` itself to fix anything the audit finds —
  a real gap gets a `TASK-XXX` filed immediately instead (`ONBOARDING.md` §3 points 6–7), not
  a same-epic patch; modifying `Sagittarius_Elite_Warrior`'s own code or docs (filing a task
  on its board when a practice check finds a divergence **is** in scope — `ONBOARDING.md` §3
  point 10 — fixing it is not); rewriting `docs/` (that tree's fate is a separate decision, not
  this epic's — flag it, don't fold it in).

## 🗂️ Subtasks

| ID | Title | Status |
| :--- | :--- | :---: |
| **EPIC-002A** | Scaffold the sample app — domain, Clean Architecture layers, `IExtension`-based module registration, honest (not forced) engine-module coverage | ✅ Completed (2026-08-23) |
| **EPIC-002B** | Wire the full `pyside_mvc` widget kit into the sample's UI, booting it as a real `IExtension` per the EPIC-001D decision | ✅ Completed (2026-08-23) |
| **EPIC-002C** | Write `AUDIT_REPORT.md` from the build experience — every ambiguity, implicit assumption, and rough edge, with evidence, not impressions | ✅ Completed (2026-08-23) |
| **EPIC-002D** | Rewrite `.agents/context/*.md` from the audit; add a staleness-detection test; fix the 4 dangling references to the deleted old sample | ✅ Completed (2026-08-23) |

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
- [`MODULE_COVERAGE.md`](MODULE_COVERAGE.md) has zero rows left as "TBD" — every package and
  extension resolved to Used/Skipped/Gap, `pyside_mvc`'s row specifically resolved to Used.
- `examples/student_management/docs/` has one design doc per hard technical topic actually
  hit while building A/B, each with a Mermaid diagram, written at the time — not
  reconstructed afterward.
- A test exists that fails if a future doc references a symbol/path that doesn't resolve —
  so this rot cannot silently repeat.
