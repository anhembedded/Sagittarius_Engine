from typing import Protocol, runtime_checkable

from examples.student_management.presentation.enroll_form.qml_enroll_form_view import (
    QmlEnrollFormView,
)
from sagittarius_engine.extensions.pyside_mvc import IView
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer

#: Guarded the same way roster_view_factory.py guards WidgetRosterView --
#: see that module's own comment for why (qfluentwidgets must not become
#: a hard dependency of the QML-only path).
try:
    from examples.student_management.presentation.enroll_form.widget_enroll_form_view import (
        WidgetEnrollFormView,
    )

    _WIDGET_ENROLL_FORM_VIEW_AVAILABLE = True
except ImportError:
    _WIDGET_ENROLL_FORM_VIEW_AVAILABLE = False


@runtime_checkable
class IEnrollFormView(IView, Protocol):
    """
    @brief `IView`, keyed distinctly per screen. `IContainer.singleton`
    caches one factory per abstract type -- registering the roster screen's
    own view under the same bare `IView` key would silently overwrite this
    one (found 2026-08-23 adding WidgetRosterView, the second screen to use
    this pattern). Adds no members of its own; it exists purely so this
    screen has its own resolvable container key.
    """


def register_enroll_form_view(container: IContainer) -> None:
    """
    @brief Registers `IEnrollFormView` -> either `QmlEnrollFormView` or
    `WidgetEnrollFormView`, decided once the first time it is resolved.

    @details The container's own factory-function support does the
    picking (`IContainer.singleton` accepts a callable; called once,
    cached) -- nothing that later calls `container.resolve(IEnrollFormView)`
    needs an if/else of its own, or even needs to know two implementations
    exist. Reads `ui.qtwidget` off `IConfig` (mirrors `database.url`,
    `env`, etc. -- an ordinary config-driven choice, not a special case).
    """

    def _build_view(c: IContainer) -> IEnrollFormView:
        config = c.resolve(IConfig)
        use_qtwidget = bool(config.get("ui.qtwidget", False))
        if use_qtwidget:
            if not _WIDGET_ENROLL_FORM_VIEW_AVAILABLE:
                raise ImportError(
                    "ui.qtwidget is set but qfluentwidgets is not installed -- "
                    "install PySide6-Fluent-Widgets (see requirements.txt) to use "
                    "the --qtwidget backend."
                )
            return WidgetEnrollFormView()
        return QmlEnrollFormView()

    container.singleton(IEnrollFormView, _build_view)
