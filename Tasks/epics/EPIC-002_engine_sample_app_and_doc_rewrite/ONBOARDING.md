# Onboarding — EPIC-002: Engine Sample App & Doc Rewrite

**Read this file first, before any other file in this epic directory.** It exists because an
AI session with no memory of prior conversations needs to reach the same starting point a
human would after being briefed — this document is that briefing.

---

## 1. What problem this solves, in one paragraph

`.agents/context/` (16 files, ~20 KB) was written once, in a single commit (`0bd461b`,
2026-08-02), and never touched again. In the 267 commits since, `sagittarius_engine/` gained
+7028/-430 lines and 9 top-level packages didn't exist yet at the time those files were
written. The result is not "a bit stale" — it is **actively wrong**: `repository.md` opens
with *"The `Sagittarius_ForkBoy` repository"* (wrong repo name), lists an extension
(`extensions/sqlalchemy`) that doesn't exist, and omits `docs/` (388 KB, 51 files) and
`scripts/` entirely. `modules.md` documents `IModule` as the module model while the engine's
own code calls it *"a legacy IModule"* (`kernel/extension_manager.py:22`) and never mentions
`IExtension` — the interface every shipped extension actually implements. Hand-written
summaries of a moving codebase rot; there is no mechanism that keeps them honest. Writing
*more* prose the same way would reproduce the exact failure this epic exists to fix.

**The fix is not "write better docs from memory."** It is: build something real that
exercises the engine end-to-end, let the ambiguities surface as concrete build friction
(not guesses), record that friction as evidence, and only then rewrite the docs — grounded
in what actually happened, not what the engine's authors assumed would happen.

## 2. Read in this order

| Order | File | Why |
| :---: | :--- | :--- |
| 1 | This file | Orientation — you are here |
| 2 | [`README.md`](README.md) (this epic's own) | Full context, subtask breakdown, scope |
| 3 | `.agents/rules/design-discipline.md` | Root-cause-first discipline; this epic's own findings must meet the same bar it sets for code |
| 4 | `.agents/rules/surprising-findings.md` | Every build-friction finding in EPIC-002B/C gets reported through this rule, not buried in a file nobody re-reads |
| 5 | The relevant subtask file (`incomplete/`) | Your actual work item |

## 3. Decisions already made — do not re-derive or relitigate these

1. **The old `examples/student_management/` is deleted, not migrated.** It was built against
   `IModule` (the interface the engine's own code now calls "legacy"), had zero contact with
   `pyside_mvc`, and was referenced by name in 4 now-inaccurate doc files. User's explicit
   instruction 2026-08-23: *"cai 'student_management' da rat loi thoi va ko theo dung y dinh
   cua toi. bo het, va xay lai. xoa no luon"* — scrap it, rebuild from zero. Recoverable from
   git history (`git log -- examples/student_management`) if anything from it is ever needed
   for reference; do not resurrect it as a starting point without asking.
2. **Domain stays "Student Management."** Not because the domain is special, but because it
   is already the engine's established example identity (`docs/`, prior `modules.md`,
   `module_discover.md` all reference it) — renaming the domain would be a second unrelated
   change bundled into this one. Reopen only if the rebuilt domain genuinely cannot exercise
   a module the audit needs to cover (see §4's coverage note).
3. **Module coverage is honest, not forced.** The reference idea this epic originated from
   said "use ALL of the engine's modules." Rejected as written: forcing modules the domain
   has no real reason to need (e.g. FSM, audit trail, on a student roster) produces fabricated
   integration patterns, and an audit of fabricated usage teaches nothing true. The rule
   instead: **use every module the domain can honestly justify; any module skipped must be
   named and justified in `AUDIT_REPORT.md`, not silently omitted.** Coverage is achieved
   through the report, not through code contorted to touch every package.
4. **The sample boots `pyside_mvc` as a real `IExtension`, not via `configure_app_qml()`.**
   [EPIC-001D](../EPIC-001_ui_engine_foundation/incomplete/EPIC-001D_runtime_slot_registry.md)
   §objective 5 was just decided (2026-08-23): the UI Engine becomes a real `IExtension`. This
   epic's sample app is the first consumer built against that decision, not against the old
   bare-function-call pattern. If the ordering constraint noted there (QApplication must
   exist before `pyside_mvc` boots) makes the standard `IExtension.boot(context)` path
   awkward, **that friction is exactly what EPIC-002B exists to surface** — record it, don't
   silently route around it.
5. **Do not fix the engine while building the sample.** If something is missing, wrong, or
   ambiguous, name it in `AUDIT_REPORT.md` with enough detail to act on later. This epic's
   deliverable is the app + the report + doc rewrite tasks — not opportunistic engine patches
   picked up along the way. An engine fix that turns out to be genuinely required to keep
   building is a `TASK-XXX` or new epic subtask on its own, flagged to the user first.
6. **The audit report and the doc rewrite are separate subtasks, deliberately sequenced.**
   Writing `AUDIT_REPORT.md` (evidence) before touching `.agents/context/*.md` (prose) is the
   whole point — it is the mechanism that makes this rewrite different from the one that
   rotted. Do not shortcut by rewriting docs directly from "what I already know about the
   engine" without the app existing first.

## 4. Current state (check this is still accurate before trusting it)

As of 2026-08-23: **nothing in this epic has started.** `examples/student_management/` is
deleted (staged for commit, not yet committed). `Tasks/epics/EPIC-002_.../` exists with this
file, `README.md`, and an empty `incomplete/`. No subtask files exist yet beyond what
`README.md` describes — check `ls incomplete/ completed/` before assuming subtask files are
present.

Stale references to the deleted example still exist and need fixing as part of EPIC-002A,
not left dangling:
- `readme.md:131` (root) — table row pointing at `examples/student_management/`
- `.agents/context/examples.md`, `.agents/context/modules.md` — both cite it by name
- `.agents/skills/module_discover.md` — references it as a discovery example

## 5. Cross-repo boundary

This epic is 100% engine-repo work (`Sagittarius_Engine`). Nothing here touches
`Sagittarius_Elite_Warrior`. Verified 2026-08-23: the app's own `palette.py` docstring still
references `pyside_mvc.QmlShared` and `QmlShared.state_tokens`, both stale paths from the
2026-08-23 `pyside_mvc` reorg (real paths now `Sagittarius/UI/` and `tokens/`). That is a
comment-only staleness in the *app* repo — out of scope here, worth flagging to the user
separately, not silently fixed from this epic.

## 6. If you get stuck or a decision genuinely isn't covered above

Say so explicitly rather than guessing and moving on. Incorrect assumptions are worse than
incomplete work — stated project-wide guidance, reinforced by this exact epic's origin story
(a docs directory that was wrong with total confidence for three weeks).
