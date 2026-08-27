# REF-002: `Tasks/` documents link into `backlog/` for tasks that moved to `completed/`

- **Status**: 🟠 Open
- **Category**: Documentation / Doc-Code Sync
- **Found while**: verifying every relative link touched during `EPIC-007`'s ADRs and epic
  files (2026-08-27) — a broader sweep of all of `Tasks/` turned up the rest

---

## 1. The disagreement

`task-tracking.md`'s own lifecycle rule: *"Move the task file from `Tasks/backlog/` to
`Tasks/completed/`"* — but nothing in that rule says anything moves the **links pointing at
the old path**. 13 links across 8 files still say `../backlog/TASK-0XX...md` for a task that
has since moved to `completed/`, and one link points the other way (`completed/` naming a
file that never left `backlog/` under that exact name).

```
Tasks/completed/TASK-026_validation_middleware_silently_self_disables.md
  -> ../backlog/TASK-023_ci_matrix_hides_312_313_breakage.md
Tasks/completed/TASK-025_dead_infrastructure_persistence_package.md
  -> ../backlog/TASK-023_ci_matrix_hides_312_313_breakage.md
Tasks/completed/TASK-027_no_py_typed_marker.md
  -> ../backlog/TASK-021_ruff_config_shadowing.md
Tasks/epics/EPIC-003_database_extension_multi_db/TASK-019_database_extension_expose_engine.md
  -> ../epics/EPIC-003_database_extension_multi_db/README.md
Tasks/epics/EPIC-002_engine_sample_app_and_doc_rewrite/ONBOARDING.md
  -> ../../backlog/TASK-019_database_extension_expose_engine.md
Tasks/epics/EPIC-002_engine_sample_app_and_doc_rewrite/MODULE_COVERAGE.md
  -> ../../backlog/TASK-019_database_extension_expose_engine.md
Tasks/epics/EPIC-002_engine_sample_app_and_doc_rewrite/AUDIT_REPORT.md
  -> ../../backlog/TASK-019_database_extension_expose_engine.md
Tasks/epics/EPIC-002_engine_sample_app_and_doc_rewrite/completed/EPIC-002D_doc_rewrite_and_staleness_guard.md
  -> ../../../backlog/TASK-020_ci_benchmark_job_stale_path.md
  -> ../../../backlog/TASK-021_ruff_config_shadowing.md
  -> ../../../backlog/TASK-022_missing_license_file.md
Tasks/epics/EPIC-002_engine_sample_app_and_doc_rewrite/completed/EPIC-002A_sample_app_scaffold.md
  -> ../../../backlog/TASK-019_database_extension_expose_engine.md
```

Two are cross-repository and out of scope for this refix (`ONBOARDING.md` links twice into
`Sagittarius_Elite_Warrior`'s own `Tasks/`, a different repository this refix cannot verify
against).

## 2. Why this needs a decision, not a find-and-replace

Every target task (`TASK-019`, `TASK-020`, `TASK-021`, `TASK-022`, `TASK-023`) already
exists in `Tasks/completed/` under the exact filename the broken link almost matches — this
is confirmed by `find` before doing anything else. So the mechanical fix is safe *once
confirmed*, which is the reconciliation step a refix names explicitly rather than assuming.

`TASK-019`'s case is slightly different and worth flagging on its own: the file
`Tasks/epics/EPIC-003_database_extension_multi_db/TASK-019_database_extension_expose_engine.md`
sits **inside the epic directory itself**, not in `backlog/` or `completed/` — i.e. `TASK-019`
was folded into `EPIC-003` rather than completed as a standalone task. Three other documents
still link to it as if it were a live backlog item. That is not a stale path, it is a stale
*claim* ("this is still to do"), and deserves a sentence at each site saying it was absorbed
into `EPIC-003`, not just a corrected link.

## 3. Proposed reconciliation (not yet applied)

1. For the five same-directory moves, repoint each link from `../backlog/TASK-0XX...` to
   `../completed/TASK-0XX...` (or the correct relative depth per file).
2. For the three `TASK-019` references, repoint to
   `../../epics/EPIC-003_database_extension_multi_db/TASK-019_database_extension_expose_engine.md`
   and add a one-clause note that it was absorbed into `EPIC-003`, not completed standalone.
3. Leave the two cross-repository links alone — verifying another repository's filesystem is
   outside what this session can check, and is its own concern if it needs one.
4. Add a link-check to CI or to a test (`tests/test_agents_docs_resolve.py` already walks
   `.agents/`'s links in the same style — extending its pattern to `Tasks/` closes this class
   of drift the way that test already closes it for `.agents/`).

## 4. Why left open rather than fixed here

Found as a side effect of an unrelated link check while working `EPIC-007`; fixing eight
files across two different epics is its own reviewable change, and `design-discipline.md`
is explicit that leaving something correctly named and undone beats folding it into a commit
where a reviewer would have to separate it from the epic's actual content.
