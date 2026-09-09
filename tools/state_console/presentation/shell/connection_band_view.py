from pathlib import Path
from typing import Any

from sagittarius_engine.extensions.pyside_mvc import QmlHostView

#: `reference/handoff.md` §6's own shell layout figure -- the status band is
#: always exactly this tall, regardless of window size.
_BAND_HEIGHT = 62


class ConnectionBandView(QmlHostView):
    QML_DIR = Path(__file__).parent / "qml"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(_BAND_HEIGHT)

    def bind(self, view_model: Any) -> None:
        self.set_view_model(view_model)
        self.load_qml("ConnectionBand.qml")
