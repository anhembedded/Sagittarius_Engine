import logging
import threading
from collections.abc import Callable
from enum import Enum
from typing import TypeVar

from sagittarius_engine.extensions.fsm.exceptions import InvalidStateTransitionError

T = TypeVar("T", bound=Enum)

logger = logging.getLogger("Engine.FSM")


class BaseStateMachine[T: Enum]:
    """
    @brief Core generic Finite State Machine utility.
    @details Provides thread-safe state transitions, rule enforcement, and lifecycle hooks.
    """

    def __init__(self, initial_state: T):
        """
        @param initial_state The starting state of the machine.
        """
        if not isinstance(initial_state, Enum):
            raise TypeError("initial_state must be an instance of Enum")

        self._current_state: T = initial_state

        # Strict Reentrant Lock to protect state and prevent deadlocks in recursive callbacks
        self._lock = threading.RLock()

        # Transition Matrix (Rules Engine)
        self._allowed_transitions: dict[T, set[T]] = {}

        # Lifecycle Callbacks
        self._on_enter: dict[T, list[Callable[[], None]]] = {}
        self._on_exit: dict[T, list[Callable[[], None]]] = {}

        # Global Callbacks triggered on ANY transition
        # Signature: Callable[[old_state, new_state], None]
        self._global_callbacks: list[Callable[[T, T], None]] = []

    @property
    def current_state(self) -> T:
        """
        @brief Thread-safe property to get the current state.
        """
        with self._lock:
            return self._current_state

    def add_transition(self, from_state: T, to_state: T) -> None:
        """
        @brief Registers a valid transition rule.
        """
        with self._lock:
            if from_state not in self._allowed_transitions:
                self._allowed_transitions[from_state] = set()
            self._allowed_transitions[from_state].add(to_state)

    def on_enter(self, state: T, callback: Callable[[], None]) -> None:
        """
        @brief Registers a callback to be executed when entering the specified state.
        """
        with self._lock:
            if state not in self._on_enter:
                self._on_enter[state] = []
            self._on_enter[state].append(callback)

    def on_exit(self, state: T, callback: Callable[[], None]) -> None:
        """
        @brief Registers a callback to be executed when exiting the specified state.
        """
        with self._lock:
            if state not in self._on_exit:
                self._on_exit[state] = []
            self._on_exit[state].append(callback)

    def add_global_callback(self, callback: Callable[[T, T], None]) -> None:
        """
        @brief Registers a global callback triggered on any successful state transition.
        @param callback Function taking (old_state, new_state) as arguments.
        """
        with self._lock:
            self._global_callbacks.append(callback)

    def transition_to(self, new_state: T) -> bool:
        """
        @brief Attempts to transition to a new state.
        @param new_state The target state.
        @return True if transition was successful.
        @raises InvalidStateTransitionError if the transition is not defined in the matrix.
        """
        with self._lock:
            old_state = self._current_state

            # 1. Validation
            allowed_targets = self._allowed_transitions.get(old_state, set())
            if new_state not in allowed_targets:
                logger.error(
                    f"FSM Error: Transition {old_state.name} -> {new_state.name} rejected."
                )
                raise InvalidStateTransitionError(old_state.name, new_state.name)

            logger.debug(f"FSM: Transitioning {old_state.name} -> {new_state.name}")

            # 2. Execute on_exit callbacks for the current state
            for cb in self._on_exit.get(old_state, []):
                try:
                    cb()
                except Exception:
                    logger.exception(
                        "Error in on_exit callback for state %s",
                        old_state.name,
                    )

            # 3. Change state
            self._current_state = new_state

            # 4. Execute global transition callbacks
            for g_cb in self._global_callbacks:
                try:
                    g_cb(old_state, new_state)
                except Exception:
                    logger.exception("Error in global transition callback")

            # 5. Execute on_enter callbacks for the new state
            for cb in self._on_enter.get(new_state, []):
                try:
                    cb()
                except Exception:
                    logger.exception(
                        "Error in on_enter callback for state %s",
                        new_state.name,
                    )

            return True


if __name__ == "__main__":
    # ==========================================
    # DEMONSTRATION BLOCK
    # ==========================================
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s - %(message)s")

    class DoorState(Enum):
        CLOSED = "CLOSED"
        OPEN = "OPEN"
        LOCKED = "LOCKED"

    # 1. Initialize FSM
    door_fsm = BaseStateMachine[DoorState](DoorState.CLOSED)

    # 2. Define Transition Matrix
    door_fsm.add_transition(DoorState.CLOSED, DoorState.OPEN)
    door_fsm.add_transition(DoorState.OPEN, DoorState.CLOSED)
    door_fsm.add_transition(DoorState.CLOSED, DoorState.LOCKED)
    door_fsm.add_transition(DoorState.LOCKED, DoorState.CLOSED)

    # 3. Register Global Callback
    def log_transition(old_st: DoorState, new_st: DoorState):
        print(f"[GLOBAL TELEMETRY] Door changed from {old_st.name} to {new_st.name}")

    door_fsm.add_global_callback(log_transition)

    # 4. Register Lifecycle Hooks
    door_fsm.on_enter(
        DoorState.OPEN, lambda: print("--> Action: Turning on room lights.")
    )
    door_fsm.on_exit(
        DoorState.OPEN, lambda: print("<-- Action: Turning off room lights.")
    )

    door_fsm.on_enter(DoorState.LOCKED, lambda: print("--> Action: Engaging deadbolt."))
    door_fsm.on_exit(
        DoorState.LOCKED, lambda: print("<-- Action: Disengaging deadbolt.")
    )

    # 5. Execute Valid Transitions
    print("\n--- Testing Valid Transitions ---")
    door_fsm.transition_to(DoorState.OPEN)
    door_fsm.transition_to(DoorState.CLOSED)
    door_fsm.transition_to(DoorState.LOCKED)
    door_fsm.transition_to(DoorState.CLOSED)

    # 6. Execute Invalid Transition (Should Raise Error)
    print("\n--- Testing Invalid Transition (OPEN -> LOCKED) ---")
    door_fsm.transition_to(DoorState.OPEN)
    try:
        door_fsm.transition_to(DoorState.LOCKED)
    except InvalidStateTransitionError as e:
        print(f"Caught expected error: {e}")

    # Reset back to CLOSED for the threaded test
    door_fsm.transition_to(DoorState.CLOSED)

    # 7. Thread-Safety Demo
    print("\n--- Testing Thread-Safety (Spamming OPEN/CLOSED) ---")

    def spam_transitions():
        try:
            for _ in range(5):
                # We attempt to transition back and forth; some might fail if threads overlap,
                # but the internal state will never be corrupted.
                current = door_fsm.current_state
                if current == DoorState.CLOSED:
                    door_fsm.transition_to(DoorState.OPEN)
                elif current == DoorState.OPEN:
                    door_fsm.transition_to(DoorState.CLOSED)
        except InvalidStateTransitionError:
            pass  # Expected in a multi-threaded race, but lock prevents data corruption

    t1 = threading.Thread(target=spam_transitions)
    t2 = threading.Thread(target=spam_transitions)

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    print(f"Final State after threaded stress test: {door_fsm.current_state.name}")
