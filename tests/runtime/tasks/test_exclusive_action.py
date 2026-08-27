"""Tests for ExclusiveAction (BOT-069, Sagittarius-Engine "lớp lỗi D").

BOT-027 (Sagittarius Elite Warrior) fixed a real race condition -- clicking
"Load History" twice before the first click finished fed the same candle
batch into the same indicator instances twice -- with a hand-rolled
`historyLoading` boolean plus an FSM check, duplicated at the top of every
entry point that needed the guard. It works, but the pattern doesn't
generalize: a third entry point added later has to remember to copy both
checks and the reset-in-finally by hand. ExclusiveAction is that pattern
turned into a primitive.

Deliberately uses a REAL ThreadManager (ThreadPoolExecutor-backed), not a
mocked/synchronous submit -- a synchronous mock would make every
single-flight assertion here pass by construction regardless of whether the
lock actually works, the same trap
test_dev_board_async_race_conditions.py's own docstring documents.
"""

import threading
import time
from concurrent.futures import Future
from unittest.mock import MagicMock

import pytest

from sagittarius_engine.infrastructure.thread_manager import ThreadManager
from sagittarius_engine.runtime.tasks.exclusive_action import ExclusiveAction


@pytest.fixture
def thread_manager():
    manager = ThreadManager(max_workers=4)
    yield manager
    manager.shutdown(wait=True)


def test_try_start_reserves_the_slot_when_free(thread_manager) -> None:
    action = ExclusiveAction(thread_manager=thread_manager)

    assert action.try_start("load_history") is True
    assert action.is_running("load_history") is True


def test_try_start_rejects_a_second_call_for_the_same_key(thread_manager) -> None:
    action = ExclusiveAction(thread_manager=thread_manager)
    action.try_start("load_history")

    assert action.try_start("load_history") is False


def test_try_start_rejects_a_different_key_sharing_the_same_instance(
    thread_manager,
) -> None:
    """This IS the cross-key exclusion group requirement: two keys on the
    same ExclusiveAction instance are mutually exclusive, mirroring
    TC-ASY-03 (Load History running blocks Start Live, and vice versa)."""
    action = ExclusiveAction(thread_manager=thread_manager)
    action.try_start("load_history")

    assert action.try_start("start_stream") is False


def test_finish_releases_the_slot_so_a_new_key_can_start(thread_manager) -> None:
    action = ExclusiveAction(thread_manager=thread_manager)
    action.try_start("load_history")

    action.finish("load_history")

    assert action.is_running() is False
    assert action.try_start("start_stream") is True


def test_finish_is_a_no_op_for_a_key_that_does_not_hold_the_slot(
    thread_manager,
) -> None:
    action = ExclusiveAction(thread_manager=thread_manager)
    action.try_start("load_history")

    action.finish("start_stream")  # never held it

    assert action.is_running("load_history") is True


def test_submit_runs_the_task_on_a_real_background_thread(thread_manager) -> None:
    action = ExclusiveAction(thread_manager=thread_manager)
    action.try_start("load_history")
    main_thread = threading.current_thread()
    result = {}

    def task() -> None:
        result["thread"] = threading.current_thread()

    future = action.submit("load_history", task)
    future.result(timeout=5)

    assert result["thread"] is not main_thread


def _do_nothing() -> None:
    pass


def test_submit_releases_the_slot_after_the_task_completes(thread_manager) -> None:
    action = ExclusiveAction(thread_manager=thread_manager)
    action.try_start("load_history")

    future = action.submit("load_history", _do_nothing)
    future.result(timeout=5)

    assert action.is_running() is False


def test_submit_releases_the_slot_even_when_the_task_raises(thread_manager) -> None:
    action = ExclusiveAction(thread_manager=thread_manager)
    action.try_start("load_history")

    def failing_task() -> None:
        raise ValueError("boom")

    future = action.submit("load_history", failing_task)
    with pytest.raises(ValueError, match="boom"):
        future.result(timeout=5)

    assert action.is_running() is False


def test_submit_passes_args_and_kwargs_through_to_the_task(thread_manager) -> None:
    action = ExclusiveAction(thread_manager=thread_manager)
    action.try_start("load_history")
    received = {}

    def task(a, b, keyword=None) -> None:
        received["a"] = a
        received["b"] = b
        received["keyword"] = keyword

    future = action.submit("load_history", task, 1, 2, keyword="three")
    future.result(timeout=5)

    assert received == {"a": 1, "b": 2, "keyword": "three"}


def test_two_real_concurrent_submits_for_the_same_key_never_run_both(
    thread_manager,
) -> None:
    """The actual race BOT-027 fixed by hand: two near-simultaneous "clicks"
    on a real thread pool, only one of which may ever be in flight."""
    action = ExclusiveAction(thread_manager=thread_manager)
    overlap_detected = threading.Event()
    concurrently_running = 0
    lock = threading.Lock()

    def slow_task() -> None:
        nonlocal concurrently_running
        with lock:
            concurrently_running += 1
            if concurrently_running > 1:
                overlap_detected.set()
        time.sleep(0.05)
        with lock:
            concurrently_running -= 1

    accepted = []
    for _ in range(4):
        if action.try_start("load_history"):
            accepted.append(action.submit("load_history", slow_task))
        time.sleep(0.005)

    for future in accepted:
        future.result(timeout=5)

    assert len(accepted) == 1, "only the first of 4 rapid attempts should be accepted"
    assert not overlap_detected.is_set()


def test_submit_passes_task_unwrapped_as_thread_managers_first_positional_arg() -> None:
    """`ExclusiveAction.submit()` must call `thread_manager.submit(task, *args,
    **kwargs)` with `task` itself as the first positional argument -- not an
    opaque wrapper closing over it -- because app code (e.g.
    StreamLifecycleController) has existing unit tests asserting on
    `mock_thread_mgr.submit.call_args[0][0] == presenter._run_load_history`
    against a mocked IThreadManager. A wrapper here would silently break
    every one of those without touching a single line of app code — this
    pins the exact call shape a mock-based caller can rely on."""
    mock_thread_manager = MagicMock()
    mock_future: Future[None] = Future()
    mock_future.set_result(None)
    mock_thread_manager.submit.return_value = mock_future
    action = ExclusiveAction(thread_manager=mock_thread_manager)
    action.try_start("load_history")

    def real_task(a, b) -> None:
        pass

    action.submit("load_history", real_task, 1, b=2)

    mock_thread_manager.submit.assert_called_once_with(real_task, 1, b=2)


def test_is_running_with_no_key_reports_whether_anything_is_running(
    thread_manager,
) -> None:
    action = ExclusiveAction(thread_manager=thread_manager)

    assert action.is_running() is False

    action.try_start("load_history")

    assert action.is_running() is True


# ------------------------------------------------------------- EPIC-007B: held_slot()


def test_held_slot_is_none_when_the_slot_is_free(thread_manager) -> None:
    action = ExclusiveAction(thread_manager=thread_manager)
    assert action.held_slot() is None


def test_held_slot_reports_the_key_and_a_growing_duration(thread_manager) -> None:
    action = ExclusiveAction(thread_manager=thread_manager)
    assert action.try_start("load_history") is True

    first = action.held_slot()
    assert first is not None
    assert first.key == "load_history"
    assert first.held_seconds >= 0

    time.sleep(0.05)
    second = action.held_slot()
    assert second is not None
    assert second.held_seconds > first.held_seconds


def test_held_slot_is_none_again_after_finish(thread_manager) -> None:
    action = ExclusiveAction(thread_manager=thread_manager)
    action.try_start("load_history")
    action.finish("load_history")
    assert action.held_slot() is None


def test_held_slot_is_singular_by_construction_only_one_key_at_a_time(
    thread_manager,
) -> None:
    """One instance has exactly one slot -- try_start() for a second key while
    the first is held must fail, so held_slot() can never need to report more
    than one entry."""
    action = ExclusiveAction(thread_manager=thread_manager)
    assert action.try_start("first") is True
    assert action.try_start("second") is False

    slot = action.held_slot()
    assert slot is not None
    assert slot.key == "first"
