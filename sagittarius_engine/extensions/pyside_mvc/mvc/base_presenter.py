from PySide6.QtCore import QObject

from sagittarius_engine.extensions.fsm import (
    BaseStateMachine,
    DeclarativeStateMachine,
)
from sagittarius_engine.extensions.pyside_mvc.mvc.base_view import (
    DEV_MODE_CONFIG_KEY,
    BaseView,
)
from sagittarius_engine.extensions.pyside_mvc.mvc.qt_event_bridge import (
    QtEventBridge,
)
from sagittarius_engine.extensions.pyside_mvc.safety.thread_affinity import (
    set_thread_affinity_dev_mode,
)
from sagittarius_engine.interfaces import (
    IConfig,
    IContainer,
    IDispatcher,
    IEventBus,
    ILogger,
)


class BasePresenter(QObject):
    """
    @brief The architectural foundation for all MVP Presenters using PySide6.

    @details
    This class enforces strict lifecycle management and architectural contracts:

    - **Single inheritance from `QObject`.** This docstring previously claimed
      "Multiple Inheritance safety (QObject first, ABC second)"; there is no
      second base and never was. Corrected 2026-08-25 (`EPIC-008D`) rather
      than left to mislead the next reader — and multiple inheritance is
      forbidden in this codebase anyway (`code-rule.md`).
    - **Avoids the 'Template Method Trap'** by NOT calling overridable methods
      in `__init__`. Child classes call `self._connect_ui_signals()` and
      `self._connect_engine_events()` themselves, at the very end of their own
      `__init__`, once their attributes exist.
    - **Subscribes through `QtEventBridge`** (`self.subscribe`), so a handler
      always runs on the Qt main thread and is always unsubscribed on
      `dispose()`. A subclass never has to remember either.

    @par Teardown: override `shutdown()`, never `dispose()`
    `dispose()` is framework-owned and final in practice: it unsubscribes
    everything this presenter registered and *then* calls `shutdown()`, the
    author hook. Overriding `dispose()` instead would skip the unsubscribe
    silently — the same override-vs-call trap the engine's extension
    lifecycle documents.
    """

    # Class-level definition for the initial state of the FSM.
    # Override this in child classes (e.g. INITIAL_STATE = UIMode.IDLE).
    INITIAL_STATE = None

    # Optional class-level declarative transition matrix for DeclarativeStateMachine.
    # Override this in child classes with dict mapping `(State, Event) -> NextState`.
    UI_TRANSITION_MATRIX = None

    # Defines the section key inside ui_matrix.json for this view (default: "main")
    UI_MATRIX_SECTION_KEY = "main"

    def __init__(self, view, container: IContainer):
        """
        @brief Base initialization.
        @param view The UI View instance associated with this presenter.
        @param container The Dependency Injection Container (for resolving ILogger, IEventBus, etc.).
        """
        super().__init__()
        self.view = view
        self.container = container

        self.event_bus = container.resolve(IEventBus)
        self.logger = container.resolve(ILogger)
        self.dispatcher = container.resolve(IDispatcher)
        self.config = container.resolve(IConfig)

        #: Owns this presenter's subscriptions and the hop onto the main
        #: thread. One bridge per presenter, so `dispose()` removes exactly
        #: this presenter's handlers and never a sibling screen's.
        self._events = QtEventBridge(self.event_bus, logger=self.logger, parent=self)
        self._disposed = False

        # Auto-activate dev-mode View instrumentation (e.g. click logging)
        # for any View that opts in by subclassing BaseView — a no-op for
        # views that don't, so this is safe for every other framework consumer.
        dev_mode = self.config.get(DEV_MODE_CONFIG_KEY, False)
        if isinstance(view, BaseView) and dev_mode:
            view.enable_dev_click_logging()

        # @ui_mutator (BOT-068) reads this process-wide, not per-instance —
        # a BaseQmlViewModel has no IConfig of its own to check. Every
        # ViewModel is constructed by a Presenter, and any background worker
        # that could reach one was submitted by that same Presenter, so this
        # is always set before it matters.
        set_thread_affinity_dev_mode(dev_mode)

        # State Machine for UI. DeclarativeStateMachine is a real subclass of
        # BaseStateMachine (extensions/fsm/declarative_state_machine.py), so
        # this one declaration covers both branches below.
        self.fsm: BaseStateMachine | None = None
        if self.INITIAL_STATE is not None:
            if (
                hasattr(self, "UI_TRANSITION_MATRIX")
                and self.UI_TRANSITION_MATRIX is not None
            ):
                self.fsm = DeclarativeStateMachine(self.INITIAL_STATE)
                self.fsm.load_matrix(self.UI_TRANSITION_MATRIX)
            else:
                self.fsm = BaseStateMachine(self.INITIAL_STATE)
            self._bind_fsm_to_ui()

        # Load UI Matrix from config and apply to view if applicable
        try:
            ui_matrix = self.config.get_all()
            if hasattr(self.view, "control_card") and hasattr(
                self.view.control_card, "set_ui_matrix"
            ):
                self.view.control_card.set_ui_matrix(ui_matrix)
            elif hasattr(self.view, "set_ui_matrix"):
                self.view.set_ui_matrix(ui_matrix)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to load UI Matrix from config: {e}")

    def _bind_fsm_to_ui(self) -> None:
        """
        @brief Automatically binds the initialized FSM to the UI Matrix.
        @details When the FSM transitions to a new state, this automatically
        applies the corresponding UI matrix mode to the view.
        Call this method from child presenters AFTER initializing `self.fsm`.
        """
        if not self.fsm:
            if self.logger:
                self.logger.warning("FSM not initialized. Cannot bind to UI.")
            return

        def _on_state_changed(old_state, new_state):
            target = self.view
            if hasattr(self.view, "control_card") and hasattr(
                self.view.control_card, "apply_ui_mode"
            ):
                target = self.view.control_card

            if hasattr(target, "apply_ui_mode"):
                target.apply_ui_mode(new_state, self.UI_MATRIX_SECTION_KEY)
            else:
                if self.logger:
                    self.logger.warning(
                        f"View {self.view} does not support apply_ui_mode"
                    )

        self.fsm.add_global_callback(_on_state_changed)

    def _connect_ui_signals(self) -> None:
        """
        @brief Connect view signals to presenter slots. Override and call
        explicitly at the end of the child's `__init__`.

        @details A no-op by default, not `raise NotImplementedError`. A screen
        with no view signals to wire is a valid screen, not a programming
        error, and raising from an inherited method breaks Liskov
        substitutability — `code-rule.md` forbids it explicitly. The cost was
        real: a Settings presenter with nothing to subscribe to had to
        override this with an empty body purely to avoid an exception.
        """

    def _connect_engine_events(self) -> None:
        """
        @brief Subscribe to Engine EventBus events via `self.subscribe`.
        Override and call explicitly at the end of the child's `__init__`.
        @details A no-op by default — see `_connect_ui_signals`.
        """

    def subscribe(self, event_name_or_type, handler) -> None:
        """
        @brief Subscribes to an engine event for the lifetime of this
        presenter.

        @details Prefer this over `self.event_bus.on(...)`. Two things come
        with it that a direct subscription does not have: the handler is
        delivered on the Qt main thread (`QtEventBridge`), and it is
        unsubscribed automatically in `dispose()`. Subscribing directly on the
        bus opts out of both, and the second one is silent — nothing fails,
        the handler simply keeps running after the screen is gone.
        """
        self._events.on(event_name_or_type, handler)

    def unsubscribe(self, event_name_or_type, handler) -> None:
        """@brief Removes one subscription made via `subscribe()`. Rarely
        needed — `dispose()` removes all of them."""
        self._events.off(event_name_or_type, handler)

    def dispose(self) -> None:
        """
        @brief Framework-owned teardown: drops every subscription this
        presenter made, then calls the author hook `shutdown()`.

        @details Idempotent, because `PresenterManager.shutdown()` may be
        reached more than once on an abnormal exit and a second teardown must
        not re-run a subclass's cleanup.

        Do not override this. Override `shutdown()` — see the class docstring.
        """
        if self._disposed:
            return
        self._disposed = True
        self._events.off_all()
        self.shutdown()

    def shutdown(self) -> None:
        """
        @brief Author hook for presenter-specific cleanup — cancelling
        in-flight work, closing resources. Called by `dispose()` after the
        event subscriptions are already gone.
        @details A no-op by default; a presenter with nothing of its own to
        clean up does not need to implement it.
        """
