from PySide6.QtGui import QIcon, QPainter, QPixmap


class SimpleIconLoader:
    """Satisfies pyside_mvc's IIconLoader with a plain filled circle,
    recolored per request — the same precedent
    `examples/student_management`'s own `SimpleIconLoader` sets: this tool
    has no real icon asset set, and a procedural glyph is enough to prove
    `image://icons/<name>/<token>` resolves and paints, which is all
    `configure_app_qml()` requires."""

    def get_icon(self, name: str, color: str, size: int) -> QIcon:
        pixmap = QPixmap(size, size)
        pixmap.fill("transparent")
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(color)
        painter.setPen("transparent")
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        return QIcon(pixmap)
