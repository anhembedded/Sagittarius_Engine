from pathlib import Path
from typing import Any

from sagittarius_engine.extensions.pyside_mvc import QmlHostView


class OverviewView(QmlHostView):
    QML_DIR = Path(__file__).parent / "qml"

    def bind(self, view_model: Any) -> None:
        self.set_view_model(view_model)
        self.load_qml("OverviewScreen.qml")
