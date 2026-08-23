# TASK-026: `PydanticValidationMiddleware` silently skips validation when hint resolution fails

> **Closed 2026-08-23.** Requirement 1 done — `logging.getLogger(__name__)` in
> `pydantic_validation_middleware.py` logs at WARNING when `get_type_hints()` raises (names the
> handler and the exception) and at ERROR at the moment validation is actually skipped as its
> consequence, so the two can be traced together instead of vanishing. Requirement 2 done —
> policy chosen deliberately: **fail open, loudly**, not fail-closed. Reason: this middleware is
> typically installed globally across every command/query, not scoped to Pydantic-validated
> ones, so raising would break any handler whose `execute()` carries an unrelated unresolvable
> annotation even when it never intended Pydantic validation at all — an excessive blast radius
> for a library with consumers. Fail-closed-at-boot (option 3) would need a handler-registry/boot
> hook this per-call middleware pipeline doesn't have; out of scope here. Requirement 3 done —
> falls back to `inspect.signature(execute).parameters[...].annotation` (raw, unresolved) before
> giving up, mirroring `StdLibContainer`'s fallback. Requirement 4 done — added
> `test_auto_infers_model_class_from_resolvable_type_hints` (a path with zero prior coverage:
> every existing test set `model_class` explicitly) and two tests for the unresolvable-hint path,
> one proving the WARNING+ERROR pair fires and dispatch proceeds unvalidated, one proving a DTO
> that is already a `BaseModel` instance still gets validated despite the resolution failure
> (`tests/middleware/test_pydantic_validation_middleware.py`). The unresolvable-hint test
> reproduces the real bug shape — a name importable only under `TYPE_CHECKING`, real to mypy,
> undefined at runtime — rather than a plain undefined name, so it doesn't trip the mypy gate.
> Requirement 5 done — audited all three sites:
> `extensions/health/health_module.py`'s `boot()` had the same silent-swallow-of-a-whole-feature
> shape (logging *and* event-emission both vanished on any exception) and now logs via
> `logger.exception(...)` before continuing (still doesn't re-raise — a health check failing
> must not abort engine bootstrap); regression test added
> (`tests/test_edge_cases.py::test_health_module__boot_raises__logs_instead_of_swallowing_silently`).
> `extensions/health/health_check_query.py`'s two `try/except: pass` blocks (DB-session
> resolution, and the dynamic-registration scan) were judged **not** bugs of this pattern — both
> already surface their outcome through the returned status dict (`"not configured"` /
> `"database connection failed"` / etc.), so nothing is silently hidden; no code change made
> there, only the audit conclusion recorded here.
>
> Full gate run: `pre_commit.ps1` steps 1–2 (ruff lint, format) pass; step 3 (mypy) is
> pre-existing red (24 errors, none in a file this task touched — matches `TASK-021`'s tracked,
> untriaged baseline, confirmed by diffing against clean `main`) and halts the script before
> steps 4–5 run automatically, so those were run directly: `pytest tests/` — 698 passed, 2
> pre-failing (unrelated: a QML-warnings test and `.agents/context/repository.md`'s `sdk/`
> doc-staleness check, both confirmed pre-existing via `git stash`) — plus this task's own 5 new
> tests, all passing; `pytest tests/test_architecture.py` — 3 passed.

## Description

`sagittarius_engine/middleware/pydantic_validation_middleware.py:67-76`:

```python
if model_class is None:
    # Dynamically infer from the handler's execute method
    try:
        type_hints = typing.get_type_hints(cmd_or_query.execute)
        for hint in type_hints.values():
            if isinstance(hint, type) and issubclass(hint, BaseModel):
                model_class = hint
                break
    except Exception:
        pass

    if model_class is None:
        ...
```

If `get_type_hints()` raises, `model_class` stays `None` and **the request proceeds
unvalidated**. No log, no warning, no metric. A validation middleware that cannot determine
what to validate quietly decides to validate nothing.

## Why this fires in practice — it is not hypothetical

`typing.get_type_hints()` raises `NameError` whenever an annotation names something not
importable in the defining module's namespace. Two ways a normal handler hits that:

1. **The `TYPE_CHECKING` idiom** — which this engine's own interfaces use and which its
   architecture rules encourage for breaking circular imports. `IModule.register`,
   `IModule.boot`, `IModule.shutdown`, and `ITaskManager.spawn` all currently raise on
   `get_type_hints()` for exactly this reason (see `KNOWN_FORWARD_REF_MEMBERS` in
   `tests/test_all_modules_importable.py`). A user handler written the same way silently loses
   validation.
2. **A genuinely missing import** — the `ITaskHandle` bug found on 2026-08-23
   (`runtime/tasks/task_manager.py` annotated a return type it never imported). Under Python
   3.14's deferred annotations that bug is invisible at import time; it surfaces *only* through
   `get_type_hints()`. Here, the one place that would surface it swallows it.

The two failure modes compound: the bug that makes hints unresolvable is invisible at import,
and the code that would trip over it is silent.

## Contrast: the container gets this right

`infrastructure/container/std_container.py:194-215` faces the identical problem and handles it
properly — falls back to the raw `param.annotation`, and if it still cannot resolve, raises
`DependencyResolutionError` with the parameter name. Loud, actionable, no silent degradation.

That is the model to copy. The inconsistency between two engine components handling the same
failure is itself worth removing.

## Requirements

1. Do not swallow. At minimum log at `WARNING` with the handler class name and the exception,
   so an operator can see that validation was skipped for a given handler.
2. **Decide the policy deliberately, and write the reason down.** Options, in rough order of
   strictness:
   - *Fail closed* — raise, refusing to dispatch a request that cannot be validated. Safest;
     an unvalidated command reaching a handler is the thing this middleware exists to prevent.
   - *Fail open, loudly* — proceed but log a warning. Preserves current behaviour, removes the
     silence.
   - *Fail closed at boot* — resolve hints once when the handler registers, and refuse to
     start if a handler's hints are unresolvable. Turns a per-request silent skip into a
     startup error, which is where this class of problem belongs.
3. Mirror the container's fallback before giving up: try `param.annotation` / the raw
   `__annotations__` entry, so a `TYPE_CHECKING` forward reference does not by itself defeat
   inference.
4. Add tests for both paths: a handler whose hints resolve (validated), and a handler with an
   unresolvable forward-ref annotation (whatever policy 2 chooses, asserted explicitly).
5. Audit the other three `try/except/pass` blocks for the same pattern —
   `extensions/health/health_check_query.py:70`, `extensions/health/health_module.py:71`
   (a health extension that silently fails to report health is worse than none), and
   `extensions/health/health_module.py`'s emit path.

## Priority

**P1** — a validation layer that disables itself without saying so is worse than no validation
layer, because the system is documented and assumed to have one.

## Category

Middleware / Correctness

## Related

- [TASK-023](TASK-023_ci_matrix_hides_312_313_breakage.md) — the `ITaskHandle` bug and the
  Python-version blind spot that hid it.
- [TASK-025](../completed/TASK-025_dead_infrastructure_persistence_package.md) — the import/annotation guard
  test added alongside this finding.
