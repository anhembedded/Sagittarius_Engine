# TASK-024: Both scaffolding commands in readme.md are broken

> **Closed 2026-08-23 by removing the feature.** The owner confirmed scaffolding is not used
> and not wanted. Deleted: `tools/scaffold.py`, `sagittarius_engine/sdk/` (277 LOC + 21
> template files), `tests/test_scaffold.py`, `tests/sdk/`. Removed: the `sagittarius` console
> script from `pyproject.toml`, Rule 4 and the sdk clauses in `tests/test_architecture.py`, and
> the Features / Option 3 / Project Templates sections of `readme.md`. Also fixed the two
> `.agents/` docs that cited `sdk/templates/` — one of which the new staleness guard caught
> automatically, which is a fair test of that guard.
>
> Kept below as the record of what was wrong, since requirement 5's reasoning outlives the
> feature: **no test ran generated output**, which is why templates could reference renamed
> engine symbols indefinitely. Worth remembering if scaffolding is ever reintroduced.

## Description

`readme.md` advertises project scaffolding twice. **Neither documented command works.** For a
framework whose pitch includes *"Generated projects are immediately runnable"*, this is the
first thing a new user hits.

### 1. `python -m tools.scaffold my_new_app` (readme "Option 3")

Runs and reports success — then produces a project that is dead on arrival. The generated
`main.py` imports three names that no longer exist:

| Generated import | Reality |
| :--- | :--- |
| `from sagittarius_engine.extensions.logger.logger_module import LoggerModule` | class is `LoggerExtension` |
| `from sagittarius_engine.infrastructure.persistence.database_module import DatabaseModule` | class is `DatabaseExtension`, and it lives in `extensions/persistence/`, not `infrastructure/` |
| `from sagittarius_engine.extensions.health.health_module import HealthModule` | class is `HealthExtension` |

Verified by generating a project and running it:

```
ImportError: cannot import name 'LoggerModule' from
'sagittarius_engine.extensions.logger.logger_module'
```

The templates in `tools/scaffold.py` were never updated when the `*Module` → `*Extension`
rename happened.

### 2. `python -m sagittarius_engine.sdk new my_app --template clean` (readme "Project Templates")

Fails two different ways:

```
No module named sagittarius_engine.sdk.__main__;
'sagittarius_engine.sdk' is a package and cannot be directly executed
```

There is no `__main__.py` in the `sdk` package — the entry point is `sdk.cli`. And even
corrected to `-m sagittarius_engine.sdk.cli`, the documented flag doesn't exist:

```
error: unrecognized arguments: --template
```

`--template` is not an option; template is the **first positional argument**.

### What actually works (documented nowhere)

```bash
python -m sagittarius_engine.sdk.cli new clean my_app --output-dir .
```

Verified end to end: generates the project, and the result runs —
`Clean Architecture App 'sdk_app3' booted successfully by Developer!`

So the SDK generator itself is **fine**. Only its invocation is misdocumented.

## Requirements

1. **Decide whether `tools/scaffold.py` should exist at all.** There are two scaffolders; the
   SDK one works and supports four templates, `tools/scaffold.py` emits one hardcoded layout
   with stale imports. Recommendation: delete `tools/scaffold.py` and remove readme "Option 3",
   rather than maintaining two. If it stays, its templates must be fixed and covered by a test.
2. Add `sagittarius_engine/sdk/__main__.py` so `python -m sagittarius_engine.sdk` works as
   documented — or change the docs to `sdk.cli`. Prefer adding `__main__.py`; the shorter form
   is what people will type.
3. Reconcile the CLI signature with the docs. Either make `--template` a real flag (nicer, and
   what readme already promises) or fix readme to the positional form. Do not leave them
   disagreeing.
4. Note `pyproject.toml` already declares `sagittarius = "sagittarius_engine.sdk.cli:main"` as a
   console script — so after `pip install`, `sagittarius new clean my_app` should be the
   documented path. Readme never mentions it. It should.
5. **Add a test that generates each of the four templates (`minimal`, `clean`, `ddd`, `mvc`)
   and executes the result.** This bug class — generated code referencing renamed engine
   symbols — is invisible to every existing test, because no test runs generated output. That
   test is the actual fix; everything above is cleanup.

## Priority

**P1** — it is the documented first-run experience, and it fails.

## Category

SDK / Developer Experience
