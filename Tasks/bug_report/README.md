# 🐞 Bug Board — Sagittarius Engine

Tracks **every reported defect** in the engine. Kept separate from
[`../README.md`](../README.md) for the same reason the app repo does it: that board tracks
*work items* (`TASK-XXX`, `EPIC-XXX`) — a fixed bug shows up in its Completed section, but an
**open** bug had nowhere to be listed at all. To know what the engine is currently carrying,
you'd have to open every file. This board is the answer to that question.

Convention mirrors `Sagittarius_Elite_Warrior/Tasks/bug_report/` deliberately, so the same
habit works in both repos — but the two boards are **independent**, like the repos themselves
(see `.agents/ONBOARDING.md` §8). Never file an engine bug on the app's board or vice versa.

- **Directory layout** (parallel to `Tasks/backlog|completed/` for tasks):
  - `incomplete/` — bugs **not yet fixed**. New bugs are always created here.
  - `completed/` — fixed bugs, with their own evidence.
- Name as `BUG-XXX_description.md`, numbering from the highest existing across **both**
  directories.
- **When fixed:** `git mv incomplete/BUG-XXX_*.md completed/`, update `Status` inside the file,
  then move its row in the tables below from Open to Fixed.
- Bugs are **not** counted in `../README.md`'s task numbers.

### BUG vs TASK — which one to file

- **BUG** — something is *wrong*: it does not work, or it states something untrue about the
  code. Regardless of size.
- **TASK** — something is *missing or should change*: a feature, a cleanup, a decision, a
  hardening program.

Borderline calls resolved so far: missing `LICENSE` is a `TASK` (nothing is wrong, something is
absent); a docstring naming a class that doesn't exist is a `BUG` (an active false statement).

> Updated: 2026-08-23 — board created during the post-EPIC-002 engine audit.

---

## 📊 Overview

| Status | Count |
| :--- | :---: |
| 🔴 **Open** | 3 |
| ✅ **Fixed** | 0 |
| 📈 **Total** | **3** |

All three were found on 2026-08-23 during the engine audit that followed `EPIC-002`. Defects
found in the *same* audit that already had a fix applied were tracked as tasks instead, because
they were closed in the same session — see `TASK-024`, `TASK-025`, and the `ITaskHandle` import
bug fixed in commit `568d3bb`. Future defects should come here first.

---

## 🔴 Open

| ID | Title | Severity | Reported | Note |
| :--- | :--- | :---: | :---: | :--- |
| **[BUG-002](incomplete/BUG-002_mkdocs_config_points_at_deleted_docs_tree.md)** | `mkdocs.yml` builds from a `docs/` tree deleted in `a338d42` | Medium | 2026-08-23 | Config, `requirements-docs.txt` and `scripts/docs.{sh,bat}` all left behind. Needs a decision: drop the doc site, or rebuild it. |
| **[BUG-001](incomplete/BUG-001_phantom_apprunner_in_iengincontext_docstring.md)** | `IEngineContext` docstring names a nonexistent `AppRunner` class | Low | 2026-08-23 | Already catalogued in `doc-code-sync.md:63` as a known finding — and never fixed. Real class is `ApplicationRunner`, and it takes no context at all. |
| **[BUG-003](incomplete/BUG-003_get_logger_annotation_contradicts_iengincontext_contract.md)** | `_get_logger()` declares `ILogger \| None` against a contract that guarantees non-None | Low | 2026-08-23 | Source of 4+ of the mypy errors currently failing `scripts/ci-local.ps1`. No runtime impact; the annotation is simply wrong. |

---

## ✅ Fixed

*(none yet)*
