# Onboarding — Sagittarius Engine

Read this before touching anything else. It replaces `PLAYBOOK.md` and `manifest.yml`
(removed 2026-08-23) — both were hand-maintained lists that drifted from the files they
claimed to describe (see "A known trap" below). This file routes; it does not duplicate.

---

## 1. What this repo is

Sagittarius Engine is a **library with consumers**, not an application. A shortcut taken here
ships, gets imported, and becomes permanent debt inside someone else's codebase — see
`rules/design-discipline.md`. The reference consumer is `Sagittarius_Elite_Warrior`, a
separate repo, nested on disk but not submodule-linked — **never write that repo's tasks into
this repo's `Tasks/` board or vice versa**, and never assume a path from one repo exists in
the other (found and fixed 2026-08-23: six rule files here told an AI session to run
`Sagittarius_Elite_Warrior\scripts\ci-local.ps1` — the *other* repo's script, which does not
exist in this one).

Python floor is **3.12** (`requires-python = ">=3.12"` in `pyproject.toml`, lowered back from
`>=3.14` on 2026-08-25). It was raised to `>=3.14` on 2026-08-23 because CI's matrix only ever
tested `3.14-dev` — see `Tasks/completed/TASK-023_ci_matrix_hides_312_313_breakage.md` for why a
declared-but-untested floor is exactly the kind of claim this repo does not make. Lowering it
back to 3.12 moved the CI matrix (`test` and `import-guard` jobs in `.github/workflows/ci.yml`)
to `3.12` in the same change, per `.agents/rules/release.md` §3, and the suite — including
`tests/test_all_modules_importable.py::test_annotations_resolve_on_public_interfaces`, the guard
against the `ITaskHandle`-shaped eager-annotation bug that motivated the 3.14 floor in the first
place — was verified green on a real Python 3.12 interpreter before the floor moved. Do not
write code that needs to run on an older Python; there is no fallback path.

## 1a. The completion gate — run this before calling anything done

`scripts/ci-local.ps1` is the actual, authoritative local CI gate — 5 steps: ruff lint, ruff
format check, mypy, pytest+coverage, architecture-boundary tests. (Moved from `pre_commit.ps1`
at the repo root 2026-08-23, `TASK-030`, rebuilt on `Sagittarius_Elite_Warrior/scripts/
ci-local.ps1`'s pattern — the "ci-local.ps1" name and `scripts/` location are now the same in
both repos, deliberately.) The old version existed on disk and was not run for four consecutive
commits before the user directly caught the omission — piecemeal `pytest`/`ruff`/`mypy` on
touched files, even all green, is not evidence the repo passes its own gate; it found 338 lint
errors across the whole tree that no touched-files check would have seen.

The rebuilt script closes two gaps the old one had. It captures every step's full output to
`logs/ci-local-<timestamp>.log` (+ a `logs/ci-local-latest.log` pointer), which is what makes
`context/testing.md`'s documented `tail -N` truncation trap actually unreachable instead of
just warned about. And it runs every step regardless of earlier failures, reporting all of them
together — the old version stopped at the first red step, which is why finding tonight's lint
and mypy problems took two runs instead of one.

Run it:

```bash
pwsh ./scripts/ci-local.ps1
```

If you set up the repo with a `.venv` per `rules/install-rule.md`, put it on `PATH` first so its
pinned tools are the ones found:

```bash
export PATH="$PWD/.venv/bin:$PATH"   # Windows: $PWD/.venv/Scripts
```

**No `.venv` is not a broken setup** (verified 2026-08-23 — this checkout genuinely has none;
`ruff`/`mypy` were installed globally instead). `scripts/ci-local.ps1` itself checks for one,
warns if absent, and falls back to whatever `ruff`/`mypy`/`pytest` resolve to on `PATH` — the
export line above is an optional accelerant for the documented `.venv` workflow, not a
requirement the script depends on.

**Always read the printed `===CI_LOCAL_RESULT===` block, and open `LOG_FILE` before reporting
status — never judge from scrollback alone**, per the block's own printed instruction. Do not
trust a hardcoded pass/fail summary here either — this exact note has already gone stale once
(claimed pins this file no longer matches, once the pins were bumped in `TASK-021`). Run the
gate and read its own output; check `requirements-dev.txt` for the current pins if a local/CI
mismatch is suspected (`scripts/ci-local.ps1` now checks this for you automatically, per
`TASK-021` req. 5).

## 2. Repository layout

```
.agents/
    AGENTS.md       Entry point stub — points here, nothing else
    ONBOARDING.md    This file
    context/         Project knowledge — what exists, how it's structured
    rules/           Engineering policy — what you must/must not do
    skills/          Task workflows
    prompts/         Optional prompt templates
    workflows/       Long-form process write-ups
    anti-patterns/   Documented failure modes to avoid
sagittarius_engine/  The package itself — 11 top-level sub-packages, see rules/architecture.md
examples/            Sample apps — currently just student_management/ (rebuilt 2026-08-23)
tests/               Engine's own test suite
tools/               Standalone utilities on top of the engine (widget_showcase/)
scripts/             Developer utility scripts, not part of the installable package
Tasks/               Kanban board — README.md is the index, epics/ holds multi-task programs
                     from here; its relationship to .agents/context/ is an open question,
                     tracked under EPIC-002, not yet resolved as of 2026-08-23
```

## 3. Execution order

1. Understand the request.
2. Load the context you actually need (§4) — not the whole directory.
3. Apply relevant rules (§5) — always-on ones apply regardless of what you loaded.
4. Pick one primary skill if the task matches one (§6).
5. Execute.
6. Validate: correct context used, rules followed, tests/docs updated if the change touched
   either, no architecture violation introduced.

Never invent an API, config key, business rule, or file location you haven't verified exists.
Incorrect assumptions cost more than incomplete work — search the repo (implementations,
tests, docs, examples, CI config) before asking the user, and ask rather than guess when the
search comes up empty.

## 4. Context routing (`.agents/context/`)

Load only what the task needs.

**History, and why this directory is now trustworthy but not infallible:** the original 16
files here were written in a single commit, 2026-08-02, and never touched again while the
engine gained 9 top-level packages and +7000 lines. A 2026-08-23 audit found `repository.md`
naming the wrong repo and citing a nonexistent extension, `modules.md` documenting an
interface the engine's own code calls "legacy," `api.md` giving `App.boot()`'s parameter the
wrong type, and `readme.md` listing four example directories that never existed.
**[EPIC-002](../Tasks/epics/EPIC-002_engine_sample_app_and_doc_rewrite/README.md)** rewrote
every file in this directory against a real, running sample app
(`examples/student_management/`) rather than from memory — see that epic's `AUDIT_REPORT.md`
for the full finding-by-finding account.

Two things now guard it: `rules/doc-code-sync.md` (always-on — a code change must update its
docs in the same change) and `tests/test_agents_docs_resolve.py`, which fails CI when a
backtick-quoted class, module, or path in `context/` stops resolving against the real tree.
That test catches *structural* rot only; a claim that is wrong but well-formed still needs a
reader. `grep`/`ls` before acting on anything load-bearing.

Always load: `project.md`, `repository.md`.

| Task | Also load |
|---|---|
| Feature development | `architectures/architecture.md`, `modules.md` |
| Bug fix | `runtime.md`, `testing.md`, `troubleshooting.md` |
| Refactoring | `architectures/architecture.md` |
| Performance | `runtime.md` |
| API | `api.md` |
| Configuration | `configuration.md` |
| Build | `build.md`, `lint.md` |
| Adding/upgrading a dependency | `dependencies.md` |
| Writing a new example, or learning the engine by reading one | `examples.md` |
| Anything touching events, an event bus, or a presenter's subscriptions | `events.md` |
| Tracing, `ctx.trace`, `sagittarius-trace`, or exporting to Perfetto/OpenTelemetry | `tracing.md` |
| Unfamiliar term in a rule or task file | `glossary.md` |

Documentation and Deployment have no `context/` entry — both were pure duplicates of
`rules/documentation.md` / `rules/deployment.md` (2026-08-23 merge, EPIC-002D) and are now
covered entirely by the rule files; load those instead (see §5's rule routing table).

## 5. Rule application (`.agents/rules/`)

**Source of truth is each file's own frontmatter — do not hand-maintain a second list of
"which rules always apply."** That second list is exactly what `PLAYBOOK.md` was, and by
2026-08-23 it had drifted from the files it described in both directions: it hardcoded
`architecture.md` and `coding-style.md` as always-on when their own frontmatter says
`model_decision`, while `code-rule.md` and `install-rule.md` self-declare `trigger: always_on`
and weren't listed anywhere. Check the file, not a summary of the file.

- `trigger: always_on` → applies to everything, no exception. Currently: `code-rule.md`,
  `design-discipline.md`, `doc-code-sync.md`, `install-rule.md`, `surprising-findings.md`.
- `trigger: model_decision` → load per its own `description:` field, or by task type:

| Task | Rule |
|---|---|
| Any code change | `architecture.md`, `coding-style.md` |
| Testing | `testing.md` |
| Documentation | `documentation.md` |
| Commit | `commit-rule.md` |
| Cutting a release (version bump, tag, changelog) | `release.md` |
| Deployment | `deployment.md` |
| Complex multi-phase task | `task-tracking.md` |
| UI / QML (`pyside_mvc`) | `ui-architecture.md` |
| Generating/refactoring a module | `module-implement-rule.md` |

Rules are mandatory once loaded; never silently violate one — if a rule and the right fix
disagree, that's a rule-file change to propose, not a rule to route around
(`design-discipline.md` §2).

**Known duplication.** Two of the three cases listed here were resolved by
[EPIC-002D](../Tasks/epics/EPIC-002_engine_sample_app_and_doc_rewrite/completed/EPIC-002D_doc_rewrite_and_staleness_guard.md)
(2026-08-23):

- ✅ `context/testing.md` vs `rules/testing.md` disagreeing on the test layout — `rules/testing.md`
  prescribed `tests/sanity/`, `tests/unit/`, `tests/integration/`, none of which exist. Both now
  describe the real, package-mirroring layout.
- ✅ `context/deployment.md` (real content) vs `rules/deployment.md` (3-line stub) — merged into
  the rule file; the context file is deleted.
- ⬜ **Still open:** `code-rule.md` and `coding-style.md` overlap substantially, both restating
  all five SOLID principles. Not consolidated. When they disagree, prefer the file with the more
  specific, example-grounded claim.

General principle when any two docs conflict: prefer the one with real, verifiable content, and
fix the other in the same change rather than working around it (`rules/doc-code-sync.md`).

## 6. Skill routing (`.agents/skills/`)

| Request | Primary skill |
|---|---|
| Work a tracked task end to end | `process_a_task.md` |
| Locate/understand a module before changing it | `module_discover.md` |

One primary skill per task; run secondary skills after, not interleaved.

## 7. Task board (`Tasks/`)

`Tasks/README.md` is the Kanban index. Multi-task programs get their own directory under
`Tasks/epics/EPIC-XXX_slug/` (convention in `Tasks/epics/README.md`) — read that epic's own
`ONBOARDING.md` before its `README.md` if one exists; it carries decisions already made that
a fresh session shouldn't re-derive. See `rules/task-tracking.md` for the full lifecycle.

**Defects go on a separate board**: [`Tasks/bug_report/README.md`](../Tasks/bug_report/README.md)
(`BUG-XXX`, `incomplete/` → `completed/`), created 2026-08-23 and mirroring the app repo's
convention so the same habit works in both. The split exists because the task board only ever
shows a bug *after* it's fixed — an open bug had nowhere to be listed. Rule of thumb: **BUG** =
something is wrong, or states something untrue about the code; **TASK** = something is missing
or should change. Check that board too before assuming the engine is clean — do not trust this
count, it drifts; read `Tasks/bug_report/README.md`'s own Overview table for the current number.

## 8. Two `.agents/` trees — don't read the wrong one

`Sagittarius_Engine` (this repo) and `Sagittarius_Elite_Warrior` (the app that consumes it)
each have their own `.agents/`, nested on disk but **two fully independent git repos** —
no submodule link. Content differs and serves two different projects; mixing them up is the
most dangerous confusion for a new session.

| | This repo (`Sagittarius_Engine`) | The app (`Sagittarius_Elite_Warrior`) |
| :--- | :--- | :--- |
| Serves | the `sagittarius_engine/` framework | the Binance trading bot |
| Task board | `Tasks/README.md` (Kanban, `TASK-XXX`/`EPIC-XXX`) | `Tasks/ROADMAP.md` (`BOT-XXX`/`BUG-XXX`/`EPIC-XXX`) |
| Entry point | `AGENTS.md` + `ONBOARDING.md` (this file) | `ONBOARDING.md` + `AGENTS.md` (same pattern, separate content) |
| Always-on rule budget | 5 files, ~350 lines (`code-rule.md`, `design-discipline.md`, `doc-code-sync.md`, `install-rule.md`, `surprising-findings.md`) | 8 of 9 files, ~1420 lines — noticeably heavier; see `doc-code-sync.md`'s "Don't over-mark always_on" for why this repo deliberately doesn't match that |
| Remote | separate | separate |

When touching the app's code, its own rules take precedence — this repo's rules apply only
when you're actually changing framework code, and that is always a separate commit/push, no
sync step between the two.

## 9. If something genuinely isn't covered here

Say so and ask, rather than guessing and proceeding. This has been the stated standing
preference throughout this repo's history, reinforced by the exact failure this onboarding
rewrite responds to: a doc that was confidently wrong for three weeks because nothing forced
anyone to check it.

## 10. Picking up work in progress — read this before you start

### 10.1 First three commands, every time

```bash
git -C . status                                   # this repo
git -C ../Sagittarius_Elite_Warrior status        # the consuming app, if it is on this disk
cat ../Sagittarius_Elite_Warrior/Tasks/epics/README.md
```

**Work here is routinely left uncommitted between sessions** — as of 2026-08-25 both repos had
substantial finished, verified, *uncommitted* work in the tree, because this project's standing
rule is that the agent does not commit unless the user asks (`code-rule.md` §9, and Elite's
`commit-rule.md`). So `git status` is not a formality: an empty-looking board plus a dirty tree
means the work exists and simply is not recorded yet. Read the diff before assuming a task is
untouched.

### 10.2 The authoritative lists — and why there is no snapshot of them here

Everything genuinely open lives on the boards. Read them directly:

- [`Tasks/README.md`](../Tasks/README.md) — this repo's backlog and epics.
- [`Tasks/bug_report/README.md`](../Tasks/bug_report/README.md) — this repo's open bugs.
- `../Sagittarius_Elite_Warrior/Tasks/epics/README.md` — the app's epics, which is where most
  cross-repo programs are driven from.

This section used to carry a list of task IDs and went stale twice (it once showed two closed
tasks as open). It is not exempt from that just because it is in the onboarding file. **If you
are about to copy an ID out of a document into your plan, stop and open the board instead.**

### 10.3 Two cross-repo programs are in flight, driven from the app repo

Both are planned and specified in `Sagittarius_Elite_Warrior/Tasks/epics/`, and both contain
sub-tasks that are implemented **in this repo**. That is normal and intentional: the app's epic
owns the *why* and the sequencing; the engine change is committed here, separately
(§8 — two repos, two commits, no sync step).

| Epic (in the app repo) | What it is | Engine's part |
| :--- | :--- | :--- |
| `EPIC-007_chuan_hoa_card_dung_chung` | Standardising the app's duplicated card widgets onto `pyside_mvc.widgets` | `007A`–`007C`: extend the widget guards to `QWidget`, add the `ConfirmOverlay`/`PickerOverlay` that `BUG-004` reports as missing, add six shared surface shapes and three leaf controls |
| `EPIC-008_chuan_hoa_luong_event` | Standardising the event flow | `008A`–`008E` are engine work; `008F`–`008H` are app work |

**Read the epic's `README.md` and its `DECISION_*.md` ADR before doing any of its sub-tasks.**
The ADR carries decisions already argued out with the user — including several that reverse an
earlier plan — and re-deriving them wastes a session and usually lands somewhere different.

### 10.4 Mechanisms added recently that you are expected to use, not re-invent

Each of these exists because the same thing had been hand-rolled in several places. Using
something else re-creates the defect they closed.

| Need | Use | Documented in |
| :--- | :--- | :--- |
| Define an event | subclass `BaseEvent` | [`context/events.md`](context/events.md) §1 |
| List/catalog events | `EventRegistry` + `scripts/generate_event_catalog.py` | `context/events.md` §3 |
| Report a handler that raised | `report_handler_failure` | `context/events.md` §4 |
| A logger when none was injected | `resolve_bus_logger` / `resolve_logger` — **not** `NullLogger` | `context/events.md` §4 |
| Subscribe from a presenter | `BasePresenter.subscribe()` (routes through `QtEventBridge`) | `context/events.md` §5 |
| Presenter cleanup | override `shutdown()`, never `dispose()` | `context/events.md` §6 |

### 10.5 Standing user preferences that outrank convenience

These have been stated directly by the user and apply to every task here, not just the epic that
prompted them:

1. **Fix the mechanism, not the symptom. No hotfixes.** If the same defect exists in four
   places, fixing the one it was reported against is not acceptable — that is the situation
   `EPIC-008C` was in, and the fix was a shared module every bus calls. A change that makes a
   symptom vanish without explaining *why* is not a fix (`rules/design-discipline.md`).
2. **One abstraction per file, and as many files as that produces.** Putting things that are
   not the same abstraction into one module is treated as an anti-pattern. The counterweight is
   `code-rule.md`'s Single-Scope Cohesion: definitions describing *one lifecycle* stay together
   (an FSM's enums plus its transition matrix; a style-role enum plus the function that renders
   it). Same abstraction across several symbols → one file; different abstractions → separate
   files.
3. **Show a design before implementing a restructure.** For anything beyond a contained change,
   produce PlantUML class + component diagrams (as-is and to-be, marking what is shared versus
   what is screen-specific) and get them reviewed before writing task files or code.
4. **Do not commit or push unless asked.**

### 10.6 One trap that will waste your time if nobody warns you

The full gate can report failures that have nothing to do with your change:

- **`BUG-006`** — two "no QML runtime warnings" tests assert on Qt's *entire* message stream, so
  a once-per-process platform warning (`QFontDatabase: Cannot find font directory ...`) lands on
  whichever one collection order reaches first. **Adding an unrelated test file changes which
  test fails, and can change the failure count.** It is reproducible in both directions, not
  random.
- `tests/test_agents_docs_resolve.py` fails intermittently **only** when the suite is launched
  through `scripts/ci-local.ps1` under PowerShell: that test shells out to `grep`, which is not
  on `PATH` in that context. Same class of problem as `TASK-028`.

**Before attributing any failure to your change, A/B it**: `git stash push -u`, run, `git stash
pop`, run. That takes two minutes and is the difference between a real regression and an hour
chasing the environment. Running `pytest` directly with the gate's own arguments (see
`scripts/ci-local.ps1`'s pytest invocation) is more stable than the PowerShell wrapper and is a
reasonable cross-check — but the gate is still what decides "done" (§1a).
