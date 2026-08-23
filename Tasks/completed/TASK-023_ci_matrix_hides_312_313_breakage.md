# TASK-023: CI's single-version matrix is the blind spot, not the version range

> **Resolved in part, 2026-08-23.** The owner confirmed 3.14 is the real target, so the
> version *range* problem is closed: `requires-python` is now `">=3.14"`, the 3.12/3.13
> classifiers are gone, and readme says "Python 3.14 or higher". CI's 3.14-only matrix is
> now correct rather than negligent. What remains is requirement 3 below — the missing
> guard — plus the record of how the bug hid. Priority dropped P1 → P3.

> **Fully closed 2026-08-23.** Requirement 4 ("keep the rule") is now written down in
> `.agents/rules/release.md` §3, in the release rule where a version-floor change actually
> gets decided — not a standalone note that would need its own routing. It states the rule
> plainly (a `requires-python` change must land with a matching CI matrix entry, in the same
> change) and carries this task's own `ITaskHandle` story as the cited evidence for why.

## Description

`pyproject.toml` declares:

```toml
requires-python = ">=3.12"
"Programming Language :: Python :: 3.12",
"Programming Language :: Python :: 3.13",
"Programming Language :: Python :: 3.14",
```

`readme.md` repeats it: *"Python 3.12 or higher (3.12, 3.13, 3.14)"*.

The CI test matrix is:

```yaml
matrix:
  os: [ubuntu-latest, windows-latest]
  python-version: ["3.14-dev"]        # .github/workflows/ci.yml
```

**Two of the three declared-supported versions are never tested.** `.agents/context/build.md`
described this job as running "multiple Python versions", which was also wrong and has been
corrected.

## The bug this hid (already fixed, 2026-08-23)

`sagittarius_engine/runtime/tasks/task_manager.py:244` annotated a method with a name it never
imported:

```python
from sagittarius_engine.interfaces.i_task_manager import ITaskManager   # ITaskHandle missing
...
def get_active_tasks(self) -> list[ITaskHandle]:                        # NameError source
```

The file has no `from __future__ import annotations`. Under **PEP 649**, which landed as the
default in Python 3.14, annotations are lazily evaluated — so on 3.14 the module imports fine
and the test suite passes. Under **Python 3.12 and 3.13, annotations are evaluated eagerly at
`def` time**, so importing this module raises `NameError` outright.

`task_manager` is not incidental: `app.boot()` imports it (via `kernel/context.py`). Verified:

```
after app.boot() -> 'sagittarius_engine.runtime.tasks.task_manager' in sys.modules == True
```

So on Python 3.12/3.13 the engine's single most fundamental call almost certainly failed at
import. Nobody noticed for as long as the CI matrix has been 3.14-only.

Evidence the annotation genuinely did not resolve (run on 3.14, evaluating in the module's own
namespace — exactly what 3.12 does at `def` time):

```
NameError when resolving annotation: name 'ITaskHandle' is not defined
```

The one-line import fix is applied. **The systemic hole is not**, and that is what this task is
for.

## Requirements

1. ~~Expand the CI matrix to cover the declared range.~~ **Done differently:** the declared
   range was narrowed to match CI instead. `requires-python = ">=3.14"`, classifiers trimmed,
   readme updated.
2. ~~Run the suite on 3.12 and fix what surfaces.~~ **Not applicable** — 3.12 is no longer
   supported.
3. **Still open — keep the guard.** `tests/test_all_modules_importable.py` now imports every
   module and forces `typing.get_type_hints()` on the public interfaces, which is what makes
   this bug class visible *without* needing a multi-version matrix. Verified it catches a
   reintroduced `ITaskHandle`-shaped bug. If the supported range ever widens again, run that
   test across the matrix rather than relying on the suite passing on one version.
4. **Keep the rule, not just the fix:** any future widening of `requires-python` must come with
   a CI matrix entry for the new floor in the same change. A declared version that CI never
   exercises is a claim, not a support commitment — that is the whole lesson here.
5. `.agents/context/build.md`'s pipeline description was corrected on 2026-08-23.

## Priority

**P3.** Downgraded from P1 once the version range was narrowed to 3.14. Kept open for
requirement 4 (the rule) and as the written record of how a one-line missing import went
unnoticed — that record is why `tests/test_all_modules_importable.py` exists.

## Category

CI / Compatibility

## Related

- [TASK-020](TASK-020_ci_benchmark_job_stale_path.md) — also a CI job that silently wasn't doing
  its job. Same theme: a green check that doesn't mean what it looks like.
- [TASK-021](TASK-021_ruff_config_shadowing.md) — mypy is what caught this, and mypy's own
  findings are currently unreviewed.
