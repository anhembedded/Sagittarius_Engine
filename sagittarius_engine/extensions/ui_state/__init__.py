"""Remembering what the user last set, as a framework capability.

The application decides *where* state lives and *what* is worth keeping; this
package provides the mechanism that carries it.
"""

from sagittarius_engine.extensions.ui_state.adapters.config_manager_state_store import (
    ConfigManagerStateStore,
)
from sagittarius_engine.extensions.ui_state.adapters.in_memory_state_store import (
    InMemoryStateStore,
)
from sagittarius_engine.extensions.ui_state.adapters.null_state_store import (
    NullStateStore,
)
from sagittarius_engine.extensions.ui_state.i_state_contributor import IStateContributor
from sagittarius_engine.extensions.ui_state.ports.i_state_store import IStateStore
from sagittarius_engine.extensions.ui_state.ports.i_state_store_locator import (
    IStateStoreLocator,
)
from sagittarius_engine.extensions.ui_state.state_scope import (
    Lifetime,
    StateData,
    StateScope,
)
from sagittarius_engine.extensions.ui_state.ui_state_coordinator import (
    UiStateCoordinator,
)
from sagittarius_engine.extensions.ui_state.ui_state_extension import UiStateExtension

__all__ = [
    "ConfigManagerStateStore",
    "IStateContributor",
    "IStateStore",
    "IStateStoreLocator",
    "InMemoryStateStore",
    "Lifetime",
    "NullStateStore",
    "StateData",
    "StateScope",
    "UiStateCoordinator",
    "UiStateExtension",
]
