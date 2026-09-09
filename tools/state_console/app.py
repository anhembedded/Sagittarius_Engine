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


def build_console_app(
    uri: str | None = None, *, extra_extensions: list | None = None, boot: bool = True
) -> App:
    """
    @brief Wires — and, by default, boots — the console's own `App`. No
    database, no persistence, nothing this tool needs beyond a container, a
    bus, and the websocket connection.

    @param uri `None` boots cold (`EPIC-008B` §3's connect flow is how a
    target then gets chosen from inside the running tool).
    @param extra_extensions Registered after `ConsoleConnectionExtension`,
    before `app.boot()` — `main.py` passes `[ConsoleMvcExtension()]` here.
    @param boot `False` to wire everything (extensions registered, the
    container populated) without calling `app.boot()` yet. `main.py` needs
    this: `ConsoleConnectionExtension.boot()` starts the one-shot connection
    attempt immediately, with no automatic retry
    (`ConsoleConnectionExtension`'s own docstring) — booting before
    `ConsoleShellView` exists would let a fast failure fire and vanish
    before `ShellPresenter` has subscribed to anything, leaving the status
    band stuck at `COLD` forever despite a real attempt having happened.
    Callers that pass `boot=False` must call `app.boot()` themselves once
    every presenter that needs to observe the connection has subscribed.
    """
    config = ConfigManager()
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    container.singleton(IConfig, config)
    container.singleton(IEventBus, event_bus)

    connection = ConsoleConnectionExtension(uri)
    # Registered by concrete type, not an interface: this extension has no
    # interface of its own (EPIC-007E never gave it one), and it's the
    # presentation layer's only way to reach connect_to()/detach() -- see
    # ShellPresenter, which resolves it the same way BasePresenter already
    # resolves IEventBus/ILogger/etc.
    container.singleton(ConsoleConnectionExtension, connection)

    app = App(container, event_bus)
    app.use(LoggerExtension())
    app.use(connection)
    for extension in extra_extensions or []:
        app.use(extension)
    if boot:
        app.boot()
    return app
