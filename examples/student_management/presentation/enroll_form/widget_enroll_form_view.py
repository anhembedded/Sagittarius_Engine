from typing import Any

from PySide6.QtWidgets import QFormLayout, QVBoxLayout
from qfluentwidgets import (
    DoubleSpinBox,
    FluentIcon,
    LineEdit,
    PrimaryPushButton,
    Theme,
    TitleLabel,
    setTheme,
)

from examples.student_management.presentation.enroll_form.enroll_form_view_model import (
    EnrollFormViewModel,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView


class WidgetEnrollFormView(BaseView):
    """
    @brief QWidget rendering backend for the same enroll form
    QmlEnrollFormView renders -- IView's other half of the prototype.
    Styled with qfluentwidgets (a real third-party library), same as
    WidgetRosterView -- every class here is a genuine subclass of its
    stock-Qt counterpart, so the wiring logic below is unchanged from the
    plain-Qt version.

    @details No custom date/number-parsing needed here the way
    EnrollForm.qml's GPA field has to hand-parse `parseFloat(text) || 0.0`:
    DoubleSpinBox validates range/decimals natively. That is the concrete
    version of the "QWidget gives you more for free" tradeoff this
    prototype exists to demonstrate -- not a hypothetical.
    """

    def bind(self, view_model: Any) -> None:
        assert isinstance(view_model, EnrollFormViewModel)
        self._view_model = view_model

        # qfluentwidgets defaults to its light theme regardless of the
        # window's own (dark) background -- idempotent, so safe to call
        # every bind() even though it's a process-global setting.
        setTheme(Theme.DARK)

        layout = QVBoxLayout(self)
        layout.addWidget(TitleLabel("Enroll Student"))

        form = QFormLayout()
        layout.addLayout(form)

        self._full_name_field = LineEdit()
        self._full_name_field.setText(view_model.fullName)
        self._full_name_field.setPlaceholderText("Full name")
        form.addRow("Full name", self._full_name_field)

        self._email_field = LineEdit()
        self._email_field.setText(view_model.email)
        self._email_field.setPlaceholderText("Email")
        form.addRow("Email", self._email_field)

        self._major_field = LineEdit()
        self._major_field.setText(view_model.major)
        self._major_field.setPlaceholderText("Major")
        form.addRow("Major", self._major_field)

        self._gpa_field = DoubleSpinBox()
        self._gpa_field.setRange(0.0, 4.0)
        self._gpa_field.setDecimals(2)
        self._gpa_field.setSingleStep(0.1)
        self._gpa_field.setValue(view_model.gpa)
        form.addRow("GPA", self._gpa_field)

        self._submit_button = PrimaryPushButton(FluentIcon.ADD, "Enroll")
        self._submit_button.setObjectName("btnSubmitEnrollForm")
        layout.addWidget(self._submit_button)
        layout.addStretch()

        self._full_name_field.textEdited.connect(self._on_full_name_edited)
        self._email_field.textEdited.connect(self._on_email_edited)
        self._major_field.textEdited.connect(self._on_major_edited)
        self._gpa_field.valueChanged.connect(self._on_gpa_changed)
        self._submit_button.clicked.connect(view_model.submit)

        # The other direction: QML's `text: viewModel.fullName` binding
        # re-renders automatically whenever the ViewModel changes, for
        # free, declaratively. A QWidget View has no such thing built in --
        # skipping this half (found 2026-08-23, verifying this prototype
        # with a real screenshot: fields set programmatically on the
        # ViewModel never appeared in the QLineEdits) would make this View
        # silently one-way, breaking for any future case where something
        # other than the user's own typing changes the ViewModel (a form
        # reset after submit, a value restored from a draft, etc.).
        view_model.fullNameChanged.connect(self._sync_full_name)
        view_model.emailChanged.connect(self._sync_email)
        view_model.majorChanged.connect(self._sync_major)
        view_model.gpaChanged.connect(self._sync_gpa)

    def _on_full_name_edited(self, text: str) -> None:
        self._view_model.fullName = text

    def _on_email_edited(self, text: str) -> None:
        self._view_model.email = text

    def _on_major_edited(self, text: str) -> None:
        self._view_model.major = text

    def _on_gpa_changed(self, value: float) -> None:
        self._view_model.gpa = value

    def _sync_full_name(self) -> None:
        if self._full_name_field.text() != self._view_model.fullName:
            self._full_name_field.setText(self._view_model.fullName)

    def _sync_email(self) -> None:
        if self._email_field.text() != self._view_model.email:
            self._email_field.setText(self._view_model.email)

    def _sync_major(self) -> None:
        if self._major_field.text() != self._view_model.major:
            self._major_field.setText(self._view_model.major)

    def _sync_gpa(self) -> None:
        if self._gpa_field.value() != self._view_model.gpa:
            self._gpa_field.setValue(self._view_model.gpa)
