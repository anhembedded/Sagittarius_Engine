# TASK-021: Two ruff configs, and the intended one is dead

## Description

The repo has ruff configured in two places:

**`pyproject.toml`** — the one that looks authoritative, and is what `.agents/context/lint.md`
used to document:

```toml
[tool.ruff]
line-length = 88
target-version = "py314"
exclude = [".venv", "build", "dist", "__pycache__", ".pytest_cache", ".git"]

[tool.ruff.lint]
extend-select = ["E", "F", "W", "C", "I", "UP", "RET"]
ignore = ["E501"]
per-file-ignores = {"__init__.py" = ["F401"]}
```

**`ruff.toml`** at the repo root — the one that actually applies:

```toml
[lint]
ignore = ["E501", "C901", "UP037"]
```

Ruff does not merge these. A `ruff.toml` outranks `pyproject.toml`'s `[tool.ruff]`, so the
entire `pyproject.toml` block — the `extend-select`, the `line-length`, the `exclude`, the
`per-file-ignores` — **is silently ignored.** With no `select` in `ruff.toml`, ruff falls
back to its built-in defaults, which is not the rule set anyone in this repo chose.

Found on 2026-08-23 while re-verifying `.agents/context/lint.md` against real config
(EPIC-002D).

## Why it matters

Two concrete consequences, both observed:

1. **The rule set is whatever the installed ruff version defaults to.** `requirements-dev.txt`
   pins `ruff==0.15.20` and CI installs that, so CI is at least self-consistent. But a
   developer on a newer ruff gets a different, larger default rule set: measured on 0.16.4,
   `ruff check sagittarius_engine` reports **308 findings** (`BLE001`, `PIE790`, `RUF022`,
   `TRY201`, `DTZ005`, `S110`, …) that CI never sees. Local and CI disagreeing about whether
   the code lints is a bad place to be.
2. **`per-file-ignores = {"__init__.py" = ["F401"]}` is not in effect.** Re-exports in
   `__init__.py` are only passing because F401 happens not to fire under the current default
   set — not because the repo's stated intent is being honoured.

### Related: there is nothing pinning the *local* toolchain to CI's

Same symptom, adjacent cause. Measured in the repo's own `.venv` on 2026-08-23:

| Tool | CI pin (`requirements-dev.txt`) | Local `.venv` |
| :--- | :--- | :--- |
| ruff | `0.15.20` | `0.16.4` |
| mypy | `2.1.0` | `2.3.1` |

Running CI's exact mypy invocation locally reports **29 errors across 11 files** in
`sagittarius_engine/` (`union-attr`, `has-type`, `return-value`, …). Whether CI sees the same
29 under mypy 2.1.0 is unknown and was not determined. Either answer is a problem worth
naming: if CI sees them, the lint job is red and being ignored; if it doesn't, then "mypy
passes" means something different locally than it does in CI, and neither number is
trustworthy on its own.

Worth folding into this task because the fix is the same shape — make one toolchain
authoritative — and fixing the config without fixing the versions just moves the disagreement.

## Requirements

1. Pick **one** config location. Recommended: delete `ruff.toml` and keep `pyproject.toml`, so
   tool config lives with the rest of the project metadata — but either choice is fine as long
   as only one file exists.
2. Whichever survives must carry the *union* of the intent currently split across both:
   `extend-select`, `line-length`, `target-version`, `exclude`, `per-file-ignores`, and the
   `ignore` list (`E501`, `C901`, `UP037` — note the last two exist only in `ruff.toml`, so
   folding them in is a real change, not a no-op).
3. Run `ruff check sagittarius_engine tests` with the consolidated config and fix or
   explicitly `ignore` whatever it surfaces. Expect real work here — this is the first time
   the intended rule set will have actually run.
4. Consider whether CI should also lint `examples/` and `tools/`. It currently lints neither,
   so the sample app that `.agents/context/` now documents as the reference implementation is
   itself unlinted.
5. Establish how a developer gets CI's exact toolchain — the versions above drift today with
   nothing catching it. Then determine whether CI's mypy is currently red, and fix or
   explicitly baseline the 29 errors.
6. Update `.agents/context/lint.md` — it currently documents the shadowing as a known trap;
   once fixed, that warning should be replaced with a plain description of the single config.

## Priority

P2 — no runtime impact, but this is the linter itself being misconfigured, which quietly
degrades every other quality gate that depends on it.

## Category

Build / Tooling
