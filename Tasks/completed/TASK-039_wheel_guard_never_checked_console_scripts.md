# TASK-039: The wheel guard imported modules but never checked the commands the package advertises

- **Status**: ✅ Completed
- **Completion Date**: 2026-08-25
- **Priority**: P1
- **Category**: Build / Packaging — Release Gate

---

## Description

`scripts/verify_wheel_importable.py` (added `49c941b`, `TASK`-less, in response to the
`df51202` Python 2 syntax defect that shipped in `v2.1.0` and `v2.2.0`) builds a wheel,
installs it into a throwaway venv, `compileall`s the installed package and imports every module
it ships. That closes the "shipped package is unusable" class properly.

It did not check **console scripts**, and that is a separate class it cannot reach:

- The sweep walks `sagittarius_engine` only. An entry point whose target lives elsewhere —
  `tools.audit_dashboard`, in the one case that existed — is never touched.
- Importing a module is not the same as resolving `module:attr` and confirming the result can
  be called. A module that imports cleanly can still be named by an entry point that does not
  resolve at all.

An entry point is a promise printed into the distribution's metadata. Nothing verified it.

## Why it mattered here

`TASK-002` shipped `sagittarius-audit` as a documented, ✅-completed feature. The command has
never been able to start, for any consumer, in **three independent ways** — established by
installing the built wheel into a clean venv and running it:

| # | Fault | Symptom |
| :-- | :--- | :--- |
| 1 | `tools/audit_dashboard/main.py` imports `PySide6.QtWidgets` at module scope, while the wheel declares no dependencies | `ModuleNotFoundError: No module named 'PySide6'` before any of its own code runs |
| 2 | Inner imports are bare — `from application.receive_audit_use_case import ...` | With `PySide6` present: `ModuleNotFoundError: No module named 'application'` unless the process starts in `tools/audit_dashboard/` |
| 3 | The entry point is `tools.audit_dashboard:main` — a *module*, where a function is required | The generated launcher calls a module object |

It survived a month, across two releases, behind 953 passing tests, a clean mypy baseline and
eight CI jobs — none of which install the artifact and try the command.

**A correction to the record:** `EPIC-005` D7 originally claimed the GUI "never ships" because
`find_packages(include=["tools*"])` returns `['tools']`. That was wrong.
`[tool.setuptools.packages.find]` defaults to `namespaces = true`, so the build uses
`find_namespace_packages`, which resolves `tools.audit_dashboard` and its five subpackages
despite the missing `__init__.py`. Listing the built wheel confirms all fourteen files are
present. The package ships; the *command* is what does not work.

## What was done

### 1. Step 3 added to the guard — resolve every declared console script

Reads `console_scripts` from the **installed** distribution's metadata (not from
`pyproject.toml`, keeping the guard's discipline of checking the artifact rather than the
source), then for each entry point performs the same two steps the generated launcher does —
import the module, walk to the attribute — and asserts the result is callable.

It deliberately **resolves but never invokes**. Running a console script would start the
application: a GUI, a server, a REPL. Resolution plus a callability check catches all three
faults above without launching anything.

Strict, with no exemption list, matching the existing sweeps and the reasoning already recorded
in the module docstring.

The distribution name is read off the wheel filename (PEP 427's first `-`-delimited field)
rather than assumed equal to the import name — `sagittarius-engine` vs `sagittarius_engine`.

### 2. `sagittarius-audit` removed from `[project.scripts]` — removed, not repaired

Repairing it means work on a component `EPIC-005` §3 already schedules for deletion, and all
three faults would need fixing to make it start. The honest minimum is to stop advertising a
command that has never run. `EPIC-005` Milestone D re-adds a console script pointing at
something that works. The reasoning is left in place in `pyproject.toml` rather than removed
silently, per `rules/doc-code-sync.md`.

## Verification

```
[1/3] compileall over the installed package
ok - every shipped module compiles

[2/3] importing every shipped module
ok - all 180 shipped modules imported

[3/3] resolving declared console scripts
ok - the distribution declares no console scripts

PASS: the built wheel installs, imports, and every advertised command resolves.
```

"No console scripts declared" passes trivially, so the check was also exercised against
deliberately broken entry points to prove it has teeth — both failure modes are caught, and a
valid entry point passes:

```
  FAIL bad-missing-attr = ...app:no_such_function: AttributeError: ... has no attribute ...
  FAIL bad-not-callable = ...domain:event_registry: resolves to a module, not a callable
  ok   good-one         = ...event_registry:EventRegistry

FAIL: 2 of 3 console scripts cannot be run by a consumer.   (exit 1)
```

Run against the real `sagittarius-audit` before its removal, the guard failed exactly as
intended — this task's premise, demonstrated rather than asserted.

Full suite: **971 passed, 8 skipped** on Python 3.12 (the `requires-python` floor as of
`58946b3`). `ruff check`, `ruff format --check` and `mypy` all clean.

## Follow-up

`EPIC-005` Milestone D and `EPIC-006` Milestone E each add a console script. Both are now
covered by this gate before they can reach a consumer, which was the point of doing this ahead
of either epic.

## Related

- `TASK-002` — shipped the entry point that has never run
- `EPIC-005` §2 (D6, D7), §10 — audit teardown; D7 corrected by this task
- `EPIC-006` §8 — identified this gap and recommended closing it ahead of both epics
- `49c941b` — the guard this extends
