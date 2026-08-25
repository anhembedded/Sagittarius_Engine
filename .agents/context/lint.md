# Code Quality (Linting & Formatting)

Sagittarius enforces extremely strict code quality and type safety rules to ensure Kernel reliability.

## Tools
* **Linter & Formatter**: `ruff`
* **Type Checker**: `mypy`

## Ruff Configuration

Single source of truth: `pyproject.toml`'s `[tool.ruff]` / `[tool.ruff.lint]`. A root
`ruff.toml` used to **shadow** this entirely — ruff picks one config file, it does not merge —
so the real rule set was ruff's version-dependent built-in default for an unknown length of
time. Deleted 2026-08-23; see
[TASK-021](../../Tasks/backlog/TASK-021_ruff_config_shadowing.md) for the full account,
including a case where trusting an unreviewed `--unsafe-fixes` autofix near a quoted forward
reference silently produced runtime-invalid code (`"ClassName" | None`, a `TypeError` waiting
on the first `typing.get_type_hints()` call) — diff every unsafe fix before applying it.

`[tool.ruff.lint]` uses `select`, not `extend-select`. `extend-select` **adds** to ruff's
built-in defaults, which grow every release — confirmed: the same `extend-select` line
reported 354 findings under ruff 0.16.4 against near-zero under CI's pinned 0.15.20. `select`
fixes the rule set as a property of this repo, not of whichever ruff happens to be installed.

⚠️ **Local and CI tool versions can still drift over time — check before trusting a diff.**
`requirements-dev.txt` pins `ruff==0.16.4` / `mypy==2.3.1` (bumped 2026-08-23, TASK-021): CI's
old `mypy==2.1.0` pin rejected `cls.__new__(cls)` inside a `type[QObject]`-narrowed classmethod
in `thread_affinity.py` (`call-overload`) that `2.3.1` resolves correctly — verified via an
isolated probe venv that this is mypy's own overload resolution improving, not a code bug
(`QObject.__new__ is object.__new__` evaluates to false, so the call is genuinely correct and
`object.__new__(cls)` would silently be a different, wrong call). Re-check `ruff --version` /
`mypy --version` against this file whenever a local/CI gate disagrees.

`scripts/ci-local.ps1` now does that comparison for you: it reads the pins out of
`requirements-dev.txt` and warns on every run when the installed `ruff`/`mypy` differ. It warns
rather than fails, so it cannot block someone deliberately running a newer tool (TASK-021 req. 5).

- Run `ruff check sagittarius_engine tests examples tools` to lint and
  `ruff format sagittarius_engine tests examples tools` to format — the exact commands CI runs
  (`.github/workflows/ci.yml`). `examples/` and `tools/` were added to CI's scope 2026-08-23
  (TASK-021); before that they went unlinted.

## Mypy (Strong Typing)
- **Rule**: Every function signature, argument, and return type MUST be explicitly typed.
- **Rule**: Do NOT use `Any` unless absolutely necessary (e.g. dynamic reflection). Prefer
  `X | None` and `X | Y` over `Optional`/`Union` — the `UP` rules in the ruff config above
  (`UP045`, `UP007`) enforce this, so writing `Optional[X]` now gets flagged, not encouraged.
  `TypeVar` is still current for `Generic[T]`; PEP 695 (`class Foo[T]:`) is available on this
  repo's Python 3.12 floor but not yet applied everywhere — see `UP046` findings tracked in
  TASK-021 for the classes still pending a deliberate (not autofixed) conversion.
- Run `mypy sagittarius_engine tests --ignore-missing-imports --follow-imports=skip`. **Clean —
  `Success: no issues found in 259 source files`**, as of 2026-08-23
  ([TASK-032](../../Tasks/completed/TASK-032_mypy_baseline_cleanup.md), split out of
  `TASK-021`). History: 28 pre-existing errors before that day's `TASK-017`, 27 after it, 23
  after `BUG-003`'s `ILogger` annotation fix, 0 after `TASK-032`'s category-by-category
  cleanup. `scripts/ci-local.ps1` passing its mypy step is now a real signal — any red mypy
  output from here on is a genuine regression, not baseline debt.

## Python Best Practices
- **Data Structures**: Use `dataclasses` (with `frozen=True` preferred) or `Pydantic` models instead of raw dictionaries.
- **Side Effects**: Avoid mutable default arguments (`def f(items=[]):`).
- **Dependencies**: Never hard-code class instantiation in domain logic. Always use Dependency Injection abstractions.
