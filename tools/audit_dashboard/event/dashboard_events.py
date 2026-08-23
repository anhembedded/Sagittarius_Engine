from typing import Any

try:
    from src.base_event import BaseEvent
except ImportError:

    class BaseEvent:  # type: ignore[no-redef]  # Fallback if run standalone without src in path
        pass


class TelemetryReceivedEvent(BaseEvent):
    """
    Fired when telemetry data is received from the engine via the realtime connector.
    """

    def __init__(self, raw_data: dict[str, Any]):
        super().__init__()
        self.raw_data = raw_data
