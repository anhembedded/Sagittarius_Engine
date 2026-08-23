from pathlib import Path
from typing import Any

from sagittarius_engine.extensions.pyside_mvc import QmlHostView


class RosterView(QmlHostView):
    QML_DIR = Path(__file__).parent / "qml"

    def bind(self, view_model: Any) -> None:
        """@brief Satisfies IView -- see WidgetRosterView.bind() for the
        QWidget backend this now has a counterpart to (TASK-037)."""
        self.set_view_model(view_model)
        self.load_qml("RosterScreen.qml")
