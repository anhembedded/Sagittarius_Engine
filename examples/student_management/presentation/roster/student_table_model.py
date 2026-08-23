from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt

#: Carries each cell's RAW value (a real float for GPA, not "3.70") so
#: sorting compares correctly -- Qt.DisplayRole alone would make
#: NumericSortProxyModel compare the *formatted* strings, wrong for GPA.
RawValueRole = Qt.ItemDataRole.UserRole + 1

_COLUMNS: list[tuple[str, str]] = [
    ("fullName", "Name"),
    ("email", "Email"),
    ("major", "Major"),
    ("gpa", "GPA"),
    ("enrolledAt", "Enrolled"),
]


class StudentTableModel(QAbstractTableModel):
    """
    @brief QAbstractTableModel backing WidgetRosterView's QTableView --
    the QWidget-backend counterpart to AppDataTable.qml, driven by the
    same row shape RosterPresenter._to_rows() already produces.

    @details Deliberately does none of AppDataTable.qml's own
    sort/resize/selection work: QTableView + QHeaderView give all three
    for free (setSortingEnabled(True), the header's own default
    Interactive resize mode, selectionModel()) -- the concrete evidence
    for TASK-037 finding 2 (a QWidget table needs far less custom code
    than the QML one did).
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[dict] = []

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(_COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        key, _ = _COLUMNS[index.column()]
        value = self._rows[index.row()][key]

        if role == RawValueRole:
            return value
        if role == Qt.ItemDataRole.DisplayRole:
            return f"{value:.2f}" if key == "gpa" else str(value)
        if role == Qt.ItemDataRole.TextAlignmentRole and key == "gpa":
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return _COLUMNS[section][1]
        return super().headerData(section, orientation, role)


class NumericAwareSortProxyModel(QSortFilterProxyModel):
    """Sorts by RawValueRole, not the formatted display text -- see
    RawValueRole's own docstring."""

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        left_value = left.data(RawValueRole)
        right_value = right.data(RawValueRole)
        return bool(left_value < right_value)
