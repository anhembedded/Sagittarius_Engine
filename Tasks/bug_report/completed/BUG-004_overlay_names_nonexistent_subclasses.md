# BUG-004 — `Overlay` tells users to instantiate two classes that do not exist

**Reported date:** 2026-08-24
**Severity:** Medium (an active false statement in a runtime error message a consumer will hit)
**Status:** ✅ Fixed — 2026-08-25
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

## Resolution — 2026-08-25

Closed by **writing the two classes**, requirement 1's recommended branch. The message keeps
naming them; they now exist.

- `widgets/overlays/confirm_overlay.py` — `ConfirmOverlay(Overlay)`: wrapped message body,
  Cancel/Confirm footer, `danger` flag selecting `DANGER_BUTTON` over `PRIMARY_BUTTON`.
  Confirm `accept()`s, Cancel `reject()`s.
- `widgets/overlays/picker_overlay.py` — `PickerOverlay(Overlay)` + `PickerItem`:
  `SelectableCard` rows in a list or an N-column grid, optional search field, `selected`
  property, `selection_changed` signal.
- Both exported from `widgets/__all__` (requirement 2). `setuptools.find_packages` picks the
  new subpackage up, so `scripts/verify_wheel_importable.py`'s CI job covers them.

**Requirement 3's regression test resolves the names out of the message itself** rather than
against a hardcoded list — `test_abstract_error_only_names_subclasses_that_exist` regexes
`\b([A-Z]\w*Overlay)\b` out of the raised `TypeError`, then asserts each one resolves on the
package, subclasses `Overlay`, and is in `__all__`. Reworded advice therefore cannot
reintroduce a phantom; only advice that resolves passes.

They live in `widgets/overlays/` rather than next to `Overlay` in `overlay.py` because that
file is one of `guards._BASE_DEFINITION_FILES`, which the bare-Qt-base guard skips wholesale —
a concrete subclass parked there would be exempt from the guard purely because of its address.

### Evidence

Requirement 4 asks for `pwsh ./scripts/ci-local.ps1`. **PowerShell is not installed in the
environment this was fixed in**, so the gate was run as its five steps directly, with the same
arguments `ci-local.ps1` passes (read out of the script, lines 199–266), on Python 3.12:

```text
ruff check sagittarius_engine tests examples tools          RC=0   All checks passed!
ruff format --check (widgets/ + its tests)                  RC=0
mypy ... --ignore-missing-imports --follow-imports=skip     RC=0   no issues in 394 files
pytest tests/ examples/student_management/tests/ ...        RC=0   1004 passed, 8 skipped
                                                                   coverage 89.46%
pytest tests/test_architecture.py                           RC=0   8 passed
```

Log: `logs/gate-final-081651.log`; grepped for `FAILED|ERROR|Traceback|SyntaxError` → 0 each.
Baseline before the change was 971 passed on the same interpreter.

Two things this fix deliberately does **not** do, recorded so they are not mistaken for
oversights:

- **`PickerOverlay` is single-select and does not close on choice.** Five of the app's six
  pickers `accept()` immediately, but its time-range picker must stay open when "custom" is
  chosen; a base that closed would need a flag to be told not to. Its indicator picker is
  multi-select with checkboxes and never closes — a different interaction, left as a candidate
  rather than guessed at.
- **The app's `ConfirmDialog`/`SymbolPickerDialog` are not migrated here.** They take an
  `on_confirm`/`on_symbol_chosen` callback and call `close()`, so `exec()` reports `Rejected`
  even on confirm. Rewiring those call sites is the consuming app's migration task
  (`EPIC-007E`/`007F`), not this repo's.

## Related

Tracked as work in the consuming app's epic
(`Sagittarius_Elite_Warrior/Tasks/epics/EPIC-007_chuan_hoa_card_dung_chung/incomplete/EPIC-007A_guard_va_overlay_con.md`),
but the **fix and its commit belong to this repo** — the two boards stay independent
(`.agents/ONBOARDING.md` §8).
