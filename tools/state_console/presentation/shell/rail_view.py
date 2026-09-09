from pathlib import Path
from typing import Any

from sagittarius_engine.extensions.pyside_mvc import QmlHostView

#: `AppRail.qml`'s own `implicitWidth` -- fixed here too so the widget's
#: actual size (which `ResizeMode.SizeRootObjectToView` then stretches the
#: QML root to fill) matches the design rather than whatever the layout
#: would otherwise give it.
_RAIL_WIDTH = 218


class RailView(QmlHostView):
    QML_DIR = Path(__file__).parent / "qml"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(_RAIL_WIDTH)

    def bind(self, view_model: Any) -> None:
        self.set_view_model(view_model)
        self.load_qml("Rail.qml")
