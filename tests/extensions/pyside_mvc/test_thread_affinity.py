"""Tests for @ui_mutator / unprotected_mutators (BOT-068, Sagittarius-Engine
"lớp lỗi A").

BUG-001 (Sagittarius Elite Warrior) is the real case this closes: a
background thread mutated Qt/QML-bound state directly (not through a
Signal), which only crashed once a `Behavior on width` animation made QML
need to start an internal `QTimer` from that same wrong thread —
`QBasicTimer::start: Timers cannot be started from another thread`. `@Slot`
alone doesn't catch this class: a queued Signal->slot connection already
marshals correctly regardless of `@Slot`; what's actually unprotected is a
background thread calling the method *directly*, bypassing Signal/emit
entirely — which is exactly what these tests exercise.

Deliberately uses REAL `threading.Thread`s, not a mocked/synchronous stand-in
— IThreadManager is a genuine ThreadPoolExecutor in the real app
(sagittarius_engine/infrastructure/thread_manager.py), and a synchronous
mock would make every cross-thread test here pass by construction, the same
trap test_dev_board_async_race_conditions.py's own docstring documents.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading
import time

from PySide6.QtCore import QObject, Signal, Slot

from sagittarius_engine.extensions.pyside_mvc.safety.thread_affinity import (
    CrossThreadUiMutationError,
    get_off_thread_mutation_count,
    not_a_ui_mutator,
    reset_off_thread_mutation_count,
    set_thread_affinity_dev_mode,
    ui_mutator,
    unprotected_mutators,
)


class _Target(QObject):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.value: int | None = None
        self.called_from_thread: threading.Thread | None = None

    @ui_mutator
    def set_value(self, value: int) -> None:
        self.value = value
        self.called_from_thread = threading.current_thread()


def setup_function() -> None:
    # Global dev-mode flag (see thread_affinity.py's own module docstring
    # for why it's process-wide) — reset before every test so one test's
    # mode can't leak into the next. The off-thread-mutation counter is the
    # same kind of process-wide state, reset for the same reason.
    set_thread_affinity_dev_mode(False)
    reset_off_thread_mutation_count()


def teardown_function() -> None:
    set_thread_affinity_dev_mode(False)
    reset_off_thread_mutation_count()


def test_a_same_thread_call_runs_synchronously_and_returns_normally() -> None:
    target = _Target()

    target.set_value(42)

    assert target.value == 42
    assert target.called_from_thread is threading.current_thread()


def test_dev_mode_raises_cross_thread_uimutation_error_from_a_real_thread() -> None:
    set_thread_affinity_dev_mode(True)
    target = _Target()
    caught = []

    def call_from_background() -> None:
        try:
            target.set_value(1)
        except CrossThreadUiMutationError as exc:
            caught.append(exc)

    worker = threading.Thread(target=call_from_background)
    worker.start()
    worker.join(timeout=5)

    assert len(caught) == 1
    assert "set_value" in str(caught[0])
    # Must not have mutated anything — the call was rejected, not deferred.
    assert target.value is None


def test_production_mode_does_not_raise_and_marshals_onto_the_main_thread(
    qapp,
) -> None:
    set_thread_affinity_dev_mode(False)
    target = _Target()
    main_thread = threading.current_thread()
    raised = []

    def call_from_background() -> None:
        try:
            result = target.set_value(7)
        except Exception as exc:  # noqa: BLE001
            raised.append(exc)
        else:
            assert result is None  # deferred call has no synchronous result

    worker = threading.Thread(target=call_from_background)
    worker.start()
    worker.join(timeout=5)

    assert raised == []
    # The call was deferred (QTimer.singleShot), so it hasn't run yet right
    # after join() — pump the event loop until it has, same technique
    # verified against this exact PySide6 build before writing this decorator.
    deadline = time.monotonic() + 2.0
    while target.value is None and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)

    assert target.value == 7
    assert target.called_from_thread is main_thread


def test_a_same_thread_call_does_not_count_as_an_off_thread_mutation() -> None:
    target = _Target()

    target.set_value(42)

    assert get_off_thread_mutation_count() == 0


def test_dev_mode_raise_still_counts_the_violation() -> None:
    """The counter tracks the violation itself, not which branch handles
    it -- `EPIC-007F` §4 reports dev-mode and production the same way."""
    set_thread_affinity_dev_mode(True)
    target = _Target()

    worker = threading.Thread(target=lambda: _try(target.set_value, 1))
    worker.start()
    worker.join(timeout=5)

    assert get_off_thread_mutation_count() == 1


def test_production_marshaling_counts_the_violation_too(qapp) -> None:
    set_thread_affinity_dev_mode(False)
    target = _Target()

    worker = threading.Thread(target=lambda: target.set_value(7))
    worker.start()
    worker.join(timeout=5)

    assert get_off_thread_mutation_count() == 1

    # Drain the deferred call so it doesn't leak into the next test.
    deadline = time.monotonic() + 2.0
    while target.value is None and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)


def test_two_cross_thread_calls_count_twice() -> None:
    set_thread_affinity_dev_mode(True)
    target = _Target()

    for _ in range(2):
        worker = threading.Thread(target=lambda: _try(target.set_value, 1))
        worker.start()
        worker.join(timeout=5)

    assert get_off_thread_mutation_count() == 2


def _try(func, *args) -> None:
    try:
        func(*args)
    except CrossThreadUiMutationError:
        pass


class _ScanTargetBase(QObject):
    def __init__(self) -> None:
        super().__init__()

    def set_inherited_unprotected(self, v) -> None:
        pass


class _ScanTarget(_ScanTargetBase):
    # A Signal is itself callable at the class level (that's how
    # `Signal(int, str)` works) — verified against the real app's
    # DataManagementViewModel.clearDataRequested, whose name alone matched
    # the "clear" prefix and false-positived before this was excluded.
    clearSomethingRequested = Signal()

    def __init__(self, required: str) -> None:
        # Deliberately takes a required constructor arg — unprotected_mutators
        # must not need to actually construct this class the normal way.
        super().__init__()
        self.required = required

    @Slot(int)
    def set_via_slot(self, v: int) -> None:
        pass

    @ui_mutator
    def set_via_ui_mutator(self, v) -> None:
        pass

    @not_a_ui_mutator
    def set_explicitly_opted_out(self, v) -> None:
        pass

    def set_unprotected(self, v) -> None:
        pass

    def append_unprotected(self, v) -> None:
        pass

    def clear_unprotected(self) -> None:
        pass

    def hide_unprotected(self) -> None:
        pass

    def not_a_mutator_by_name(self) -> None:
        pass

    def _set_private_is_not_scanned(self, v) -> None:
        pass


def test_scanner_flags_every_unprotected_mutator_prefix() -> None:
    unprotected = unprotected_mutators(_ScanTarget)

    assert set(unprotected) == {
        "set_unprotected",
        "append_unprotected",
        "clear_unprotected",
        "hide_unprotected",
        "set_inherited_unprotected",
    }


def test_scanner_does_not_flag_a_slot_decorated_method() -> None:
    assert "set_via_slot" not in unprotected_mutators(_ScanTarget)


def test_scanner_does_not_flag_a_ui_mutator_decorated_method() -> None:
    assert "set_via_ui_mutator" not in unprotected_mutators(_ScanTarget)


def test_scanner_respects_the_explicit_opt_out_marker() -> None:
    assert "set_explicitly_opted_out" not in unprotected_mutators(_ScanTarget)


def test_scanner_ignores_methods_that_do_not_match_the_mutator_prefixes() -> None:
    assert "not_a_mutator_by_name" not in unprotected_mutators(_ScanTarget)


def test_scanner_ignores_private_methods() -> None:
    assert "_set_private_is_not_scanned" not in unprotected_mutators(_ScanTarget)


def test_scanner_does_not_flag_a_signal_whose_name_matches_a_mutator_prefix() -> None:
    """A `Signal` is itself callable at the class level — must not be
    mistaken for an unprotected method just because its name starts with
    `clear`/`set_`/etc."""
    assert "clearSomethingRequested" not in unprotected_mutators(_ScanTarget)


def test_scanner_never_constructs_the_class_the_normal_way() -> None:
    """`_ScanTarget.__init__` requires an argument — if the scanner tried
    calling it normally this would raise TypeError before ever returning."""
    unprotected_mutators(_ScanTarget)  # must not raise
