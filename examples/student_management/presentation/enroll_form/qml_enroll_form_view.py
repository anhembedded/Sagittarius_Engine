from pathlib import Path
from typing import Any

from sagittarius_engine.extensions.pyside_mvc import QmlHostView


class QmlEnrollFormView(QmlHostView):
    """
    @brief QML rendering backend for the enroll form -- satisfies IView via
    `bind()`, which does exactly what RosterView's Presenter already does
    by hand (`set_view_model()` then `load_qml()`), just packaged behind
    the one-method contract a renderer-agnostic Presenter can call without
    knowing this is QML underneath.
    """

    QML_DIR = Path(__file__).parent / "qml"

    def bind(self, view_model: Any) -> None:
        self.set_view_model(view_model)
        self.load_qml("EnrollForm.qml")
