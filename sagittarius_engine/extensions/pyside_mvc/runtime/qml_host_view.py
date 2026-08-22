from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QVBoxLayout

from sagittarius_engine.extensions.pyside_mvc.mvc.base_view import BaseView
from sagittarius_engine.extensions.pyside_mvc.tokens.theme_bridge import register_theme
from sagittarius_engine.extensions.pyside_mvc.tokens.vocabulary import (
    MissingRequiredTokensError,
    missing_required_tokens,
)

from .icon_image_provider import ICON_PROVIDER_ID, IconImageProvider, IIconLoader
from .qml_style import ensure_qml_style

#: The widget kit's QML lives at `pyside_mvc/Sagittarius/UI/` (the
#: `Sagittarius.UI` module — see EPIC-001C's directory-per-component
#: reorg). Consumer .qml files reach it as `import Sagittarius.UI 1.0`
#: once *this* path (the directory containing `Sagittarius/`) has been
#: added to the QQmlEngine's import path (see create_quick_widget) — Qt
#: resolves a namespaced module by walking `Sagittarius/UI/qmldir` under
#: one of the configured import paths.
#:
#: Written as an explicit path relative to this package's own root, not
#: derived from any other directory's coincidental depth/position — the
#: assertion below turns a future "someone moved the QML tree and forgot
#: this constant" into a loud failure right here, instead of a silent
#: `import Sagittarius.UI 1.0` resolution failure deep inside Qt with no
#: indication of why.
_PYSIDE_MVC_ROOT = Path(__file__).resolve().parent.parent
_QML_MODULE_ROOT = _PYSIDE_MVC_ROOT / "Sagittarius" / "UI"
_QML_IMPORT_PATH = str(_PYSIDE_MVC_ROOT)
assert (_QML_MODULE_ROOT / "qmldir").is_file(), (
    f"Expected the Sagittarius.UI QML module at {_QML_MODULE_ROOT}/qmldir — "
    "not found. qml_host_view.py's location relative to the QML module tree "
    "has changed without updating _PYSIDE_MVC_ROOT/_QML_MODULE_ROOT above."
)


@dataclass(frozen=True)
class AppQmlConfig:
    ui_palette: dict[str, str]
    icon_loader: IIconLoader
    icon_palette: dict[str, str]


_app_qml_config: AppQmlConfig | None = None


def configure_app_qml(
    ui_palette: dict[str, str],
    icon_loader: IIconLoader,
    icon_palette: dict[str, str],
) -> None:
    """
    @brief Registers the app's theme/icon wiring for every QmlHostView to
    use. Call once during bootstrap, before constructing any QML-hosted view.

    @details
    A one-time module-level registration rather than a constructor
    parameter on every QmlHostView subclass: those subclasses are
    instantiated throughout the app's presentation layer with no other
    reason to know about theming, so threading palette/icon_loader through
    every one of their constructors would leak a cross-cutting concern into
    call sites that have nothing to do with it. Mirrors the lazy-singleton
    pattern already used for the theme bridge itself.

    @param ui_palette Maps QML property name (e.g. "accent", "bgSidebar") to
    a color value — exposed to QML as `Theme.<name>`. Must supply every
    token in `tokens.vocabulary.REQUIRED_COLOUR_TOKENS`.
    @param icon_loader The app's own icon loader, satisfying IIconLoader.
    @param icon_palette Maps icon-color token (used in
    `image://icons/<name>/<token>` URLs) to a color value. Kept distinct
    from `ui_palette` since the two vocabularies evolved independently.

    @raise MissingRequiredTokensError If `ui_palette` omits any required
    colour token. Fails here, at the one place an app declares its palette,
    rather than deferring to an undefined `Theme.<name>` surfacing later as
    a silent rendering bug somewhere in QML — see `ui-architecture.md` §2.1.
    """
    missing = missing_required_tokens(ui_palette)
    if missing:
        raise MissingRequiredTokensError(missing)

    global _app_qml_config
    _app_qml_config = AppQmlConfig(
        ui_palette=ui_palette, icon_loader=icon_loader, icon_palette=icon_palette
    )


def create_quick_widget() -> QQuickWidget:
    """
    @brief Builds a QQuickWidget wired with this framework's shared QML
    plumbing — the "Basic" style, the `Theme` singleton, and the icon
    provider.

    @details
    Every QML-hosting widget needs this setup, whether it's the sole widget
    of a QmlHostView (one QML screen per View) or one of several widgets
    sharing a single View. Factored out so every path configures
    identically instead of hand-rolling a partial copy.

    @raise RuntimeError If called before @ref configure_app_qml.
    """
    if _app_qml_config is None:
        raise RuntimeError(
            "create_quick_widget() called before configure_app_qml() — "
            "call it once during app bootstrap first."
        )

    ensure_qml_style()
    quick_widget = QQuickWidget()
    quick_widget.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    quick_widget.engine().addImportPath(_QML_IMPORT_PATH)
    register_theme(quick_widget, _app_qml_config.ui_palette)
    # Engine takes ownership of the provider, so each QQuickWidget gets its
    # own instance; the underlying icon_loader it delegates to is whatever
    # the app registered — typically its own shared app-wide singleton, so
    # the icon cache is still not duplicated.
    quick_widget.engine().addImageProvider(
        ICON_PROVIDER_ID,
        IconImageProvider(_app_qml_config.icon_loader, _app_qml_config.icon_palette),
    )
    return quick_widget


class QmlHostView(BaseView):
    """
    @brief Base class for every QML-backed screen: hosts a QQuickWidget,
    wires the shared `Theme` singleton, and bridges BasePresenter's FSM
    state into a QML-bindable property.

    @details
    Being a QWidget subclass is what lets PresenterManager keep routing
    these screens with zero changes (`stacked_widget.addWidget(view)`).

    Ordering contract: `setSource()` is deliberately NOT called in
    __init__ — a Presenter must register its ViewModel as a context
    property *before* `load_qml()`, or QML resolves that name to undefined
    at parse time. Subclass presenters call:
        view.set_view_model(vm)   # optional, screen-specific
        view.load_qml("screen.qml")

    FSM binding: BasePresenter._bind_fsm_to_ui duck-types
    `view.apply_ui_mode(mode, section_key)` (falling back to it when the
    view has no `control_card`), so overriding it here is enough to route
    FSM state into QML — no changes to the shared pyside_mvc package.
    Screens expose it to QML as a `uiMode` string property on their
    ViewModel, which QML binds to directly (e.g.
    `enabled: viewModel.uiMode !== "LOCKED"`), replacing the
    reflection-based ui_matrix.json mechanism used by the Widgets screens.
    """

    #: Subclasses set this to the directory holding their .qml files.
    QML_DIR: Path = Path(__file__).parent

    def __init__(self, parent=None):
        super().__init__(parent)

        self.quick_widget = create_quick_widget()
        self._view_model = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.quick_widget)

    def set_view_model(self, view_model, context_name: str = "viewModel") -> None:
        """Registers a screen's ViewModel as a QML context property. Must be
        called before load_qml() — see the ordering contract above."""
        self._view_model = view_model
        self.quick_widget.rootContext().setContextProperty(context_name, view_model)

    def load_qml(self, qml_filename: str) -> None:
        """Loads a QML document by filename, relative to the subclass's QML_DIR."""
        qml_path = self.QML_DIR / qml_filename
        self.quick_widget.setSource(QUrl.fromLocalFile(str(qml_path)))

    def apply_ui_mode(self, mode, section_key: str = "main") -> None:
        """
        @brief Receives FSM state changes from BasePresenter and forwards them
        to the ViewModel's `uiMode` property for QML to bind against.
        @param mode A UIMode enum member or plain string; normalized to its
        string value (BasePresenter passes the enum, tests may pass either).
        @param section_key Accepted for signature compatibility with
        UIMatrixMixin.apply_ui_mode; unused here — QML screens bind their own
        controls directly instead of consulting a per-section JSON matrix.
        """
        if self._view_model is None:
            return
        mode_value = getattr(mode, "value", mode)
        self._view_model.set_ui_mode(str(mode_value))
