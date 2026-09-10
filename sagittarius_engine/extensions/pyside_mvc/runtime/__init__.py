"""
@brief Screen-hosting / bootstrap layer — `configure_app_qml()` and
`create_quick_widget()` (the one-time app wiring and the per-screen
QQuickWidget factory), `QmlHostView` (the QML-backed screen base class),
`OverlayHost` (full-window modal hosting, `BOT-087`), the icon image
provider, and the Python<->QML value-normalization/model-adapter glue.

Split out of the flat `QmlShared/` (EPIC-001C reorg): this package is pure
Python bootstrap/runtime plumbing, distinct from `QmlShared/`'s pure QML
widget-kit content — the two used to share one directory, which is exactly
the "different abstraction levels sitting together" problem this reorg
fixes. See `ui-architecture.md` and this extension's target structure
recorded in `EPIC-001A`.
"""

from .base_view_model import BaseQmlViewModel
from .icon_image_provider import ICON_PROVIDER_ID, IconImageProvider, IIconLoader
from .log_list_model import LogListModel
from .overlay_host import OverlayHost
from .qml_host_view import (
    AppQmlConfig,
    QmlHostView,
    configure_app_qml,
    create_quick_widget,
)
from .qml_style import ensure_qml_style
from .qml_value_normalizer import from_qml
from .quick_background import DEFAULT_BACKGROUND, resolve_opaque_background

__all__ = [
    "DEFAULT_BACKGROUND",
    "ICON_PROVIDER_ID",
    "AppQmlConfig",
    "BaseQmlViewModel",
    "IIconLoader",
    "IconImageProvider",
    "LogListModel",
    "OverlayHost",
    "QmlHostView",
    "configure_app_qml",
    "create_quick_widget",
    "ensure_qml_style",
    "from_qml",
    "resolve_opaque_background",
]
