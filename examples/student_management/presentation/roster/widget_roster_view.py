from typing import Any

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CheckBox,
    DateTimeEdit,
    DoubleSpinBox,
    FluentIcon,
    HeaderCardWidget,
    LineEdit,
    ListWidget,
    MessageBoxBase,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    TableView,
    Theme,
    TitleLabel,
    setTheme,
)

from examples.student_management.presentation.roster.roster_view_model import (
    RosterViewModel,
)
from examples.student_management.presentation.roster.student_table_model import (
    NumericAwareSortProxyModel,
    StudentTableModel,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

#: Matches RosterPresenter's own _DATE_TIME_FORMAT (%Y-%m-%d %H:%M) and
#: DateTimePicker.qml's placeholder -- one format, three places, all
#: independently correct rather than sharing a constant, since they live
#: in different languages/toolkits (Python strftime, QDateTimeEdit).
_QDATETIME_FORMAT = "yyyy-MM-dd HH:mm"


class WidgetRosterView(BaseView):
    """
    @brief QWidget rendering backend for the roster screen -- the full
    rollout TASK-037's enroll-form prototype was validating, now styled
    with qfluentwidgets (a real third-party library, not stock Qt) rather
    than plain QWidget primitives, per the user's own "make it look WOW"
    request after seeing the plain-Qt version work. Every qfluentwidgets
    class used here is a genuine subclass of its stock-Qt counterpart
    (`TableView` subclasses `QTableView`, `DateTimeEdit` subclasses
    `QDateTimeEdit`, etc.) so the widget-wiring code underneath is
    unchanged from the plain-Qt version -- only the imports and
    construction changed.

    @details No compact-mode toggle: BaseCard's compact/full distinction
    is a QML-card-specific visual concept (a badge-sized card vs a full
    one) that has no natural QWidget equivalent worth inventing just for
    parity: omitted rather than faked.
    """

    def bind(self, view_model: Any) -> None:
        assert isinstance(view_model, RosterViewModel)
        self._view_model = view_model
        self._updating_filter_from_model = False

        # qfluentwidgets defaults to its light theme regardless of the
        # window's own (dark) background -- idempotent, so safe to call
        # every bind() even though it's a process-global setting.
        setTheme(Theme.DARK)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        header_row = QHBoxLayout()
        header_row.addWidget(TitleLabel("Student Roster"))
        header_row.addStretch()
        self._enroll_button = PrimaryPushButton(FluentIcon.ADD, "Enroll Student")
        self._enroll_button.setObjectName("btnEnrollStudent")
        self._enroll_button.clicked.connect(self._open_enroll_dialog)
        header_row.addWidget(self._enroll_button)
        outer.addLayout(header_row)

        stats_filter_row = QHBoxLayout()
        stats_filter_row.setSpacing(16)
        stats_filter_row.addWidget(self._build_stats_card())
        stats_filter_row.addWidget(self._build_filter_card())
        stats_filter_row.addStretch()
        outer.addLayout(stats_filter_row)

        table_log_row = QHBoxLayout()
        table_log_row.setSpacing(16)
        table_log_row.addWidget(self._build_table_card(), 3)
        table_log_row.addWidget(self._build_log_card(), 1)
        outer.addLayout(table_log_row)

        view_model.studentsChanged.connect(self._refresh_table)
        view_model.statsChanged.connect(self._refresh_stats)
        view_model.dateFilterChanged.connect(self._sync_filter_from_model)
        view_model.logModel.countChanged.connect(self._refresh_log)

        self._refresh_table()
        self._refresh_stats()
        self._refresh_log()

    # ---- Stats -----------------------------------------------------

    def _build_stats_card(self) -> HeaderCardWidget:
        card = HeaderCardWidget("Roster Stats", self)
        layout = QVBoxLayout()
        self._total_label = BodyLabel("Total: 0")
        self._average_gpa_label = BodyLabel("Average GPA: 0.00")
        layout.addWidget(self._total_label)
        layout.addWidget(self._average_gpa_label)
        card.viewLayout.addLayout(layout)
        return card

    def _refresh_stats(self) -> None:
        self._total_label.setText(f"Total: {self._view_model.totalStudents}")
        self._average_gpa_label.setText(
            f"Average GPA: {self._view_model.averageGpa:.2f}"
        )

    # ---- Time-range filter ------------------------------------------

    def _build_filter_card(self) -> HeaderCardWidget:
        card = HeaderCardWidget("Time Range", self)
        layout = QVBoxLayout()

        self._use_custom_time_check = CheckBox("Use Custom Time Range")
        layout.addWidget(self._use_custom_time_check)

        from_row = QHBoxLayout()
        from_row.addWidget(BodyLabel("From"))
        self._from_edit = DateTimeEdit()
        self._from_edit.setDateTime(QDateTime.currentDateTime())
        self._from_edit.setDisplayFormat(_QDATETIME_FORMAT)
        self._from_edit.setCalendarPopup(True)
        from_row.addWidget(self._from_edit)
        layout.addLayout(from_row)

        to_row = QHBoxLayout()
        to_row.addWidget(BodyLabel("To"))
        self._to_edit = DateTimeEdit()
        self._to_edit.setDateTime(QDateTime.currentDateTime())
        self._to_edit.setDisplayFormat(_QDATETIME_FORMAT)
        self._to_edit.setCalendarPopup(True)
        to_row.addWidget(self._to_edit)
        layout.addLayout(to_row)

        self._clear_filter_button = PushButton(FluentIcon.CLEAR_SELECTION, "Clear")
        layout.addWidget(self._clear_filter_button)
        card.viewLayout.addLayout(layout)

        self._use_custom_time_check.toggled.connect(self._on_filter_edited)
        self._from_edit.dateTimeChanged.connect(self._on_filter_edited)
        self._to_edit.dateTimeChanged.connect(self._on_filter_edited)
        self._clear_filter_button.clicked.connect(self._on_clear_filter)

        return card

    def _on_filter_edited(self, *_args: Any) -> None:
        if self._updating_filter_from_model:
            return
        self._view_model.setUseCustomTime(self._use_custom_time_check.isChecked())
        self._view_model.setFromDateTime(
            self._from_edit.dateTime().toString(_QDATETIME_FORMAT)
        )
        self._view_model.setToDateTime(
            self._to_edit.dateTime().toString(_QDATETIME_FORMAT)
        )

    def _on_clear_filter(self) -> None:
        self._view_model.setUseCustomTime(False)
        self._view_model.setFromDateTime("")
        self._view_model.setToDateTime("")

    def _sync_filter_from_model(self) -> None:
        """QML's TimeRangeCard binds `useCustomTime`/`fromDateTime`/
        `toDateTime` declaratively, so it never needs this. A QWidget View
        has to wire the ViewModel -> widget direction back explicitly or
        it silently only works forward (same class of gap the enroll-form
        prototype found and fixed for QLineEdit)."""
        self._updating_filter_from_model = True
        try:
            self._use_custom_time_check.setChecked(self._view_model.useCustomTime)
            from_text = self._view_model.fromDateTime
            if from_text:
                self._from_edit.setDateTime(
                    QDateTime.fromString(from_text, _QDATETIME_FORMAT)
                )
            to_text = self._view_model.toDateTime
            if to_text:
                self._to_edit.setDateTime(
                    QDateTime.fromString(to_text, _QDATETIME_FORMAT)
                )
        finally:
            self._updating_filter_from_model = False

    # ---- Table --------------------------------------------------------

    def _build_table_card(self) -> HeaderCardWidget:
        # Wrapped in a card, like every other section, rather than sitting
        # bare -- matches AppDataTable.qml being a BaseCard itself, and
        # keeps the "everything is a card" look consistent across the
        # screen instead of the table standing out as the one unframed
        # element.
        card = HeaderCardWidget("Roster", self)
        card.viewLayout.setContentsMargins(0, 0, 0, 0)

        self._table_model = StudentTableModel()
        self._proxy_model = NumericAwareSortProxyModel()
        self._proxy_model.setSourceModel(self._table_model)

        self._table_view = TableView(self)
        self._table_view.setObjectName("rosterTableView")
        self._table_view.setModel(self._proxy_model)
        self._table_view.setBorderVisible(False)
        # Sorting, resizing, and selection are all QHeaderView/QTableView
        # defaults -- no equivalent of AppDataTable.qml's _sortedModel(),
        # _resizeColumn(), or DragHandler needed (TASK-037 finding 2).
        self._table_view.setSortingEnabled(True)
        self._table_view.setSelectionBehavior(TableView.SelectionBehavior.SelectRows)
        self._table_view.horizontalHeader().setStretchLastSection(True)
        # The default row-number column is the proxy model's arbitrary
        # sorted index, not meaningful data -- AppDataTable.qml has no
        # equivalent, so hide it here too rather than exposing a QTableView
        # implementation detail as if it were a real column.
        self._table_view.verticalHeader().setVisible(False)

        card.viewLayout.addWidget(self._table_view)
        return card

    def _refresh_table(self) -> None:
        self._table_model.set_rows(self._view_model.students)

    # ---- Activity log --------------------------------------------------

    def _build_log_card(self) -> HeaderCardWidget:
        card = HeaderCardWidget("Activity Log", self)
        layout = QVBoxLayout()

        self._auto_scroll_check = CheckBox("Auto-scroll")
        self._auto_scroll_check.setChecked(True)
        layout.addWidget(self._auto_scroll_check)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch()
        copy_button = PushButton(FluentIcon.COPY, "Copy")
        clear_button = PushButton(FluentIcon.DELETE, "Clear")
        buttons_row.addWidget(copy_button)
        buttons_row.addWidget(clear_button)
        layout.addLayout(buttons_row)

        self._log_list = ListWidget()
        layout.addWidget(self._log_list)
        card.viewLayout.addLayout(layout)

        copy_button.clicked.connect(self._view_model.logModel.copyAllToClipboard)
        clear_button.clicked.connect(self._view_model.logModel.clear)

        return card

    def _refresh_log(self) -> None:
        self._log_list.clear()
        for entry in self._view_model.logModel.entries:
            self._log_list.addItem(f"[{entry.timestamp}] {entry.message}")
        if self._auto_scroll_check.isChecked():
            self._log_list.scrollToBottom()

    # ---- Enroll dialog --------------------------------------------------

    def _open_enroll_dialog(self) -> None:
        dialog = _EnrollDialog(self)
        if dialog.exec():
            self._view_model.requestEnroll(
                dialog.full_name_field.text(),
                dialog.email_field.text(),
                dialog.major_field.text(),
                dialog.gpa_field.value(),
            )


class _EnrollDialog(MessageBoxBase):
    """Small inline dialog, not WidgetEnrollFormView -- that one's bind()
    asserts on EnrollFormViewModel specifically, and RosterViewModel isn't
    that type; forcing reuse across mismatched ViewModel types would be
    worse than the few duplicated lines here."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.viewLayout.addWidget(StrongBodyLabel("Enroll Student"))

        form = QFormLayout()
        content = QWidget(self)
        content.setLayout(form)

        self.full_name_field = LineEdit()
        self.full_name_field.setPlaceholderText("Full name")
        self.email_field = LineEdit()
        self.email_field.setPlaceholderText("Email")
        self.major_field = LineEdit()
        self.major_field.setPlaceholderText("Major")
        self.gpa_field = DoubleSpinBox()
        self.gpa_field.setRange(0.0, 4.0)
        self.gpa_field.setDecimals(2)
        self.gpa_field.setSingleStep(0.1)

        form.addRow("Full name", self.full_name_field)
        form.addRow("Email", self.email_field)
        form.addRow("Major", self.major_field)
        form.addRow("GPA", self.gpa_field)

        self.viewLayout.addWidget(content)
        self.widget.setMinimumWidth(360)

        self.yesButton.setText("Enroll")
        self.yesButton.setIcon(FluentIcon.ADD)
