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

Python floor is **3.14** (`requires-python = ">=3.14"` in `pyproject.toml`, raised from `>=3.12`
on 2026-08-23 to match what CI actually tests — see
`Tasks/backlog/TASK-023_ci_matrix_hides_312_313_breakage.md` for why a declared-but-untested
floor is exactly the kind of claim this repo no longer makes). Do not
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
export PATH="$PWD/.venv/bin:$PATH"
pwsh ./scripts/ci-local.ps1
```

**Always read the printed `===CI_LOCAL_RESULT===` block, and open `LOG_FILE` before reporting
status — never judge from scrollback alone**, per the block's own printed instruction.

**Known current state (2026-08-23):** all 5 steps pass — `RESULT: PASS`, `FAILED_STEPS: none`.
mypy's pre-existing debt (28 → 27 → 23 → 0, see `TASK-032`) is fully cleared as of this date. If
the gate is red for you, it is either a real regression from whatever you just touched, or your
local toolchain drifting from CI's pinned versions (`TASK-021` — local `ruff`/`mypy` are not
currently pinned to CI's `0.15.20`/`2.1.0`) — not leftover baseline debt. There is none left to
blame.

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
tools/               Standalone utilities on top of the engine (audit_dashboard/)
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
or should change. Check that board too before assuming the engine is clean — 3 open as of
2026-08-23.

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

## 10. Where things stand (2026-08-23, commit `df51202`)

For a fresh session picking this up: EPIC-002 is fully complete (4/4). The engine audit that
followed it found real bugs, not just doc drift — a full account is in each commit message
(`git log --oneline -8`), summarized here so it doesn't need re-deriving:

- Fixed: a missing import (`ITaskHandle`) that made `app.boot()` raise on Python ≤3.13 while
  staying invisible on 3.14's deferred annotations; a dead unimportable package
  (`infrastructure/persistence/`); the scaffolding feature (`tools/scaffold.py`,
  `sagittarius_engine/sdk/`) removed entirely — unused, and broken in both its documented
  forms; the `ruff.toml`/`pyproject.toml` config shadow (§1a's gate now actually lints).
- Added two permanent guards: `tests/test_agents_docs_resolve.py` (`.agents/context/` claims
  must resolve against the real tree) and `tests/test_all_modules_importable.py` (every module
  must import, and public interface annotations must resolve — this is what would have caught
  `ITaskHandle` on day one).
- `TASK-026` (validation middleware silently skipping on unresolvable hints) and `TASK-017`
  (7-item production-readiness checklist — 2 of the 7 items turned out already-fixed/wrong-on-
  inspection when re-verified against the tree, not blindly executed) are both **done**,
  released as `2.1.0`. `TASK-032` (the mypy baseline) is also done — see §1a. Do not re-derive
  or re-plan any of these three; check `git log`/`CHANGELOG.md` before assuming something
  still-listed elsewhere is still open.
- **Everything genuinely still open** is on the two boards — read them directly rather than
  trusting a snapshot list here, since this paragraph is exactly the kind of thing that goes
  stale:
  - [`Tasks/README.md`](../Tasks/README.md)'s backlog table — as of 2026-08-23: `TASK-019`
    (`DatabaseExtension` can't reach the raw `Engine`, P2), `TASK-020`/`TASK-021`/`TASK-023`
    (CI/build tooling gaps, P2-P3), `TASK-022` (missing `LICENSE`, blocked on the owner for a
    copyright name/year — deliberately not guessed), `TASK-027` (no `py.typed`, P2),
    `TASK-028`/`TASK-031` (small, P3).
  - [`Tasks/bug_report/README.md`](../Tasks/bug_report/README.md) — 2 open: `BUG-001` (a
    phantom class name in a docstring — already catalogued once in `doc-code-sync.md` and never
    fixed the first time), `BUG-002` (`mkdocs.yml` points at a `docs/` tree deleted months ago;
    needs a decision — drop the doc site or rebuild it — not a mechanical fix).
- Two tasks filed on the *other* repo (`Sagittarius_Elite_Warrior/Tasks/backlog/BOT-118`,
  `BOT-119`) from cross-checking its engine usage — see §8, do not action them from here.
