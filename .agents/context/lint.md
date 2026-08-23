# Code Quality (Linting & Formatting)

Sagittarius enforces extremely strict code quality and type safety rules to ensure Kernel reliability.

## Tools
* **Linter & Formatter**: `ruff`
* **Type Checker**: `mypy`

## Ruff Configuration

⚠️ **There are two ruff configs, and the one you'd expect is the one that loses.** A
`ruff.toml` at the repo root **shadows** `pyproject.toml`'s `[tool.ruff]` section entirely —
ruff never merges the two, it picks the higher-priority file and ignores the other. So the
`extend-select = ["E", "F", "W", "C", "I", "UP", "RET"]` in `pyproject.toml` is **dead
config**; what actually applies is `ruff.toml`'s two lines:

```toml
[lint]
ignore = ["E501", "C901", "UP037"]
```

With no `select`/`extend-select` there, ruff falls back to its **built-in default rule set**,
which varies by ruff version. Verified 2026-08-23; corrected from a previous version of this
file that named `pyproject.toml` as the config source.

**Consequence to know before you run it:** `requirements-dev.txt` pins `ruff==0.15.20`, and
that is what CI installs. A newer local ruff enables more default rules and will report
hundreds of findings the pipeline never sees (measured: ~308 in `sagittarius_engine/` alone
under 0.16.4). If your local run and CI disagree, check `ruff --version` before chasing the
diff. Tracked as [TASK-021](../../Tasks/backlog/TASK-021_ruff_config_shadowing.md).

- Run `ruff check sagittarius_engine tests` to lint and `ruff format sagittarius_engine tests`
  to format — the exact commands CI runs (`.github/workflows/ci.yml`). Note these scope to two
  directories; `examples/` and `tools/` are **not** linted in CI.

## Mypy (Strong Typing)
- **Rule**: Every function signature, argument, and return type MUST be explicitly typed.
- **Rule**: Do NOT use `Any` unless absolutely necessary (e.g. dynamic reflection). Use `Optional`, `Union`, `TypeVar`, or `Generics`.
- Run `mypy sagittarius_engine tests --ignore-missing-imports --follow-imports=skip`.

## Python Best Practices
- **Data Structures**: Use `dataclasses` (with `frozen=True` preferred) or `Pydantic` models instead of raw dictionaries.
- **Side Effects**: Avoid mutable default arguments (`def f(items=[]):`).
- **Dependencies**: Never hard-code class instantiation in domain logic. Always use Dependency Injection abstractions.
