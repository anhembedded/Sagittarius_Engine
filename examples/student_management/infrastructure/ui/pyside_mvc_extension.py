from typing import Protocol

from examples.student_management.presentation.theme.icon_loader import SimpleIconLoader
from examples.student_management.presentation.theme.palette import (
    STUDENT_MANAGEMENT_ICON_PALETTE,
    STUDENT_MANAGEMENT_PALETTE,
)
from sagittarius_engine.extensions.pyside_mvc import configure_app_qml
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_extension import IExtension


class IPySideMvcContext(Protocol):
    @property
    def container(self) -> IContainer: ...


class PySideMvcExtension(IExtension[IPySideMvcContext]):
    """
    @brief App-side IExtension wrapper for the engine's pyside_mvc UI framework.

    @details No IExtension for pyside_mvc exists in the engine itself yet —
    EPIC-001D decided it should, but hasn't built it (see
    Tasks/epics/EPIC-001_ui_engine_foundation/incomplete/EPIC-001D_runtime_slot_registry.md).
    This class is a real, running prototype of what that engine-side class
    needs to do, kept here (app code) rather than in sagittarius_engine/ —
    see docs/ui_extension_lifecycle.md for the full ordering story.

    Caller contract (see gui.py): a QApplication MUST already exist before
    app.boot() runs this extension's register() — configure_app_qml()
    (and everything it sets up) needs a running Qt event loop's QObject
    machinery, which doesn't exist before QApplication is constructed.
    This is the one thing EPIC-001D's eventual engine-side version cannot
    avoid either; it's a property of Qt, not of how this wrapper is written.
    """

    def register(self, context: IPySideMvcContext) -> None:
        configure_app_qml(
            STUDENT_MANAGEMENT_PALETTE,
            SimpleIconLoader(),
            STUDENT_MANAGEMENT_ICON_PALETTE,
        )

    def boot(self, context: IPySideMvcContext) -> None:
        pass

    def shutdown(self, context: IPySideMvcContext) -> None:
        pass
