# BUG-003 — `_get_logger()` declares `ILogger | None`, contradicting the contract it wraps

**Reported date:** 2026-08-23
**Severity:** Low (no runtime failure; produces 4+ false mypy errors and misleads readers)
**Status:** 🔴 Open

---

## 1. Symptom

`IEngineContext.logger` is declared to never be `None`, and says so explicitly in its own
docstring (`sagittarius_engine/interfaces/i_engine_context.py:63-66`):

```python
    def logger(self) -> ILogger:
        """
        @brief The Logger interface.
        @return ILogger instance (returns a NullLogger if logging module is disabled, guaranteeing it is never None).
```

The concrete implementation honours that (`kernel/context.py:94-100`) — on resolution failure it
returns a `NullLogger`, never `None`:

```python
    def logger(self) -> ILogger:
        try:
            return self.container.resolve(ILogger)
        except Exception:
            from sagittarius_engine.utils.null_logger import NullLogger
            return NullLogger()
```

But two private helpers that do nothing except return that value widen it back to optional:

| File | Line | Declaration |
| :--- | :--- | :--- |
| `kernel/dispatcher.py` | 17 | `def _get_logger(self) -> ILogger \| None:` |
| `kernel/bootstrap.py` | 14 | `def _get_logger(self) -> ILogger \| None:` |

Both bodies are a bare `return self.context.logger`.

## 2. Consequence

The code then immediately calls `.info()` / `.debug()` / `.error()` on the result without a
`None` check — correctly, because it genuinely cannot be `None`. mypy has no way to know that,
so it reports the calls as errors:

```
kernel/dispatcher.py:34: error: Item "None" of "ILogger | None" has no attribute "info"  [union-attr]
kernel/dispatcher.py:39: error: Item "None" of "ILogger | None" has no attribute "debug"  [union-attr]
kernel/dispatcher.py:48: error: Item "None" of "ILogger | None" has no attribute "debug"  [union-attr]
kernel/dispatcher.py:54: error: Item "None" of "ILogger | None" has no attribute "error"  [union-attr]
```

Four of the ~27 errors currently failing `scripts/ci-local.ps1`'s mypy step come from this one
wrong annotation, plus more from `bootstrap.py`. **Nothing is broken at runtime** — the calls
are safe and always have been. The defect is that the type says otherwise.

This is worth separating from the general mypy debt in `TASK-021` requirement 5 because it is
not a case of "code needs more types": the correct type is already known, documented, and
enforced one layer down. The annotation is simply wrong.

## 3. Why it matters beyond the error count

A reader (or an AI session) trusting the signature will conclude `context.logger` can be `None`
and add defensive `if logger:` guards that can never fire — dead branches that then need test
coverage they can never get. The contract is deliberately designed around the Null Object
pattern (`utils/null_logger.py`, `TASK-015`) precisely so callers *don't* have to null-check;
these annotations undo that design at the call site.

## 4. Fix

1. Narrow both to `-> ILogger`, matching `IEngineContext.logger`'s declared and implemented
   contract.
2. Re-run `pwsh ./scripts/ci-local.ps1` and record the new mypy error count — expect roughly
   27 → 22-ish. Confirm the drop comes only from these call sites and no new error appears.
3. `grep -rn "ILogger | None\|Optional\[ILogger\]" sagittarius_engine/` for any other place that
   widened the same guarantee.
4. Do **not** add null-checks to satisfy mypy instead — that would encode the wrong contract
   permanently and defeat the Null Object pattern this engine deliberately uses.

## 5. Category

Kernel / Typing

## 6. Related

- `TASK-021` requirement 5 — the remaining, genuinely-untriaged mypy debt. Sampled separately
  and found to be missing annotations (e.g. `base_presenter.self.fsm` assigned three different
  types across branches), which is real debt but a different kind of problem from this one.
- `TASK-015` (completed) — introduced the `NullLogger` guarantee these annotations contradict.
