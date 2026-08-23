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

---

## ✅ Outcome — completed 2026-08-23

All 5 files fixed, plus one thing the task didn't anticipate.

- `rules/architecture.md` — removed the `sdk/` bullet from the "exhaustive" Engine Package
  Layout list entirely (it was self-contradicting: the same file's own Clean-Architecture-Layers
  note already said scaffolding was deleted). List is now 10 entries, matching the real
  `sagittarius_engine/*/` count on disk.
- `rules/testing.md` — dropped `sdk/` from the real-directories list in the tests-mirror-source
  rule.
- `context/testing.md` — dropped the `sdk/` row from the `tests/` tree diagram.
- `context/project.md` — dropped the "SDK accelerates development" philosophy bullet and the
  `SDK | Templates, Generator, Project Setup` architecture-table row; replaced the row with a
  short note explaining the deletion and pointing at `CHANGELOG.md`'s `2.0.0` entry, per
  `doc-code-sync.md` (state plainly that a feature was removed, don't just delete the line).
- `context/repository.md` — "11 top-level packages" corrected to "10".

**Unplanned finding while verifying:** `sagittarius_engine/sdk/__pycache__/` and
`tests/sdk/__pycache__/` still existed on disk — untracked build artifacts left over from before
`TASK-024`'s deletion, never caught because `git status`/`git ls-files` correctly show nothing
(they were never tracked). `ls -d sagittarius_engine/*/` was reporting 11 directories because of
this, which is what caused the double-check in the first place — good thing to verify against
disk, not against the task's own claim. Deleted; already covered by the existing
`__pycache__` gitignore entry, so this shouldn't recur.

Requirement 3 (extend the staleness guard to catch bare-prose claims like "SDK accelerates
development") — **not done**, left as noted for whoever next touches that guard. The two
deleted-feature paths quoted in `project.md`'s new explanatory note
(`sagittarius_engine.sdk`, `tools/scaffold.py`) were added to `IGNORE_TOKENS` instead, same
pattern already used for `IConnector`/`TerminalMenu`.

Verified: `tests/test_agents_docs_resolve.py` — 2 passed. `scripts/ci-local.ps1` — lint/format
green, mypy at the known 27 baseline (unchanged by this task).
