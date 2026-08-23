from collections.abc import Callable

from examples.student_management.presentation.enroll_form.enroll_form_view_model import (
    EnrollFormViewModel,
)
from sagittarius_engine.extensions.pyside_mvc import IView


class EnrollFormPresenter:
    """
    @brief The IView prototype's actual point: this class never imports
    QML or QWidget machinery, never checks which concrete View it was
    given, and works identically whether `view` is a QmlEnrollFormView or
    a WidgetEnrollFormView -- it only knows `view.bind()` exists (IView),
    same as RosterPresenter today only knows `view.set_view_model()`/
    `view.load_qml()` exist because it was written specifically for
    QmlHostView.

    @param on_submit Injected rather than dispatching a real CQRS command
    directly -- this prototype exists to prove the View-swap works, not to
    re-prove the enroll flow examples/student_management already has via
    RosterPresenter._on_enroll_requested.
    """

    def __init__(
        self, view: IView, on_submit: Callable[[str, str, str, float], None]
    ) -> None:
        self.view = view
        self.view_model = EnrollFormViewModel()
        self._on_submit = on_submit

        self.view.bind(self.view_model)
        self.view_model.submitRequested.connect(self._on_submit_requested)

    def _on_submit_requested(
        self, full_name: str, email: str, major: str, gpa: float
    ) -> None:
        self._on_submit(full_name, email, major, gpa)
