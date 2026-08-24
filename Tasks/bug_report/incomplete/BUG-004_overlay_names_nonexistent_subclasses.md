# BUG-004 — `Overlay` tells users to instantiate two classes that do not exist

**Reported date:** 2026-08-24
**Severity:** Medium (an active false statement in a runtime error message a consumer will hit)
**Status:** 🔴 Open
**Found by:** cross-repo widget audit for `Sagittarius_Elite_Warrior`'s `EPIC-007`

---

## What is wrong

`extensions/pyside_mvc/widgets/overlay.py` names `ConfirmOverlay` and `PickerOverlay` twice —
once in the class docstring (line 18) and once in the `TypeError` a consumer actually sees:

```python
raise TypeError(
    "Overlay is abstract — instantiate a subclass (e.g. "
    "ConfirmOverlay, PickerOverlay)."
)
```

Neither class exists anywhere in the shipped package. `grep -rn "ConfirmOverlay\|PickerOverlay"`
over the whole repo returns only `tests/extensions/pyside_mvc/widgets/test_overlay.py`, which
defines a **test-local** `_ConfirmOverlay`, and one string inside `test_guards.py`.

So a consumer who hits the abstract-instantiation guard is told, by the engine itself, to go
use an API that was never written.

## Why it counts as a BUG, not a TASK

Per `Tasks/bug_report/README.md`'s own rule of thumb: **BUG = something is wrong, or states
something untrue about the code**. The borderline call already settled in that file is the exact
match — *"a docstring naming a class that doesn't exist is a BUG (an active false statement)"*
(`BUG-001` set that precedent).

## Requirements

1. Decide and record which way this is closed: **write the two classes**, or **stop naming
   them**. Do not do both halves silently.
2. If writing them (recommended — `Sagittarius_Elite_Warrior` has 9 real consumers waiting:
   `ConfirmDialog` + `CriticalErrorDialog` for `ConfirmOverlay`; `SymbolPickerDialog` + 6
   Backtest pickers for `PickerOverlay`), then one file per class under
   `widgets/overlays/`, and both must appear in `widgets/__all__`.
3. Regression test: the `TypeError` message must only name symbols that resolve.
4. `pwsh ./scripts/ci-local.ps1` green — paste the `===CI_LOCAL_RESULT===` block and the log path.

## Related

Tracked as work in the consuming app's epic
(`Sagittarius_Elite_Warrior/Tasks/epics/EPIC-007_chuan_hoa_card_dung_chung/incomplete/EPIC-007A_guard_va_overlay_con.md`),
but the **fix and its commit belong to this repo** — the two boards stay independent
(`.agents/ONBOARDING.md` §8).
