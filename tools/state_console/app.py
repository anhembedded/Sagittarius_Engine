"""`build_console_app()` — this tool's counterpart to
`examples/student_management/main.py::build_app()`.

`BasePresenter.__init__` resolves `IEventBus`/`ILogger`/`IDispatcher`/
`IConfig` off the container unconditionally (no fallback) — `IDispatcher` is
the one `EngineContext` registers itself; the other three are this
function's job, the same three lines `build_app()` needs for the same
reason (`docs/bootstrap.md`'s "the trap": `App(container, event_bus)` does
not register either into the container on its own).
"""

from __future__ import annotations

from sagittarius_engine.extensions.logger.logger_module import LoggerExtension
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)
from sagittarius_engine.interfaces import IConfig, IEventBus
from sagittarius_engine.kernel import App
from tools.state_console.infrastructure.console_connection_extension import (
    ConsoleConnectionExtension,
)


def build_console_app(uri: str, *, extra_extensions: list | None = None) -> App:
    """
    @brief Wires and boots the console's own `App` — no database, no
    persistence, nothing this tool needs beyond a container, a bus, and the
    websocket connection.

    @param extra_extensions Registered after `ConsoleConnectionExtension`,
    before `app.boot()` — `main.py` passes `[ConsoleMvcExtension()]` here.
    """
    config = ConfigManager()
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    container.singleton(IConfig, config)
    container.singleton(IEventBus, event_bus)

    app = App(container, event_bus)
    app.use(LoggerExtension())
    app.use(ConsoleConnectionExtension(uri))
    for extension in extra_extensions or []:
        app.use(extension)
    app.boot()
    return app
