from typing import Protocol, runtime_checkable

from examples.student_management.presentation.roster.roster_view import RosterView
from sagittarius_engine.extensions.pyside_mvc import IView
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer

#: WidgetRosterView imports qfluentwidgets, a third-party dependency the
#: QML-only path has no reason to require -- guarded the same way
#: persistence/database_module.py guards its own optional `sqlalchemy`
#: import (top-level try/except, not a function-local import; this
#: codebase's `code-rule.md` §5 forbids local imports outright). Found
#: 2026-08-23: an unguarded top-level import of WidgetRosterView here
#: made qfluentwidgets a hard dependency even for callers that never
#: select `--qtwidget`, breaking any environment with PySide6 but not
#: qfluentwidgets installed (this repo's own system Python, before a
#: `.venv` was set up).
try:
    from examples.student_management.presentation.roster.widget_roster_view import (
        WidgetRosterView,
    )

    _WIDGET_ROSTER_VIEW_AVAILABLE = True
except ImportError:
    _WIDGET_ROSTER_VIEW_AVAILABLE = False


@runtime_checkable
class IRosterView(IView, Protocol):
    """`IView`, keyed distinctly for the roster screen -- see
    `IEnrollFormView`'s own docstring for why each screen needs its own
    marker type rather than sharing the bare `IView` container key."""


def register_roster_view(container: IContainer) -> None:
    """
    @brief Registers `IRosterView` -> either `RosterView` (QML) or
    `WidgetRosterView` (QWidget, TASK-037's full rollout), decided once
    the first time it is resolved -- same `ui.qtwidget`-driven factory
    pattern as `register_enroll_form_view`.
    """

    def _build_view(c: IContainer) -> IRosterView:
        config = c.resolve(IConfig)
        use_qtwidget = bool(config.get("ui.qtwidget", False))
        if use_qtwidget:
            if not _WIDGET_ROSTER_VIEW_AVAILABLE:
                raise ImportError(
                    "ui.qtwidget is set but qfluentwidgets is not installed -- "
                    "install PySide6-Fluent-Widgets (see requirements.txt) to use "
                    "the --qtwidget backend."
                )
            return WidgetRosterView()
        return RosterView()

    container.singleton(IRosterView, _build_view)
