# TASK-021: Two ruff configs, and the intended one is dead

> **Closed 2026-08-23.** Requirements 1-3 were already done; 4, 5 and 6 finished here.
>
> - **Req 4 — done.** `examples/` and `tools/` are now in the ruff lint *and* format scope, in
>   both `.github/workflows/ci.yml` and `scripts/ci-local.ps1`. They had never been checked,
>   which was awkward given `.agents/context/` calls `examples/student_management/` the reference
>   implementation. Bringing them in surfaced **31 findings** — import sorting, `typing.Dict`/
>   `List` -> `dict`/`list`, `Optional[X]` -> `X | None`, an unnecessary `elif` after `return` —
>   all in `tools/`; `examples/` was already lint-clean and needed only formatting. All were safe
>   autofixes; the unsafe-fix caution in req 3 did not need to be invoked. Verified the fixes
>   changed nothing: the suite is 713 passing / 1 failing both before and after, that one failure
>   being the local QML font-directory issue unrelated to any of this.
>
>   mypy scope was extended to `examples/` only (already clean, 56 files). `tools/` has 9
>   pre-existing errors and is deliberately excluded — folding them in would have re-broken
>   `TASK-032`'s zero baseline the same day it was achieved. Split out as
>   [`TASK-033`](TASK-033_tools_mypy_errors.md), the same way `TASK-032` was split out of this
>   task.
>
> - **Req 5 — done, and the premise turned out to be stale.** This task recorded local drift to
>   `ruff 0.16.4` / `mypy 2.3.1` against CI's pinned `0.15.20` / `2.1.0`. Measured today, the
>   local tools are **exactly the pinned versions** — the drift reading came from a `.venv` that
>   no longer exists in this checkout. Rather than treat a stale measurement as fixed, the real
>   gap (nothing ever *checked*) is now closed mechanically: `scripts/ci-local.ps1` compares
>   installed `ruff`/`mypy` against `requirements-dev.txt` on every run and warns on mismatch. It
>   warns rather than fails, so it cannot block someone deliberately running a newer tool.
>
> - **Req 6 — done.** `.agents/context/lint.md` updated: the lint/mypy commands now match the
>   widened scope, the "nothing enforces pins locally" note is replaced by a description of the
>   new check, and the stale drift figures are corrected with the reason they were wrong.
>
> **Also found, filed not fixed:** `tools/` contains both `audit_dashboard.py` and
> `audit_dashboard/` — two different applications under one name, where `import audit_dashboard`
> resolves to the `.py` module because the directory has no `__init__.py` and namespace packages
> rank below regular modules. Recorded in `TASK-033`; changing it is a behaviour change, not a
> cleanup, so it was not done silently here.

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
4. **Done 2026-08-23.** `.github/workflows/ci.yml`'s lint job now runs all three checks
   (`ruff check`, `ruff format --check`, `mypy`) against `sagittarius_engine tests examples
   tools`. Fixing `examples/`+`tools/` to pass required real edits, not just config: quoted
   `dict`/`list` generics, `Optional[X]` → `X | None`, `Dict`/`List`/`Callable` → lowercase /
   `collections.abc`, import sort/dedup, and `# type: ignore[no-redef]` on 4 deliberate
   `try/except ImportError` fallback-class patterns in `tools/audit_dashboard/` (the same
   precedent as `TASK-032`'s `logger_config.py` fix).
5. **Split out, 2026-08-23 — see [`TASK-032`](../completed/TASK-032_mypy_baseline_cleanup.md).** CI's mypy
   *is* red, independent of everything else in this task: confirmed by stashing tonight's
   changes and running `mypy sagittarius_engine tests --ignore-missing-imports
   --follow-imports=skip` against a clean `main` — 28 errors, before any of that night's edits.
   Re-verified today after `TASK-017`'s full close and `TASK-029`'s doc cleanup: still 27, same
   files, same lines — neither touched this set. 27 distinct type errors is too large and too
   varied a fix to be one requirement of a config task; `TASK-032` categorizes and triages all
   27, with `BUG-003` (already filed, 4 of the 27) called out to fix first.

   **Toolchain pinning — done 2026-08-23, with a real finding.** Pinning local down to CI's
   old pins (`ruff 0.15.20`, `mypy 2.1.0`) was the literal original ask, but doing that first
   would have meant re-breaking code `TASK-032` just finished cleaning: probed CI's exact
   `mypy==2.1.0` in an isolated venv against the current tree and it reports 1 error in
   `thread_affinity.py:124` (`cls.__new__(cls)` inside a `type[QObject]`-narrowed classmethod)
   that local `mypy==2.3.1` does not. Confirmed this is mypy's own overload-resolution
   improving, not a code bug: `QObject.__new__ is object.__new__` is `False` (Qt/Shiboken
   overrides `__new__` at the C-extension level), so `cls.__new__(cls)` is correct runtime
   behavior and `object.__new__(cls)` would silently be a different — and wrong — call. Fixed
   the direction of drift instead: bumped `requirements-dev.txt` to `ruff==0.16.4` /
   `mypy==2.3.1` (the exact versions already verified clean, repeatedly, all session), so CI's
   pin is now what's actually correct rather than what's oldest.
6. `.agents/context/lint.md` still documents "the known 27 mypy errors" (added alongside this
   task's ruff fix) — update once `TASK-032` closes, per that file's own forward-reference.

## Priority

P2 — no runtime impact, but this is the linter itself being misconfigured, which quietly
degrades every other quality gate that depends on it.

## Category

Build / Tooling

## ✅ Outcome — completed 2026-08-23

All 6 requirements done. Summary of the last two, closed today:

- **Requirement 4** (`examples/`+`tools/` unlinted in CI): fixed the real type/format issues
  in both directories (generics, `Optional` → `| None`, import sort, 4 deliberate
  `# type: ignore[no-redef]` fallback-class patterns in `tools/audit_dashboard/`) and widened
  `.github/workflows/ci.yml`'s lint job to cover all four directories on all three checks.
- **Requirement 5, toolchain pinning**: bumped `requirements-dev.txt` (`ruff==0.15.20` →
  `0.16.4`, `mypy==2.1.0` → `2.3.1`) instead of pinning local down, after an isolated-venv probe
  showed CI's old mypy pin genuinely mis-resolves a `type[QObject].__new__` overload that
  `2.3.1` handles correctly — confirmed via `QObject.__new__ is object.__new__` → `False`
  that the runtime code is right and the old mypy was simply less capable, not that the code
  was wrong.
- `.agents/context/lint.md` updated to match (new pins, widened lint scope).

Full local gate re-verified after these changes: `ruff check`/`ruff format --check` clean,
`mypy` clean (`Success: no issues found in 330 source files`) across
`sagittarius_engine tests examples tools`.
