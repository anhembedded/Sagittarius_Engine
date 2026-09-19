# BUG-016 — `test_scheduler_sleep_time_fallback` races a leaked real `Scheduler` thread through a process-global mock

**Reported date:** 2026-09-19
**Severity:** Low (a test-isolation flake, surfaced only under `pytest -W error::pytest.PytestUnhandledThreadExceptionWarning`; does not fail the gate under its normal warning-only settings)
**Status:** 🔴 Open
**Found by:** re-investigating `BUG-014`'s reopening, while adding a regression test for the `Scheduler.start()` orphan gap found by independent PR review

---

## What is wrong

`tests/runtime/test_scheduler.py::test_scheduler_sleep_time_fallback` patches
`sagittarius_engine.runtime.scheduler.scheduler.datetime` — a **module-level**, process-global
attribute, not anything scoped to one `Scheduler` instance — and queues exactly two
`side_effect` values for `datetime.now()`. If any *other* `Scheduler` instance's real
`_run()` background thread (started by an earlier test via `.start()`) is still alive when
this test's `with patch(...)` block is active, that leaked thread's own `datetime.now()`
calls land on the same mock, and a third call (from the leaked thread, not this test) raises
`StopIteration` inside `unittest.mock`, which pytest reports as an unhandled thread exception:

```
Exception in thread SagittariusScheduler:
  File ".../scheduler.py", line 206, in _run
    now = datetime.now()
  File ".../unittest/mock.py", line 1195, in _execute_mock_call
    result = next(effect)
StopIteration
```

Reproduces only as part of the combined suite (`tests/runtime/scheduler/test_scheduler.py
tests/kernel/ tests/runtime/`, run under `-W error::pytest.PytestUnhandledThreadExceptionWarning`
to turn the normally-swallowed warning into a failure) — never in isolation
(`tests/runtime/test_scheduler.py` alone, 10/10 clean under the same `-W error`). Under pytest's
default settings this only ever prints a `PytestUnhandledThreadExceptionWarning`, so it does not
fail `ci-local.ps1`'s own gate, and it is not routed through the app's `"App"` logger, so
`ci-rule.md`'s `- (WARNING|ERROR|CRITICAL) -` log scan would not catch it either — the same way
`BUG-014`'s original segfault dodged that scan.

## Why it matters

This is a second, independent, directly-observed instance of the same family `BUG-014` describes:
a real background `Scheduler`/`AsyncRuntime` thread from one test outliving that test and reaching
into a later, unrelated one. Here the damage is limited to corrupting a mock's `side_effect`
queue rather than crashing the interpreter, but it is concrete evidence — caught in this repo's
own suite, not hypothesized — that background threads from `Scheduler`/`AsyncRuntime`-using tests
do sometimes survive past their own test's teardown under load, which is directly relevant to
`BUG-014`'s still-open question of why dozens of such threads end up alive simultaneously in a
full run.

## Requirements

1. Identify which earlier test's `.start()`ed thread is the one still alive when
   `test_scheduler_sleep_time_fallback` begins patching — add a thread census
   (`threading.enumerate()` naming `SagittariusScheduler`) around the suspect tests to confirm,
   rather than guessing from the crash dump alone.
2. Fix `test_scheduler_sleep_time_fallback` to not depend on `scheduler.py`'s module-level
   `datetime` being exclusively owned by this test — either scope the mock more narrowly, or
   have the test assert its own thread's isolation before patching a process-global name.
3. Separately, confirm or rule out whether the earlier test's own `.stop()` call is itself
   correctly joining (i.e., whether this is a second manifestation of a `stop()`-side leak, or a
   test merely leaving `scheduler._running = True` with no `stop()` call on some exit path).
4. Once fixed, re-run the combined suite under `-W error::pytest.PytestUnhandledThreadExceptionWarning`
   several times to confirm the race is actually closed, not just less likely to trigger.

## Related

- `BUG-014` — the segfault/leaked-thread report this was found while re-investigating; same
  family (a `Scheduler`/`AsyncRuntime` background thread outliving its own test), different
  symptom (a corrupted mock instead of a crash)
- `BUG-015` — another flake surfaced the same day while verifying a `BUG-014` fix, also filed
  separately rather than folded in
