"""
@brief PySide6 MVC Extension for Sagittarius Engine — the Sagittarius UI
Engine. See `README.md` for the ownership boundary (tokens/kit/runtime)
and directory layout.
@details Provides true lazy-loaded UI routing, base presenters, and data-driven matrix UI.
"""

import sys

# Dependency Guard: Protects the UI-Agnostic Core from crashing if PySide6 is missing.
try:
    import PySide6
except ImportError:
    print(
        "[sagittarius_engine.extensions.pyside_mvc] WARNING: PySide6 is not installed. "
        "The pyside_mvc extension will be unavailable. Please install PySide6 if you need GUI features.",
        file=sys.stderr,
    )
    # Expose dummies or just let subsequent imports fail explicitly when consumer code runs.
    # We don't raise an error here because simply scanning the extensions folder shouldn't crash the engine.
else:
    from .kit import RawPrimitiveFinding, find_raw_primitives
    from .mvc import (
        BasePresenter,
        BaseView,
        EventDelivery,
        IView,
        PresenterManager,
        QtEventBridge,
    )
    from .runtime import (
        ICON_PROVIDER_ID,
        AppQmlConfig,
        BaseQmlViewModel,
        IconImageProvider,
        IIconLoader,
        LogListModel,
        OverlayHost,
        QmlHostView,
        configure_app_qml,
        create_quick_widget,
        ensure_qml_style,
        from_qml,
    )
    from .safety import (
        CrossThreadUiMutationError,
        UIMatrixMixin,
        UIWatchdog,
        not_a_ui_mutator,
        safe_ui_action,
        set_thread_affinity_dev_mode,
        setup_qt_signal_handling,
        ui_mutator,
        unprotected_mutators,
    )
    from .tokens import (
        DEFAULT_MOTION_TOKENS,
        DEFAULT_RADIUS_TOKENS,
        DEFAULT_SPACING_TOKENS,
        DEFAULT_STATE_TOKENS,
        DEFAULT_TYPOGRAPHY_TOKENS,
        REQUIRED_COLOUR_TOKEN_NAMES,
        REQUIRED_COLOUR_TOKENS,
        LiteralColorFinding,
        MissingRequiredTokensError,
        TokenSpec,
        find_literal_colors,
        get_theme_bridge,
        missing_required_tokens,
        register_theme,
        with_state_token_defaults,
        with_token_defaults,
    )
    from .widgets import (
        BareQtBaseFinding,
        Card,
        DateTimeField,
        InlineStylesheetFinding,
        Overlay,
        Panel,
        SelectableCard,
        StyledButton,
        StyledCheckBox,
        StyledField,
        StyleRole,
        Surface,
        WidgetState,
        apply_role,
        find_bare_qt_base_widgets,
        find_inline_stylesheets,
        format_bare_qt_base_findings,
        format_inline_stylesheet_findings,
    )

    __all__ = [
        "DEFAULT_MOTION_TOKENS",
        "DEFAULT_RADIUS_TOKENS",
        "DEFAULT_SPACING_TOKENS",
        "DEFAULT_STATE_TOKENS",
        "DEFAULT_TYPOGRAPHY_TOKENS",
        "ICON_PROVIDER_ID",
        "REQUIRED_COLOUR_TOKENS",
        "REQUIRED_COLOUR_TOKEN_NAMES",
        "AppQmlConfig",
        "BareQtBaseFinding",
        "BasePresenter",
        "EventDelivery",
        "BaseQmlViewModel",
        "BaseView",
        "Card",
        "CrossThreadUiMutationError",
        "DateTimeField",
        "IIconLoader",
        "IView",
        "IconImageProvider",
        "InlineStylesheetFinding",
        "LiteralColorFinding",
        "LogListModel",
        "MissingRequiredTokensError",
        "Overlay",
        "OverlayHost",
        "Panel",
        "PresenterManager",
        "QtEventBridge",
        "QmlHostView",
        "RawPrimitiveFinding",
        "SelectableCard",
        "StyleRole",
        "StyledButton",
        "StyledCheckBox",
        "StyledField",
        "Surface",
        "TokenSpec",
        "UIMatrixMixin",
        "UIWatchdog",
        "WidgetState",
        "apply_role",
        "configure_app_qml",
        "create_quick_widget",
        "ensure_qml_style",
        "find_bare_qt_base_widgets",
        "find_inline_stylesheets",
        "find_literal_colors",
        "find_raw_primitives",
        "format_bare_qt_base_findings",
        "format_inline_stylesheet_findings",
        "from_qml",
        "get_theme_bridge",
        "missing_required_tokens",
        "not_a_ui_mutator",
        "register_theme",
        "safe_ui_action",
        "set_thread_affinity_dev_mode",
        "setup_qt_signal_handling",
        "ui_mutator",
        "unprotected_mutators",
        "with_state_token_defaults",
        "with_token_defaults",
    ]
