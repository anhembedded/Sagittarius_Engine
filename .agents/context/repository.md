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
| `sagittarius_engine/` | The framework itself. 11 top-level packages — see `rules/architecture.md`'s "Engine Package Layout" for the exhaustive, authoritative list; not duplicated here. |
| `examples/` | Runnable reference apps. Currently: `student_management/` — a real, running Clean Architecture + `pyside_mvc` app; see `examples.md` in this directory. |
| `tools/` | Standalone utilities built on top of the engine, not part of the installable package. `audit_dashboard/` — a PySide6 desktop app consuming `AuditExtension` over WebSockets. |
| `tests/` | The engine's own test suite. Mirrors `sagittarius_engine/`'s package layout: `base/`, `domain/`, `extensions/`, `infrastructure/`, `interfaces/`, `kernel/`, `middleware/`, `runtime/`, `sdk/`. |
| `scripts/` | Developer-facing utility scripts — not part of the installable package. `render_gallery_snapshot.py` (renders the `pyside_mvc` widget-kit gallery), `show-gallery.ps1` (PowerShell wrapper), `docs.sh`/`docs.bat` (doc-site build). |
| `docs/` (repo root) | **Does not exist.** Deleted whole — 53 files, 6070 lines — in commit `a338d42` ("Remove outdated tutorials and examples"), 2026-08-23. Confirmed via `git ls-tree -r HEAD` (0 files). `mkdocs.yml` still declares `docs_dir: docs`, so `mkdocs serve` fails; `requirements-docs.txt` also remains with nothing to build. `readme.md`'s Documentation section pointed here and was corrected the same day. Note: `examples/student_management/docs/` is a separate, real, small directory of design notes for that one sample app — unrelated to this row. |
| `Tasks/` | The project's Kanban board. `README.md` is the index; `epics/` holds multi-subtask programs (see `rules/task-tracking.md`); `backlog/`/`completed/` hold standalone `TASK-XXX` items. |
| `.agents/` | This directory — AI-facing rules, context, and skills. Entry point is `AGENTS.md` → `ONBOARDING.md`. |
| `.github/workflows/` | CI/CD pipeline (`ci.yml`) — see `build.md`. |

## What used to be here

`examples/student_management/` was completely rebuilt from zero on 2026-08-23 (`EPIC-002`) —
the old version (`IModule`-based, no `pyside_mvc` contact) is reachable via
`git log -- examples/student_management` if ever needed for historical reference, but is not
a starting point for anything new.
