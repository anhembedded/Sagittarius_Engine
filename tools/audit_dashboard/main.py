import argparse
import sys

from PySide6.QtWidgets import QApplication

# Try to use standard container and event bus from Sagittarius
try:
    from sagittarius_engine import App
    from sagittarius_engine.infrastructure import MemoryEventBus, StdLibContainer
    from sagittarius_engine.interfaces import IContainer, IEventBus
except ImportError:
    # Dummy fallbacks for standalone execution without framework
    class StdLibContainer:  # type: ignore[no-redef]
        def singleton(self, interface, instance):
            pass

        def resolve(self, cls):
            return cls()

    class MemoryEventBus:  # type: ignore[no-redef]
        def on(self, event_name, handler):
            pass

        def emit(self, event_name, event):
            pass

    class App:  # type: ignore[no-redef]
        def __init__(self, container, event_bus):
            self.container = container
            self.event_bus = event_bus

        def boot(self, auto_discover=None):
            pass

        def execute(self, cmd_cls, data=None):
            pass


from application.receive_audit_use_case import StartRealtimeListenerCommand
from infra.websocket_connector import WebsocketConnector
from presentation.main_window import MainWindow


def main():
    parser = argparse.ArgumentParser(description="Audit Dashboard")
    parser.add_argument(
        "--ui-only",
        action="store_true",
        help="Run UI only without connecting to the engine",
    )
    args = parser.parse_args()

    # 1. Setup Framework Kernel
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    app = App(container, event_bus)

    # 2. Register core services
    try:
        container.singleton(IContainer, container)
        container.singleton(IEventBus, event_bus)
    except NameError:
        pass

    # 3. Setup UI
    qt_app = QApplication(sys.argv)
    main_window = MainWindow()

    # 4. Wire events to UI
    # Note: Event Bus handlers might run on background threads.
    # We use Qt Signals to safely pass data to the main thread UI.
    def on_telemetry_received(event):
        # Emits signal to MainWindow (thread-safe)
        main_window.signals.telemetry_received.emit(event.raw_data)

    event_bus.on("dashboard.telemetry_received", on_telemetry_received)

    if not args.ui_only:
        # 5. Bind Infrastructure & Start App
        connector = WebsocketConnector(url="ws://127.0.0.1:9999")

        # Boot the application
        app.boot()

        # Execute the Use Case to start listening
        cmd = StartRealtimeListenerCommand(connector, event_bus)
        cmd.execute()
    else:
        print("Running in UI-Only mode. Realtime connector disabled.")

    # 6. Show UI and run event loop
    main_window.show()
    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
