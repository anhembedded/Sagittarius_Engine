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

⚠️ **Still true, config aside: local and CI can disagree on tool version.**
`requirements-dev.txt` pins `ruff==0.15.20` / `mypy==2.1.0`; nothing enforces that locally.
Check `ruff --version` / `mypy --version` before chasing a diff that isn't there.

- Run `ruff check sagittarius_engine tests` to lint and `ruff format sagittarius_engine tests`
  to format — the exact commands CI runs (`.github/workflows/ci.yml`). Note these scope to two
  directories; `examples/` and `tools/` are **not** linted in CI (TASK-021).

## Mypy (Strong Typing)
- **Rule**: Every function signature, argument, and return type MUST be explicitly typed.
- **Rule**: Do NOT use `Any` unless absolutely necessary (e.g. dynamic reflection). Prefer
  `X | None` and `X | Y` over `Optional`/`Union` — the `UP` rules in the ruff config above
  (`UP045`, `UP007`) enforce this, so writing `Optional[X]` now gets flagged, not encouraged.
  `TypeVar` is still current for `Generic[T]`; PEP 695 (`class Foo[T]:`) is available on this
  repo's Python 3.14 floor but not yet applied everywhere — see `UP046` findings tracked in
  TASK-021 for the classes still pending a deliberate (not autofixed) conversion.
- Run `mypy sagittarius_engine tests --ignore-missing-imports --follow-imports=skip`. ⚠️ This
  currently reports **23 pre-existing errors**, unrelated to any config issue. History: 28
  before `TASK-017`, 27 after it, 23 after `BUG-003`'s fix (2026-08-23) narrowed two wrongly-
  optional `ILogger` annotations. Categorized and tracked in
  [TASK-032](../../Tasks/backlog/TASK-032_mypy_baseline_cleanup.md) (split out of `TASK-021`).
  Do not treat new mypy output as your own regression without checking whether the specific
  error is already in that count.

## Python Best Practices
- **Data Structures**: Use `dataclasses` (with `frozen=True` preferred) or `Pydantic` models instead of raw dictionaries.
- **Side Effects**: Avoid mutable default arguments (`def f(items=[]):`).
- **Dependencies**: Never hard-code class instantiation in domain logic. Always use Dependency Injection abstractions.
