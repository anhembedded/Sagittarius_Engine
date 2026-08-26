"""`UiStateExtension` — binding the coordinator without deciding policy."""

from __future__ import annotations

import pytest

from sagittarius_engine.extensions.ui_state import (
    InMemoryStateStore,
    IStateStore,
    NullStateStore,
    StateScope,
    UiStateCoordinator,
    UiStateExtension,
)
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer


class _Context:
    def __init__(self, container) -> None:
        self.container = container


@pytest.fixture
def container() -> StdLibContainer:
    return StdLibContainer()


def test_registers_a_coordinator(container):
    UiStateExtension().register(_Context(container))

    assert isinstance(container.resolve(UiStateCoordinator), UiStateCoordinator)


def test_uses_the_store_the_application_bound(container):
    """The framework carries state; the application decides where it goes."""
    store = InMemoryStateStore()
    container.singleton(IStateStore, store)

    UiStateExtension().register(_Context(container))
    coordinator = container.resolve(UiStateCoordinator)

    assert coordinator._store is store


def test_an_application_that_bound_nothing_gets_a_no_op_store(container):
    """Opting out has to be the default. A framework that picked a path and
    started writing files an app never asked for would be making a policy
    decision that is not its to make."""
    UiStateExtension().register(_Context(container))
    coordinator = container.resolve(UiStateCoordinator)

    assert isinstance(coordinator._store, NullStateStore)


def test_a_coordinator_over_the_null_store_still_works(container):
    """The opted-out path must be usable, not merely present: a contributor
    restoring from it gets an empty mapping rather than an error."""
    UiStateExtension().register(_Context(container))
    coordinator = container.resolve(UiStateCoordinator)

    assert coordinator._store.read(StateScope(key="anything")) == {}


def test_shutdown_flushes_what_is_still_pending(container, qapp):
    """The real safety net: a `QTimer` never fires once the event loop has
    stopped turning, so a value changed moments before quitting would be lost
    without this."""
    store = InMemoryStateStore()
    container.singleton(IStateStore, store)
    extension = UiStateExtension()
    context = _Context(container)
    extension.register(context)
    coordinator = container.resolve(UiStateCoordinator)

    class _Contributor:
        state_scope = StateScope(key="screen")

        def capture_state(self):
            return {"value": "typed just before quitting"}

        def restore_state(self, data):
            pass

    coordinator.mark_dirty(_Contributor())
    extension.shutdown(context)

    assert store.read(StateScope(key="screen")) == {
        "value": "typed just before quitting"
    }
