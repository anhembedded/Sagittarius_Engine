# Repository Structure

Rewritten 2026-08-23 from a real, exhaustive listing — the previous version (single commit,
2026-08-02) named the wrong repository, listed a nonexistent extension, and omitted `docs/`
and `scripts/` entirely. See
[EPIC-002's `AUDIT_REPORT.md`](../../Tasks/epics/EPIC-002_engine_sample_app_and_doc_rewrite/AUDIT_REPORT.md)
§1.1 for the full history. This repository is **`Sagittarius_Engine`**.

## Root directories

Exhaustive as of 2026-08-23 — generated from `ls`, not recalled. If a new top-level directory
appears later, add a row; don't let this list quietly go stale the way its predecessor did.

| Directory | Contents |
| :--- | :--- |
| `sagittarius_engine/` | The framework itself. 10 top-level packages — see `rules/architecture.md`'s "Engine Package Layout" for the exhaustive, authoritative list; not duplicated here. |
| `examples/` | Runnable reference apps. Currently: `student_management/` — a real, running Clean Architecture + `pyside_mvc` app; see `examples.md` in this directory. |
| `tools/` | Standalone utilities built on top of the engine, not part of the installable package. **Currently holds no tool of its own.** (audit_dashboard/ was here until `EPIC-005A` deleted it; `sagittarius-trace` replaces it as a console script, not a tool directory. The QtWidgets kit gallery was here until `EPIC-007H` moved the kit — and its gallery — out to the consuming app.) |
| `tests/` | The engine's own test suite. Mirrors `sagittarius_engine/`'s package layout: `base/`, `domain/`, `extensions/`, `infrastructure/`, `interfaces/`, `kernel/`, `middleware/`, `runtime/`. |
| `scripts/` | Developer-facing utility scripts — not part of the installable package. `render_gallery_snapshot.py` (renders the `pyside_mvc` widget-kit gallery), `show-gallery.ps1` (PowerShell wrapper), `ci-local.ps1` (the completion gate — see `ONBOARDING.md` §1a). |
| `docs/` (repo root) | **Does not exist, and there is no doc-site toolchain any more.** The tree was deleted whole — 53 files, 6070 lines — in commit `a338d42` ("Remove outdated tutorials and examples"), 2026-08-23. `mkdocs.yml`, `requirements-docs.txt`, and the doc-build wrapper scripts under `scripts/` were left pointing at it for a time and were all removed rather than rebuilt (`BUG-002`, closed 2026-08-23) — `.agents/context/` is the documentation now, with no present intent to publish a separate site. Note: `examples/student_management/docs/` is a separate, real, small directory of design notes for that one sample app — unrelated to this row. |
| `Tasks/` | The project's Kanban board. `README.md` is the index; `epics/` holds multi-subtask programs (see `rules/task-tracking.md`); `backlog/`/`completed/` hold standalone `TASK-XXX` items. |
| `.agents/` | This directory — AI-facing rules, context, and skills. Entry point is `AGENTS.md` → `ONBOARDING.md`. |
| `.github/workflows/` | CI/CD pipeline (`ci.yml`) — see `build.md`. |

## What used to be here

`examples/student_management/` was completely rebuilt from zero on 2026-08-23 (`EPIC-002`) —
the old version (`IModule`-based, no `pyside_mvc` contact) is reachable via
`git log -- examples/student_management` if ever needed for historical reference, but is not
a starting point for anything new.
