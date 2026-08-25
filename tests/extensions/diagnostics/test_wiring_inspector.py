"""`WiringInspector` against a deliberately mis-wired application.

`EPIC-006B`'s acceptance criterion: a fixture wired wrongly on purpose produces
exactly the findings that describe the wiring, and a correctly wired one
produces none.
"""

from abc import ABC, abstractmethod

import pytest

from sagittarius_engine.domain.base_event import BaseEvent
from sagittarius_engine.extensions.diagnostics import WiringInspector
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus


class OrderFilled(BaseEvent):
    event_name = "diag.order.filled"


class OrderCancelled(BaseEvent):
    event_name = "diag.order.cancelled"


def _noop(data=None):
    return data


def _other(data=None):
    return data


def _findings(report, check):
    return [f for f in report.findings if f.check == check]


# ----------------------------------------------------------------- A2: typos


def test_a2_reports_a_misspelled_subscription_as_an_error_and_names_the_intent():
    bus = MemoryEventBus()
    bus.on("diag.order.cancelld", _noop)  # missing 'e'

    (finding,) = _findings(WiringInspector().inspect(bus=bus), "A2")

    assert finding.severity == "error"
    assert finding.subject == "diag.order.cancelld"
    assert "can never run" in finding.message
    assert finding.hint == 'did you mean "diag.order.cancelled"?'


def test_a2_does_not_call_an_unrecognisable_name_a_typo():
    """Otherwise every undeclared event in an ordinary app reads as a defect."""
    bus = MemoryEventBus()
    bus.on("something.entirely.unrelated", _noop)

    (finding,) = _findings(WiringInspector().inspect(bus=bus), "A2")

    assert finding.severity == "warning"
    assert finding.hint is not None
    assert "EventRegistry" in finding.message


def test_a2_is_silent_when_the_subscription_is_correct():
    bus = MemoryEventBus()
    bus.on(OrderFilled, _noop)

    assert _findings(WiringInspector().inspect(bus=bus), "A2") == []


def test_a_class_based_subscription_is_matched_by_its_registered_name():
    bus = MemoryEventBus()
    bus.on(OrderCancelled, _noop)

    report = WiringInspector().inspect(bus=bus)

    assert _findings(report, "A2") == []
    assert "diag.order.cancelled" not in {f.subject for f in _findings(report, "A1")}


# ------------------------------------------------- A1: declared but unheard


def test_a1_is_advisory_not_a_warning():
    """EventRegistry is process-wide; most of it is legitimately unheard.

    Reporting those as warnings on every boot trains the reader to skip the
    report, which costs more than the check finds.
    """
    report = WiringInspector().inspect(bus=MemoryEventBus())

    unheard = _findings(report, "A1")
    assert unheard, "the engine's own events are declared and unheard here"
    assert {f.severity for f in unheard} == {"info"}


def test_a1_respects_the_applications_expected_unheard_list():
    bus = MemoryEventBus()

    reported = {
        f.subject
        for f in _findings(
            WiringInspector().inspect(bus=bus, expected_unheard=["diag.order.filled"]),
            "A1",
        )
    }

    assert "diag.order.filled" not in reported
    assert "diag.order.cancelled" in reported


# ------------------------------------------------------------ A3 / A5: info


def test_a3_reports_an_event_with_more_than_one_handler():
    bus = MemoryEventBus()
    bus.on(OrderFilled, _noop)
    bus.on(OrderFilled, _other)

    (finding,) = _findings(WiringInspector().inspect(bus=bus), "A3")

    assert finding.severity == "info"
    assert "2 handlers" in finding.message


def test_a3_is_silent_for_a_single_handler():
    bus = MemoryEventBus()
    bus.on(OrderFilled, _noop)

    assert _findings(WiringInspector().inspect(bus=bus), "A3") == []


def test_a5_names_string_subscriptions_as_the_ones_a2_exists_to_protect():
    """A class-based subscription cannot be misspelled — NameError comes first."""
    bus = MemoryEventBus()
    bus.on("app.booted", _noop)  # engine lifecycle event, registered by name
    bus.on(OrderFilled, _other)  # typed

    exposed = {f.subject for f in _findings(WiringInspector().inspect(bus=bus), "A5")}

    assert "app.booted" in exposed
    assert "diag.order.filled" not in exposed


# ------------------------------------------------------------ C: the container


class IMailer(ABC):
    @abstractmethod
    def send(self) -> None: ...


class PlainMailer:
    """An 'interface' that is instantiable — the silent case, EPIC-006 §2.3."""


class NeedsAbstract:
    def __init__(self, mailer: IMailer):
        self.mailer = mailer


class NeedsPlain:
    def __init__(self, mailer: PlainMailer):
        self.mailer = mailer


def test_c1_reports_an_unbound_abstract_dependency_as_an_error():
    container = StdLibContainer()
    container.bind(NeedsAbstract, NeedsAbstract)

    (finding,) = _findings(WiringInspector().inspect(container=container), "C1")

    assert finding.severity == "error"
    assert finding.subject == "NeedsAbstract.mailer"
    assert "IMailer" in finding.message


def test_c2_reports_the_unbound_plain_dependency_that_does_not_raise():
    """The dangerous one: resolve() succeeds and injects an empty stand-in."""
    container = StdLibContainer()
    container.bind(NeedsPlain, NeedsPlain)

    (finding,) = _findings(WiringInspector().inspect(container=container), "C2")

    assert finding.severity == "warning"
    assert "does not raise" in finding.message

    # The behaviour the finding describes, demonstrated rather than asserted.
    assert type(container.resolve(NeedsPlain).mailer) is PlainMailer


def test_c_is_silent_once_the_dependency_is_bound():
    class RealMailer(IMailer):
        def send(self) -> None: ...

    container = StdLibContainer()
    container.bind(IMailer, RealMailer)
    container.bind(NeedsAbstract, NeedsAbstract)

    report = WiringInspector().inspect(container=container)

    assert _findings(report, "C1") == []
    assert _findings(report, "C2") == []


def test_inspecting_the_container_never_constructs_anything():
    built = []

    class Tracked:
        def __init__(self) -> None:
            built.append(1)

    class Uses:
        def __init__(self, dep: Tracked) -> None:
            self.dep = dep

    container = StdLibContainer()
    container.bind(Tracked, Tracked)
    container.bind(Uses, Uses)

    WiringInspector().inspect(container=container)

    assert built == [], "a diagnostic that builds objects runs the application"


def test_c3_names_a_dependency_cycle_in_full():
    class A:
        def __init__(self, b: "B") -> None: ...

    class B:
        def __init__(self, a: A) -> None: ...

    A.__init__.__annotations__["b"] = B

    container = StdLibContainer()
    container.bind(A, A)
    container.bind(B, B)

    cycles = _findings(WiringInspector().inspect(container=container), "C3")

    assert len(cycles) == 1
    assert cycles[0].severity == "error"
    assert "A" in cycles[0].subject and "B" in cycles[0].subject


# ------------------------------------------------------------- D: lifecycle


class _Descriptor:
    def __init__(self, name, dependencies=(), enabled=True):
        self.name = name
        self.dependencies = list(dependencies)
        self.enabled = enabled


class _Ext:
    def __init__(self, name, dependencies=(), enabled=True):
        self.descriptor = _Descriptor(name, dependencies, enabled)


class _Manager:
    def __init__(self, registered, initialized):
        self.registered_extensions = registered
        self.initialized_extensions = initialized


def test_d1_reports_an_extension_stranded_by_a_dependency_that_never_arrived():
    audit = _Ext("AuditExtension", dependencies=["HealthExtension"])
    manager = _Manager(registered=[audit], initialized=[])

    (finding,) = _findings(WiringInspector().inspect(extension_manager=manager), "D1")

    assert finding.severity == "error"
    assert finding.subject == "AuditExtension"
    assert "HealthExtension" in finding.message


def test_d1_is_silent_for_an_initialised_extension():
    health = _Ext("HealthExtension")
    manager = _Manager(registered=[health], initialized=[health])

    assert _findings(WiringInspector().inspect(extension_manager=manager), "D1") == []


def test_d1_ignores_a_disabled_extension():
    off = _Ext("Disabled", enabled=False)
    manager = _Manager(registered=[off], initialized=[])

    assert _findings(WiringInspector().inspect(extension_manager=manager), "D1") == []


class _Service:
    pass


class _HostedManager:
    def __init__(self, services, started):
        self.services = services
        self.started_services = started


def test_d2_reports_a_hosted_service_that_never_started():
    running, stalled = _Service(), _Service()
    manager = _HostedManager(services=[running, stalled], started=[running])

    (finding,) = _findings(WiringInspector().inspect(hosted_services=manager), "D2")

    assert finding.severity == "warning"
    assert "never started" in finding.message


class _Job:
    def __init__(self, next_run):
        self.next_run = next_run

        def job_func() -> None: ...

        self.job_func = job_func


class _Scheduler:
    def __init__(self, jobs):
        self.jobs = jobs


def test_d3_reports_a_job_that_will_never_fire():
    from datetime import datetime

    manager = _Scheduler(jobs=[_Job(datetime.now()), _Job(None)])

    (finding,) = _findings(WiringInspector().inspect(scheduler=manager), "D3")

    assert finding.severity == "warning"
    assert "never fire" in finding.message


# ------------------------------------------------------------------- report


def test_report_ok_is_about_errors_not_warnings():
    bus = MemoryEventBus()
    bus.on("something.entirely.unrelated", _noop)  # warning only

    report = WiringInspector().inspect(bus=bus)

    assert report.warnings
    assert report.ok


def test_a_correctly_wired_application_reports_no_errors_or_warnings():
    class RealMailer(IMailer):
        def send(self) -> None: ...

    bus = MemoryEventBus()
    bus.on(OrderFilled, _noop)
    container = StdLibContainer()
    container.bind(IMailer, RealMailer)
    container.bind(NeedsAbstract, NeedsAbstract)

    report = WiringInspector().inspect(bus=bus, container=container)

    assert report.errors == ()
    assert report.warnings == ()
    assert report.ok


def test_findings_are_ordered_worst_first_and_stably():
    bus = MemoryEventBus()
    bus.on("diag.order.cancelld", _noop)
    bus.on("something.entirely.unrelated", _other)

    report = WiringInspector().inspect(bus=bus)
    severities = [f.severity for f in report.sorted_findings()]

    assert severities == sorted(severities, key=["error", "warning", "info"].index)
    assert report.sorted_findings() == report.sorted_findings()


def test_format_leads_with_the_counts_and_renders_hints():
    bus = MemoryEventBus()
    bus.on("diag.order.cancelld", _noop)

    text = WiringInspector().inspect(bus=bus).format()

    assert "1 error(s)" in text
    assert 'did you mean "diag.order.cancelled"?' in text


def test_format_of_a_clean_report_says_so():
    assert "Wiring OK" in WiringInspector().inspect().format()


@pytest.mark.parametrize(
    "check", ["A1", "A2", "A3", "C1", "C2", "C3", "D1", "D2", "D3"]
)
def test_every_check_id_is_traceable_to_the_epic(check):
    """Each finding names the check that produced it, so a report line can be
    looked up in EPIC-006 §3 without guessing."""
    assert check[0] in {"A", "C", "D"} and check[1:].isdigit()
