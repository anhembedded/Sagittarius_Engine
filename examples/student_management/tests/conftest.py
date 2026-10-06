"""Shared guard for the example app's tests (`BUG-020`)."""

from __future__ import annotations

import threading
from collections.abc import Iterator

import pytest

RUNTIME_THREAD_NAMES = ("SagittariusScheduler", "AsyncRuntimeLoop")


def leaked_runtime_threads(before: set[int | None]) -> list[str]:
    """Names of scheduler / async-runtime threads started since `before`
    (a set of `Thread.ident`) that are still alive."""
    return [
        t.name
        for t in threading.enumerate()
        if t.ident not in before and t.name in RUNTIME_THREAD_NAMES
    ]


@pytest.fixture(autouse=True)
def no_leaked_runtime_threads() -> Iterator[None]:
    """`build_app()` boots a real `App`, which starts a scheduler and an
    async-runtime thread; a test that never stops it leaves both running for
    the rest of the process (`BUG-014`, `BUG-020`). Fails any test under
    `examples/student_management/tests/` that does. Autouse fixtures tear down
    last, so a fixture that stops its app has already done so.
    """
    before = {t.ident for t in threading.enumerate()}
    yield
    leaked = leaked_runtime_threads(before)
    assert not leaked, f"test left runtime threads running: {leaked}"
