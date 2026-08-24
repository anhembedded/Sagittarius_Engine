from dataclasses import dataclass
from typing import ClassVar

from sagittarius_engine.domain.event_registry import EventRegistry


@dataclass
class ExtensionInitializing:
    """Event emitted when an extension is about to initialize."""

    event_name: ClassVar[str] = "extension.initializing"

    extension_name: str


@dataclass
class ExtensionStarted:
    """Event emitted when an extension has started."""

    event_name: ClassVar[str] = "extension.started"

    extension_name: str


@dataclass
class ExtensionStopped:
    """Event emitted when an extension has stopped."""

    event_name: ClassVar[str] = "extension.stopped"

    extension_name: str


@dataclass
class ExtensionDisposed:
    """Event emitted when an extension has been disposed."""

    event_name: ClassVar[str] = "extension.disposed"

    extension_name: str


EventRegistry.register_named(
    ExtensionInitializing.event_name, ExtensionInitializing, module=__name__
)
EventRegistry.register_named(
    ExtensionStarted.event_name, ExtensionStarted, module=__name__
)
EventRegistry.register_named(
    ExtensionStopped.event_name, ExtensionStopped, module=__name__
)
EventRegistry.register_named(
    ExtensionDisposed.event_name, ExtensionDisposed, module=__name__
)
