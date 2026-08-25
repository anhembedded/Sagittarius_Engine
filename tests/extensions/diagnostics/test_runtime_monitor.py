"""`EPIC-006F` — anomalies visible only while the application runs.

The observer registry is **process-global**, which is the right shape for it
(every bus routes through the same two funnels) and a hazard for a test suite.
The autouse fixture below returns it to empty after every test; without it a
monitor left registered by one test silently counts another test's events.
"""

from __future__ import annotations

import pytest

from sagittarius_engine.extensions.diagnostics import DiagnosticsExtension
from sagittarius_engine.extensions.diagnostics.runtime import RuntimeMonitor
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus import bus_observers
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.kernel import App


@pytest.fixture(autouse=True)
def _no_leaked_observers():
    yield
    for observer in bus_observers.bus_observers():
        bus_observers.remove_bus_observer(observer)


@pytest.fixture
def bus():
    return MemoryEventBus()


@pytest.fixture
def monitor():
    m = RuntimeMonitor()
    m.start()
    yield m
    m.stop()


def _explode(_payload=None):
    raise ValueError("boom")


# ------------------------------------------------------------- the registry


def test_add_is_idempotent():
    """Registering twice would double-count every event, which is a worse
    outcome than the second call being ignored."""
    m = RuntimeMonitor()
    bus_observers.add_bus_observer(m)
    bus_observers.add_bus_observer(m)
    assert bus_observers.bus_observers() == (m,)


def test_remove_is_silent_for_an_unregistered_observer():
    """So a shutdown path does not have to track whether boot got far enough
    to register."""
    bus_observers.remove_bus_observer(RuntimeMonitor())  # must not raise


class _BrokenObserver(bus_observers.IBusObserver):
    def event_emitted(self, event_name, handler_count):
        raise RuntimeError("observer is broken")


def test_a_broken_observer_cannot_break_the_application(bus):
    """The one place not propagating is right: a diagnostic that can raise into
    the dispatch path is a worse failure mode than the ones it reports."""
    received = []
    bus_observers.add_bus_observer(_BrokenObserver())
    bus.on("e", received.append)

    bus.emit("e", "payload")

    assert received == ["payload"], "a broken observer stopped the delivery"


def test_a_broken_observer_is_counted_rather_than_silenced(bus):
    """Contained is not the same as silent. The counter replaced a bare
    `except: pass` that Bandit flagged as B110 and was right to — it keeps the
    containment and drops the silence, which beats the `#nosec` the finding
    invited. A log line here would flood: one per emit is the BUG-042 failure
    mode that froze a UI thread.

    Read as a delta because the counter is process-global and never resets.
    """
    before = bus_observers.notification_failures()
    bus_observers.add_bus_observer(_BrokenObserver())

    bus.emit("e", None)
    bus.emit("e", None)

    assert bus_observers.notification_failures() - before == 2


# --------------------------------------------------------- R1: into the void


def test_r1_reports_an_event_nobody_received(bus, monitor):
    bus.emit("order.cancelled", {"id": 1})

    findings = monitor.findings()
    assert [f.check for f in findings] == ["R1"]
    assert findings[0].subject == "order.cancelled"
    assert findings[0].severity == "warning"


def test_r1_is_silent_when_something_is_listening(bus, monitor):
    bus.on("order.cancelled", lambda e: None)
    bus.emit("order.cancelled", {"id": 1})
    assert monitor.is_clean


def test_r1_aggregates_rather_than_accumulating(bus, monitor):
    """One entry per distinct name, with a count — not one record per emit.
    An application emitting into the void in a loop must not grow memory
    without bound."""
    for i in range(50):
        bus.emit("order.cancelled", i)

    findings = monitor.findings()
    assert len(findings) == 1
    assert "50x" in findings[0].message


def test_r1_names_the_emit_site(bus, monitor):
    bus.emit("order.cancelled", None)

    hint = monitor.findings()[0].hint
    assert "test_runtime_monitor.py" in hint, (
        "the site must be the line that emitted, not a frame inside the engine "
        f"or the monitor itself — got {hint!r}"
    )


def test_r1_honours_expected_unheard(bus):
    m = RuntimeMonitor(expected_unheard=("order.cancelled",))
    m.start()
    try:
        bus.emit("order.cancelled", None)
        assert m.is_clean
    finally:
        m.stop()


def test_r1_ignores_the_engines_own_lifecycle_events_by_default():
    """Measured, not assumed: a trivial boot/stop produced six R1 warnings,
    five of them engine lifecycle events no application has reason to handle.
    That is the flood A1 is advisory to avoid."""
    m = RuntimeMonitor()
    m.start()
    app = App(StdLibContainer(), MemoryEventBus())
    try:
        app.boot()
        app.stop()
        subjects = [f.subject for f in m.findings()]
        assert subjects == [], f"engine events leaked into R1: {subjects}"
    finally:
        m.stop()


def test_include_engine_events_reveals_them_without_a_second_run():
    """Everything is counted either way — the flag filters at report time, so
    turning it on does not require re-running the application."""
    m = RuntimeMonitor(include_engine_events=True)
    m.start()
    app = App(StdLibContainer(), MemoryEventBus())
    try:
        app.boot()
        app.stop()
        assert any(f.subject == "app.ready" for f in m.findings())
    finally:
        m.stop()


def test_an_application_event_named_like_an_engine_one_is_still_reported(bus, monitor):
    """The filter is exact — it reads each registration's declaring module —
    rather than a guess from the name's prefix."""
    bus.emit("app.something_of_mine", None)
    assert [f.subject for f in monitor.findings()] == ["app.something_of_mine"]


# ------------------------------------------------------ R2: a handler raised


def test_r2_reports_a_handler_that_raised(bus, monitor):
    bus.on("order.shipped", _explode)
    bus.emit("order.shipped", {"id": 1})

    findings = [f for f in monitor.findings() if f.check == "R2"]
    assert len(findings) == 1
    assert findings[0].severity == "error"
    assert "ValueError" in findings[0].message
    assert "boom" in findings[0].hint


def test_r2_counts_repeats_and_records_every_exception_type(bus, monitor):
    state = {"n": 0}

    def flaky(_payload):
        state["n"] += 1
        raise (ValueError if state["n"] == 1 else KeyError)("nope")

    bus.on("order.shipped", flaky)
    bus.emit("order.shipped", None)
    bus.emit("order.shipped", None)

    message = next(f for f in monitor.findings() if f.check == "R2").message
    assert "2x" in message
    assert "KeyError" in message and "ValueError" in message


def test_a_raising_handler_still_does_not_stop_the_others(bus, monitor):
    """R2 surfaces the failure; it must not change the bus's isolation, which
    `handler_reporting.py` documents as deliberate."""
    received = []
    bus.on("order.shipped", _explode)
    bus.on("order.shipped", received.append)

    bus.emit("order.shipped", "payload")

    assert received == ["payload"]
    assert [f.check for f in monitor.findings()] == ["R2"]


# ------------------------------------------------------------- reading state


def test_stop_keeps_what_was_seen(bus):
    """The report is usually read *after* shutdown — that is when everything
    that was going to happen has."""
    m = RuntimeMonitor()
    m.start()
    bus.emit("order.cancelled", None)
    m.stop()

    assert not m.is_clean
    assert m.report().warnings


def test_reset_forgets_without_unregistering(bus, monitor):
    bus.emit("order.cancelled", None)
    monitor.reset()

    assert monitor.is_clean
    assert monitor in bus_observers.bus_observers()


def test_the_report_is_a_wiring_report(bus, monitor):
    """Deliberately the same type as the static checks: an operator should not
    have to learn two report formats because one ran at a different time."""
    bus.emit("order.cancelled", None)
    text = monitor.report().format()
    assert "[R1]" in text and "WARNING" in text


# ------------------------------------------------------------ the extension


def test_watch_runtime_is_off_by_default():
    """The static checks are one pass at readiness; this one observes every
    dispatch for the life of the process. Opt-in, not opt-out."""
    assert DiagnosticsExtension().runtime_monitor is None
    assert DiagnosticsExtension().runtime_report() is None


def test_the_extension_registers_at_boot_and_unregisters_at_shutdown():
    diag = DiagnosticsExtension(watch_runtime=True)
    app = App(StdLibContainer(), MemoryEventBus())
    app.use(diag)

    app.boot()
    assert diag.runtime_monitor in bus_observers.bus_observers()

    app.stop()
    assert diag.runtime_monitor not in bus_observers.bus_observers(), (
        "the observer outlived the application that installed it"
    )


def test_the_extension_reports_what_the_run_turned_up():
    diag = DiagnosticsExtension(watch_runtime=True)
    app = App(StdLibContainer(), MemoryEventBus())
    app.use(diag)
    app.boot()

    app.event_bus.on("order.shipped", _explode)
    app.event_bus.emit("order.shipped", None)
    app.event_bus.emit("order.cancelled", None)
    app.stop()

    report = diag.runtime_report()
    assert {f.check for f in report.sorted_findings()} == {"R1", "R2"}


def test_the_extensions_expected_unheard_reaches_the_monitor():
    """One argument, one meaning, whichever check consumes it."""
    diag = DiagnosticsExtension(
        watch_runtime=True, expected_unheard=("order.cancelled",)
    )
    app = App(StdLibContainer(), MemoryEventBus())
    app.use(diag)
    app.boot()

    app.event_bus.emit("order.cancelled", None)
    app.stop()

    assert diag.runtime_report().ok
