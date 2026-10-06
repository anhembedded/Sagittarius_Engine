"""The thread guard in `conftest.py` catches what `BUG-020` leaked."""

from __future__ import annotations

import threading

from examples.student_management.tests.conftest import leaked_runtime_threads


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
