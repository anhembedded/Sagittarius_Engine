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
`scripts/` entirely. *(Postscript, EPIC-002D: `docs/` was itself deleted — all 53 files — in
commit `a338d42`, hours after this paragraph was written. The claim was true when made and
false by the end of the day. Left as written, because a doc going stale mid-epic is the
sharpest possible illustration of the problem this epic exists to fix.)* `modules.md` documents `IModule` as the module model while the engine's
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
| 3 | [`MODULE_COVERAGE.md`](MODULE_COVERAGE.md) | The ledger every subtask from A onward must keep current — check its state before assuming what's already covered |
| 4 | `.agents/rules/design-discipline.md` | Root-cause-first discipline; this epic's own findings must meet the same bar it sets for code |
| 5 | `.agents/rules/surprising-findings.md` | Every build-friction finding in EPIC-002B/C gets reported through this rule, not buried in a file nobody re-reads |
| 6 | The relevant subtask file (`incomplete/`) | Your actual work item |

Note: two files named `ONBOARDING.md` exist in this repo — this one (epic-specific) and
`.agents/ONBOARDING.md` (engine-wide, general routing). When something below says
"`.agents/ONBOARDING.md`" it means the other one; a bare "`ONBOARDING.md` §N" always means
this file.

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

   **"Honest, not forced" is not a promise — it's checked against a ledger.** User's
   challenge, 2026-08-23: *"có gì đảm bảo bạn sẽ dùng hết các module để demo không?"* (what
   guarantees you'll actually use the modules?). Fair — prose commitments don't survive
   contact with a real build. `MODULE_COVERAGE.md` (this epic's own directory) is an
   **exhaustive** table, one row per top-level `sagittarius_engine/` package and per
   extension, each row resolved to exactly one of: **Used** (with the file/line that proves
   it), **Skipped** (with the domain reason), or **Gap found** (with a task ID — see point 5
   below). EPIC-002A cannot move to `completed/` with an unresolved row. This is the same
   "exhaustive, not illustrative" principle `doc-code-sync.md` already applies to lists —
   an incomplete ledger is visibly incomplete; a paragraph claiming honesty is not.
4. **The UI is QML through `pyside_mvc`, not hand-rolled `QtWidgets` — and this is now
   checked, because prose already failed here once.** Both prior sample UIs in this repo —
   the deleted `student_management/presentation/ui/desktop_window.py` **and**
   `tools/audit_dashboard/presentation/main_window.py` — are plain `PySide6.QtWidgets`,
   built without touching `pyside_mvc` at all (confirmed 2026-08-23:
   `grep -rln pyside_mvc tools/ examples/` returned nothing). The engine has shipped a real UI
   framework and its own sample apps didn't use it. EPIC-002B's verification section
   (already written) requires a check that fails if the sample's screens are built from
   `QtWidgets` directly instead of `pyside_mvc`'s `Sagittarius/UI/` components loaded as
   `.qml` — do not weaken that check.
5. **The sample boots `pyside_mvc` as a real `IExtension`, not via `configure_app_qml()`.**
   [EPIC-001D](../EPIC-001_ui_engine_foundation/incomplete/EPIC-001D_runtime_slot_registry.md)
   §objective 5 was just decided (2026-08-23): the UI Engine becomes a real `IExtension`. This
   epic's sample app is the first consumer built against that decision, not against the old
   bare-function-call pattern. If the ordering constraint noted there (QApplication must
   exist before `pyside_mvc` boots) makes the standard `IExtension.boot(context)` path
   awkward, **that friction is exactly what EPIC-002B exists to surface** — record it, don't
   silently route around it.
6. **A genuine engine gap gets a task filed immediately, not a line in a report for later.**
   Sharpened 2026-08-23 (user: *"UI thiếu cơ chế thì tạo task hoàn thiện cơ chế đó luôn"* — if
   the UI mechanism is missing something, create the task to complete it right away),
   specifically because `pyside_mvc` is exactly the area most likely to have a real gap
   (it's mid-epic itself, see EPIC-001D). The distinction that still holds: **do not silently
   patch the engine inline** to route around a gap — but do not just describe the gap in
   `AUDIT_REPORT.md` and move on either. The moment a gap is confirmed real (not a usage
   mistake — verify first), file it as a proper `TASK-XXX` in this repo's own
   `Tasks/backlog/` (or a new epic subtask if it's large), immediately, in the same session.
   `AUDIT_REPORT.md` then cites that task ID rather than being the only record of the gap —
   a report nobody re-reads is not a substitute for a tracked, actionable task.
7. **Do not fix the engine while building the sample** by quietly routing around a gap. If
   something is missing, wrong, or ambiguous, name it and file the task per point 6 above.
   This epic's deliverable is the app + the ledger + the report + doc rewrite tasks — not
   opportunistic, unfiled engine patches picked up along the way.
8. **A design doc per hard technical topic, written the moment it's settled, not batched.**
   User's instruction 2026-08-23: whichever technical question EPIC-002A/B reaches (boot
   sequence, module registration, config loading, `pyside_mvc`'s `IExtension` ordering, …),
   generate that topic's design doc right then, with a Mermaid diagram, in
   `examples/student_management/docs/`. See the epic `README.md`'s "Design docs" section for
   the full convention. This is not optional polish — EPIC-002C consolidates these into
   `AUDIT_REPORT.md` rather than reconstructing them from memory, so a topic settled without
   its doc is a topic EPIC-002C will get wrong or have to re-investigate.
9. **The audit report and the doc rewrite are separate subtasks, deliberately sequenced.**
   Writing `AUDIT_REPORT.md` (evidence) before touching `.agents/context/*.md` (prose) is the
   whole point — it is the mechanism that makes this rewrite different from the one that
   rotted. Do not shortcut by rewriting docs directly from "what I already know about the
   engine" without the app existing first.
10. **Every practice settled in the sample gets spot-checked against `Sagittarius_Elite_Warrior`
    — as you go, not at the end.** User's instruction, 2026-08-23: *"trong quá trình tạo app
    mới, viết tới đâu, bạn check xem Elite Warrior có theo đúng practice không, cái nào sai thì
    tạo task bên Elite, sau này làm sau"* (as you write the new app, check whether Elite
    Warrior follows the same practice at each point; whatever's wrong gets a task filed on
    Elite's side, to be worked later). Concretely: when EPIC-002A/B settles how something is
    done — `IExtension` registration, config loading, `pyside_mvc` boot ordering, whatever —
    grep the app's real code for the equivalent. If it diverges, **file a `BOT-XXX` in
    `Sagittarius_Elite_Warrior/Tasks/backlog/`** (that repo's own numbering/format/bookkeeping
    rules — update its `ROADMAP.md` table and counts too, per its own `ONBOARDING.md` §6) —
    do not fix it there now, and do not write it into *this* repo's `Tasks/` board (§5 below —
    "Cross-repo boundary" — still holds for code changes; filing a task on Elite's board is
    the one thing this point explicitly carves out as in scope). First instance already done
    2026-08-23:
    [`BOT-117`](../../../../Sagittarius_Elite_Warrior/Tasks/completed/BOT-117_stale_pyside_mvc_paths_in_palette_docstring.md)
    — `palette.py`'s docstring still names the pre-reorg `QmlShared` paths.

## 4. Current state (check this is still accurate before trusting it)

As of 2026-08-23: **EPIC-002A and EPIC-002B are both done** (moved to `completed/`). What's
actually in place:

- `examples/student_management/` is a real, running app, backend and UI both: domain,
  application (7 use cases), infrastructure (real SQLite persistence via the engine's
  `persistence` extension), a `StudentManagementExtension` (`IExtension`, not `IModule`),
  `main.py` (an `argparse` CLI), and `gui.py` (a real QML UI — `RosterScreen.qml` composing
  `AppDataTable`/`BaseCard`/`AppModal`, `RosterView`/`RosterPresenter`/`RosterViewModel`, and
  `PySideMvcExtension` booting `pyside_mvc` as a real `IExtension`). 34 tests, all collected by
  the root suite. Verified by hand, not just by test: ran the real CLI across separate process
  invocations (persistence survives) and ran the real GUI with `QT_QPA_PLATFORM=offscreen`.
- `MODULE_COVERAGE.md` is filled in for **every** row, `pyside_mvc` included — resolved to
  Used, not Skipped, unlike the two prior sample apps in this repo.
- Five design docs exist in `examples/student_management/docs/`, each with a Mermaid diagram,
  written as their topic was settled: `bootstrap.md`, `module_registration.md`,
  `config_loading.md`, `persistence_and_transactions.md`, `ui_extension_lifecycle.md` — the
  last one also documents a real methodology correction (a filed engine task that turned out
  to be a false positive, retracted after `tail`-truncated command output was found to have
  hidden a passing test result — read it before trusting any "N warnings" claim made by
  piping test output through `tail` in this repo).
- **One real engine gap found and filed, not worked around invisibly:**
  [`TASK-019`](../../backlog/TASK-019_database_extension_expose_engine.md) —
  `DatabaseExtension` exposes no way to reach the raw SQLAlchemy `Engine` it builds
  internally, so a consumer has no sanctioned way to run schema creation. `EPIC-002A`'s own
  workaround is documented in `docs/persistence_and_transactions.md`.
- One cross-repo task is already filed as a first instance of §3 point 10's convention:
  [`BOT-117`](../../../../Sagittarius_Elite_Warrior/Tasks/completed/BOT-117_stale_pyside_mvc_paths_in_palette_docstring.md)
  in `Sagittarius_Elite_Warrior`.

- [`AUDIT_REPORT.md`](AUDIT_REPORT.md) (epic root) consolidates everything above, plus a
  **newly found** `context/api.md` error (discovered writing the report, not before) —
  `auto_discover` documented as `bool`, actually `str | None`; `IExtension` omitted from "Key
  Interfaces" entirely despite being what every real extension in this codebase implements.

**The next concrete action is EPIC-002D** — rewrite `.agents/context/*.md` from
`AUDIT_REPORT.md`, add the staleness-detection test, fix the 4 dangling references to the
deleted old example. Read `AUDIT_REPORT.md` in full before starting; it's the source of truth
for what needs to change and why, not this file's summary of it.

Stale references to the deleted *old* example still exist and need fixing as part of
EPIC-002D (not A/B — these are `.agents/`-side references, D's job):
- `readme.md:131` (root) — table row pointing at `examples/student_management/`
- `.agents/context/examples.md`, `.agents/context/modules.md` — both cite the old shape by name
- `.agents/skills/module_discover.md` — references it as a discovery example

## 5. Cross-repo boundary

This epic's **code and doc changes** are 100% engine-repo work (`Sagittarius_Engine`) — no
`sagittarius_engine/` source changes, no edits to `Sagittarius_Elite_Warrior`'s own code or
docs. The one deliberate exception is §3 point 10: **filing a task** (not fixing anything) on
Elite's own `Tasks/backlog/` when a practice check finds a real divergence — that is in scope,
already exercised once (`BOT-117`, filed 2026-08-23 for `palette.py`'s docstring still naming
the pre-reorg `pyside_mvc.QmlShared`/`QmlShared.state_tokens` paths). If this epic's work
seems to require an actual *code* change in Elite's repo, that is out of scope — flag it to
the user rather than making it.

## 6. If you get stuck or a decision genuinely isn't covered above

Say so explicitly rather than guessing and moving on. Incorrect assumptions are worse than
incomplete work — stated project-wide guidance, reinforced by this exact epic's origin story
(a docs directory that was wrong with total confidence for three weeks).
