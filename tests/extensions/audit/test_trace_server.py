"""`TraceServer` — the live transport (`EPIC-005D`, `EPIC-005A` requirements
5/6).

Modelled directly on the old `test_websocket_broadcaster_auth.py`, which
`EPIC-005A` names explicitly: its behaviour — an ephemeral port, a readiness
signal, `?token=` auth rejected with close code `4401` before anything is sent
— must "come back as tests against the new transport". Same shape, same close
code, same fixture pattern.

**This file is that restoration.** The original was deleted with the
broadcaster it covered, by the same teardown; it is recoverable from the
`archive/pre-epic-005-audit` branch.
"""

from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("websockets")

import websockets.asyncio.client  # noqa: E402
from websockets.exceptions import ConnectionClosed  # noqa: E402

from sagittarius_engine.extensions.audit.contracts import Lane  # noqa: E402
from sagittarius_engine.extensions.audit.infra.trace_server import (  # noqa: E402
    TraceServer,
    TraceServerConfigError,
)
from sagittarius_engine.extensions.audit.recorder import TraceRecorder  # noqa: E402

READY_TIMEOUT_SECONDS = 2.0
CONNECT_TIMEOUT_SECONDS = 2.0
UNAUTHORIZED_CLOSE_CODE = 4401


@pytest.fixture
def recorder():
    return TraceRecorder(capacity=1000)


@pytest.fixture
def running_server(recorder):
    server = TraceServer(recorder, host="127.0.0.1", port=0)
    server.start()
    assert server.ready_event.wait(timeout=READY_TIMEOUT_SECONDS)
    yield server
    server.stop()


@pytest.fixture
def running_authed_server(recorder):
    server = TraceServer(recorder, host="127.0.0.1", port=0, token="secret-token")
    server.start()
    assert server.ready_event.wait(timeout=READY_TIMEOUT_SECONDS)
    yield server
    server.stop()


async def _recv_envelope(client) -> dict:
    return json.loads(
        await asyncio.wait_for(client.recv(), timeout=CONNECT_TIMEOUT_SECONDS)
    )


# ---------------------------------------------------------------- requirement 4


def test_binding_off_loopback_without_a_token_is_refused_at_startup(recorder):
    """The second half of requirement 4: refused at construction, not merely
    logged -- a warning nobody reads is exactly how the old broadcaster's
    unauthenticated-by-default posture went unnoticed."""
    with pytest.raises(TraceServerConfigError, match="token"):
        TraceServer(recorder, host="0.0.0.0", port=0, token=None)


def test_binding_loopback_without_a_token_is_allowed(recorder):
    server = TraceServer(recorder, host="127.0.0.1", port=0, token=None)
    assert server.host == "127.0.0.1"  # must not raise


def test_binding_off_loopback_with_a_token_is_allowed(recorder):
    TraceServer(recorder, host="0.0.0.0", port=0, token="secret")  # must not raise


@pytest.mark.asyncio
async def test_connection_rejected_without_a_valid_token(running_authed_server):
    """The first half of requirement 4, and the same close code the old
    broadcaster used -- this assertion is what carries that coverage forward."""
    uri = f"ws://{running_authed_server.host}:{running_authed_server.port}"
    async with websockets.asyncio.client.connect(
        uri, open_timeout=CONNECT_TIMEOUT_SECONDS
    ) as client:
        with pytest.raises(ConnectionClosed):
            await client.recv()
        assert client.close_code == UNAUTHORIZED_CLOSE_CODE


@pytest.mark.asyncio
async def test_connection_rejected_with_the_wrong_token(running_authed_server):
    uri = f"ws://{running_authed_server.host}:{running_authed_server.port}?token=wrong"
    async with websockets.asyncio.client.connect(
        uri, open_timeout=CONNECT_TIMEOUT_SECONDS
    ) as client:
        with pytest.raises(ConnectionClosed):
            await client.recv()
        assert client.close_code == UNAUTHORIZED_CLOSE_CODE


@pytest.mark.asyncio
async def test_connection_accepted_with_the_right_token(running_authed_server):
    uri = (
        f"ws://{running_authed_server.host}:{running_authed_server.port}"
        "?token=secret-token"
    )
    async with websockets.asyncio.client.connect(
        uri, open_timeout=CONNECT_TIMEOUT_SECONDS
    ) as client:
        hello = await _recv_envelope(client)
        assert hello["type"] == "hello"


# ------------------------------------------------------------ requirement 2


@pytest.mark.asyncio
async def test_hello_is_sent_first_and_names_the_protocol_version(running_server):
    from sagittarius_engine.extensions.audit.contracts import PROTOCOL_VERSION

    uri = f"ws://{running_server.host}:{running_server.port}"
    async with websockets.asyncio.client.connect(
        uri, open_timeout=CONNECT_TIMEOUT_SECONDS
    ) as client:
        hello = await _recv_envelope(client)
        assert hello["type"] == "hello"
        assert hello["data"]["v"] == PROTOCOL_VERSION


# ------------------------------------------------------------ requirement 3


@pytest.mark.asyncio
async def test_attaching_late_shows_a_workload_that_already_finished(recorder):
    """The literal wording of requirement 3: start the app, run a workload,
    *then* attach -- the retained buffer must show what already happened."""
    recorder.instant(Lane.USER, "already-happened", args={"n": 1})
    recorder.instant(Lane.USER, "also-already-happened", args={"n": 2})

    server = TraceServer(recorder, host="127.0.0.1", port=0)
    server.start()
    assert server.ready_event.wait(timeout=READY_TIMEOUT_SECONDS)
    try:
        uri = f"ws://{server.host}:{server.port}"
        async with websockets.asyncio.client.connect(
            uri, open_timeout=CONNECT_TIMEOUT_SECONDS
        ) as client:
            await _recv_envelope(client)  # hello
            backlog = await _recv_envelope(client)
            assert backlog["type"] == "trace"
            names = [r["n"] for r in backlog["data"]]
            assert names == ["already-happened", "also-already-happened"]
    finally:
        server.stop()


@pytest.mark.asyncio
async def test_a_client_that_attaches_before_anything_happened_sees_no_backlog_batch(
    running_server,
):
    """An empty retained buffer must not send an empty `trace` envelope --
    the client should be able to tell "nothing has happened yet" from
    "no message has arrived yet" without a timeout."""
    uri = f"ws://{running_server.host}:{running_server.port}"
    async with websockets.asyncio.client.connect(
        uri, open_timeout=CONNECT_TIMEOUT_SECONDS
    ) as client:
        await _recv_envelope(client)  # hello
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(client.recv(), timeout=0.2)


@pytest.mark.asyncio
async def test_a_record_captured_after_attaching_streams_live(recorder, running_server):
    """requirement 1: streams the live event log, not only the backlog."""
    uri = f"ws://{running_server.host}:{running_server.port}"
    async with websockets.asyncio.client.connect(
        uri, open_timeout=CONNECT_TIMEOUT_SECONDS
    ) as client:
        await _recv_envelope(client)  # hello, no backlog yet

        recorder.instant(Lane.USER, "order-filled", args={"price": 101.5})

        live = await _recv_envelope(client)
        assert live["type"] == "trace"
        assert live["data"][0]["n"] == "order-filled"
        assert live["data"][0]["a"] == {"price": 101.5}


@pytest.mark.asyncio
async def test_two_clients_each_see_the_same_live_records(recorder, running_server):
    """The tap fans out to every connection, not just the first one."""
    uri = f"ws://{running_server.host}:{running_server.port}"
    async with (
        websockets.asyncio.client.connect(
            uri, open_timeout=CONNECT_TIMEOUT_SECONDS
        ) as a,
        websockets.asyncio.client.connect(
            uri, open_timeout=CONNECT_TIMEOUT_SECONDS
        ) as b,
    ):
        await _recv_envelope(a)
        await _recv_envelope(b)

        recorder.instant(Lane.USER, "broadcast-me")

        seen_a = await _recv_envelope(a)
        seen_b = await _recv_envelope(b)
        assert seen_a["data"][0]["n"] == "broadcast-me"
        assert seen_b["data"][0]["n"] == "broadcast-me"


@pytest.mark.asyncio
async def test_a_disconnected_clients_tap_is_removed(recorder, running_server):
    """Otherwise every past client's queue keeps growing forever, off a
    connection nothing is reading from anymore."""
    uri = f"ws://{running_server.host}:{running_server.port}"
    async with websockets.asyncio.client.connect(
        uri, open_timeout=CONNECT_TIMEOUT_SECONDS
    ) as client:
        await _recv_envelope(client)

    # Give the server a moment to notice the close and run its `finally`.
    for _ in range(50):
        if not recorder._taps:  # noqa: SLF001 - the thing under test
            break
        await asyncio.sleep(0.02)

    assert recorder._taps == ()  # noqa: SLF001


# --------------------------------------------------------------------- lifecycle


def test_stop_without_start_is_safe(recorder):
    TraceServer(recorder, host="127.0.0.1", port=0).stop()  # must not raise


def test_starting_twice_is_idempotent(recorder):
    server = TraceServer(recorder, host="127.0.0.1", port=0)
    server.start()
    assert server.ready_event.wait(timeout=READY_TIMEOUT_SECONDS)
    first_port = server.port

    server.start()  # must not raise, must not rebind

    assert server.port == first_port
    server.stop()


def test_an_ephemeral_port_is_resolved_after_binding(recorder):
    server = TraceServer(recorder, host="127.0.0.1", port=0)
    assert server.port == 0
    server.start()
    assert server.ready_event.wait(timeout=READY_TIMEOUT_SECONDS)
    try:
        assert server.port != 0
    finally:
        server.stop()
