# BUG-020 — The example app's sample-shell tests leave a running `App` behind

**Reported date:** 2026-10-06
**Severity:** Low. Each leaked `App` is a `SagittariusScheduler` thread and an `AsyncRuntimeLoop` thread that live to the end of the process; three of them do not fail anything, but they are the `BUG-014` family, which crashed the full suite.
**Status:** ✅ Fixed (2026-10-06)
**Found by:** a per-test thread census (the approach `BUG-014` describes) over `examples/student_management/tests/`.

---

## What is wrong

`examples/student_management/tests/presentation/workbench/test_sample_shell.py` built its config through `build_app()`, which boots a real `App` (scheduler and async-runtime threads), kept only the `IConfig` and dropped the app without calling `app.stop()`. All three tests did this:

- `test_the_sample_window_has_the_standard_menus_and_its_mode`
- `test_the_options_page_applies_to_the_config`
- `test_tools_options_opens_with_the_general_page`

## Evidence

Census of `SagittariusScheduler` / `AsyncRuntimeLoop` threads still alive after each test, before the fix:

```
test_the_sample_window_has_the_standard_menus_and_its_mode: ['AsyncRuntimeLoop', 'SagittariusScheduler']
test_the_options_page_applies_to_the_config: ['AsyncRuntimeLoop', 'SagittariusScheduler']
test_tools_options_opens_with_the_general_page: ['AsyncRuntimeLoop', 'SagittariusScheduler']
```

After the fix, all three lists are empty.

## Fix

The file's `_config(tmp_path)` helper became a `config` fixture that yields the `IConfig` and calls `app.stop()` in teardown, so the app stops even when the test fails. (`tests/conftest.py`'s `app_factory` is not visible to `examples/`, and these tests need `build_app()`'s wiring, not a bare `App`.)

## Regression test

An autouse fixture, `no_leaked_runtime_threads`, in `examples/student_management/tests/conftest.py` fails any test under that directory that leaves a new `SagittariusScheduler` or `AsyncRuntimeLoop` thread running, so the next test that boots an `App` and forgets it is caught, not just these three. `test_runtime_thread_guard.py` tests the guard's own check (reports a live runtime thread, ignores an unrelated one).

With the `app.stop()` removed from the `config` fixture, the guard errors exactly those three tests and no other in the example suite (69 passed, 3 errors); with it, all pass.
