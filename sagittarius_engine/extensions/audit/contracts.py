"""Trace protocol v1 — the single schema both sides import (`EPIC-005A`).

@par Why this module exists at all
`D3` and `D4` in `EPIC-005`'s defect table are the same defect twice: the
engine and the dashboard each hand-maintained their own idea of the payload,
and the two drifted until the consumer was reading fields the producer had
stopped sending. There is now exactly one schema, here, and **the client
imports it rather than redeclaring it**. A drift of that kind should become an
`ImportError` or a type error, not a panel that quietly goes blank.

@par Stdlib only, deliberately
This module is imported by the engine — which ships as a zero-dependency wheel
— *and* by any consumer attaching to it. A third-party serialisation library
here would put a dependency on both sides of a wire whose whole purpose is to
be attachable from anywhere. `dataclasses` and `json` are enough.

@par Nothing here formats anything
`to_dict()` produces primitives; rendering is the consumer's job (`EPIC-005`
§4.1). A record is captured on a hot path, and `strftime`/`repr()`/f-strings at
capture time were what made the old `AuditService` cost more per event than the
work it was observing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

#: Bumped on any **incompatible** change to the shapes below. The consumer
#: refuses a mismatch loudly at connect rather than degrading into a blank
#: panel — that degradation is `D1`, and a version handshake is its direct fix.
PROTOCOL_VERSION = 1


class MessageType(StrEnum):
    """@brief The four envelope kinds. A `StrEnum` so `to_dict()` needs no
    conversion step and the wire stays readable to a human with `jq`."""

    HELLO = "hello"
    TRACE = "trace"
    SNAPSHOT = "snapshot"
    ERROR = "error"


class RecordKind(StrEnum):
    """
    @brief Instant or span (`EPIC-005` §4.1).

    @details An **instant** is a point in time — a task was enqueued, a job
    fired, a user dropped a marker. A **span** is a begin/end pair carrying a
    duration. Two kinds rather than one because a viewer draws them
    differently, and because a span is not complete until it closes: giving
    them the same shape would mean either a nullable duration on everything or
    a second pass to pair them up.
    """

    INSTANT = "i"
    SPAN = "s"


class Lane(StrEnum):
    """
    @brief Which subsystem a record came from.

    @details A closed set, not a free string: the lane table goes over the wire
    in `hello` so a consumer can build its rows before the first batch arrives,
    and an unknown lane appearing mid-stream would mean rebuilding the view.
    Applications do not add lanes — their records go in `USER`, which is
    SystemView's user-marker model and the reason the framework needs to know
    nothing about application events (`D8`).
    """

    KERNEL = "kernel"
    EXTENSION = "extension"
    EVENT_BUS = "event_bus"
    DISPATCH = "dispatch"
    MIDDLEWARE = "middleware"
    TASK = "task"
    SCHEDULER = "scheduler"
    HOSTED = "hosted"
    USER = "user"


@dataclass(frozen=True, slots=True)
class TraceRecord:
    """
    @brief One captured event.

    @details Frozen and `slots=True`: a record is never edited after capture,
    and there may be a hundred thousand of them retained.

    @warning This is the *transport* shape, not the capture shape. The recorder
    appends a plain tuple to its ring buffer and only builds one of these when
    a batch is drained for sending — constructing a dataclass per event on the
    hot path is precisely the overhead `EPIC-005` §4.2 budgets against. See
    `from_row()`.

    @param t Nanoseconds since the session epoch, from `perf_counter_ns()`.
        Monotonic, so it is immune to NTP steps and DST — which is what
        duration measurement requires. Wall-clock is anchored once, in `Hello`.
    @param dur Nanoseconds. `0` for an instant, and for a span that has not
        closed yet.
    @param cid Correlation id, tying a span's parts and related records
        together. `0` when nothing correlates.
    @param args Free-form, and the one place a payload may appear. Kept
        optional because serialising an arbitrary object is the expensive part
        of any trace record.
    """

    t: int
    kind: RecordKind
    lane: Lane
    name: str
    cat: str = ""
    cid: int = 0
    dur: int = 0
    args: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """@brief Primitives only. Empty and zero fields are omitted — on a
        10k-events/sec stream the difference between sending `"cat": ""` and
        sending nothing is most of the bandwidth."""
        out: dict[str, Any] = {
            "t": self.t,
            "k": self.kind.value,
            "l": self.lane.value,
            "n": self.name,
        }
        if self.cat:
            out["c"] = self.cat
        if self.cid:
            out["id"] = self.cid
        if self.dur:
            out["d"] = self.dur
        if self.args is not None:
            out["a"] = self.args
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceRecord:
        """@brief The inverse. Absent optional keys take their defaults, which
        is what makes the omission above safe."""
        return cls(
            t=data["t"],
            kind=RecordKind(data["k"]),
            lane=Lane(data["l"]),
            name=data["n"],
            cat=data.get("c", ""),
            cid=data.get("id", 0),
            dur=data.get("d", 0),
            args=data.get("a"),
        )

    @classmethod
    def from_row(cls, row: tuple[Any, ...]) -> TraceRecord:
        """
        @brief Builds a record from the recorder's raw ring-buffer tuple.

        @details The hot path stores a tuple in a fixed field order and nothing
        else; this is where it becomes a typed object, off that path. The order
        is `(t, kind, lane, name, cat, cid, dur, args)` and is defined by
        `recorder.py` — the two must agree, which is why they live one import
        apart and are covered by the same test.
        """
        t, kind, lane, name, cat, cid, dur, args = row
        return cls(
            t=t,
            kind=RecordKind(kind),
            lane=Lane(lane),
            name=name,
            cat=cat,
            cid=cid,
            dur=dur,
            args=args,
        )


@dataclass(frozen=True, slots=True)
class Hello:
    """
    @brief Sent once, on connect, before any batch.

    @details Everything a consumer needs to interpret what follows and to know
    what it has already missed.

    @param epoch_wall_ns Unix nanoseconds, captured once at session start
        alongside the monotonic origin. Durations come from the monotonic
        clock; this is what lets a recording be lined up against log files.
    @param clock_resolution_ns Honest, not aspirational. `perf_counter_ns()`
        reports nanoseconds but an instrumentation call in CPython costs more
        than the clock read, so a consumer must not present sub-microsecond
        differences as meaningful.
    @param dropped_before_connect How many records the ring buffer had already
        evicted. A consumer that does not show this is showing a trace with
        holes in it and calling it complete.
    """

    protocol_version: int = PROTOCOL_VERSION
    epoch_wall_ns: int = 0
    clock_resolution_ns: int = 1000
    capacity: int = 0
    dropped_before_connect: int = 0
    lanes: tuple[str, ...] = field(
        default_factory=lambda: tuple(lane.value for lane in Lane)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "v": self.protocol_version,
            "epoch_wall_ns": self.epoch_wall_ns,
            "clock_resolution_ns": self.clock_resolution_ns,
            "capacity": self.capacity,
            "dropped_before_connect": self.dropped_before_connect,
            "lanes": list(self.lanes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Hello:
        return cls(
            protocol_version=data["v"],
            epoch_wall_ns=data.get("epoch_wall_ns", 0),
            clock_resolution_ns=data.get("clock_resolution_ns", 1000),
            capacity=data.get("capacity", 0),
            dropped_before_connect=data.get("dropped_before_connect", 0),
            lanes=tuple(data.get("lanes", ())),
        )


class ProtocolMismatch(Exception):
    """
    @brief The peer speaks a version this build cannot read.

    @details Raised at connect, on purpose. `D1` is what happens instead when a
    mismatch is tolerated: the old CLI polled HTTP against a socket that had
    moved to WebSocket, reported a connection error on every refresh, and
    presented an empty panel that looked like "nothing is happening".
    """


def check_protocol(peer_version: int) -> None:
    """
    @brief Fails loudly on a version this build cannot read.

    @details v1 has no backward-compatible predecessors, so the rule is
    equality. When v2 exists this becomes a range check — and the reason it is
    a function rather than an inline `if` is so that widening happens in one
    place for both sides of the wire.

    @raises ProtocolMismatch Naming both versions, because "which end is old"
        is the first question anyone asks.
    """
    if peer_version != PROTOCOL_VERSION:
        raise ProtocolMismatch(
            f"peer speaks protocol v{peer_version}, this build speaks "
            f"v{PROTOCOL_VERSION} — upgrade whichever end is older"
        )


@dataclass(frozen=True, slots=True)
class Envelope:
    """
    @brief What actually goes on the wire.

    @param seq Monotonic per connection, so a consumer can detect a gap. A
        dropped *message* and a dropped *record* are different failures and are
        reported separately: `Hello.dropped_before_connect` covers eviction,
        this covers transport.
    """

    type: MessageType
    seq: int
    data: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "v": PROTOCOL_VERSION,
            "type": self.type.value,
            "seq": self.seq,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Envelope:
        """@raises ProtocolMismatch Before anything else is read — a payload
        from a version this build does not know is not worth parsing."""
        check_protocol(data["v"])
        return cls(
            type=MessageType(data["type"]),
            seq=data["seq"],
            data=data.get("data"),
        )


def trace_batch(seq: int, records: tuple[TraceRecord, ...]) -> Envelope:
    """@brief A batch of records as one message. Batched because a
    10k-events/sec workload must not become 10k frames — `EPIC-005` §4.4."""
    return Envelope(
        type=MessageType.TRACE, seq=seq, data=[r.to_dict() for r in records]
    )


def error_message(seq: int, detail: str) -> Envelope:
    """
    @brief A server-side failure, surfaced to the operator.

    @details The old implementation had eleven bare
    `except Exception: self._logger.error(...)` blocks, and the consumer just
    saw a field quietly go missing. A failure the operator cannot see is a
    failure they will debug as something else.
    """
    return Envelope(type=MessageType.ERROR, seq=seq, data={"detail": detail})
