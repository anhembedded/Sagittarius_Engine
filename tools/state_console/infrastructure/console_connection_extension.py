"""`ConsoleConnectionExtension` — `EPIC-007E` §1.1.

Owns the one thing no screen may know exists: the websocket to the observed
app. The snapshot request loop runs as a `TaskManager` task — background work
the engine already knows how to spawn, track and cancel, not a bespoke
`QThread` (`EPIC-007E` criterion 10).
"""

from __future__ import annotations

import json
from typing import Any

from sagittarius_engine.extensions.audit.contracts import (
    Envelope,
    MessageType,
    ProtocolMismatch,
    StateSnapshot,
)
from sagittarius_engine.interfaces import IExtension
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken
from tools.state_console.domain.events import (
    ConsoleAttached,
    ConsoleDetached,
    SnapshotReceived,
)

#: How long a single recv() waits before checking the cancellation token
#: again -- short enough that app.stop() returns promptly, long enough that
#: this is not a busy loop.
_RECV_POLL_SECONDS = 0.5

#: Spacing between two snapshot requests once attached. Independent of the
#: server's own StateConsoleExtension(interval_hz=...) cache: this is how
#: often the client asks, not how often the server actually collects.
_REQUEST_INTERVAL_SECONDS = 1.0

#: How long to wait before retrying after a connection attempt fails.
_RECONNECT_DELAY_SECONDS = 2.0


class ConsoleConnectionExtension(IExtension[Any]):
    """
    @brief Connects to a `TraceServer`'s snapshot path, requests a fresh
    `StateSnapshot` on an interval, and emits it as a domain event.

    @details Never touched by a presenter or a view: `ConsoleAttached`,
    `ConsoleDetached` and `SnapshotReceived` are the entire surface a
    consumer of this extension ever sees.

    @param uri `ws://host:port[?token=...]` of a running `TraceServer`.
    """

    def __init__(self, uri: str) -> None:
        self.uri = uri
        self.dependencies: list[str] = []
        self._context: Any = None
        self._token: CancellationToken | None = None

    def register(self, context: Any) -> None:
        pass

    def boot(self, context: Any) -> None:
        self._context = context
        self._token = CancellationToken()
        context.tasks.spawn(self._run, name="ConsoleConnection", token=self._token)

    def shutdown(self, context: Any) -> None:
        if self._token is not None:
            self._token.cancel()

    # ------------------------------------------------------------ the loop

    def _run(self, token: CancellationToken) -> None:
        """@brief Runs until cancelled. Every connection attempt that fails
        or drops is `ConsoleDetached`, not an exception -- a client that
        cannot reach the observed app is an ordinary state (`EPIC-007E` §4),
        never a crash."""
        from websockets.exceptions import ConnectionClosed
        from websockets.sync.client import connect

        while not token.is_cancelled():
            try:
                connection_cm = connect(self.uri)
            except OSError as exc:
                self._emit_detached(f"could not connect: {exc}")
                token.wait(_RECONNECT_DELAY_SECONDS)
                continue

            try:
                with connection_cm as connection:
                    try:
                        hello = self._recv_envelope(connection)
                    except ProtocolMismatch as exc:
                        self._emit_detached(f"protocol mismatch: {exc}")
                        return
                    if hello.type is not MessageType.HELLO:
                        self._emit_detached(
                            f"expected 'hello' first, got {hello.type.value!r}"
                        )
                        return

                    self._emit(ConsoleAttached())
                    self._request_loop(connection, token)
            except (ConnectionClosed, OSError) as exc:
                self._emit_detached(f"connection lost: {exc}")
                if not token.is_cancelled():
                    token.wait(_RECONNECT_DELAY_SECONDS)

        self._emit_detached("stopped")

    def _request_loop(self, connection: Any, token: CancellationToken) -> None:
        """@brief Runs until cancelled or the connection drops. Returns
        normally either way -- the caller's `with` block closes the socket,
        and `_run()`'s own loop reads `token.is_cancelled()` to decide
        whether to reconnect."""
        while not token.is_cancelled():
            connection.send("snapshot")
            envelope = self._recv_with_timeout(connection, token)
            if envelope is not None and envelope.type is MessageType.SNAPSHOT:
                self._emit(SnapshotReceived(StateSnapshot.from_dict(envelope.data)))
            token.wait(_REQUEST_INTERVAL_SECONDS)

    def _recv_with_timeout(
        self, connection: Any, token: CancellationToken
    ) -> Envelope | None:
        """@brief `None` on cancellation, a protocol mismatch (logged by the
        contract layer already; treated here as no update this round), or
        while merely waiting out the poll timeout."""
        while not token.is_cancelled():
            try:
                return self._recv_envelope(connection, timeout=_RECV_POLL_SECONDS)
            except TimeoutError:
                continue
            except ProtocolMismatch:
                return None
        return None

    @staticmethod
    def _recv_envelope(connection: Any, *, timeout: float | None = None) -> Envelope:
        return Envelope.from_dict(json.loads(connection.recv(timeout=timeout)))

    def _emit(self, event: Any) -> None:
        if self._context is not None:
            self._context.event_bus.emit(event)

    def _emit_detached(self, reason: str) -> None:
        self._emit(ConsoleDetached(reason=reason))
