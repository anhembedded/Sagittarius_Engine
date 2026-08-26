import functools

from PySide6.QtCore import QChildEvent, QEvent, QObject, Qt
from PySide6.QtWidgets import QPushButton, QWidget

# Config key any app built on this framework can set (e.g. via
# ConfigManager.load_dict({DEV_MODE_CONFIG_KEY: True})) to turn on dev-mode
# View instrumentation — currently: auto-logging every button click.
DEV_MODE_CONFIG_KEY = "dev.mode"


class BaseView(QWidget):  # base-exempt: an MVC view root, not a styled surface
    """
    @brief Base class for every PySide6 View in an app built on this framework.

    @details
    Mirrors BasePresenter: subclassing this is enough to get shared behavior
    for free. Today that behavior is opt-in dev-mode click logging, activated
    automatically by BasePresenter (see base_presenter.py) when the app's
    `dev.mode` config flag is on — a View never has to call anything itself.

    Every view sets `WA_StyledBackground`, because a plain `QWidget`
    subclass **silently ignores a stylesheet background once it is nested
    inside another widget**. Standalone it paints, which is why no test
    caught it: a view under test is the top-level window, and Qt fills that
    itself. In a real window the consuming app's sidebar asked for its own
    darker background for as long as it has existed and never got it — the
    colour on screen came from its unscoped stylesheet leaking onto every
    child, each of which did paint. Fixing that leak is what made the
    missing background visible.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def log_dev_action(self, message: str) -> None:
        """
        @brief Routes a dev-mode diagnostic message somewhere visible.
        @details Default: duck-types a `monitor_card.append_log(...)` if the
        concrete View has one (matches this framework's existing
        `control_card` duck-typing convention in BasePresenter). Falls back
        to a no-op when there's no such attribute, so this never crashes for
        a View with no log sink. Override for different routing.
        """
        monitor_card = getattr(self, "monitor_card", None)
        if monitor_card is not None and hasattr(monitor_card, "append_log"):
            monitor_card.append_log(message)

    def enable_dev_click_logging(self) -> None:
        """
        @brief Wires every QPushButton under this View — present now or
        added at any point later — to call `self.log_dev_action(...)` on
        click.
        """
        _ButtonClickWatcher(self).watch(self)


class _ButtonClickWatcher(QObject):
    """
    @brief Watches a widget subtree and logs every QPushButton click via the
    owning BaseView's `log_dev_action`, including buttons added to the
    subtree after installation.
    @details Uses an installed event filter (not per-button wiring) so it
    keeps working for widgets that don't exist yet at install time — e.g. a
    table's per-row action buttons, or a whole new card added later. Whenever
    a new QWidget child appears anywhere in the watched subtree, the filter
    installs itself on that child too, so watching propagates automatically
    to arbitrarily deep future additions.
    """

    def __init__(self, view: BaseView) -> None:
        super().__init__(view)
        self._view = view

    def watch(self, root: QWidget) -> None:
        # Install on every EXISTING descendant too (not just `root`) — a
        # container like QTableWidget reparents cell widgets onto its
        # internal viewport, which only an event filter installed directly
        # on that viewport (found here via the recursive findChildren) will
        # ever see ChildAdded events for.
        root.installEventFilter(self)
        for widget in root.findChildren(QWidget):
            widget.installEventFilter(self)
        for button in root.findChildren(QPushButton):
            self._connect(button)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ChildAdded and isinstance(event, QChildEvent):
            child = event.child()
            if isinstance(child, QPushButton):
                self._connect(child)
            elif isinstance(child, QWidget):
                self.watch(child)
        return False

    def _connect(self, button: QPushButton) -> None:
        button.clicked.connect(functools.partial(self._log_click, button))

    def _log_click(self, button: QPushButton, checked: bool = False) -> None:
        label = button.text().strip() or button.objectName() or "unnamed button"
        self._view.log_dev_action(f'User clicked "{label}"')
