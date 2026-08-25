"""Checks B1–B3 — the dispatch resolvability pre-flight (`EPIC-006D`).

`dispatch()` resolves a handler class straight from the container, with no
registration step. Nothing binds a handler, so `inspect_container()` never sees
one, and a handler whose dependency is unbound fails only when a user first
triggers that command. These tests pin that failure being pulled forward.
"""

from abc import ABC, abstractmethod

from sagittarius_engine.extensions.cqrs.interfaces.commands import ICommand
from sagittarius_engine.extensions.diagnostics import (
    WiringInspector,
    discover_handlers,
    looks_dispatchable,
)
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.interfaces.i_dispatchable import IDispatchable


class IRepo(ABC):
    @abstractmethod
    def all(self) -> list: ...


class Repo(IRepo):
    def all(self) -> list:
        return []


class PlainDep:
    """An 'interface' that is instantiable — EPIC-006 §2.3's silent case."""


class GoodHandler:
    def __init__(self, repo: IRepo) -> None:
        self._repo = repo

    def execute(self, dto):
        return None


class AbstractDepHandler:
    def __init__(self, repo: IRepo) -> None:
        self._repo = repo

    def execute(self, dto):
        return None


class PlainDepHandler:
    def __init__(self, dep: PlainDep) -> None:
        self._dep = dep

    def execute(self, dto):
        return None


class NoDepsHandler:
    def execute(self, dto):
        return None


def _findings(report, check):
    return [f for f in report.findings if f.check == check]


# ------------------------------------------------------- what counts as one


def test_a_bare_class_with_execute_is_dispatchable():
    """The engine's own reference app writes handlers exactly this way."""
    assert looks_dispatchable(GoodHandler)
    assert not issubclass(GoodHandler, IDispatchable), (
        "if handlers ever must inherit IDispatchable, discovery can be "
        "simplified and this test should be revisited"
    )


def test_the_marker_interfaces_are_not_themselves_handlers():
    """Reporting a finding against ICommand would name the interface where the
    reader needs the implementation."""
    assert not looks_dispatchable(IDispatchable)
    assert not looks_dispatchable(ICommand)


def test_a_class_without_execute_is_not_dispatchable():
    assert not looks_dispatchable(Repo)


def test_execute_taking_the_wrong_number_of_arguments_is_not_dispatchable():
    class Odd:
        def execute(self, a, b):
            return None

    assert not looks_dispatchable(Odd)


# ------------------------------------------------------------- B1: abstract


def test_b1_reports_an_unbound_abstract_dependency_as_an_error():
    container = StdLibContainer()

    report = WiringInspector().inspect(
        container=container, handlers=[AbstractDepHandler]
    )
    (finding,) = _findings(report, "B1")

    assert finding.severity == "error"
    assert finding.subject == "AbstractDepHandler.repo"
    assert "IRepo" in finding.message
    assert not report.ok


def test_b1_is_silent_once_the_dependency_is_bound():
    container = StdLibContainer()
    container.bind(IRepo, Repo)

    report = WiringInspector().inspect(container=container, handlers=[GoodHandler])

    assert _findings(report, "B1") == []
    assert _findings(report, "B2") == []


# ---------------------------------------------------------------- B2: plain


def test_b2_reports_the_unbound_plain_dependency_that_does_not_raise():
    container = StdLibContainer()

    report = WiringInspector().inspect(container=container, handlers=[PlainDepHandler])
    (finding,) = _findings(report, "B2")

    assert finding.severity == "warning"
    assert "does not raise" in finding.message
    assert report.ok, "a silent substitution is a warning, not a boot-stopper"


# ------------------------------------------------------------- B3: the chain


def test_b3_reports_what_a_handler_depends_on():
    container = StdLibContainer()
    container.bind(IRepo, Repo)

    (finding,) = _findings(
        WiringInspector().inspect(container=container, handlers=[GoodHandler]), "B3"
    )

    assert finding.severity == "info"
    assert finding.hint == "repo: IRepo"


def test_b3_says_nothing_about_a_handler_with_no_dependencies():
    report = WiringInspector().inspect(
        container=StdLibContainer(), handlers=[NoDepsHandler]
    )

    assert _findings(report, "B3") == []


# ------------------------------------------------------- the container gap


def test_handlers_are_invisible_to_the_container_check():
    """The premise of this whole subtask, asserted rather than assumed."""
    container = StdLibContainer()

    report = WiringInspector().inspect(container=container)

    assert container.registrations() == {}
    assert _findings(report, "C1") == [], "nothing registered, nothing to check"

    with_handler = WiringInspector().inspect(
        container=container, handlers=[AbstractDepHandler]
    )
    assert _findings(with_handler, "B1"), "only the handler check finds it"


def test_the_preflight_never_constructs_a_handler():
    built = []

    class Tracked:
        def __init__(self) -> None:
            built.append(1)

    class Uses:
        def __init__(self, dep: Tracked) -> None:
            self.dep = dep

        def execute(self, dto):
            return None

    WiringInspector().inspect(container=StdLibContainer(), handlers=[Uses])

    assert built == [], "a diagnostic that builds handlers runs the application"


# ----------------------------------------------------------------- discovery


def test_discover_handlers_finds_the_handlers_in_this_module():
    found = discover_handlers(__name__)

    names = {c.__qualname__ for c in found}
    assert {
        "GoodHandler",
        "AbstractDepHandler",
        "PlainDepHandler",
        "NoDepsHandler",
    } <= names
    assert "Repo" not in names
    assert "ICommand" not in names


def test_discover_handlers_imports_nothing():
    """It walks sys.modules; anything the app uses is already imported."""
    import sys

    before = set(sys.modules)
    discover_handlers("examples.student_management")

    assert set(sys.modules) == before


def test_discover_handlers_requires_a_prefix_and_respects_it():
    assert discover_handlers("nothing.matches.this") == ()


def test_a_handler_is_reported_once_even_when_several_modules_import_it():
    found = discover_handlers(__name__)

    assert len(found) == len({id(c) for c in found})
