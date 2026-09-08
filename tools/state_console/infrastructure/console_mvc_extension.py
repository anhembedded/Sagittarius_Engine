"""`ConsoleMvcExtension` — `EPIC-007E` §1.1, the console's counterpart to
`examples/student_management`'s `PySideMvcExtension`. Registers this tool's
own palette (`ADR-002` §2.2), never `examples/student_management`'s.

Caller contract (see `main.py`, copying `gui.py`'s own): a `QApplication`
MUST already exist before `app.boot()` runs this extension's `register()` —
`configure_app_qml()` needs a running Qt event loop's `QObject` machinery,
which doesn't exist before `QApplication` is constructed.
"""

from typing import Protocol

from sagittarius_engine.extensions.pyside_mvc import configure_app_qml
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_extension import IExtension
from tools.state_console.presentation.theme.icon_loader import SimpleIconLoader
from tools.state_console.presentation.theme.palette import (
    STATE_CONSOLE_ICON_PALETTE,
    STATE_CONSOLE_PALETTE,
)


class IConsoleMvcContext(Protocol):
    @property
    def container(self) -> IContainer: ...


class ConsoleMvcExtension(IExtension[IConsoleMvcContext]):
    def register(self, context: IConsoleMvcContext) -> None:
        configure_app_qml(
            STATE_CONSOLE_PALETTE, SimpleIconLoader(), STATE_CONSOLE_ICON_PALETTE
        )

    def boot(self, context: IConsoleMvcContext) -> None:
        pass

    def shutdown(self, context: IConsoleMvcContext) -> None:
        pass
