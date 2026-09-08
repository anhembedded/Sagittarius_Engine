"""`UIWatchdog`'s freeze counters — `EPIC-007F` §4. Real background monitor
thread, real timing, no heartbeat pumped: the same "no synchronous stand-in"
discipline `test_thread_affinity.py` documents for cross-thread tests.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

from sagittarius_engine.extensions.pyside_mvc.safety.ui_watchdog import UIWatchdog


def test_a_fresh_watchdog_reports_no_freezes() -> None:
    watchdog = UIWatchdog(freeze_threshold_sec=5.0, check_interval_sec=1.0)
    assert watchdog.freeze_count == 0
    assert watchdog.worst_freeze_elapsed_sec == 0.0


def test_watchdog_counts_a_real_freeze_and_records_the_worst_elapsed(qapp) -> None:
    """No `qapp.processEvents()` call anywhere in this test — the heartbeat
    timer never fires, so the monitor thread must detect the freeze from
    elapsed wall-clock time alone, the same as it would in a real app whose
    main thread is genuinely blocked."""
    watchdog = UIWatchdog(freeze_threshold_sec=0.05, check_interval_sec=0.02)
    watchdog.start()
    try:
        time.sleep(0.3)
        assert watchdog.freeze_count == 1
        assert watchdog.worst_freeze_elapsed_sec >= 0.05
    finally:
        watchdog.stop()


def test_worst_freeze_elapsed_tracks_the_maximum_across_freezes() -> None:
    """`_handle_freeze()` is the real code the monitor thread calls (the
    other two tests exercise it that way, through real timing); called
    directly here to pin down the "keeps the worst, not the latest"
    behaviour without a second real-time freeze/recover/freeze cycle's
    timing sensitivity."""
    watchdog = UIWatchdog(freeze_threshold_sec=5.0, check_interval_sec=1.0)

    watchdog._handle_freeze(0.2)  # noqa: SLF001
    assert watchdog.freeze_count == 1
    assert watchdog.worst_freeze_elapsed_sec == 0.2

    watchdog._handle_freeze(0.1)  # noqa: SLF001 -- shorter, must not overwrite
    assert watchdog.freeze_count == 2
    assert watchdog.worst_freeze_elapsed_sec == 0.2

    watchdog._handle_freeze(5.0)  # noqa: SLF001 -- longer, must overwrite
    assert watchdog.freeze_count == 3
    assert watchdog.worst_freeze_elapsed_sec == 5.0
