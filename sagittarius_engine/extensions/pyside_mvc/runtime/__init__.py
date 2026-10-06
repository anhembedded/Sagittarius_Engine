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

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .contribution_descriptor import ContributionDescriptor
from .contribution_error import ContributionError
from .contribution_registry import ContributionRegistry
from .i_contribution_registry import IContributionRegistry
from .i_region_host import IRegionHost
from .log_list_model import LogListModel
from .qml_value_normalizer import from_qml
from .quick_background import DEFAULT_BACKGROUND, resolve_opaque_background
from .region_host import RegionHost
from .region_kind import RegionKind
from .size_hint import SizeHint
from .surface_declaration import SurfaceDeclaration

if TYPE_CHECKING:
    from .base_view_model import BaseQmlViewModel
    from .icon_image_provider import ICON_PROVIDER_ID, IconImageProvider, IIconLoader
    from .overlay_host import OverlayHost
    from .qml_host_view import (
        AppQmlConfig,
        QmlHostView,
        configure_app_qml,
        create_quick_widget,
    )
    from .qml_style import ensure_qml_style

#: The QML layer, loaded when a name is first used, not at package import.
#: `BaseQmlViewModel` defines `QtCore.Property`s, and PySide6 6.9-6.11 leaks
#: one uncollectable object per such class alive at interpreter exit
#: (BUG-023); the rest pull in Qt Quick, which a consumer that never hosts
#: QML should not pay for. The public names are unchanged (PEP 562).
_LAZY = {
    "BaseQmlViewModel": ".base_view_model",
    "ICON_PROVIDER_ID": ".icon_image_provider",
    "IconImageProvider": ".icon_image_provider",
    "IIconLoader": ".icon_image_provider",
    "OverlayHost": ".overlay_host",
    "AppQmlConfig": ".qml_host_view",
    "QmlHostView": ".qml_host_view",
    "configure_app_qml": ".qml_host_view",
    "create_quick_widget": ".qml_host_view",
    "ensure_qml_style": ".qml_style",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        value = getattr(import_module(_LAZY[name], __name__), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DEFAULT_BACKGROUND",
    "ICON_PROVIDER_ID",
    "AppQmlConfig",
    "BaseQmlViewModel",
    "ContributionDescriptor",
    "ContributionError",
    "ContributionRegistry",
    "IContributionRegistry",
    "IIconLoader",
    "IRegionHost",
    "IconImageProvider",
    "LogListModel",
    "OverlayHost",
    "QmlHostView",
    "RegionHost",
    "RegionKind",
    "SizeHint",
    "SurfaceDeclaration",
    "configure_app_qml",
    "create_quick_widget",
    "ensure_qml_style",
    "from_qml",
    "resolve_opaque_background",
]
