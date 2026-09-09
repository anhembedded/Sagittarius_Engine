"""`ConsoleConnectionExtension` — `EPIC-007E` §1.1, extended by `EPIC-008B`.

Owns the one thing no screen may know exists: the websocket to the observed
app. The snapshot request loop runs as a `TaskManager` task — background work
the engine already knows how to spawn, track and cancel, not a bespoke
`QThread` (`EPIC-007E` criterion 10).
"""

from __future__ import annotations

import functools
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
    ConsoleConnecting,
    ConsoleDetached,
    ConsoleFailed,
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

#: `TraceServer`'s own close code for a rejected `?token=` handshake
#: (`extensions/audit/infra/trace_server.py::_UNAUTHORIZED_CLOSE_CODE`).
#: Duplicated as a literal rather than imported: that module is the
#: *server*-side extension, deliberately not a runtime dependency of this
#: *client*-side one — the two sides of this protocol detail agreeing is
#: covered by `tests/extensions/audit/test_trace_server.py` on the server
#: side and this file's own tests on the client side, not by a shared import.
_UNAUTHORIZED_CLOSE_CODE = 4401


class ConsoleConnectionExtension(IExtension[Any]):
    """
    @brief Connects to a `TraceServer`'s snapshot path, requests a fresh
    `StateSnapshot` on an interval, and emits domain events describing what
    happened.

    @details Never touched by a presenter or a view: `ConsoleConnecting`,
    `ConsoleAttached`, `ConsoleFailed`, `ConsoleDetached` and
    `SnapshotReceived` are the entire surface a consumer of this extension
    ever sees.

    @par Two distinct "not connected" events, on purpose
    `ConsoleFailed` means an attempt never succeeded — no snapshot was ever
    received from that address. `ConsoleDetached` means a connection that
    WAS attached (reached `ConsoleAttached` at least once) has since
    stopped. Folding the two together, and giving neither a `kind`/`code`
    a UI could classify (refused/malformed/rejected), was the actual defect
    `EPIC-008A`'s gap analysis found in the version of this file that
    shipped with `EPIC-007E` — see `reference/handoff.md` §4.

    @par No automatic retry
    Every attempt is exactly one attempt: connect once, run the snapshot
    loop until cancelled or the connection drops, emit exactly one terminal
    event, return. Reconnecting — after a `ConsoleFailed` OR a
    `ConsoleDetached` — is always a fresh `connect_to()` call, driven by the
    UI's own Retry/Reconnect action, never a background loop retrying
    silently. This is a deliberate change from `EPIC-007E`'s version, which
    retried every failure forever on a timer: that shape has no room for a
    `FAILED` state a user acts on, which `reference/handoff.md` §4
    specifically requires (a `Retry` button, not a spinner that eventually
    gives up on its own).

    @param uri `ws://host:port[?token=...]` of a running `TraceServer`, or
    `None` to boot "cold" — attached to nothing until `connect_to()` is
    called, which is what lets a consumer attach from inside the running
    tool instead of only via a CLI flag at launch.
    """

    def __init__(self, uri: str | None = None) -> None:
        self.uri = uri
        self.dependencies: list[str] = []
        self._context: Any = None
        self._token: CancellationToken | None = None

    def register(self, context: Any) -> None:
        pass

    def boot(self, context: Any) -> None:
        self._context = context
        if self.uri is not None:
            self._start(self.uri)

    def shutdown(self, context: Any) -> None:
        self.detach()

    # ------------------------------------------------------------ public API

    def connect_to(self, uri: str) -> None:
        """@brief Stops any in-flight connection or attempt and starts a
        fresh one against `uri`. Safe to call from any state — the tool
        never holds two targets at once (`reference/handoff.md` §5's own
        "connecting somewhere else drops this connection first" rule)."""
        self.detach()
        self._start(uri)

    def detach(self) -> None:
        """@brief Cancels the current connection or attempt, if any.
        Unlike `shutdown()` — which calls this as part of the whole app
        tearing down — the extension is left ready for another
        `connect_to()` call afterward."""
        if self._token is not None:
            self._token.cancel()

    # ------------------------------------------------------------ internals

    def _start(self, uri: str) -> None:
        self.uri = uri
        self._token = CancellationToken()
        # `uri` is bound into the callable rather than read from `self.uri`
        # inside `_run()` — a `connect_to()` call reassigns `self.uri`
        # immediately, and `_run()` for the PREVIOUS attempt may still be
        # unwinding (`TaskManager.spawn()`'s own cancellation is
        # cooperative, not preemptive); reading `self.uri` live could make
        # that old run's tail end reconnect to the NEW address under the
        # old attempt's identity. `TaskManager.spawn()` only forwards a
        # `token` kwarg automatically (inspects the callable's signature
        # for one) — `functools.partial` keeps `token` visible in that
        # signature while binding `uri`, verified empirically.
        self._context.tasks.spawn(
            functools.partial(self._run, uri=uri),
            name="ConsoleConnection",
            token=self._token,
        )

    def _run(self, token: CancellationToken, *, uri: str) -> None:
        """@brief One connection attempt, start to finish. Never loops to
        retry on its own — see this class's own "No automatic retry" note."""
        from websockets.exceptions import ConnectionClosed, InvalidURI
        from websockets.sync.client import connect

        self._emit(ConsoleConnecting(uri))

        try:
            connection_cm = connect(uri)
        except InvalidURI as exc:
            # A malformed URI is never attempted as a socket — the design
            # this class satisfies (`reference/handoff.md` §5) says exactly
            # that: "no connection was attempted."
            self._emit_failed("malformed", "EINVAL", str(exc), uri)
            return
        except OSError as exc:
            self._emit_failed("refused", "ECONNREFUSED", str(exc), uri)
            return

        try:
            with connection_cm as connection:
                try:
                    hello = self._recv_envelope(connection)
                except ProtocolMismatch as exc:
                    self._emit_failed("unknown", "PROTOCOL_MISMATCH", str(exc), uri)
                    return
                if hello.type is not MessageType.HELLO:
                    self._emit_failed(
                        "unknown",
                        "UNEXPECTED_MESSAGE",
                        f"expected 'hello' first, got {hello.type.value!r}",
                        uri,
                    )
                    return

                self._emit(ConsoleAttached())
                self._request_loop(connection, token)
        except ConnectionClosed as exc:
            if self._close_code(exc) == _UNAUTHORIZED_CLOSE_CODE:
                self._emit_failed("rejected", "HTTP 401", str(exc), uri)
            else:
                self._emit_detached(f"connection lost: {exc}")
            return
        except OSError as exc:
            self._emit_detached(f"connection lost: {exc}")
            return

        # No exception reached here: the `with` block exited because
        # `_request_loop()` returned cooperatively (`token` was cancelled),
        # not because the connection dropped — a drop always raises out of
        # `connection.recv()`/`.send()`, caught above. A real detach, not a
        # failure.
        self._emit_detached("stopped")

    def _request_loop(self, connection: Any, token: CancellationToken) -> None:
        """@brief Runs until cancelled or the connection drops. Returns
        normally only on cancellation — the caller's `with` block closes
        the socket either way, and `_run()` tells the two cases apart by
        whether an exception propagated out of this call."""
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

    @staticmethod
    def _close_code(exc: Exception) -> int | None:
        """@brief The close code a peer sent, if any. `ConnectionClosed.rcvd`
        is `None` when the close was never actually received from the
        remote (e.g. this side closed first), which this helper treats the
        same as "no code" rather than raising on `None.code`."""
        frame = getattr(exc, "rcvd", None)
        return frame.code if frame is not None else None

    def _emit(self, event: Any) -> None:
        if self._context is not None:
            self._context.event_bus.emit(event)

    def _emit_detached(self, reason: str) -> None:
        self._emit(ConsoleDetached(reason=reason))

    def _emit_failed(self, kind: str, code: str, detail: str, uri: str) -> None:
        self._emit(ConsoleFailed(kind=kind, code=code, detail=detail, uri=uri))
