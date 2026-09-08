"""
@brief UI Thread Watchdog and Freeze Detector for Sagittarius Engine.

@details
Runs an independent background monitor thread that tracks heartbeats emitted
by the Qt Main Thread. If the Main Thread freezes for longer than the configured
threshold (e.g. 5.0s), the watchdog automatically captures the Main Thread's
live stack trace and logs a critical diagnostic warning to pinpoint the blocking code.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading
import time
import traceback
from typing import TYPE_CHECKING

from PySide6 import QtCore

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtWidgets import QApplication

_DEFAULT_HEARTBEAT_INTERVAL_MS: int = 1000
_DEFAULT_FREEZE_THRESHOLD_SEC: float = 5.0
_DEFAULT_CHECK_INTERVAL_SEC: float = 1.0
_SIGNAL_TIMER_INTERVAL_MS: int = 500


def setup_qt_signal_handling(app: QApplication) -> QtCore.QTimer:
    """
    @brief Enable clean Ctrl+C / SIGINT termination during Qt event loop execution.

    @details
    Sets OS signal handlers for SIGINT/SIGTERM and starts a 500ms QTimer to
    wake up Python runtime periodically so terminal interrupts are processed promptly.
    """
    signal.signal(signal.SIGINT, lambda *args: app.quit())
    signal.signal(signal.SIGTERM, lambda *args: app.quit())

    sig_timer = QtCore.QTimer()
    sig_timer.setInterval(_SIGNAL_TIMER_INTERVAL_MS)
    sig_timer.timeout.connect(lambda: None)
    sig_timer.start()
    return sig_timer


class UIWatchdog(QtCore.QObject):
    """
    @brief Watchdog service detecting UI Main Thread freezes and deadlocks.

    @details
    Spawns a background daemon thread that periodically checks the elapsed time
    since the last heartbeat received from the Qt Main Thread.
    """

    def __init__(
        self,
        freeze_threshold_sec: float = _DEFAULT_FREEZE_THRESHOLD_SEC,
        check_interval_sec: float = _DEFAULT_CHECK_INTERVAL_SEC,
        heartbeat_interval_ms: int = _DEFAULT_HEARTBEAT_INTERVAL_MS,
        logger: logging.Logger | None = None,
        on_freeze_callback: Callable[[str], None] | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._freeze_threshold_sec: float = freeze_threshold_sec
        self._check_interval_sec: float = check_interval_sec
        self._heartbeat_interval_ms: int = heartbeat_interval_ms
        self._logger: logging.Logger = logger or logging.getLogger("UIWatchdog")
        self._on_freeze_callback: Callable[[str], None] | None = on_freeze_callback

        self._main_thread_id: int = threading.main_thread().ident or 0
        self._last_heartbeat_time: float = time.monotonic()
        self._is_running: bool = False
        self._is_frozen: bool = False
        self._lock: threading.Lock = threading.Lock()

        #: `EPIC-007F` §4 — the runtime state console's "cheapest red flag"
        #: reads these two, so they are tracked here rather than derived from
        #: log lines a console would otherwise have to scrape.
        self._freeze_count: int = 0
        self._worst_freeze_elapsed_sec: float = 0.0

        self._monitor_thread: threading.Thread | None = None
        self._heartbeat_timer: QtCore.QTimer | None = None

    def start(self) -> None:
        """Start the watchdog heartbeat timer on the Main Thread and background monitor."""
        if self._is_running:
            return

        self._is_running = True
        self._is_frozen = False
        with self._lock:
            self._last_heartbeat_time = time.monotonic()

        # 1. Main Thread Heartbeat Timer
        self._heartbeat_timer = QtCore.QTimer(self)
        self._heartbeat_timer.setInterval(self._heartbeat_interval_ms)
        self._heartbeat_timer.timeout.connect(self.record_heartbeat)
        self._heartbeat_timer.start()

        # 2. Background Monitor Thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="UIWatchdogMonitorThread",
            daemon=True,
        )
        self._monitor_thread.start()
        self._logger.debug(
            f"UIWatchdog started (Threshold: {self._freeze_threshold_sec}s, Interval: {self._check_interval_sec}s)"
        )

    def stop(self) -> None:
        """Stop the watchdog and clean up timers and threads."""
        self._is_running = False

        if self._heartbeat_timer is not None:
            self._heartbeat_timer.stop()
            self._heartbeat_timer = None

        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=self._check_interval_sec * 2)
            self._monitor_thread = None

        self._logger.debug("UIWatchdog stopped.")

    @QtCore.Slot()
    def record_heartbeat(self) -> None:
        """Record a heartbeat timestamp from the Qt Main Thread."""
        with self._lock:
            self._last_heartbeat_time = time.monotonic()
            if self._is_frozen:
                self._is_frozen = False
                self._logger.info(
                    "UI Thread recovered from freeze. Event loop responsive."
                )

    def _monitor_loop(self) -> None:
        """Background loop inspecting main thread responsiveness."""
        while self._is_running:
            time.sleep(self._check_interval_sec)

            if not self._is_running:
                break

            with self._lock:
                elapsed = time.monotonic() - self._last_heartbeat_time
                was_frozen = self._is_frozen

            if elapsed > self._freeze_threshold_sec and not was_frozen:
                with self._lock:
                    self._is_frozen = True
                self._handle_freeze(elapsed)

    @property
    def freeze_count(self) -> int:
        """@brief How many distinct freezes this watchdog has detected this
        run — `EPIC-007F` §4."""
        with self._lock:
            return self._freeze_count

    @property
    def worst_freeze_elapsed_sec(self) -> float:
        """@brief The longest single freeze measured so far, `0.0` until the
        first one — `EPIC-007F` §4."""
        with self._lock:
            return self._worst_freeze_elapsed_sec

    def _handle_freeze(self, elapsed: float) -> None:
        """Capture the Main Thread stack trace and log a diagnostic warning."""
        with self._lock:
            self._freeze_count += 1
            self._worst_freeze_elapsed_sec = max(
                self._worst_freeze_elapsed_sec, elapsed
            )

        frames = sys._current_frames()
        main_frame = frames.get(self._main_thread_id)

        if main_frame is not None:
            stack_lines = traceback.format_stack(main_frame)
            stack_trace_str = "".join(stack_lines)
        else:
            stack_trace_str = "Main thread frame not available."

        freeze_message = (
            f"🚨 UI FREEZE DETECTED: Qt Main Thread unresponsive for {elapsed:.1f}s "
            f"(Threshold: {self._freeze_threshold_sec:.1f}s).\n"
            f"Current Main Thread Stack Trace:\n{stack_trace_str}"
        )
        self._logger.warning(freeze_message)

        if self._on_freeze_callback is not None:
            try:
                self._on_freeze_callback(freeze_message)
            except Exception as callback_err:  # noqa: BLE001
                self._logger.error(f"Error in on_freeze_callback: {callback_err}")
