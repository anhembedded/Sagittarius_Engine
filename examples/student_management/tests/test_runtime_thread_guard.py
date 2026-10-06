"""The thread guard in `conftest.py` catches what `BUG-020` leaked."""

from __future__ import annotations

import threading

import pytest

from examples.student_management.tests.conftest import (
    assert_no_leaked_runtime_threads,
    leaked_runtime_threads,
)


def test_a_running_runtime_thread_is_reported_until_it_stops() -> None:
    before = {t.ident for t in threading.enumerate()}
    stop = threading.Event()
    worker = threading.Thread(target=stop.wait, name="SagittariusScheduler")
    worker.start()
    try:
        assert leaked_runtime_threads(before) == ["SagittariusScheduler"]
    finally:
        stop.set()
        worker.join()
    assert leaked_runtime_threads(before) == []


def test_an_unrelated_thread_is_not_reported() -> None:
    before = {t.ident for t in threading.enumerate()}
    stop = threading.Event()
    worker = threading.Thread(target=stop.wait, name="something-else")
    worker.start()
    try:
        assert leaked_runtime_threads(before) == []
    finally:
        stop.set()
        worker.join()


def test_a_runtime_thread_already_running_before_the_test_is_not_its_leak() -> None:
    """Only threads a test started are its leak: one alive before the test
    began is somebody else's (the guard reports that test, not this one)."""
    stop = threading.Event()
    worker = threading.Thread(target=stop.wait, name="AsyncRuntimeLoop")
    worker.start()
    try:
        before = {t.ident for t in threading.enumerate()}
        assert leaked_runtime_threads(before) == []
    finally:
        stop.set()
        worker.join()


def test_the_guards_check_fails_on_a_leak() -> None:
    before = {t.ident for t in threading.enumerate()}
    stop = threading.Event()
    worker = threading.Thread(target=stop.wait, name="SagittariusScheduler")
    worker.start()
    try:
        with pytest.raises(AssertionError, match="SagittariusScheduler"):
            assert_no_leaked_runtime_threads(before)
    finally:
        stop.set()
        worker.join()
    assert_no_leaked_runtime_threads(before)
