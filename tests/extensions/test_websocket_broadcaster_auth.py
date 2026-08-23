"""Regression tests for TASK-017 issue 6: WebsocketBroadcaster must reject a
connection with a missing/invalid token when an auth_token is configured, and
accept + broadcast normally when a valid token is supplied."""

import asyncio

import pytest

pytest.importorskip("websockets")

import websockets.asyncio.client  # noqa: E402
from websockets.exceptions import ConnectionClosed  # noqa: E402

from sagittarius_engine.extensions.audit.infra.websocket_broadcaster import (
    WebsocketBroadcaster,
)

READY_TIMEOUT_SECONDS = 2.0
CONNECT_TIMEOUT_SECONDS = 2.0


@pytest.fixture
def running_broadcaster():
    broadcaster = WebsocketBroadcaster(
        host="127.0.0.1", port=0, auth_token="secret-token"
    )
    broadcaster.start()
    assert broadcaster._ready_event.wait(timeout=READY_TIMEOUT_SECONDS)
    yield broadcaster
    broadcaster.stop()


UNAUTHORIZED_CLOSE_CODE = 4401


async def _assert_rejected(uri: str, running_broadcaster) -> None:
    # The auth check runs inside the handler, after the WS handshake itself
    # already succeeded — so rejection is a close frame with our custom code,
    # not a failed handshake. The client is never registered either way.
    async with websockets.asyncio.client.connect(
        uri, open_timeout=CONNECT_TIMEOUT_SECONDS
    ) as client:
        with pytest.raises(ConnectionClosed):
            await client.recv()
        assert client.close_code == UNAUTHORIZED_CLOSE_CODE
    assert len(running_broadcaster.clients) == 0


@pytest.mark.asyncio
async def test_connection_rejected_without_valid_token(running_broadcaster):
    uri = f"ws://{running_broadcaster.host}:{running_broadcaster.port}"

    await _assert_rejected(uri, running_broadcaster)
    await _assert_rejected(f"{uri}?token=wrong-token", running_broadcaster)


@pytest.mark.asyncio
async def test_connection_accepted_and_broadcast_received_with_valid_token(
    running_broadcaster,
):
    uri = (
        f"ws://{running_broadcaster.host}:{running_broadcaster.port}?token=secret-token"
    )

    async with websockets.asyncio.client.connect(
        uri, open_timeout=CONNECT_TIMEOUT_SECONDS
    ) as client:
        # Give the server a moment to register the client before broadcasting.
        for _ in range(50):
            if running_broadcaster.clients:
                break
            await asyncio.sleep(0.02)
        assert len(running_broadcaster.clients) == 1

        running_broadcaster.broadcast("telemetry.update", {"cpu": 42})

        message = await asyncio.wait_for(client.recv(), timeout=CONNECT_TIMEOUT_SECONDS)
        assert '"telemetry.update"' in message
        assert '"cpu": 42' in message
