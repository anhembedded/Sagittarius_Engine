# BUG-019 — `QtEventBridge` made every subscriber a reference cycle, and the full suite crashed natively about one run in seven

**Reported date:** 2026-10-06
**Severity:** Medium. The full gate (`tests/` with `examples/student_management/tests/`) died with `Fatal Python error: Segmentation fault` in about 15% of runs, locally and on GitHub Actions, on `main` as well as on every branch. A crash in an unrelated test hides real results, and re-running until green teaches everyone to ignore it.
**Status:** ✅ Fixed (2026-10-06)
**Found by:** the reference consumer's `EPIC-033N` work (Engine PR #230), where the gate crashed on `6bfaba7` and on GitHub Actions; the PR #230 reviewer asked for it to be tracked rather than retried away.

---

## What is wrong

`QtEventBridge.on()` (`sagittarius_engine/extensions/pyside_mvc/mvc/qt_event_bridge.py`) stored, in the bridge's own `_forwarders`, a `forward` closure that captured the bridge, under a key holding the subscriber's bound method. A presenter owns its bridge (`BasePresenter._events`), so every bridge, and every presenter that subscribed through one, was a reference cycle. Python frees a cycle only when its collector runs, which happens on whichever thread allocates at that moment and at whatever point that thread is in. A presenter freed that way while it owned an active `QTimer` (the state console's `OverviewPresenter`, a 1 s age tick no test stopped) killed the UI thread inside Qt's event dispatch.

The example app's `RosterPresenter` subscribed on the raw bus (`self.event_bus.on`) instead of `self.subscribe`, a second cycle (presenter → container → bus → presenter) that also dragged its QML scene (`QQuickWidget`, `QQmlEngine`, `QQmlContext`) to the collector, and handlers that ran on the emitting thread.

## Evidence

- **Where it crashed.** Every crash was inside `pytestqt.plugin._process_events`, with 0 to 2 other threads alive. The five local crashes caught with test names fell in tests that use no Qt themselves (`test_ipc_queue_event_bus.py::test_inter_process_communication` twice, `test_sqlalchemy_student_repository.py` twice, `demo_faults/test_extension.py`); one more fell in `test_roster_screen.py::test_roster_screen_date_filter_narrows_visible_students`, and GitHub Actions' crash on `main` (run 37428664730) in `test_roster_screen.py` too. Leaked threads, `BUG-014`'s mechanism, were ruled out with a per-test thread census.
- **Rate.** 3 crashes in 20 runs of the gate's exact command on `be06cf4`.
- **The mechanism, in isolation.** A `QObject` owning an active `QTimer`, whose last reference is dropped on a worker thread while the UI thread processes events: segmentation fault 3 runs of 3. The same with the timer stopped: 3 of 3 clean.
- **The collector is the trigger.** With automatic collection off and `gc.collect()` run only between tests, 9 runs of 9 were clean (stopped by the session's time limit). On its own that is weak: at the base rate, 9 clean runs happen by chance about one time in four. It is supporting evidence; the isolated reproduction above and the 20-run result below are the proof.
- **What was in cycles.** A per-test scan of `gc.garbage` under `DEBUG_SAVEALL` found Qt objects left in cycles by 30 tests: `QtEventBridge` 22 times, presenters, view models, two `QTimer`s (one active, the `OverviewPresenter`'s), a `QThread`, and the roster's QML scene.

## Fix

- **`QtEventBridge`** holds nothing that refers back: a forwarder holds the bridge by `weakref.ref`, and a handler that is a bound method by `weakref.WeakMethod` (a method of an object that takes no weak reference, a function or a lambda is still held). A subscription is keyed by the method's object identity and function, so `off()` still finds it; a key whose object is gone and whose identity is reused is replaced, not taken for a duplicate.
- **Behaviour change:** a bus subscription no longer keeps its subscriber alive; whoever owns the subscriber does. A subscriber that is gone receives nothing.
- **`RosterPresenter`** subscribes through `self.subscribe`, so its handlers run on the UI thread and `dispose()` removes them.

## Regression tests

- `tests/extensions/pyside_mvc/test_qt_event_bridge.py::TestNoReferenceCycle`
  - `test_an_abandoned_bridge_is_freed_without_the_collector` and `test_a_subscriber_is_not_kept_alive_by_its_subscription`: **before**, red (the objects outlived their last reference with the collector off); **after**, green.
  - `test_a_freed_subscriber_receives_nothing`: **before**, red (the bus delivered to it); **after**, green.
  - `test_a_method_subscription_can_still_be_removed` and `test_a_method_of_an_object_without_weak_references_is_still_delivered`: the keyed and fallback paths.

## Verification

- Cycle scan after the fix: 18 tests leave Qt objects in cycles (was 30); no active `QTimer` among them.
- 20 runs of the gate's exact command after the fix, part of them under the extra load of the consumer's suite running alongside: 20 of 20 clean, 1732 passed each (before: 3 crashes in 20; the chance of 20 clean runs at the old rate is about 4%).
- The reference consumer's unit, integration and sanity tiers against this Engine: two tests that built an `OrderFeed` without keeping it relied on the bus to keep it alive; they now own it, as the app's desk does (`parent=`). That change, and the consumer's `engine.ref` bump to this fix, ship in the consumer's own pull request once this one merges; production code there needed no change.
- Review of this PR: a test now covers the identity-reuse branch (it fails when that branch is reduced to a bare `return`), and `.agents/context/events.md` §5 and `BasePresenter.subscribe()` state the lifetime contract.

## Not fixed here

- 18 tests still leave Qt objects in cycles, from presenters' own closures (FSM callbacks), `UIWatchdog`'s monitor thread and the roster tests' QML scene; none holds an active timer.
- **Inert forwarders stay on the bus.** When a bridge or a subscriber is freed without `off_all()`, its forwarder stays registered and returns at once on every emit. It holds nothing alive, so it cannot crash; it costs one call per emit until the bus goes. Removing it needs the bus to drop a handler from inside its own `emit()`, which no `IEventBus` promises today.
- The three `examples/student_management/tests/presentation/workbench/test_sample_shell.py` tests boot an `App` and never stop it, leaving a `Scheduler` and an `AsyncRuntime` thread each (thread census; `BUG-014`'s family). They run after every crash point seen, so they did not cause this crash.

## Related

- `BUG-014`: the earlier intermittent segfault, from leaked `Scheduler`/`AsyncRuntime` threads.
- `BUG-006`: QML teardown `TypeError`s from bindings reading a dead context object; the same family of a QML scene outliving what it binds to.
