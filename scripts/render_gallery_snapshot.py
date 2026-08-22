"""Renders Sagittarius/UI/Gallery/Gallery.qml offscreen and saves a PNG snapshot.

Not a test — a manual/CI-optional tool for actually *seeing* the Widget
Kit (EPIC-001C) instead of trusting that the QML loads clean. Uses the
reference consumer's real black/gold palette so the snapshot reflects the
UI Engine's intended visual identity, not an arbitrary placeholder.

Usage:
    QT_QPA_PLATFORM=offscreen python scripts/render_gallery_snapshot.py [output.png]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QUrl
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from sagittarius_engine.extensions.pyside_mvc.runtime import (
    configure_app_qml,
    create_quick_widget,
)

#: The reference consumer's real palette (Sagittarius_Elite_Warrior's
#: assets/palette.py Palette.as_ui_dict()) — the actual black/gold identity
#: this engine is being built for, not an arbitrary placeholder.
_REFERENCE_PALETTE = {
    "bg": "#0a0a0c",
    "bgSidebar": "#0d0e11",
    "bgCard": "#111318",
    "bgCardHeader": "#15171d",
    "border": "#23262e",
    "textPrimary": "#e8e9ec",
    "accent": "#F3BA2F",
    "success": "#0ECB81",
    "danger": "#F6465D",
    "muted": "#848E9C",
}


class _PlaceholderIconLoader:
    """Procedural rounded-square glyph tinted per request — good enough to
    prove `image://icons/<name>/<token>` resolves and paints, without
    depending on any consuming app's real SVG icon set from this repo."""

    def get_icon(self, name: str, color: str, size: int) -> QIcon:
        pixmap = QPixmap(size, size)
        pixmap.fill("transparent")
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(color)
        painter.setPen("transparent")
        inset = max(1, size // 6)
        painter.drawRoundedRect(inset, inset, size - 2 * inset, size - 2 * inset, 3, 3)
        painter.end()
        return QIcon(pixmap)


GALLERY_QML = (
    Path(__file__).resolve().parent.parent
    / "sagittarius_engine"
    / "extensions"
    / "pyside_mvc"
    / "Sagittarius"
    / "UI"
    / "Gallery"
    / "Gallery.qml"
)


def _build_gallery_widget():
    """Boots the shared QML plumbing and loads the Gallery, exiting on any
    QML error rather than showing a half-rendered window — a silently
    broken gallery is worse than no gallery, since its whole purpose is to
    be trusted as a visual reference."""
    configure_app_qml(
        _REFERENCE_PALETTE, _PlaceholderIconLoader(), {"muted": "#848E9C"}
    )

    quick_widget = create_quick_widget()
    quick_widget.resize(960, 1200)
    quick_widget.setWindowTitle("Sagittarius UI Engine — Widget Kit Gallery")
    quick_widget.setSource(QUrl.fromLocalFile(str(GALLERY_QML)))

    errors = quick_widget.errors()
    if errors:
        for error in errors:
            print(f"QML ERROR: {error.toString()}", file=sys.stderr)
        sys.exit(1)

    return quick_widget


def render(output_path: Path) -> None:
    """Headless: renders the Gallery offscreen and writes a PNG."""
    app = QApplication.instance() or QApplication(sys.argv)
    quick_widget = _build_gallery_widget()

    app.processEvents()
    quick_widget.show()
    for _ in range(10):
        app.processEvents()

    image = quick_widget.grabFramebuffer()
    if image.isNull():
        print("grabFramebuffer() returned a null image", file=sys.stderr)
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(output_path))
    print(f"Saved {output_path} ({image.width()}x{image.height()})")


def show() -> int:
    """Interactive: opens a real window and blocks until it is closed.

    The reason this mode exists at all: hover, press and focus states are
    invisible in a snapshot (no synthetic pointer is driven), so the PNG
    alone cannot verify roughly half of what `StatefulButton` and the
    input controls actually do.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    quick_widget = _build_gallery_widget()
    quick_widget.show()
    return app.exec()


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--show":
        sys.exit(show())
    out = Path(args[0]) if args else Path("gallery_snapshot.png")
    render(out)
