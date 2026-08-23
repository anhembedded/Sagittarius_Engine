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
examples/            Sample apps demonstrating engine usage (see §5 below — under active rebuild)
tests/               Engine's own test suite
Tasks/               Kanban board — README.md is the index, epics/ holds multi-task programs
docs/                Separate, larger doc tree (388 KB, 51 files) — not currently routed to
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

**A known trap, read before trusting anything in `context/`:** these 16 files were written in
a single commit, 2026-08-02, and not touched again while the engine gained 9 top-level
packages and +7000 lines. An audit on 2026-08-23 found `repository.md` naming the wrong repo,
citing a nonexistent extension, and `modules.md` documenting an interface the engine's own
code calls "legacy." **[EPIC-002](../Tasks/epics/EPIC-002_engine_sample_app_and_doc_rewrite/README.md)**
is rewriting this directory from a real sample app, grounded and guarded against re-rotting.
Until that epic's `D` subtask lands, verify a `context/` claim against the actual code before
relying on it for anything you'll act on — `grep`/`ls` it, don't trust it at face value.

Always load: `project.md`, `repository.md`.

| Task | Also load |
|---|---|
| Feature development | `architectures/architecture.md`, `modules.md` |
| Bug fix | `runtime.md`, `testing.md` |
| Refactoring | `architectures/architecture.md` |
| Documentation | `documentation.md` |
| Deployment | `deployment.md` |
| Performance | `runtime.md` |
| API | `api.md` |
| Configuration | `configuration.md` |
| Build | `build.md` |

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

**Known duplication, not yet resolved:** `code-rule.md` and `coding-style.md` overlap
substantially (both restate all five SOLID principles); `context/testing.md` and
`rules/testing.md` disagree on the real test directory layout (the `context/` one is
correct — verified against `tests/` on disk); `context/deployment.md` has real content while
`rules/deployment.md` is a 3-line stub. Consolidating these is in scope for
[EPIC-002D](../Tasks/epics/EPIC-002_engine_sample_app_and_doc_rewrite/incomplete/EPIC-002D_doc_rewrite_and_staleness_guard.md) —
until then, prefer the file with real, verifiable content when two disagree.

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
