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

1. ~~Pick **one** config location.~~ **Done 2026-08-23:** `ruff.toml` deleted, `pyproject.toml`
   is now the only config. Also switched `extend-select` → `select` — `extend-select` adds to
   ruff's built-in defaults, which widen every release (confirmed: the same `extend-select`
   line reported 354 findings under ruff 0.16.4 against ~0 under CI's pinned 0.15.20). `select`
   makes the rule set a property of this file, not of whichever ruff happens to be installed.
2. ~~Carry the union of both files' intent.~~ **Done** — `C901`/`UP037` folded into the
   surviving `ignore` list with a comment explaining why.
3. **Done — with a genuine finding.** Ran the consolidated config; 172 errors, 153
   auto-fixable. Applying `--fix` (safe) then `--unsafe-fixes` (reviewed individually) cleared
   all but 3, each left with an inline `# noqa` explaining why: `ICommand`/`IQuery` (multiple
   inheritance order defeats ruff's PEP 695 autofix) and `IExtension` (its `TContext` is
   `contravariant=True`, which the unsafe-fix silently drops — PEP 695 infers variance rather
   than declaring it, confirmed by previewing the diff before applying).

   **The unsafe-fix for `UP045` corrupted working code once**, and this is worth keeping as a
   permanent caution about trusting autofixes near forward references: it turned
   `token: Optional["CancellationToken"] = None` in `interfaces/i_task_manager.py` into
   `token: "CancellationToken" | None = None` — a string literal ORed with `None`, which raises
   `TypeError` the moment anything calls `typing.get_type_hints()` on it. Under Python 3.14's
   deferred annotation evaluation this stayed invisible at import time; only
   `tests/test_all_modules_importable.py` (added earlier in this series) caught it, immediately,
   by forcing hint resolution. Fixed by quoting the whole union
   (`"CancellationToken | None"`) instead of just the class name. **Always diff an unsafe-fix
   near a quoted forward reference before trusting it — this is not hypothetical, it happened
   in this repo tonight.**
4. **Still open.** CI lints neither `examples/` nor `tools/` — the sample app
   `.agents/context/` documents as the reference implementation remains unlinted.
5. **Split out, 2026-08-23 — see [`TASK-032`](../completed/TASK-032_mypy_baseline_cleanup.md).** CI's mypy
   *is* red, independent of everything else in this task: confirmed by stashing tonight's
   changes and running `mypy sagittarius_engine tests --ignore-missing-imports
   --follow-imports=skip` against a clean `main` — 28 errors, before any of that night's edits.
   Re-verified today after `TASK-017`'s full close and `TASK-029`'s doc cleanup: still 27, same
   files, same lines — neither touched this set. 27 distinct type errors is too large and too
   varied a fix to be one requirement of a config task; `TASK-032` categorizes and triages all
   27, with `BUG-003` (already filed, 4 of the 27) called out to fix first.

   **Still this task's own scope:** getting the local toolchain to match CI's pins (`ruff
   0.15.20`, `mypy 2.1.0`) — undone. Local currently drifts (`ruff 0.16.4`, `mypy 2.3.1`).
6. `.agents/context/lint.md` still documents "the known 27 mypy errors" (added alongside this
   task's ruff fix) — update once `TASK-032` closes, per that file's own forward-reference.

## Priority

P2 — no runtime impact, but this is the linter itself being misconfigured, which quietly
degrades every other quality gate that depends on it.

## Category

Build / Tooling
