from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt, QUrl
from PySide6.QtGui import QColor
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget

from .qml_host_view import create_quick_widget

#: `OverlayHost.qml` is deliberately kept as a sibling of this file, not
#: inside the `Sagittarius.UI` widget kit — it is bootstrap plumbing (loaded
#: by direct file path, never `import`ed by other QML) paired 1:1 with this
#: module, not a reusable component. The assertion converts a future
#: accidental split of the pair into a loud failure here rather than a
#: silent `QQuickWidget.setSource()` failure at first use.
_OVERLAY_HOST_QML = Path(__file__).with_name("OverlayHost.qml")
assert _OVERLAY_HOST_QML.is_file(), (
    f"Expected OverlayHost.qml next to overlay_host.py at {_OVERLAY_HOST_QML} "
    "— not found. The two are meant to move together."
)
_OVERLAY_CONTENT_PROPERTY = "contentSource"
_HAS_OPEN_MODAL_PROPERTY = "hasOpenModal"
_OVERLAY_WIDTH_PROPERTY = "overlayWidth"
_OVERLAY_HEIGHT_PROPERTY = "overlayHeight"


class OverlayHost(QObject):
    """Hosts QML modal content above every child of one QWidget.

    ``OverlayHost`` owns a transparent ``QQuickWidget`` that is parented to
    ``parent_widget`` but deliberately excluded from its layout.  Consequently
    a QML ``Popup`` loaded through :meth:`load_content` resolves
    ``Overlay.overlay`` against the full parent widget rather than a small
    QML panel nested inside it.

    A loaded QML document must expose a bindable ``hasOpenModal`` boolean.
    The document remains the source of truth for whether input is captured;
    this class only maps that property to Qt's click-through attribute.
    """

    def __init__(self, parent_widget: QWidget) -> None:
        """Creates an overlay that tracks ``parent_widget``'s geometry."""
        super().__init__(parent_widget)
        self._parent_widget = parent_widget
        self._is_disposed = False
        self._quick_widget = create_quick_widget()
        self._quick_widget.setParent(parent_widget)
        self._quick_widget.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)
        self._quick_widget.setClearColor(QColor(Qt.GlobalColor.transparent))

        self._quick_widget.setSource(QUrl.fromLocalFile(str(_OVERLAY_HOST_QML)))
        self._parent_widget.installEventFilter(self)

        root = self._quick_widget.rootObject()
        if root is None:
            raise RuntimeError("OverlayHost.qml did not create a QML root object.")
        root.hasOpenModalChanged.connect(self._sync_input_transparency)

        self._sync_geometry()
        self._quick_widget.show()
        self._sync_input_transparency()

    @property
    def quick_widget(self) -> QQuickWidget:
        """Returns the full-window QML widget owned by this host."""
        return self._quick_widget

    @property
    def content_item(self) -> QObject | None:
        """Returns the root QML item loaded through :meth:`load_content`."""
        root = self._quick_widget.rootObject()
        if root is None:
            return None
        return root.property("contentItem")

    @property
    def overlay_size(self) -> tuple[int, int]:
        """Returns the QML ``Overlay.overlay`` dimensions for UI assertions."""
        root = self._quick_widget.rootObject()
        if root is None:
            return (0, 0)
        return (
            int(root.property(_OVERLAY_WIDTH_PROPERTY)),
            int(root.property(_OVERLAY_HEIGHT_PROPERTY)),
        )

    @property
    def is_click_through(self) -> bool:
        """Whether empty overlay space currently passes input to widgets below."""
        return self._quick_widget.testAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )

    def load_content(
        self, source: QUrl, context_properties: Mapping[str, Any] | None = None
    ) -> None:
        """Loads a QML modal document and supplies its required context values.

        ``source`` must resolve to an ``Item`` exposing ``hasOpenModal``.  The
        context properties are registered before the Loader receives the URL,
        preserving the same parse-time ordering contract as ``QmlHostView``.
        """
        if source.isEmpty() or not source.isValid():
            raise ValueError("Overlay content source must be a valid QUrl.")

        if context_properties is not None:
            self._set_context_properties(context_properties)

        root = self._require_root()
        root.setProperty(_OVERLAY_CONTENT_PROPERTY, source)

    def clear_content(self) -> None:
        """Unloads the current modal document and restores click-through."""
        root = self._require_root()
        root.setProperty(_OVERLAY_CONTENT_PROPERTY, QUrl())

    def dispose(self) -> None:
        """Detaches event handling and schedules the overlay widget for deletion."""
        if self._is_disposed:
            return
        self._is_disposed = True
        self._parent_widget.removeEventFilter(self)
        self._quick_widget.deleteLater()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Keeps the overlay aligned with its parent without consuming events."""
        parent_widget = getattr(self, "_parent_widget", None)
        if (
            parent_widget is not None
            and not getattr(self, "_is_disposed", False)
            and watched is parent_widget
            and event.type()
            in {
                QEvent.Type.Resize,
                QEvent.Type.Show,
            }
        ):
            self._sync_geometry()
        return False

    def _set_context_properties(self, context_properties: Mapping[str, Any]) -> None:
        for name, value in context_properties.items():
            self._quick_widget.rootContext().setContextProperty(name, value)

    def _require_root(self) -> QObject:
        root = self._quick_widget.rootObject()
        if root is None:
            raise RuntimeError("OverlayHost.qml root object is unavailable.")
        return root

    def _sync_geometry(self) -> None:
        if self._is_disposed:
            return
        self._quick_widget.setGeometry(self._parent_widget.rect())
        self._quick_widget.raise_()

    def _sync_input_transparency(self) -> None:
        root = self._require_root()
        has_open_modal = bool(root.property(_HAS_OPEN_MODAL_PROPERTY))
        self._quick_widget.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, not has_open_modal
        )
