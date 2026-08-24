from PySide6.QtCore import Property, QObject, Signal, Slot


class BaseQmlViewModel(QObject):
    """
    @brief Base for every QML screen's ViewModel: carries the FSM-driven
    `uiMode` property QML binds its enabled/visible states to.

    @details
    QmlHostView.apply_ui_mode() (fed by BasePresenter's FSM binding) calls
    `set_ui_mode()` here; QML reads `viewModel.uiMode` — e.g.
    `enabled: viewModel.uiMode !== "LOCKED"`. This replaces the
    reflection-over-ui_matrix.json mechanism (UIMatrixMixin) used by the
    QtWidgets screens: QML binds declaratively, so a JSON matrix mapping
    widget-attribute names to booleans has nothing to drive.
    """

    uiModeChanged = Signal()
    controlsEnabledChanged = Signal()

    #: Which `uiMode` string values should disable this screen's controls —
    #: subclasses override to opt in (e.g. `frozenset({"LOCKED", "LIVE"})`).
    #: Empty by default: the engine has no opinion on which of an app's
    #: modes are "busy" states, mirroring BaseStateMachine's own genericity
    #: over "any Enum" — a subclass that never sets this keeps today's
    #: behavior (`controlsEnabled` always True) unchanged.
    DISABLED_UI_MODES: frozenset[str] = frozenset()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._ui_mode = "IDLE"
        self._controls_enabled = "IDLE" not in self.DISABLED_UI_MODES

    def _get_ui_mode(self) -> str:
        return self._ui_mode

    uiMode = Property(str, _get_ui_mode, notify=uiModeChanged)

    def _get_controls_enabled(self) -> bool:
        return self._controls_enabled

    #: Derived from `uiMode`/`DISABLED_UI_MODES` — screens bind
    #: `enabled: viewModel.controlsEnabled` instead of hand-rolling their own
    #: `uiMode === "IDLE" || uiMode === "ERROR"`-style string comparison,
    #: which is where screens have drifted into inconsistent (and once,
    #: behaviorally different) ad hoc conditions in the past.
    controlsEnabled = Property(
        bool, _get_controls_enabled, notify=controlsEnabledChanged
    )

    @Slot(str)
    def set_ui_mode(self, mode: str) -> None:
        """
        @details Updates BOTH `_ui_mode` and `_controls_enabled` before
        emitting either signal — a direct (same-thread) Qt signal/slot
        connection runs its slot synchronously, inside `.emit()`, so a slot
        connected to `uiModeChanged` that reads `self.controlsEnabled` must
        see the fully-updated value, not a stale one from before this call.
        QML's declarative bindings never observed the old, buggier
        ordering (`uiModeChanged` emitted, THEN `_controls_enabled`
        recomputed): a binding re-evaluates lazily, after this whole method
        has returned, so it always read the final state regardless of emit
        order. A directly-connected Python/QtWidgets slot has no such
        buffer — verified empirically (EPIC-006D) with a QtWidgets consumer
        of `controlsEnabled`, the first imperative one this class has had.
        """
        if mode == self._ui_mode:
            return
        self._ui_mode = mode

        enabled = mode not in self.DISABLED_UI_MODES
        controls_enabled_changed = enabled != self._controls_enabled
        self._controls_enabled = enabled

        self.uiModeChanged.emit()
        if controls_enabled_changed:
            self.controlsEnabledChanged.emit()
