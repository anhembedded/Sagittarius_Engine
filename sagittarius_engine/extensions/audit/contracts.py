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

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from sagittarius_engine.interfaces.i_trace_recorder import Lane

#: Bumped on any **incompatible** change to the shapes below. The consumer
#: refuses a mismatch loudly at connect rather than degrading into a blank
#: panel — that degradation is `D1`, and a version handshake is its direct fix.
#:
#: **v2** (`EPIC-007A`) adds the snapshot shapes below `Envelope`, filling
#: `MessageType.SNAPSHOT` — declared in v1 and constructed by nothing. The bump
#: is incompatible on purpose: a v1 `sagittarius-trace` refuses a v2 server at
#: connect, naming both versions, rather than attaching and silently rendering
#: a message type it cannot read.
PROTOCOL_VERSION = 2

#: Substrings that mark a config key's value as a secret (`ADR-001` §2.8).
#: Matched case-insensitively against the key name; `_has_userinfo()` covers
#: the credential whose key name gives nothing away.
_SECRET_KEY_PATTERNS: tuple[str, ...] = (
    "secret",
    "token",
    "password",
    "key",
    "dsn",
    "credential",
)


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


#: Re-exported, not redefined. `Lane` moved to `interfaces/i_trace_recorder.py`
#: in `EPIC-005B`, because `tests/test_architecture.py` forbids `kernel/` from
#: importing `extensions/` and the kernel's instrumentation sites have to name a
#: lane. Defining it in both places would be `D3`/`D4` a third time — this
#: module exists to argue that two hand-maintained copies of a schema drift, so
#: it does not get to keep a second copy of its own vocabulary.
__all__ = [
    "PROTOCOL_VERSION",
    "BoundedStructures",
    "ConfigEntry",
    "ContainerState",
    "Envelope",
    "EventState",
    "FindingRecord",
    "Hello",
    "Lane",
    "LifecycleState",
    "MessageType",
    "ProtocolMismatch",
    "RecordKind",
    "RegistrationState",
    "StateSnapshot",
    "TaskRecord",
    "ThreadPoolStats",
    "TraceRecord",
    "check_protocol",
    "error_message",
    "mask_config",
    "snapshot_message",
    "trace_batch",
]


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


# ── Snapshot: protocol v2 ────────────────────────────────────────────────────
#
# `EPIC-007A`. `MessageType.SNAPSHOT` was declared in v1 and constructed by
# nothing; `EPIC-005` §1 left the seat deliberately ("snapshots stay, demoted to
# one message type among several"). These are the shapes that fill it.
#
# @par Readable keys here, terse keys above -- on purpose
# `TraceRecord.to_dict()` uses single letters and omits empty fields because it
# is measured against a 10k-events/sec stream, where "the difference between
# sending `"cat": ""` and sending nothing is most of the bandwidth". A snapshot
# is collected at 1 Hz at most (`ADR-001` §2.4), so that pressure does not
# exist, and paying for it anyway would buy nothing and cost every reader who
# ever pipes this wire through `jq`. Same module, different budget, stated so
# the inconsistency reads as a decision rather than an oversight.


def _is_secret_key(key: str) -> bool:
    """@brief Whether a config key's *name* marks its value as a secret."""
    lowered = key.lower()
    return any(pattern in lowered for pattern in _SECRET_KEY_PATTERNS)


def _has_userinfo(value: str) -> bool:
    """
    @brief Whether a URL-shaped value carries `user:password@` credentials.

    @details `postgresql://app:hunter2@db/prod` is a secret whose *key* is
    `database.url` -- which matches no secret-shaped pattern. Checking the
    value as well is what stops the most common real credential from being the
    one thing masking misses.
    """
    scheme, separator, rest = value.partition("://")
    if not separator or " " in scheme:
        return False
    authority = rest.split("/", 1)[0]
    return "@" in authority


@dataclass(frozen=True, slots=True)
class ConfigEntry:
    """
    @brief One configuration key, with its value or with a mask -- never both.

    @details The masking decision is made engine-side, before the record is
    built, and nothing on the wire can undo it: `ADR-001` §2.8. A console that
    opens a socket and ships `IConfig.get_all()` wholesale is a credential
    disclosure path, not a feature.

    The key and its source survive masking, because "which layer won" is the
    question a config panel is actually opened for.

    @param source Which layer supplied the winning value (`json:config.json`,
        `env:APP_`). Empty when the producer cannot say -- see
        `EPIC-007B` §2.4: `IConfig` has no public reader for this yet, and
        guessing would be worse than admitting it.
    @param value `None` exactly when `masked` is true.
    """

    key: str
    source: str = ""
    value: str | None = None
    masked: bool = False

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"key": self.key, "masked": self.masked}
        if self.source:
            out["source"] = self.source
        if not self.masked:
            out["value"] = self.value
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConfigEntry:
        masked = bool(data.get("masked", False))
        return cls(
            key=data["key"],
            source=data.get("source", ""),
            value=None if masked else data.get("value"),
            masked=masked,
        )


def mask_config(
    values: Mapping[str, Any],
    *,
    reveal: bool = False,
    sources: Mapping[str, str] | None = None,
) -> tuple[ConfigEntry, ...]:
    """
    @brief Turns a flat config mapping into wire records, masking secrets.

    @details `reveal` is a **producer-side** parameter and is deliberately not
    reachable from any field on the wire. A client must not be able to ask a
    server to disclose more than it was configured to disclose; the only way to
    see an unmasked secret is an explicit opt-in where the extension is
    constructed.

    @param sources Optional key -> layer mapping. Absent today for the reason
        given on `ConfigEntry.source`.
    """
    source_map = sources or {}
    entries: list[ConfigEntry] = []
    for key in sorted(values):
        raw = values[key]
        rendered = "" if raw is None else str(raw)
        secret = _is_secret_key(key) or _has_userinfo(rendered)
        masked = secret and not reveal
        entries.append(
            ConfigEntry(
                key=key,
                source=source_map.get(key, ""),
                value=None if masked else rendered,
                masked=masked,
            )
        )
    return tuple(entries)


@dataclass(frozen=True, slots=True)
class FindingRecord:
    """
    @brief The wire form of `extensions.diagnostics.report.Finding`.

    @details Mirrored rather than reused. `Finding` lives in the diagnostics
    package, and this module is imported by consumers that have no reason to
    pull that package in -- `contracts.py` is the one schema both sides of the
    wire import, and widening what importing it costs would work against that.

    The duplication is guarded: a test asserts this carries every field
    `Finding` has, and fails when `Finding` grows one. That is the difference
    between a mirror and the `D3`/`D4` drift this module exists to prevent.
    """

    check: str
    severity: str
    subject: str
    message: str
    hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "check": self.check,
            "severity": self.severity,
            "subject": self.subject,
            "message": self.message,
        }
        if self.hint is not None:
            out["hint"] = self.hint
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FindingRecord:
        return cls(
            check=data["check"],
            severity=data["severity"],
            subject=data["subject"],
            message=data["message"],
            hint=data.get("hint"),
        )


@dataclass(frozen=True, slots=True)
class LifecycleState:
    """
    @brief Where the engine got to, and how long each step took.

    @param transitions `(state_name, ns_since_session_epoch)` in the order
        reached. Monotonic nanoseconds, like every other timestamp here -- the
        wall clock is anchored once, in `Hello`.
    """

    state: str = ""
    transitions: tuple[tuple[str, int], ...] = ()
    extensions_registered: int = 0
    extensions_initialized: int = 0
    hosted_registered: int = 0
    hosted_started: int = 0
    scheduler_jobs: int = 0
    scheduler_jobs_without_next_run: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "transitions": [[name, t] for name, t in self.transitions],
            "extensions_registered": self.extensions_registered,
            "extensions_initialized": self.extensions_initialized,
            "hosted_registered": self.hosted_registered,
            "hosted_started": self.hosted_started,
            "scheduler_jobs": self.scheduler_jobs,
            "scheduler_jobs_without_next_run": self.scheduler_jobs_without_next_run,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LifecycleState:
        return cls(
            state=data.get("state", ""),
            transitions=tuple(
                (str(name), int(t)) for name, t in data.get("transitions", ())
            ),
            extensions_registered=data.get("extensions_registered", 0),
            extensions_initialized=data.get("extensions_initialized", 0),
            hosted_registered=data.get("hosted_registered", 0),
            hosted_started=data.get("hosted_started", 0),
            scheduler_jobs=data.get("scheduler_jobs", 0),
            scheduler_jobs_without_next_run=data.get(
                "scheduler_jobs_without_next_run", 0
            ),
        )


@dataclass(frozen=True, slots=True)
class EventState:
    """
    @brief One event name, joined across the registry and the live bus.

    @param registered False when a handler is subscribed to a name the registry
        does not know -- check `A2`, the typo that nothing else in the
        toolchain can see, because the name is a valid `str` and the handler
        simply never runs.
    @param handlers Qualified names, not callables: this crosses a wire.
    """

    name: str
    module: str = ""
    handlers: tuple[str, ...] = ()
    emits: int = 0
    failures: int = 0
    registered: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "module": self.module,
            "handlers": list(self.handlers),
            "emits": self.emits,
            "failures": self.failures,
            "registered": self.registered,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventState:
        return cls(
            name=data["name"],
            module=data.get("module", ""),
            handlers=tuple(data.get("handlers", ())),
            emits=data.get("emits", 0),
            failures=data.get("failures", 0),
            registered=data.get("registered", True),
        )


@dataclass(frozen=True, slots=True)
class RegistrationState:
    """
    @brief One container registration, as `IContainer.registrations()` reports
    it -- type *names*, never the types, and never an instance.

    @param concrete `None` for a singleton registered as a factory, whose
        result type is unknowable before it runs.
    @param instantiated Whether an instance already exists. A singleton
        registered and never resolved is dead wiring, and this is what says so.
    """

    abstract: str
    concrete: str | None = None
    lifetime: str = ""
    instantiated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "abstract": self.abstract,
            "concrete": self.concrete,
            "lifetime": self.lifetime,
            "instantiated": self.instantiated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RegistrationState:
        return cls(
            abstract=data["abstract"],
            concrete=data.get("concrete"),
            lifetime=data.get("lifetime", ""),
            instantiated=data.get("instantiated", False),
        )


@dataclass(frozen=True, slots=True)
class ContainerState:
    """
    @brief The container's registry, plus the scope census.

    @param open_scopes A count that only ever rises is a `with` block that
        never exits -- invisible by any other means today.
    """

    registrations: tuple[RegistrationState, ...] = ()
    open_scopes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "registrations": [r.to_dict() for r in self.registrations],
            "open_scopes": self.open_scopes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContainerState:
        return cls(
            registrations=tuple(
                RegistrationState.from_dict(r) for r in data.get("registrations", ())
            ),
            open_scopes=data.get("open_scopes", 0),
        )


@dataclass(frozen=True, slots=True)
class TaskRecord:
    """
    @brief One retained background task.

    @details Named `TaskRecord`, not `TaskState`: `runtime.tasks.TaskState` is
    the engine's own enum and two things called the same thing one import apart
    is how `EventRegistry`'s collision warning came to exist. The enum's
    *value* travels here as `state`.

    @param age_ns Since the task was spawned. **Corrected 2026-08-27, `EPIC-007C`**:
        this originally said "on the monotonic clock", written before `EPIC-007B`
        confirmed `BackgroundTask.start_time`/`end_time` are wall clock
        (`datetime.now(UTC)`), not monotonic. Wall clock is the wrong clock for
        *measuring a duration* elsewhere in this engine (`EPIC-005` §4.1's own
        reasoning), but an "age" a diagnostic console rounds to whole seconds does
        not need monotonic precision, and changing `BackgroundTask` to also carry a
        monotonic timestamp is its own change, not a silent assumption to carry
        here.
    @param error Terminal failure text for a `FAILED` task, empty otherwise.
    """

    id: str
    name: str = ""
    state: str = ""
    progress: float = 0.0
    age_ns: int = 0
    thread: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state,
            "progress": self.progress,
            "age_ns": self.age_ns,
            "thread": self.thread,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskRecord:
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            state=data.get("state", ""),
            progress=data.get("progress", 0.0),
            age_ns=data.get("age_ns", 0),
            thread=data.get("thread", ""),
            error=data.get("error", ""),
        )


@dataclass(frozen=True, slots=True)
class ThreadPoolStats:
    """
    @brief One executor's occupancy.

    @param queue_depth The backpressure signal, and the reason this type
        exists: a queue that grows is the earliest visible sign the
        application is falling behind, and `IThreadManager` exposes no way to
        see it today.
    """

    name: str
    max_workers: int = 0
    in_flight: int = 0
    queue_depth: int = 0
    submitted: int = 0
    completed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "max_workers": self.max_workers,
            "in_flight": self.in_flight,
            "queue_depth": self.queue_depth,
            "submitted": self.submitted,
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThreadPoolStats:
        return cls(
            name=data["name"],
            max_workers=data.get("max_workers", 0),
            in_flight=data.get("in_flight", 0),
            queue_depth=data.get("queue_depth", 0),
            submitted=data.get("submitted", 0),
            completed=data.get("completed", 0),
        )


@dataclass(frozen=True, slots=True)
class BoundedStructures:
    """
    @brief Occupancy of everything in the engine that has a ceiling.

    @details This is what `ADR-001` §2.9 answers "dynamic memory" with. The
    wheel declares no dependencies, so `psutil` is not available; `tracemalloc`
    is stdlib but costs a 2-4x slowdown while tracing, and a diagnostic that
    perturbs what it measures by that much is the problem it was meant to find.
    Every field here is O(1) to read, and each is a place a long-running engine
    actually grows.

    @param subscriptions Total handler count across every event name. A number
        that only rises is a missing `unsubscribe`.
    """

    ring_used: int = 0
    ring_capacity: int = 0
    ring_dropped: int = 0
    retained_tasks: int = 0
    retained_task_limit: int = 0
    subscriptions: int = 0
    gc_counts: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ring_used": self.ring_used,
            "ring_capacity": self.ring_capacity,
            "ring_dropped": self.ring_dropped,
            "retained_tasks": self.retained_tasks,
            "retained_task_limit": self.retained_task_limit,
            "subscriptions": self.subscriptions,
            "gc_counts": list(self.gc_counts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BoundedStructures:
        return cls(
            ring_used=data.get("ring_used", 0),
            ring_capacity=data.get("ring_capacity", 0),
            ring_dropped=data.get("ring_dropped", 0),
            retained_tasks=data.get("retained_tasks", 0),
            retained_task_limit=data.get("retained_task_limit", 0),
            subscriptions=data.get("subscriptions", 0),
            gc_counts=tuple(data.get("gc_counts", ())),
        )


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    """
    @brief One reading of the whole application, at one instant.

    @details Every section is optional and defaults to empty, so a producer
    that cannot answer a question sends nothing rather than a zero. The
    distinction is load-bearing on the consumer side: an absent `thread_pools`
    means "not observed", a present-and-empty one means "observed, none exist",
    and rendering those identically is how a panel comes to read as healthy
    while measuring nothing.

    @param t Nanoseconds since the session epoch, on the same monotonic clock
        as `TraceRecord.t`, so a snapshot lines up against the trace.
    """

    t: int = 0
    lifecycle: LifecycleState | None = None
    events: tuple[EventState, ...] = ()
    container: ContainerState | None = None
    tasks: tuple[TaskRecord, ...] = ()
    thread_pools: tuple[ThreadPoolStats, ...] = ()
    bounded: BoundedStructures | None = None
    config: tuple[ConfigEntry, ...] = ()
    findings: tuple[FindingRecord, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"t": self.t}
        if self.lifecycle is not None:
            out["lifecycle"] = self.lifecycle.to_dict()
        if self.events:
            out["events"] = [e.to_dict() for e in self.events]
        if self.container is not None:
            out["container"] = self.container.to_dict()
        if self.tasks:
            out["tasks"] = [t.to_dict() for t in self.tasks]
        if self.thread_pools:
            out["thread_pools"] = [p.to_dict() for p in self.thread_pools]
        if self.bounded is not None:
            out["bounded"] = self.bounded.to_dict()
        if self.config:
            out["config"] = [c.to_dict() for c in self.config]
        if self.findings:
            out["findings"] = [f.to_dict() for f in self.findings]
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StateSnapshot:
        lifecycle = data.get("lifecycle")
        container = data.get("container")
        bounded = data.get("bounded")
        return cls(
            t=data.get("t", 0),
            lifecycle=None
            if lifecycle is None
            else LifecycleState.from_dict(lifecycle),
            events=tuple(EventState.from_dict(e) for e in data.get("events", ())),
            container=None
            if container is None
            else ContainerState.from_dict(container),
            tasks=tuple(TaskRecord.from_dict(t) for t in data.get("tasks", ())),
            thread_pools=tuple(
                ThreadPoolStats.from_dict(p) for p in data.get("thread_pools", ())
            ),
            bounded=None if bounded is None else BoundedStructures.from_dict(bounded),
            config=tuple(ConfigEntry.from_dict(c) for c in data.get("config", ())),
            findings=tuple(
                FindingRecord.from_dict(f) for f in data.get("findings", ())
            ),
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


def snapshot_message(seq: int, snapshot: StateSnapshot) -> Envelope:
    """
    @brief One reading of the application, as one message.

    @details Not batched, unlike `trace_batch()`: a snapshot is whole by
    definition, and there is at most one per interval (`ADR-001` §2.4) rather
    than ten thousand per second.
    """
    return Envelope(type=MessageType.SNAPSHOT, seq=seq, data=snapshot.to_dict())
