# TASK-029: `TASK-024`'s `sdk/` deletion was never fully propagated through `.agents/`

## Description

`TASK-024` (2026-08-23) deleted `sagittarius_engine/sdk/` and `tools/scaffold.py` entirely —
confirmed on disk: `sagittarius_engine/` now has exactly 10 top-level packages (`adapters/`,
`base/`, `domain/`, `extensions/`, `infrastructure/`, `interfaces/`, `kernel/`, `middleware/`,
`runtime/`, `utils/`), no `sdk/`, and `tests/sdk/` does not exist either. Several `.agents/`
files were updated to reflect this correctly (`.agents/context/api.md` cites `TASK-024`
explicitly and reads as historical fact). **Others were not touched and still present `sdk/` as
a currently-existing package or feature:**

| File | Stale claim |
| :--- | :--- |
| `.agents/rules/architecture.md` | "Engine Package Layout" (§ stated to be *exhaustive*) still lists `sdk/` — "Project scaffolding (`project_generator.py`, `cli.py`) plus the `templates/` the engine emits: `minimal`, `clean`, `ddd`" — as one of the top-level packages, contradicting the same file's own later note that "the scaffolding feature was deleted on 2026-08-23." A doc that documents its own claim as both true and false is worse than one nobody checked. |
| `.agents/rules/testing.md` | "The real directories are `base/`, `domain/`, `extensions/`, `infrastructure/`, `interfaces/`, `kernel/`, `middleware/`, `runtime/`, `sdk/`" — `sdk/` is not a real directory under `tests/` any more. |
| `.agents/context/testing.md` | A directory-tree diagram includes `├── sdk/  tests for sdk/ (scaffolding, templates)`. |
| `.agents/context/project.md` | Philosophy list: "SDK accelerates development." Architecture table: a full `SDK \| Templates, Generator, Project Setup` row, presented alongside the still-real `Kernel`/`Runtime`/`Extensions` rows with no indication it no longer exists. |
| `.agents/context/repository.md` | Repository-layout table's `tests/` row lists `sdk/` among the mirrored package directories. |

## Why it survived

`rules/doc-code-sync.md` (always-on) requires the person making a code change to grep `.agents/`
for the old name and fix every doc claim in the same change. `TASK-024`'s own completed file
shows this was done for the files that name `TASK-024` explicitly (`api.md`,
`architecture.md`'s Clean-Architecture-Layers note), but the grep evidently didn't reach the
five spots above — plausibly because they say "SDK" as prose or a table cell rather than the
literal path `sdk/`, so a path-only grep would miss them. This is the same failure category
`EPIC-002` was created to fix in the first place: a claim nobody re-checks stays wrong
indefinitely. Found 2026-08-23 while closing `TASK-026`, via
`tests/test_agents_docs_resolve.py::test_agents_docs_have_no_unresolved_structural_references`
failing on `repository.md`'s backtick-quoted `sdk/` — that automated guard caught one of the
five; the other four use plain prose ("SDK accelerates development") that the guard's
backtick-token check cannot see, which is itself worth noting as a gap in that guard's coverage.

## Requirements

1. Remove or correct the `sdk/` / "SDK" references in all five files above, consistent with how
   `api.md` and `architecture.md`'s Clean-Architecture-Layers section already handle it
   (state plainly that the feature was removed, cite `TASK-024`, don't just delete the line
   silently — see `rules/doc-code-sync.md`).
2. `rules/architecture.md`'s "Engine Package Layout" list is declared exhaustive; after this
   fix it should read 10 packages, not 11, and should not need a second correction pass to
   also mention the removal (unlike some of the files it currently contradicts).
3. Consider whether `tests/test_agents_docs_resolve.py`'s unresolved-token check should be
   extended to catch a prose claim like "SDK accelerates development" — not required for this
   task to close, but worth a line noting the gap for whoever next touches that guard.

## Priority

P3 — no runtime impact; a documentation-only correction. Priority follows `doc-code-sync.md`'s
general concern (a wrong doc misleads with the authority of a written rule/doc behind it) rather
than any functional risk.

## Category

Documentation / Doc-Code Sync

## Related

- [TASK-024](../completed/TASK-024_getting_started_scaffolders_broken.md) — the deletion this
  task is finishing the doc cleanup for.
- [TASK-026](../completed/TASK-026_validation_middleware_silently_self_disables.md) — the task
  during which this was found.
- [EPIC-002](../epics/EPIC-002_engine_sample_app_and_doc_rewrite/README.md) — the program that
  rewrote `.agents/context/` against real code in the first place; this is exactly the kind of
  drift it was meant to prevent recurring.
