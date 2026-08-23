from typing import Any

from Domain.ports import IRealtimeConnector
from event.dashboard_events import TelemetryReceivedEvent

# Try to use Sagittarius interfaces if available
try:
    from src.interfaces import ICommand, IEventBus
except ImportError:

    class ICommand:  # type: ignore[no-redef]
        def execute(self, data: Any) -> Any:
            pass

    class IEventBus:  # type: ignore[no-redef]
        def emit(self, event_name: str, event: Any) -> None:
            pass


class StartRealtimeListenerCommand(ICommand):
    """
    Use case to start listening for realtime data and emitting events.
    """

    def __init__(self, connector: IRealtimeConnector, event_bus: IEventBus):
        self.connector = connector
        self.event_bus = event_bus

    def execute(self, data_transfer_obj: dict[str, Any] | None = None) -> None:
        def handle_message(payload: Any) -> None:
            # Emits event so that the UI can update
            event = TelemetryReceivedEvent(raw_data=payload)
            self.event_bus.emit("dashboard.telemetry_received", event)

        self.connector.on_message_received(handle_message)
        self.connector.connect()
