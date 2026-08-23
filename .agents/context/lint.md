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

**Local vs CI tool version — now checked, not merely warned about.**
`requirements-dev.txt` pins `ruff==0.15.20` / `mypy==2.1.0`. `scripts/ci-local.ps1` compares the
installed versions against those pins on every run and prints a warning (never a failure — it
must not block someone deliberately running a newer tool) when they differ. Measured 2026-08-23
on this machine: both match. An earlier note here reported drift to `ruff 0.16.4` / `mypy 2.3.1`;
that measurement came from a `.venv` that no longer exists in this checkout (TASK-021 req. 5).

- Run `ruff check sagittarius_engine tests examples tools` to lint and
  `ruff format sagittarius_engine tests examples tools` to format — the exact commands CI runs
  (`.github/workflows/ci.yml`). `examples/` and `tools/` joined that scope in TASK-021 req. 4;
  they had never been linted, which was awkward given `.agents/context/` calls
  `examples/student_management/` the reference implementation. Bringing them in fixed 31 findings
  (import sorting, `typing.Dict`/`List` → `dict`/`list`, `Optional` → `| None`) and reformatted
  4 files.

## Mypy (Strong Typing)
- **Rule**: Every function signature, argument, and return type MUST be explicitly typed.
- **Rule**: Do NOT use `Any` unless absolutely necessary (e.g. dynamic reflection). Prefer
  `X | None` and `X | Y` over `Optional`/`Union` — the `UP` rules in the ruff config above
  (`UP045`, `UP007`) enforce this, so writing `Optional[X]` now gets flagged, not encouraged.
  `TypeVar` is still current for `Generic[T]`; PEP 695 (`class Foo[T]:`) is available on this
  repo's Python 3.14 floor but not yet applied everywhere — see `UP046` findings tracked in
  TASK-021 for the classes still pending a deliberate (not autofixed) conversion.
- Run `mypy sagittarius_engine tests examples --ignore-missing-imports --follow-imports=skip`.
  **Clean** as of 2026-08-23. `examples/` was added to this scope in TASK-021 req. 4 and was
  already clean. `tools/` is deliberately **excluded** — it has 9 pre-existing errors
  (`TASK-033`), and folding them in here would have re-broken the zero baseline the moment it
  was achieved
  ([TASK-032](../../Tasks/completed/TASK-032_mypy_baseline_cleanup.md), split out of
  `TASK-021`). History: 28 pre-existing errors before that day's `TASK-017`, 27 after it, 23
  after `BUG-003`'s `ILogger` annotation fix, 0 after `TASK-032`'s category-by-category
  cleanup. `scripts/ci-local.ps1` passing its mypy step is now a real signal — any red mypy
  output from here on is a genuine regression, not baseline debt.

## Python Best Practices
- **Data Structures**: Use `dataclasses` (with `frozen=True` preferred) or `Pydantic` models instead of raw dictionaries.
- **Side Effects**: Avoid mutable default arguments (`def f(items=[]):`).
- **Dependencies**: Never hard-code class instantiation in domain logic. Always use Dependency Injection abstractions.
