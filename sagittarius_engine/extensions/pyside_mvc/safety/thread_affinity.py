import functools
import threading
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, QTimer, Signal

#: Process-wide, counting `@ui_mutator`'s cross-thread branch regardless of
#: which way it resolves (`CrossThreadUiMutationError` in dev mode,
#: `QTimer.singleShot` marshaling in production) -- both are the same
#: underlying violation, just handled differently. `EPIC-007F` §4: the
#: runtime state console reports this alongside `UIWatchdog`'s freeze count
#: as the cheapest red flag a `pyside_mvc` app can show.
_off_thread_mutation_count = 0
_off_thread_mutation_lock = threading.Lock()


def get_off_thread_mutation_count() -> int:
    """@brief How many times `@ui_mutator` caught a cross-thread call this
    process, dev mode and production alike."""
    with _off_thread_mutation_lock:
        return _off_thread_mutation_count


def reset_off_thread_mutation_count() -> None:
    """@brief Test-only reset of the process-wide counter, same precedent as
    `set_thread_affinity_dev_mode` being the one function allowed to touch
    `_dev_mode_enabled` from outside this module."""
    global _off_thread_mutation_count
    with _off_thread_mutation_lock:
        _off_thread_mutation_count = 0


def _record_off_thread_mutation() -> None:
    global _off_thread_mutation_count
    with _off_thread_mutation_lock:
        _off_thread_mutation_count += 1


#: Process-wide, not per-instance: a `QObject` mutator has no reliable way
#: to reach `IConfig` on its own (`BaseQmlViewModel` takes no DI container —
#: only its owning Presenter does), and "is this process in dev mode" is a
#: single fact for the whole run anyway. `BasePresenter.__init__` sets this
#: from the same `dev.mode` read it already does for `enable_dev_click_logging`
#: (see `base_view.DEV_MODE_CONFIG_KEY`) — by the time any background worker
#: could call a `@ui_mutator` method, the Presenter that submitted that worker
#: has necessarily already run its own `__init__`, so this is never read
#: before it's set for any call that could actually happen.
_dev_mode_enabled = False


def set_thread_affinity_dev_mode(enabled: bool) -> None:
    """@brief Sets the process-wide dev-mode flag `@ui_mutator` checks."""
    global _dev_mode_enabled
    _dev_mode_enabled = enabled


class CrossThreadUiMutationError(RuntimeError):
    """@brief Raised (dev mode only) when a `@ui_mutator`-decorated method is
    called from a thread other than the one its `QObject` lives on."""


def ui_mutator(func: Callable) -> Callable:
    """
    @brief Marks a `QObject` method (typically a `BaseQmlViewModel` mutator —
    `set_*`/`append*`/`clear*`/`hide_*`) as one that must only ever run on the
    object's own thread, and enforces it.

    @details
    Unlike `@Slot`, which only makes a method callable *as a Qt slot* (queued
    connections promote automatically when the sender lives on another
    thread — that part of Qt already works without this decorator), this
    guards the case `@Slot` does NOT cover: a background thread calling the
    method directly as a plain Python function, bypassing signals entirely.
    That direct-call shape is exactly the class of bug BUG-001 (Sagittarius
    Elite Warrior) surfaced — a background thread mutated Qt/QML state
    directly, which only crashed once a `Behavior on width` animation made
    QML need to start an internal `QTimer` from that same wrong thread.

    Same-thread calls pass straight through, unchanged. Cross-thread calls:
    - **dev mode** (`dev.mode` config key, see `set_thread_affinity_dev_mode`):
      raises `CrossThreadUiMutationError` immediately — fail loud during
      development instead of only reaching production silently broken.
    - **production**: marshals the call onto the object's own thread via
      `QTimer.singleShot(0, self, ...)` — verified empirically (this PySide6
      build's `QMetaObject.invokeMethod` does NOT support a bare Python
      callable/functor, only a `@Slot`-registered method name by string; the
      `QTimer.singleShot(msec, receiver, callable)` overload does, and is
      documented Qt behavior for "run this on receiver's thread") — and
      returns `None` immediately, same as any other queued/deferred call.

    Usage:
        @Slot(int, int, bool)
        @ui_mutator
        def set_progress(self, value, maximum, visible):
            ...
    """

    @functools.wraps(func)
    def wrapper(self: QObject, *args: Any, **kwargs: Any) -> Any:
        if QThread.currentThread() is self.thread():
            return func(self, *args, **kwargs)

        _record_off_thread_mutation()

        if _dev_mode_enabled:
            raise CrossThreadUiMutationError(
                f"{func.__qualname__} was called from {QThread.currentThread()!r} "
                f"but belongs to {self.thread()!r} — use a Signal instead of "
                f"calling this directly from a background thread."
            )

        QTimer.singleShot(0, self, functools.partial(func, self, *args, **kwargs))
        return None

    # Stashing metadata directly on the wrapped callable, read back via
    # `getattr(member, "_is_ui_mutator", False)` in unprotected_mutators()
    # below — same pattern and same suppression as logger_config.py's
    # `logging.TRACE = TRACE`. No static type covers "an arbitrary attribute
    # on a function object" without a Protocol this internal marker doesn't
    # warrant.
    wrapper._is_ui_mutator = True  # type: ignore[attr-defined]
    return wrapper


def not_a_ui_mutator(func: Callable) -> Callable:
    """
    @brief Explicit opt-out marker for a method whose name matches the
    mutator-name heuristic (`set_*`/`append*`/`clear*`/`hide_*`) but isn't
    one — e.g. a pure computation, or something only ever called from
    QML itself (always the main thread by construction).
    @details A no-op at runtime; `unprotected_mutators()` skips anything
    carrying this marker. Prefer `@Slot`/`@ui_mutator` when either is
    actually correct — this is for the genuine exceptions, and each one
    should be able to justify itself in a comment at the call site.
    """
    func._is_not_a_ui_mutator = True  # type: ignore[attr-defined]
    return func


#: Name prefixes `unprotected_mutators()` treats as "this looks like it
#: mutates UI-visible state and could plausibly be reached from a
#: background thread" — a heuristic, not a guarantee. False negatives
#: (a mutator named something else) won't be caught; false positives
#: should get `@not_a_ui_mutator`, not a heuristic change, until the
#: heuristic stops catching anything real (see BOT-068 task notes).
_MUTATOR_NAME_PREFIXES = ("set_", "append", "clear", "hide_")


def _registered_slot_names(cls: type[QObject]) -> set[str]:
    """@brief Every method name registered as a Qt slot on `cls`'s
    meta-object. Requires a live instance (`metaObject()` isn't available on
    the class alone) — constructs one via `__new__`/`QObject.__init__` only,
    deliberately skipping `cls`'s own `__init__` (which may require
    constructor arguments this scan has no business supplying): verified
    empirically that `metaObject()` reflects the class's compiled-in
    meta-object regardless, since slot registration happens at class
    definition time, not instance construction time."""
    instance = cls.__new__(cls)
    QObject.__init__(instance)
    meta = instance.metaObject()
    return {
        bytes(meta.method(i).name()).decode()
        for i in range(meta.methodCount())
        if meta.method(i).methodType().name == "Slot"
    }


def unprotected_mutators(cls: type[QObject]) -> list[str]:
    """
    @brief Returns the names of every public method reachable on `cls`
    (including inherited ones — e.g. `BaseQmlViewModel.set_ui_mode`) that
    looks like a UI mutator (see `_MUTATOR_NAME_PREFIXES`) but is protected
    by neither `@Slot` nor `@ui_mutator`, and isn't marked
    `@not_a_ui_mutator`.
    @details Meant to back a sanity test per concrete `QObject` subclass
    (typically a `BaseQmlViewModel`) in an app built on this framework —
    an empty list is the passing case. Walks `dir(cls)` (not just
    `cls.__dict__`) so a mutator inherited from a base class is caught too —
    verified `getattr(cls, name)` on a class (not instance) doesn't trigger
    `Property` getters, just returns the descriptor/function itself. Plus
    one throwaway instance for the `@Slot` check; does not require a
    booted app or QML.
    """
    slot_names = _registered_slot_names(cls)
    unprotected = []
    for name in dir(cls):
        if name.startswith("_") or not name.startswith(_MUTATOR_NAME_PREFIXES):
            continue
        member = getattr(cls, name, None)
        # A `Signal` declaration (e.g. `clearDataRequested = Signal()`) is
        # itself callable at the class level (that's how `Signal(int, str)`
        # works) but isn't a method at all — verified empirically it would
        # otherwise false-positive on any signal whose name happens to start
        # with one of the mutator prefixes (e.g. `clearDataRequested`).
        if isinstance(member, Signal) or not callable(member):
            continue
        if getattr(member, "_is_not_a_ui_mutator", False):
            continue
        if getattr(member, "_is_ui_mutator", False):
            continue
        if name in slot_names:
            continue
        unprotected.append(name)
    return unprotected
