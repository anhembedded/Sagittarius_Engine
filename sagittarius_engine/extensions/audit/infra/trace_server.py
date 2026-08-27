"""Live trace transport (`EPIC-005D`, and `EPIC-005A` requirements 5/6).

@par What this is, and what it is not
A thin WebSocket server that lets `sagittarius-trace attach` (`cli.py`) — or a
raw `websockets` client — watch a `TraceRecorder` while the application runs,
and see what it already recorded before attaching. It is not a dashboard, has
no timeline, and does not aggregate anything: `EPIC-005` §5 is the standing
decision that Perfetto and OpenTelemetry cover that ground better than a
bespoke viewer ever would. Live streaming is the one thing they cannot give
you, and this exists only for that.

@par Shape borrowed deliberately
The threaded-server-with-a-readiness-event shape below is the same one the old
`WebsocketBroadcaster` used — an ephemeral port (`port=0`), a
`threading.Event` set once actually bound, `?token=` query-string auth rejected
with close code `4401` before anything is sent. `EPIC-005A`'s own requirement
said that behaviour must come back "as tests against the new transport", so its
test file was read before this module was written and reproduced against it in
`tests/extensions/audit/test_trace_server.py`. Both the broadcaster and its
test have since been deleted by that teardown; recover them from the
`archive/pre-epic-005-audit` branch if the comparison is ever needed again.

@par How attach-late works
`add_tap()` is registered **before** `snapshot()` is read for the backlog: a
row captured in the gap between the two can be delivered twice (once in the
backlog, once live) but never dropped. The reverse order can drop one. For a
diagnostic stream a duplicate is a shrug; a silent gap is the defect this
engine exists to stop shipping — see `TraceRecorder.add_tap()`.

@par What is honestly not bulletproof
Each connection's outgoing queue is unbounded. A client that stops reading
while the application keeps recording will grow that queue without limit
until it disconnects or the process runs out of memory. Deliberate: backpressure
across a whole publish/subscribe fan-out is real engineering that this "roughly
a tenth of what it was before the scope cut" milestone does not need — the
fix, if it is ever needed, is the client reading faster or disconnecting and
reattaching, which the retained buffer makes safe to do.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import queue
import threading
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..contracts import (
    Envelope,
    MessageType,
    StateSnapshot,
    TraceRecord,
    snapshot_message,
    trace_batch,
)
from ..recorder import TraceRecorder

#: Hosts this server accepts binding to **without** a token configured.
#: Anything else and no token is `TraceServerConfigError` at construction —
#: `EPIC-005D` requirement 4's second half: binding off-loopback without a
#: token is refused at startup, not merely logged as a warning nobody reads.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

#: How many queued rows one outgoing batch carries at most, and how long the
#: forwarding loop sleeps when the queue is empty. Neither is tuned for
#: throughput — this is a debugging tool, not a production telemetry
#: pipeline — they exist so an idle connection does not spin a CPU core.
_MAX_BATCH_ROWS = 500
_POLL_INTERVAL_SECONDS = 0.05

_UNAUTHORIZED_CLOSE_CODE = 4401


class TraceServerConfigError(ValueError):
    """@brief Raised at construction when the configuration cannot be started
    safely — currently, binding off-loopback with no token configured."""


class TraceServer:
    """
    @brief Serves one `TraceRecorder` to any number of live WebSocket clients.

    @param recorder The recorder to serve. Not owned: the caller starts and
        stops tracing on it independently: this class only ever *reads* it
        (`snapshot()`, `add_tap()`/`remove_tap()`).
    @param host Bind address. Anything other than loopback requires `token`.
    @param port `0` for an ephemeral port, resolved into `.port` once bound —
        the same pattern the old broadcaster used to make ephemeral-port
        tests possible.
    @param token If set, a connecting client must supply a matching
        `?token=...` query parameter or the connection is rejected — closed
        with code `4401` before `hello` or any trace data is sent.
    @param snapshot_provider `EPIC-007C`. Called once per client-sent frame —
        the content is not parsed; any inbound message means "send me a
        current snapshot" — and the result is sent back as one
        `MessageType.SNAPSHOT` envelope. `None` (the default) leaves this
        server exactly as `EPIC-005D` shipped it: trace-only, any inbound
        frame simply ignored. Same token and off-loopback rules as the trace
        path — an auth check that covers one of two message types is not an
        auth check.
    @raises TraceServerConfigError `host` is not loopback and `token` is
        `None`. Refused here, at construction, rather than left to bind and
        quietly accept unauthenticated connections from anywhere reachable.
    """

    def __init__(
        self,
        recorder: TraceRecorder,
        host: str = "127.0.0.1",
        port: int = 0,
        token: str | None = None,
        snapshot_provider: Callable[[], StateSnapshot] | None = None,
    ) -> None:
        if host not in _LOOPBACK_HOSTS and token is None:
            raise TraceServerConfigError(
                f"refusing to bind {host!r} without a token — an unauthenticated "
                "trace server reachable off this machine would hand out everything "
                "the application records to anyone who connects. Pass `token=` or "
                "bind to loopback."
            )
        self._recorder = recorder
        self.host = host
        self.port = port
        self._token = token
        self._snapshot_provider = snapshot_provider
        self._clients: set[Any] = set()
        self._logger = logging.getLogger("sagittarius_engine.trace_server")
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop_event: asyncio.Event | None = None
        #: Set once actually bound and listening. `port=0` is not resolved
        #: into a real number until then — see `_resolve_bound_port()`.
        self.ready_event = threading.Event()

    # ------------------------------------------------------------ lifecycle

    def start(self) -> None:
        """@brief Starts the server on a background thread. Returns
        immediately; wait on `ready_event` to know it is actually listening."""
        if self._thread and self._thread.is_alive():
            return
        self.ready_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """@brief Stops the server and waits for the background thread to
        exit. Safe to call even if `start()` was never called."""
        if self._loop is not None and self._loop.is_running() and self._stop_event:
            self._loop.call_soon_threadsafe(self._stop_event.set)
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        finally:
            self._loop.close()

    async def _serve(self) -> None:
        # Imported here, not at module level: this is the one place an
        # application without the transport's runtime dependency installed
        # would fail, and it should fail with a clear ImportError pointing at
        # this line, not silently at random inside asyncio machinery.
        from websockets.asyncio.server import serve

        self._stop_event = asyncio.Event()
        async with serve(self._handle, self.host, self.port) as server:
            self._resolve_bound_port(server)
            self._logger.info(f"trace server listening on ws://{self.host}:{self.port}")
            self.ready_event.set()
            await self._stop_event.wait()

    def _resolve_bound_port(self, server: Any) -> None:
        sockets = getattr(server, "sockets", None)
        if sockets:
            self.port = sockets[0].getsockname()[1]

    # ------------------------------------------------------- per connection

    def _extract_token(self, websocket: Any) -> str | None:
        request = getattr(websocket, "request", None)
        raw_path = getattr(request, "path", None) if request is not None else None
        if not raw_path:
            return None
        values = parse_qs(urlparse(raw_path).query).get("token")
        return values[0] if values else None

    async def _handle(self, websocket: Any) -> None:
        if self._token is not None and self._extract_token(websocket) != self._token:
            self._logger.warning(
                f"rejected connection from "
                f"{getattr(websocket, 'remote_address', '?')}: bad or missing token"
            )
            await websocket.close(code=_UNAUTHORIZED_CLOSE_CODE, reason="Unauthorized")
            return

        self._clients.add(websocket)
        row_queue: queue.SimpleQueue[tuple[Any, ...]] = queue.SimpleQueue()
        try:
            await websocket.send(
                _envelope_json(
                    Envelope(
                        type=MessageType.HELLO,
                        seq=0,
                        data=self._recorder.hello().to_dict(),
                    )
                )
            )

            # Tap registered before the backlog read is what makes attach-late
            # honest: a row captured in this exact gap is delivered twice
            # (backlog + live), never dropped. See the module docstring.
            self._recorder.add_tap(row_queue.put)
            try:
                # Shared across the trace-forwarding loop and the snapshot-
                # request loop (EPIC-007C) — a plain int, but `next()` on it
                # never straddles an `await`, so two coroutines on the same
                # event loop thread cannot race incrementing it.
                seq_counter = itertools.count(1)
                backlog = self._recorder.snapshot()
                if backlog:
                    await websocket.send(
                        _envelope_json(trace_batch(next(seq_counter), backlog))
                    )

                await self._forward_until_closed(websocket, row_queue, seq_counter)
            finally:
                self._recorder.remove_tap(row_queue.put)
        finally:
            self._clients.discard(websocket)

    async def _forward_until_closed(
        self,
        websocket: Any,
        row_queue: "queue.SimpleQueue[tuple[Any, ...]]",
        seq_counter: "itertools.count[int]",
    ) -> None:
        """@brief Runs trace forwarding, snapshot-request handling (`EPIC-007C`),
        and disconnect detection concurrently until the client disconnects.

        @details Three tasks racing rather than one loop checking a `closed`
        flag between sends: with a flag, a disconnect during `websocket.send()`
        itself would only be noticed on the *next* loop iteration, which is one
        avoidable wasted send (and, worse, one avoidable delay before this
        connection's slot is freed).
        """
        forward = asyncio.ensure_future(
            self._forward_loop(websocket, row_queue, seq_counter)
        )
        requests = asyncio.ensure_future(
            self._snapshot_request_loop(websocket, seq_counter)
        )
        closed = asyncio.ensure_future(websocket.wait_closed())
        try:
            await asyncio.wait(
                {forward, requests, closed}, return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            for task in (forward, requests, closed):
                if not task.done():
                    task.cancel()

    async def _snapshot_request_loop(
        self, websocket: Any, seq_counter: "itertools.count[int]"
    ) -> None:
        """
        @brief `EPIC-007C`: any frame the client sends means "send me a current
        snapshot" — the content is not parsed, there is no request schema to
        get wrong. Collection happens here, once per inbound frame, never on a
        server-side timer: `ADR-001` §2.4 — a snapshot is collected when a
        client asks for one, or on the interval *the client* polls at, and
        never by anything the observed application does.

        @details A no-op loop (reads and discards every frame) when no
        provider was configured — `EPIC-005D`'s trace-only server keeps
        behaving exactly as it always has for a client that sends it nothing,
        which every existing client of this class does.
        """
        async for _message in websocket:
            if self._snapshot_provider is None:
                continue
            snapshot = self._snapshot_provider()
            await websocket.send(
                _envelope_json(snapshot_message(next(seq_counter), snapshot))
            )

    async def _forward_loop(
        self,
        websocket: Any,
        row_queue: "queue.SimpleQueue[tuple[Any, ...]]",
        seq_counter: "itertools.count[int]",
    ) -> None:
        while True:
            rows = _drain(row_queue, _MAX_BATCH_ROWS)
            if rows:
                records = tuple(TraceRecord.from_row(row) for row in rows)
                await websocket.send(
                    _envelope_json(trace_batch(next(seq_counter), records))
                )
            else:
                await asyncio.sleep(_POLL_INTERVAL_SECONDS)


def _drain(
    q: "queue.SimpleQueue[tuple[Any, ...]]", limit: int
) -> list[tuple[Any, ...]]:
    """@brief Non-blocking: up to `limit` items currently queued, or fewer if
    that is all there is."""
    rows: list[tuple[Any, ...]] = []
    while len(rows) < limit:
        try:
            rows.append(q.get_nowait())
        except queue.Empty:
            break
    return rows


def _envelope_json(envelope: Envelope) -> str:
    return json.dumps(envelope.to_dict())
