"""`DiagnosticsExtension` — the wiring inspection, attached to readiness.

Boots a real engine rather than a fixture: the point of this subtask is that
the inspection happens at the right moment in a real lifecycle, and a mock
cannot demonstrate a moment.
"""

import pytest

from sagittarius_engine.extensions.diagnostics import (
    DiagnosticsError,
    DiagnosticsExtension,
)
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.kernel import App
from sagittarius_engine.kernel.lifecycle import APP_READY_EVENT_NAME


def _app():
    return App(StdLibContainer(), MemoryEventBus())


def _noop(data=None):
    return data


def test_boot_reaches_ready_and_emits_app_ready_once():
    app = _app()
    seen = []
    app.event_bus.on(APP_READY_EVENT_NAME, lambda a: seen.append(a))

    app.boot()

    assert app.context.lifecycle.is_ready
    assert len(seen) == 1
    assert seen[0] is app
    app.stop()


def test_ready_is_reached_only_after_booted():
    app = _app()
    order = []
    app.event_bus.on("app.booted", lambda a: order.append("booted"))
    app.event_bus.on(APP_READY_EVENT_NAME, lambda a: order.append("ready"))

    app.boot()

    assert order == ["booted", "ready"]
    app.stop()


def test_the_extension_runs_the_inspection_at_readiness():
    app = _app()
    diagnostics = DiagnosticsExtension()
    app.use(diagnostics)

    assert diagnostics.last_report is None, "nothing before boot"

    app.boot()

    assert diagnostics.last_report is not None
    assert diagnostics.last_report.ok
    app.stop()


def test_fail_fast_aborts_the_boot_on_a_wiring_error():
    app = _app()
    app.event_bus.on("app.bootd", _noop)  # typo of app.booted — check A2
    app.use(DiagnosticsExtension(fail_fast=True))

    with pytest.raises(DiagnosticsError) as excinfo:
        app.boot()

    assert "app.bootd" in str(excinfo.value)
    assert 'did you mean "app.booted"?' in str(excinfo.value)


def test_fail_fast_is_off_by_default():
    """An engine that refuses to start over a diagnostic is a worse default."""
    app = _app()
    app.event_bus.on("app.bootd", _noop)
    diagnostics = DiagnosticsExtension()
    app.use(diagnostics)

    app.boot()

    assert diagnostics.last_report is not None
    assert not diagnostics.last_report.ok, "the error is still reported"
    app.stop()


def test_warnings_alone_do_not_trip_fail_fast():
    app = _app()
    app.event_bus.on("nothing.like.any.declared.name", _noop)
    diagnostics = DiagnosticsExtension(fail_fast=True)
    app.use(diagnostics)

    app.boot()

    assert diagnostics.last_report is not None
    assert diagnostics.last_report.warnings
    assert diagnostics.last_report.ok
    app.stop()


def test_expected_unheard_reaches_the_inspection():
    app = _app()
    diagnostics = DiagnosticsExtension(expected_unheard=["app.booted"])
    app.use(diagnostics)

    app.boot()

    report = diagnostics.last_report
    assert report is not None
    unheard = {f.subject for f in report.findings if f.check == "A1"}
    assert "app.booted" not in unheard
    app.stop()


def test_a_component_arriving_after_readiness_still_runs():
    """The health_check_requested.py:9 defect, closed at the engine level."""
    app = _app()
    app.boot()
    assert app.context.lifecycle.is_ready

    ran = []
    app.context.lifecycle.when_ready(lambda: ran.append("late"))

    assert ran == ["late"]
    app.stop()


def test_subscribing_to_the_event_after_it_fired_still_misses_it():
    """Why `when_ready()` exists rather than only an event.

    This is not a defect being reported — it is how events work, and the
    reason readiness had to be a queryable state as well as a broadcast.
    """
    app = _app()
    app.boot()

    late = []
    app.event_bus.on(APP_READY_EVENT_NAME, lambda a: late.append(a))

    assert late == []
    app.stop()


def test_stopping_leaves_the_state_stopped_not_ready():
    app = _app()
    app.boot()
    app.stop()

    assert not app.context.lifecycle.is_ready
    assert app.context.lifecycle.is_stopped


# ------------------------------------------- EPIC-006D: handlers at readiness


class _IThing:
    """Unbound plain dependency — the silent case."""


class _Handler:
    def __init__(self, thing: _IThing) -> None:
        self._thing = thing

    def execute(self, dto):
        return None


def test_handlers_named_explicitly_are_pre_flighted_at_readiness():
    app = _app()
    diagnostics = DiagnosticsExtension(handlers=[_Handler])
    app.use(diagnostics)

    app.boot()

    report = diagnostics.last_report
    assert report is not None
    assert [f.check for f in report.findings if f.check.startswith("B")]
    app.stop()


def test_handler_packages_are_searched_when_no_list_is_given():
    app = _app()
    diagnostics = DiagnosticsExtension(handler_packages=[__name__])
    app.use(diagnostics)

    app.boot()

    report = diagnostics.last_report
    assert report is not None
    subjects = {f.subject for f in report.findings if f.check == "B3"}
    assert "_Handler" in subjects
    app.stop()


def test_a_non_handler_in_the_explicit_list_is_dropped_not_reported():
    """A typo in the list is not a wiring defect in the application."""
    app = _app()
    diagnostics = DiagnosticsExtension(handlers=[_IThing])
    app.use(diagnostics)

    app.boot()

    report = diagnostics.last_report
    assert report is not None
    assert [f for f in report.findings if f.check.startswith("B")] == []
    app.stop()
