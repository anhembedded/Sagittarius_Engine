"""`StateConsoleExtension` — `EPIC-007C`.

Attaches at the readiness milestone, the same way `DiagnosticsExtension`
does, through `when_ready()`. The kernel knows nothing about this extension;
the dependency points from the extension to the lifecycle, never back
(`EPIC-006C`).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from sagittarius_engine.extensions.audit.contracts import StateSnapshot, UiThreadHealth
from sagittarius_engine.extensions.audit.infra.trace_server import TraceServer
from sagittarius_engine.extensions.audit.recorder import TraceRecorder
from sagittarius_engine.extensions.state_console.collectors.bounded import (
    BoundedStructuresCollector,
)
from sagittarius_engine.extensions.state_console.collectors.config import (
    ConfigCollector,
)
from sagittarius_engine.extensions.state_console.collectors.container import (
    ContainerCollector,
)
from sagittarius_engine.extensions.state_console.collectors.events import EventCollector
from sagittarius_engine.extensions.state_console.collectors.lifecycle import (
    LifecycleCollector,
)
from sagittarius_engine.extensions.state_console.collectors.signals import (
    SignalsCollector,
)
from sagittarius_engine.extensions.state_console.collectors.tasks import TaskCollector
from sagittarius_engine.extensions.state_console.collectors.thread_pools import (
    ThreadPoolCollector,
)
from sagittarius_engine.extensions.state_console.state_machine_watcher import (
    _StateMachineWatcher,
)
from sagittarius_engine.interfaces import IExtension
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


class StateConsoleExtension(IExtension[Any]):
    """
    @brief Serves a `StateSnapshot` (`EPIC-007A`) to any connected client, over
    the same `TraceServer` transport `sagittarius-trace attach` already uses.

    @details Collection is pull-only (`ADR-001` §2.4): nothing here runs on a
    timer, and nothing here subscribes to any event. A snapshot is built only
    when a connected client sends a frame asking for one — see
    `TraceServer._snapshot_request_loop()`.

    @param port, host, token Forwarded to `TraceServer` unchanged — same
        `?token=` auth, same off-loopback refusal, same ephemeral-port
        binding.
    @param interval_hz The minimum spacing between two *actually collected*
        snapshots. A request arriving sooner than `1 / interval_hz` seconds
        after the last one gets that same cached snapshot back rather than
        triggering fresh collection — this is what makes an aggressive or
        misbehaving client unable to force the collector to run faster than
        this, without `TraceServer` (a generic transport, reused by
        `sagittarius-trace attach`) needing to know this concept exists.
    @param reveal_config `ADR-001` §2.8 — producer-side only. `False` unless
        the application deliberately opts in; a client can never turn this on
        by asking.
    """

    def __init__(
        self,
        *,
        port: int = 8781,
        host: str = "127.0.0.1",
        token: str | None = None,
        interval_hz: float = 1.0,
        reveal_config: bool = False,
    ) -> None:
        self.port = port
        self.host = host
        self.token = token
        self._min_interval_seconds = 1.0 / interval_hz if interval_hz > 0 else 0.0
        self._reveal_config = reveal_config
        self.dependencies: list[str] = []
        self._server: TraceServer | None = None
        self._collectors: tuple[Any, ...] = ()
        self._last_snapshot: StateSnapshot | None = None
        self._last_collected_at: float | None = None

        # EPIC-007F §2/§3/§4 — populated only by explicit opt-in, never
        # discovered. A ResilientEventBus wraps whichever bus an
        # application chose, on top of it rather than in place of it
        # (ResilientEventBus.on() registers on inner_bus directly), so
        # there is no way to find one by walking context.event_bus.
        #
        # All three are mutable containers `SignalsCollector` is handed a
        # direct reference to, deliberately, not read via a getter: an
        # application's own `when_ready()` callback (e.g. a demo extension
        # seeding a fault) commonly runs *after* this extension's own
        # `_start()` has already built its collectors — readiness callbacks
        # fire in registration order (`EngineLifecycle._ready_callbacks`),
        # and this extension typically registers first. A plain
        # reassignable attribute captured by value at collector-build time
        # would miss a `watch_*()` call made after that point; a container
        # mutated in place is visible through the same reference regardless
        # of when it is mutated.
        self._dlq_buses: list[Any] = []
        self._state_machine_watchers: dict[str, _StateMachineWatcher] = {}
        self._ui_thread_health_sources: list[Callable[[], UiThreadHealth]] = []

    def register(self, context: Any) -> None:
        pass

    def boot(self, context: Any) -> None:
        """@brief Defers wiring to the readiness milestone — same reasoning
        as `DiagnosticsExtension.boot()`: extensions boot in dependency
        order, so this one may boot before readiness in some arrangements,
        and a snapshot taken then would describe a partially-wired app."""
        context.lifecycle.when_ready(lambda: self._start(context))

    def shutdown(self, context: Any) -> None:
        if self._server is not None:
            self._server.stop()
            self._server = None

    # --------------------------------------------------------- EPIC-007F §5

    def watch_dlq(self, bus: Any) -> None:
        """
        @brief Opts a `ResilientEventBus` into the dead-letter panel —
        `EPIC-007F` §2.

        @details A plain append: `get_dlq()` is read fresh at collection
        time, so watching costs nothing measurable while detached
        (criterion 5) — there is no timer, no subscription, nothing that
        runs on its own.
        """
        self._dlq_buses.append(bus)

    def watch_state_machine(self, name: str, machine: Any) -> None:
        """
        @brief Opts a `BaseStateMachine` into the state-machine panel —
        `EPIC-007F` §3.2.

        @details Explicit, one line per machine, at the point the
        application constructs it — not a subclass registry
        (`EPIC-006D` found one would have discovered 0 of the demo app's 7
        handlers, because the marker was duck-typed). Installs
        `_StateMachineWatcher`, which wraps `transition_to`/`dispatch` on
        `machine` itself; call this *before* driving the machine, or an
        already-happened transition is invisible to it, same as any
        listener added after the fact.
        """
        self._state_machine_watchers[name] = _StateMachineWatcher(name, machine)

    def watch_ui_thread_health(self, source: Callable[[], UiThreadHealth]) -> None:
        """
        @brief Opts UI-thread freeze/off-thread-mutation counts into the
        signals panel — `EPIC-007F` §4.

        @details `source` is a callback, not a value: `sagittarius_engine`
        must not import `PySide6` (`ADR-001` §2.10), so this extension
        cannot read a `UIWatchdog` itself. The application supplies a
        zero-argument function (typically closing over its own `UIWatchdog`
        and reading `pyside_mvc.safety.get_off_thread_mutation_count()`)
        that this collector calls once per snapshot. A second call replaces
        the source rather than adding a second one — only one application
        is being observed.
        """
        self._ui_thread_health_sources[:] = [source]

    # ------------------------------------------------------------- wiring

    def _start(self, context: Any) -> None:
        self._collectors = self._build_collectors(context)

        recorder = (
            context.recorder if isinstance(context.recorder, TraceRecorder) else None
        )
        if recorder is None:
            # TraceServer requires a real TraceRecorder — the snapshot path
            # does not need trace data, but it rides the same transport, and
            # that transport owns one. An application that never called
            # enable_tracing() gets an empty one here: its `hello`/backlog
            # will be trivially empty, and the trace path simply has nothing
            # to show, which is honest given nothing was ever recorded.
            recorder = TraceRecorder(capacity=1)

        self._server = TraceServer(
            recorder,
            host=self.host,
            port=self.port,
            token=self.token,
            snapshot_provider=self.collect,
        )
        self._server.start()
        # Found by running this against a real app (examples/student_management),
        # not by a unit test: `TraceServer.stop()` races its own background
        # thread when called before that thread's `_stop_event` exists yet --
        # every existing caller of TraceServer (the CLI, the test fixtures)
        # waits on `ready_event` first; this extension is the first one that
        # did not. Skipping this wait made `app.stop()` block for the full
        # 2-second `stop(timeout=...)` default whenever shutdown followed
        # boot quickly enough to win that race -- reliably, not occasionally,
        # in a script with nothing else running between boot and stop.
        if not self._server.ready_event.wait(timeout=2.0):
            context.logger.warning(
                "StateConsoleExtension: trace server did not report ready "
                f"within 2s on {self.host}:{self.port} -- continuing without "
                "confirmation it is actually listening."
            )

    def _build_collectors(self, context: Any) -> tuple[Any, ...]:
        config = context.config
        thread_manager: IThreadManager | None = None
        try:
            thread_manager = context.container.resolve(IThreadManager)
        except Exception:
            thread_manager = None

        collectors: list[Any] = [
            LifecycleCollector(
                context.lifecycle,
                extension_manager=getattr(context, "extension_manager", None),
                hosted_services=getattr(context, "hosted_services", None),
                scheduler=getattr(context, "scheduler", None),
            ),
            EventCollector(context.event_bus),
            ContainerCollector(context.container),
            TaskCollector(context.tasks),
            ThreadPoolCollector(context.tasks, thread_manager),
            BoundedStructuresCollector(
                context.tasks,
                context.event_bus,
                context.recorder
                if isinstance(context.recorder, TraceRecorder)
                else None,
            ),
            SignalsCollector(
                self._dlq_buses,
                self._state_machine_watchers,
                self._ui_thread_health_sources,
            ),
        ]
        if config is not None:
            collectors.append(ConfigCollector(config, reveal=self._reveal_config))
        return tuple(collectors)

    # ----------------------------------------------------------- collection

    def collect(self) -> StateSnapshot:
        """
        @brief Builds a fresh `StateSnapshot`, or returns the last one if it
        is younger than the configured minimum interval.

        @details Every field is assigned by keyword against the collector
        that produced it, not by iterating collectors generically — a
        collector never self-declares which `StateSnapshot` field it fills
        (`EPIC-007C` §2.1.1's own reasoning: the seven-way split is fixed by
        the schema, not discovered at runtime).
        """
        now = time.monotonic()
        if (
            self._last_snapshot is not None
            and self._last_collected_at is not None
            and (now - self._last_collected_at) < self._min_interval_seconds
        ):
            return self._last_snapshot

        by_type = {type(c).__name__: c for c in self._collectors}
        config_collector = by_type.get("ConfigCollector")

        snapshot = StateSnapshot(
            t=time.perf_counter_ns(),
            lifecycle=by_type["LifecycleCollector"].collect(),
            events=by_type["EventCollector"].collect(),
            container=by_type["ContainerCollector"].collect(),
            tasks=by_type["TaskCollector"].collect(),
            thread_pools=by_type["ThreadPoolCollector"].collect(),
            bounded=by_type["BoundedStructuresCollector"].collect(),
            config=config_collector.collect() if config_collector is not None else (),
            signals=by_type["SignalsCollector"].collect(),
        )
        self._last_snapshot = snapshot
        self._last_collected_at = now
        return snapshot
