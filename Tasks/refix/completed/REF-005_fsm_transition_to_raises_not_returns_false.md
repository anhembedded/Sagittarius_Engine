# REF-005: `EPIC-007D`/`EPIC-007F` claim `transition_to()` returns `False`; it raises

- **Status**: ✅ Done 2026-08-27
- **Category**: Spec / Code Discrepancy
- **Found while**: designing `EnrolmentFlow`'s seeded illegal move for `EPIC-007D`

---

## 1. The disagreement

`EPIC-007D` §2.2's seed table and `EPIC-007F` §3.1 (verbatim, before this fix) both assert:

> `transition_to()` **returns `False` on an illegal transition and raises nothing.**

`sagittarius_engine/extensions/fsm/state_machine.py::BaseStateMachine.transition_to()`:

```python
if new_state not in allowed_targets:
    logger.error(
        f"FSM Error: Transition {old_state.name} -> {new_state.name} rejected."
    )
    raise InvalidStateTransitionError(old_state.name, new_state.name)
```

It logs, and it raises. `DeclarativeStateMachine.dispatch()` does the same
(`declarative_state_machine.py`). Neither method has ever returned `False` — both return
`True` only on a *successful* transition; there is no code path that returns `False`. This
was two documents describing behaviour that does not exist, not a disagreement between two
correct things.

## 2. Reconciliation

Kept the code. `logger.error` + a typed exception is the more informative contract — a caller
that wants "check first" already has `DeclarativeStateMachine.can_dispatch()`, which answers
without mutating state or raising; changing `transition_to()` to swallow the exception would
remove information from every existing caller to satisfy two documents that had not shipped
yet.

Corrected instead:

- `EPIC-007D` §2.2's table row now says `transition_to()` raises `InvalidStateTransitionError`,
  and that the demo catches it — the seed still produces "a rejected transition" for the
  future panel to show, it is just observed at a `try`/`except`, not a return value.
- `EPIC-007F` §3.1's justification is rewritten on the ground that actually holds: the
  exception is real, but nothing downstream of a handler currently does anything with it — the
  event bus's own failure isolation (`handler_reporting.py`) catches it, logs once, and it is
  otherwise lost. That is still the class of finding worth a panel for; the previous wording
  just described a defect the FSM does not have.
- `EPIC-007F` §6 criterion 4 corrected the same way: the panel's transition log has to observe
  a rejection by catching the exception at the call site the global callback cannot see,
  because the callback (`add_global_callback`) only fires on transitions that succeeded.

No code changed in `sagittarius_engine/extensions/fsm/` — this is a documentation-only
correction; `EPIC-007F` is not yet implemented, so nothing downstream depended on the wrong
description yet.

## Verified

| Gate | Result |
| :--- | :--- |
| Read `transition_to()`/`dispatch()` directly | both raise `InvalidStateTransitionError`, confirmed line-by-line, not from a summary |
| `grep -rn "returns \`False\`" Tasks/epics/EPIC-007_runtime_state_console/` | 2 hits, both inside this REF's own "previously said"/"originally claimed" correction text, not a live claim |
| `pytest tests/` — unaffected | this task changed no source under test |
