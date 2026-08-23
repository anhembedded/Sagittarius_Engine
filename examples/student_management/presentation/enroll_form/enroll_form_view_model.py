from PySide6.QtCore import Property, QObject, Signal, Slot


class EnrollFormViewModel(QObject):
    """
    @brief State + user-action surface for the enroll form -- deliberately
    a plain QObject, not BaseQmlViewModel (that base's whole reason to
    exist is the QML-specific uiMode/controlsEnabled FSM binding; see its
    own docstring). This ViewModel is the IView prototype's proof that a
    ViewModel needs no opinion about which rendering backend its View
    uses: `Property`/`Signal` work identically whether a QML document
    binds to them declaratively or a QWidget View wires them by hand in
    Python.

    @details No application logic here -- same rule as RosterViewModel.
    EnrollFormPresenter owns every decision; this class only exposes state
    and forwards the one user action (submit) as a Signal.
    """

    fullNameChanged = Signal()
    emailChanged = Signal()
    majorChanged = Signal()
    gpaChanged = Signal()

    #: Emitted when the user submits the form -- the Presenter decides
    #: what "submit" means (dispatch a command, just log it, etc.), same
    #: contract as RosterViewModel.enrollRequested.
    submitRequested = Signal(str, str, str, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._full_name = ""
        self._email = ""
        self._major = ""
        self._gpa = 0.0

    def _get_full_name(self) -> str:
        return self._full_name

    def _set_full_name(self, value: str) -> None:
        if value != self._full_name:
            self._full_name = value
            self.fullNameChanged.emit()

    fullName = Property(str, _get_full_name, _set_full_name, notify=fullNameChanged)

    def _get_email(self) -> str:
        return self._email

    def _set_email(self, value: str) -> None:
        if value != self._email:
            self._email = value
            self.emailChanged.emit()

    email = Property(str, _get_email, _set_email, notify=emailChanged)

    def _get_major(self) -> str:
        return self._major

    def _set_major(self, value: str) -> None:
        if value != self._major:
            self._major = value
            self.majorChanged.emit()

    major = Property(str, _get_major, _set_major, notify=majorChanged)

    def _get_gpa(self) -> float:
        return self._gpa

    def _set_gpa(self, value: float) -> None:
        if value != self._gpa:
            self._gpa = value
            self.gpaChanged.emit()

    gpa = Property(float, _get_gpa, _set_gpa, notify=gpaChanged)

    @Slot()
    def submit(self) -> None:
        self.submitRequested.emit(self._full_name, self._email, self._major, self._gpa)
