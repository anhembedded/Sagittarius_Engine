"""Regression test for TASK-017 issue 1: a full/hung subscriber queue must not
deadlock the IPCBroker's broadcast loop for every other subscriber."""

import queue

BROADCAST_WAIT_SECONDS = 1.0


def test_full_subscriber_queue_does_not_block_other_subscribers(ipc_broker_factory):
    pub_q: queue.Queue = queue.Queue()
    full_sub_q: queue.Queue = queue.Queue(maxsize=1)
    healthy_sub_q: queue.Queue = queue.Queue()

    broker = ipc_broker_factory(publish_queue=pub_q, subscriber_put_timeout=0.05)

    # Fill the first subscriber's queue to capacity *before* anything is
    # published, and register it before the healthy subscriber — with the
    # pre-fix blocking put(), the broadcast loop would hang on this queue
    # forever and healthy_sub_q would never receive anything.
    full_sub_q.put("blocker")
    broker.add_subscriber(full_sub_q)
    broker.add_subscriber(healthy_sub_q)

    broker.start()
    pub_q.put(("test.event", "data"))

    # If the broker deadlocked on full_sub_q, this raises queue.Empty instead
    # of hanging forever, because get() itself is bounded.
    msg = healthy_sub_q.get(timeout=BROADCAST_WAIT_SECONDS)
    assert msg == ("test.event", "data")

    # The full queue's own single slot must still hold only the original
    # blocker — the event was dropped, not silently queued past capacity.
    assert full_sub_q.qsize() == 1
    assert full_sub_q.get_nowait() == "blocker"

    # The broker must still be responsive afterwards — the lock was never
    # held indefinitely.
    another_sub_q: queue.Queue = queue.Queue()
    broker.add_subscriber(another_sub_q)
    pub_q.put(("second.event", "more-data"))
    assert another_sub_q.get(timeout=BROADCAST_WAIT_SECONDS) == (
        "second.event",
        "more-data",
    )
