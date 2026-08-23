from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable
from enum import Enum
from typing import TypeVar

from sagittarius_engine.extensions.fsm.exceptions import (
    InvalidStateTransitionError,
)
from sagittarius_engine.extensions.fsm.state_machine import BaseStateMachine

StateT = TypeVar("StateT", bound=Enum)
EventT = TypeVar("EventT", bound=Enum)

logger = logging.getLogger("Engine.DeclarativeFSM")


class DeclarativeStateMachine[StateT: Enum, EventT: Enum](BaseStateMachine[StateT]):
    """
    @brief Event-driven Declarative Finite State Machine for stateful workflows and UI controllers.
    @details Extends BaseStateMachine with:
    - Centralized declarative transition matrix: `(State, Event) -> NextState`.
    - Event dispatching via `dispatch(event)` with re-entrancy defense (FIFO Event Queue).
    - Event inspection APIs: `can_dispatch(event)`, `get_valid_events()`, `get_next_state(event)`.
    - Event-specific lifecycle callbacks: `on_event(event, callback)`.
    - Full thread-safety backed by re-entrant locking (`threading.RLock`).
    """

    def __init__(self, initial_state: StateT) -> None:
        """
        @param initial_state The starting state Enum of the machine.
        """
        super().__init__(initial_state)

        # Transition Matrix: (CurrentState, Event) -> NextState
        self._event_matrix: dict[tuple[StateT, EventT], StateT] = {}

        # Event-specific callbacks: Callable[[old_state, new_state, event], None]
        self._on_event: dict[
            EventT, list[Callable[[StateT, StateT, EventT], None]]
        ] = {}

        # Re-entrancy queue: buffers events emitted inside lifecycle callbacks
        self._event_queue: deque[EventT] = deque()
        self._is_dispatching: bool = False

    def add_event_transition(
        self,
        from_state: StateT,
        event: EventT,
        to_state: StateT,
    ) -> None:
        """
        @brief Registers an event-driven state transition rule.
        @param from_state The origin state.
        @param event The triggering event Enum.
        @param to_state The target state.
        """
        if not isinstance(from_state, Enum):
            raise TypeError("from_state must be an instance of Enum")
        if not isinstance(event, Enum):
            raise TypeError("event must be an instance of Enum")
        if not isinstance(to_state, Enum):
            raise TypeError("to_state must be an instance of Enum")

        with self._lock:
            self._event_matrix[(from_state, event)] = to_state
            # Keep base class _allowed_transitions synchronized for direct transition_to compatibility
            self.add_transition(from_state, to_state)

    def load_matrix(
        self,
        matrix: dict[tuple[StateT, EventT], StateT],
    ) -> None:
        """
        @brief Bulk loads a declarative transition matrix dictionary.
        @param matrix Mapping of `(from_state, event) -> to_state`.
        """
        with self._lock:
            for (from_st, ev), to_st in matrix.items():
                self.add_event_transition(from_st, ev, to_st)

    def on_event(
        self,
        event: EventT,
        callback: Callable[[StateT, StateT, EventT], None],
    ) -> None:
        """
        @brief Registers a callback executed when a specific event triggers a transition.
        @param event The event Enum to observe.
        @param callback Callable taking `(old_state, new_state, event)`.
        """
        if not isinstance(event, Enum):
            raise TypeError("event must be an instance of Enum")

        with self._lock:
            if event not in self._on_event:
                self._on_event[event] = []
            self._on_event[event].append(callback)

    def can_dispatch(self, event: EventT) -> bool:
        """
        @brief Checks whether an event is valid from the current state without triggering side effects.
        @param event The candidate event Enum.
        @return True if the transition is allowed, False otherwise.
        """
        if not isinstance(event, Enum):
            raise TypeError("event must be an instance of Enum")

        with self._lock:
            return (self._current_state, event) in self._event_matrix

    def get_valid_events(self) -> set[EventT]:
        """
        @brief Returns the set of all events that are valid triggers from the current state.
        """
        with self._lock:
            return {ev for (st, ev) in self._event_matrix if st == self._current_state}

    def get_next_state(self, event: EventT) -> StateT | None:
        """
        @brief Returns the destination state for an event without transitioning, or None if invalid.
        @param event The candidate event Enum.
        """
        if not isinstance(event, Enum):
            raise TypeError("event must be an instance of Enum")

        with self._lock:
            return self._event_matrix.get((self._current_state, event))

    def dispatch(self, event: EventT) -> bool:
        """
        @brief Dispatches an event to trigger a state transition.
        @details If a lifecycle callback emits another event, the re-entrancy queue ensures
        events are executed sequentially in FIFO order without recursive stack corruption.
        @param event The event Enum to dispatch.
        @return True if the transition succeeded.
        @raises InvalidStateTransitionError if the event is not defined from the current state.
        """
        if not isinstance(event, Enum):
            raise TypeError("event must be an instance of Enum")

        with self._lock:
            # If already dispatching an event loop (e.g. from an inner callback), enqueue and return
            if self._is_dispatching:
                self._event_queue.append(event)
                return True

            self._is_dispatching = True
            self._event_queue.append(event)

            try:
                while self._event_queue:
                    current_event = self._event_queue.popleft()
                    old_state = self._current_state
                    target_state = self._event_matrix.get((old_state, current_event))

                    if target_state is None:
                        logger.error(
                            "FSM Error: Event '%s' is invalid from state '%s'.",
                            current_event.name,
                            old_state.name,
                        )
                        self._event_queue.clear()
                        raise InvalidStateTransitionError(
                            from_state=old_state.name,
                            to_state="UNKNOWN",
                            event=current_event.name,
                        )

                    logger.debug(
                        "FSM: Dispatching '%s': %s -> %s",
                        current_event.name,
                        old_state.name,
                        target_state.name,
                    )

                    # 1. Execute on_exit callbacks for the current state
                    for cb in self._on_exit.get(old_state, []):
                        try:
                            cb()
                        except Exception:
                            logger.exception(
                                "Error in on_exit callback for state %s",
                                old_state.name,
                            )

                    # 2. Change state
                    self._current_state = target_state

                    # 3. Execute global transition callbacks (old_state, new_state)
                    for g_cb in self._global_callbacks:
                        try:
                            g_cb(old_state, target_state)
                        except Exception:
                            logger.exception("Error in global transition callback")

                    # 4. Execute event-specific callbacks (old_state, new_state, event)
                    for ev_cb in self._on_event.get(current_event, []):
                        try:
                            ev_cb(old_state, target_state, current_event)
                        except Exception:
                            logger.exception(
                                "Error in on_event callback for event %s",
                                current_event.name,
                            )

                    # 5. Execute on_enter callbacks for the new state
                    for cb in self._on_enter.get(target_state, []):
                        try:
                            cb()
                        except Exception:
                            logger.exception(
                                "Error in on_enter callback for state %s",
                                target_state.name,
                            )

                return True
            finally:
                self._is_dispatching = False
