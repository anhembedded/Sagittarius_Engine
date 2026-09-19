# BUG-015 — `UiStateCoordinator`'s debounce-restart test intermittently fails under full-suite load

**Reported date:** 2026-09-19
**Severity:** Low (a test flake, not a product defect — no evidence the underlying `QTimer` restart
behavior itself is wrong)
**Status:** 🔴 Open
**Found by:** verifying `BUG-014`'s fix, unrelated to that bug's own mechanism

---

## What is wrong

`tests/extensions/ui_state/test_ui_state_coordinator.py::test_marking_again_restarts_the_window_instead_of_letting_it_run_out`
failed once during a full `pwsh scripts/ci-local.ps1` run:

```
assert after > before, "the second mark must reset the countdown, not ride it out"
AssertionError: the second mark must reset the countdown, not ride it out
assert 1900 > 1900
```

`before` and `after` are two `QTimer.remainingTime()` reads, taken immediately before and after a
second `coordinator.mark_dirty(contributor)` call that is supposed to restart a 2000ms single-shot
debounce timer. The test's own docstring already documents a *previous* rewrite away from a
wall-clock-racing version of this same test (`qtbot.wait()` sleeps, three marks, one write) —
exactly the class of full-suite-load sensitivity this failure is another instance of, just in the
rewritten version.

## Reproduction

Reproduces only under load, not in isolation:

| Run | Result |
| :-- | :--- |
| Inside `pwsh scripts/ci-local.ps1`'s full suite (2026-09-19, `logs/ci-local-20260919-104944.log`) | **FAILED** — `assert 1900 > 1900` |
| `pytest tests/extensions/ui_state/test_ui_state_coordinator.py::test_marking_again_restarts_the_window_instead_of_letting_it_run_out -q`, run 5× in immediate succession, isolated | 5/5 passed |

## Why it matters

Millisecond-resolution `QTimer.remainingTime()` reads taken microseconds apart are exactly the kind
of comparison a loaded CI runner can round to the same value even when the underlying restart did
happen correctly — the test's own `before`/`after` gap (`debounce_ms=2000`, "far wider than any
plausible scheduling delay" per its own comment) was sized against normal load, not against a
full-suite run sharing the CPU with ~1400 other tests. Not yet established whether this is a real
timer-restart defect surfacing only under contention, or purely a test-resolution artifact — that is
exactly what needs investigating before writing a fix, not assumed.

## Requirements

1. Determine whether `QTimer.start()` on a running single-shot timer (the mechanism the test
   documents in its own docstring, design §5.6.6 row 8) can genuinely fail to restart under load, or
   whether this is purely `remainingTime()`'s millisecond rounding producing a false negative.
2. If it's a rounding/resolution artifact: widen the margin the test asserts on (e.g. assert
   `after >= before` is too weak — it wouldn't have caught a real non-restart — so the fix needs a
   sturdier signal than a wider `>`, such as asserting the timer's `isActive()` state transition or
   an explicit `timeout.connect()` call count, not just tightening the existing comparison).
3. If it's a genuine restart defect under contention: root-cause against `UiStateCoordinator`'s own
   `mark_dirty()`/timer-management code, not just the test.
4. Once fixed, re-run inside the full gate (not just in isolation) several times, since the failure
   is itself load-dependent and did not reproduce in isolation here.

## Related

- `BUG-014` — unrelated bug whose own fix-verification runs surfaced this; not the same mechanism
  (that bug was `Scheduler`/`AsyncRuntime` thread lifecycle, this is a Qt timer test's own
  resolution assumption)
- The test's own docstring — records an earlier, different flake in the same test that was already
  fixed once (wall-clock racing removed in favor of reading `remainingTime()` directly); this is a
  second, distinct flake surfacing in the replacement
