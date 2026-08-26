"""Registers a `UiStateCoordinator` so screens can remember what the user set.

@details The framework half of `EPIC-010`, promoted here after the shape was
proven across five real screens in an application repo rather than designed
against one imagined consumer.

@par What this extension does NOT decide
Where the file lives, which values are worth remembering, and whether a
restored value is still valid are all **application** questions, and the
framework must not answer any of them:

- The **store** is injected. This extension registers whatever
  `IStateStore` the app has already bound, and only falls back to
  `NullStateStore` when the app bound nothing — so an app that has not opted
  in gets a coordinator that quietly does nothing, rather than a surprise file
  appearing somewhere the framework picked.
- **Validation** lives in each contributor's `restore_state()`. The
  coordinator never inspects the data it carries; it cannot know what a valid
  symbol or leverage is.

Those two rules are what keep this an extension rather than a policy.
"""

from __future__ import annotations

from typing import Protocol

from sagittarius_engine.extensions.ui_state.adapters.null_state_store import (
    NullStateStore,
)
from sagittarius_engine.extensions.ui_state.ports.i_state_store import IStateStore
from sagittarius_engine.extensions.ui_state.ui_state_coordinator import (
    UiStateCoordinator,
)
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_extension import IExtension


class IUiStateContext(Protocol):
    @property
    def container(self) -> IContainer: ...


class UiStateExtension(IExtension[IUiStateContext]):
    """Binds `UiStateCoordinator` into the container."""

    def register(self, context: IUiStateContext) -> None:
        container = context.container
        store = self._resolve_store(container)
        container.singleton(UiStateCoordinator, UiStateCoordinator(store))

    def boot(self, context: IUiStateContext) -> None:
        pass

    def shutdown(self, context: IUiStateContext) -> None:
        """Writes anything still pending.

        @details The real safety net, not the debounce timer: a `QTimer` never
        fires once the event loop has stopped turning, so a value the user
        changed moments before quitting would be lost without this.
        """
        coordinator = context.container.resolve(UiStateCoordinator)
        if coordinator is not None:
            coordinator.flush()

    @staticmethod
    def _resolve_store(container: IContainer) -> IStateStore:
        """The app's own store, or a no-op one if it bound none.

        @details Checked through `registrations()` rather than by catching a
        resolve error: `IContainer` declares that method as returning a
        `Mapping`, so asking is cheap and explicit, and a container that cannot
        answer in the shape its own interface promises is treated as holding
        nothing.
        """
        registrations = container.registrations()
        if not isinstance(registrations, dict) and not hasattr(
            registrations, "__contains__"
        ):
            return NullStateStore()
        if IStateStore not in registrations:
            return NullStateStore()
        resolved = container.resolve(IStateStore)
        return resolved if isinstance(resolved, IStateStore) else NullStateStore()
