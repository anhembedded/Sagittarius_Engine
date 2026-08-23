from pathlib import Path

from sagittarius_engine.extensions.pyside_mvc import QmlHostView


class RosterView(QmlHostView):
    QML_DIR = Path(__file__).parent / "qml"
