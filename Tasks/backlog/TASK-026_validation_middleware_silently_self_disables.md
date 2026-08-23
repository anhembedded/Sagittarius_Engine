# TASK-026: `PydanticValidationMiddleware` silently skips validation when hint resolution fails

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
