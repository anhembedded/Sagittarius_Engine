"""Engine lifecycle state — `EPIC-006C`.

Two states carry the weight here, and the distinction between them is the point.

**`BOOTED`** means the boot sequence ran to the end. **`READY`** means everything
that was supposed to come up actually did. They are not the same, and the gap
between them is real: `ExtensionManager` defers an extension whose declared
dependencies are not yet registered, and if the dependency never arrives the
extension sits in `registered_extensions` forever, uninitialised, while
`boot()` returns perfectly normally. The application starts, minus a feature,
and nothing says so — this is check D1 in `EPIC-006` §3, and it is why "booted"
was never a safe answer to "is it up?".
"""

from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING

from sagittarius_engine.domain.event_registry import EventRegistry

if TYPE_CHECKING:
    from sagittarius_engine.kernel.i_kernel_context import IKernelContext

#: Emitted once, when the engine reaches `READY`. The payload is the `App`,
#: matching `app.booted` — see `bootstrap.py` for why these two have no event
#: class of their own.
APP_READY_EVENT_NAME = "app.ready"

EventRegistry.register_named(
    APP_READY_EVENT_NAME, None, module="sagittarius_engine.kernel.lifecycle"
)


class InvalidStateTransition(RuntimeError):
    """
    @brief Raised when the engine is asked to move between two states that do
    not connect.

    @details A transition that cannot happen is a programming error in whoever
    drives the lifecycle, not a runtime condition to recover from. Silently
    accepting it would let the engine report `READY` after a failed boot, which
    is worse than a crash: every consumer of that state would then be reasoning
    from a lie.
    """


class EngineState(Enum):
    """@brief Where the engine is in its life.

    @details `CREATED` and `STOPPED` are deliberately distinct. Before
    `EPIC-006C` a freshly constructed engine reported `STOPPED`, so "never
    started" and "has been shut down" were indistinguishable — and the first
    question anything monitoring an engine asks is exactly which of those two
    it is looking at.
    """

    CREATED = "created"
    BOOTING = "booting"
    BOOTED = "booted"
    READY = "ready"
    STOPPING = "stopping"
    STOPPED = "stopped"


#: Which states each state can move to. A same-state transition is always
#: allowed and does nothing — shutdown paths call `set_stopped()` from more
#: than one place and must not be made fragile by that.
_ALLOWED: dict[EngineState, frozenset[EngineState]] = {
    # CREATED may go to STOPPING: `App.stop()` on an engine that was never
    # booted is a legitimate no-op teardown, and refusing the transition would
    # turn a harmless call into a crash.
    EngineState.CREATED: frozenset(
        {EngineState.BOOTING, EngineState.STOPPING, EngineState.STOPPED}
    ),
    # BOOTING may go straight to STOPPING: `Bootstrap.boot()` cleans up and
    # re-raises when a step fails, and the state must follow it down rather
    # than being left claiming a boot is still in progress.
    EngineState.BOOTING: frozenset(
        {EngineState.BOOTED, EngineState.STOPPING, EngineState.STOPPED}
    ),
    EngineState.BOOTED: frozenset(
        {EngineState.READY, EngineState.STOPPING, EngineState.STOPPED}
    ),
    EngineState.READY: frozenset({EngineState.STOPPING, EngineState.STOPPED}),
    EngineState.STOPPING: frozenset({EngineState.STOPPED}),
    # A stopped engine may be booted again. Nothing in this repository does so,
    # but forbidding it would be a restriction invented here rather than one
    # the design implies.
    EngineState.STOPPED: frozenset({EngineState.BOOTING}),
}


class Lifecycle:
    """@brief Unused. Kept only because deleting it is a separate change from
    `EPIC-006C`'s, and this file's history should show one thing at a time."""

    def __init__(self, context: "IKernelContext") -> None:
        self._state = "created"


class EngineLifecycle:
    """
    @brief Owns the engine's state, the transitions between states, and the
    one-shot `app.ready` milestone.
    """

    def __init__(self, context: "IKernelContext") -> None:
        self.context = context
        self.state = EngineState.CREATED
        self._ready_callbacks: list[Callable[[], None]] = []

    # ----------------------------------------------------------- transitions

    def _transition(self, target: EngineState) -> None:
        if target is self.state:
            return
        if target not in _ALLOWED[self.state]:
            raise InvalidStateTransition(
                f"cannot move from {self.state.value} to {target.value}"
            )
        self.state = target

    def set_booting(self) -> None:
        self._transition(EngineState.BOOTING)

    def set_booted(self) -> None:
        self._transition(EngineState.BOOTED)

    def set_stopping(self) -> None:
        self._transition(EngineState.STOPPING)

    def set_stopped(self) -> None:
        self._transition(EngineState.STOPPED)

    def set_ready(self) -> None:
        """
        @brief Marks the engine ready and emits `app.ready` — exactly once.

        @details Emission lives here rather than at the call site so that
        "exactly once" is enforced by the same guard that enforces the
        transition. A second call is a no-op, so a caller cannot produce two
        `app.ready` events by being defensive.

        @raises InvalidStateTransition If the engine is not `BOOTED`. Readiness
            after a failed boot is precisely the lie this class exists to
            prevent.
        """
        if self.state is EngineState.READY:
            return

        self._transition(EngineState.READY)

        callbacks, self._ready_callbacks = self._ready_callbacks, []
        for callback in callbacks:
            callback()

        self.context.event_bus.emit(APP_READY_EVENT_NAME, self.context.app)

    # -------------------------------------------------------- late arrivals

    def when_ready(self, callback: Callable[[], None]) -> None:
        """
        @brief Runs `callback` when the engine is ready — **immediately** if it
        already is.

        @details This is the whole reason readiness is a queryable state and not
        only an event. A component that subscribes to `app.ready` after the
        event has fired waits forever, and the engine has already been bitten by
        exactly that: `extensions/health/health_check_requested.py` carries the
        note *"already missed it, and its subscription is dead code that never
        fires"* in its own source.

        Callbacks run once, in registration order, before `app.ready` is
        emitted — so a subscriber that needs to be in place *for* that event
        still is.
        """
        if self.is_ready:
            callback()
            return
        self._ready_callbacks.append(callback)

    # ------------------------------------------------------------ predicates

    @property
    def is_created(self) -> bool:
        """@brief Constructed, never booted. Distinct from `is_stopped`."""
        return self.state == EngineState.CREATED

    @property
    def is_booted(self) -> bool:
        """@brief The boot sequence completed.

        @details True in `READY` as well: readiness is a state *past* booted,
        and a caller asking "did it boot" would be misled by `False` there.
        """
        return self.state in (EngineState.BOOTED, EngineState.READY)

    @property
    def is_ready(self) -> bool:
        """@brief Booted **and** everything that should have come up did."""
        return self.state == EngineState.READY

    @property
    def is_booting(self) -> bool:
        return self.state == EngineState.BOOTING

    @property
    def is_stopping(self) -> bool:
        return self.state == EngineState.STOPPING

    @property
    def is_stopped(self) -> bool:
        return self.state == EngineState.STOPPED
