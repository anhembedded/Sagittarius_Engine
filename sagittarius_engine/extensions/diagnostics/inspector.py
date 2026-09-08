"""Wiring inspection — compare what an application *declared* against what it
actually *wired*, and report the difference.

Every check here is a set difference or a static walk. Nothing is resolved,
constructed, emitted or started: a diagnostic that builds objects in order to
describe them would run half the application as a side effect of being asked a
question, and could not honestly be run at boot.

See `EPIC-006` §3 for the check catalogue; each finding carries the id.
"""

from __future__ import annotations

import difflib
import inspect
from abc import ABC
from collections.abc import Iterable, Sequence
from typing import Any

from sagittarius_engine.domain.event_registry import EventRegistry
from sagittarius_engine.interfaces import IContainer, IEventBus

from .report import Finding, WiringReport

#: How close a subscribed name must be to a declared one before it is called a
#: typo rather than an undeclared event. 0.8 separates `order.cancelld` from
#: `order.cancelled` (a hit) while leaving `legacy.tick` unmatched against
#: everything — which is the distinction that keeps A2 from crying wolf on
#: applications that simply have not declared their events.
_TYPO_CUTOFF = 0.8


class WiringInspector:
    """
    @brief Runs the wiring checks and returns a `WiringReport`.

    @details Takes the subsystems it needs one at a time rather than an engine
    context. The repository has twice removed god-object coupling from this
    kind of code (`TASK-008`, `TASK-013`), and a narrow signature is also what
    lets each check be tested against a two-line fixture instead of a booted
    application.
    """

    # ------------------------------------------------------------------ events

    def inspect_events(
        self,
        bus: IEventBus,
        *,
        expected_unheard: Iterable[str] = (),
    ) -> tuple[Finding, ...]:
        """
        @brief Checks A1–A3: the event bus against the declared catalogue.

        @param expected_unheard Event names this application deliberately does
            not listen to. Declared by the application; the framework never
            decides an event is legitimately unheard on its behalf.
        """
        findings: list[Finding] = []

        declared = {entry.event_name for entry in EventRegistry.all()}
        typed = {
            entry.event_name
            for entry in EventRegistry.all()
            if entry.event_class is not None
        }
        subscribed = dict(bus.subscriptions())
        allowed = set(expected_unheard)

        # --- A2: subscribed to a name that does not exist --------------------
        # The flagship check. Nothing else in the toolchain can see this: the
        # name is a valid `str`, so the type checker has no opinion, and the
        # handler simply never runs.
        for name in sorted(set(subscribed) - declared):
            near = difflib.get_close_matches(name, declared, n=1, cutoff=_TYPO_CUTOFF)
            if near:
                findings.append(
                    Finding(
                        check="A2",
                        severity="error",
                        subject=name,
                        message=(
                            "a handler is subscribed to this name, but no event "
                            "is registered under it — the handler can never run"
                        ),
                        hint=f'did you mean "{near[0]}"?',
                    )
                )
            else:
                findings.append(
                    Finding(
                        check="A2",
                        severity="warning",
                        subject=name,
                        message=(
                            "subscribed, but not registered in EventRegistry, and "
                            "not close to any name that is — so it cannot be "
                            "checked for typos either"
                        ),
                        hint=(
                            "declare it as a BaseEvent subclass, or via "
                            "EventRegistry.register_named() at its definition site"
                        ),
                    )
                )

        # --- A1: declared, but nobody is listening ---------------------------
        # Advisory on purpose. EventRegistry is process-wide and holds every
        # event the engine can emit, most of which any given application has no
        # reason to handle. Reporting those as warnings every boot would train
        # the reader to skip the whole report, which costs more than it finds.
        for name in sorted(declared - set(subscribed) - allowed):
            findings.append(
                Finding(
                    check="A1",
                    severity="info",
                    subject=name,
                    message="declared, but no handler is subscribed",
                    hint=(
                        "intentional? pass it in expected_unheard to stop reporting it"
                    ),
                )
            )

        # --- A3: more handlers than the author may realise -------------------
        for name, handlers in sorted(subscribed.items()):
            if len(handlers) > 1:
                names = ", ".join(getattr(h, "__qualname__", repr(h)) for h in handlers)
                findings.append(
                    Finding(
                        check="A3",
                        severity="info",
                        subject=name,
                        message=f"{len(handlers)} handlers subscribed",
                        hint=names,
                    )
                )

        # --- exposure: string subscriptions are the ones A2 exists for -------
        # A class-based subscription cannot be misspelled — Python raises
        # NameError on an undefined class before the bus is ever reached. This
        # names the places where that protection is absent.
        for name in sorted((set(subscribed) & declared) - typed):
            findings.append(
                Finding(
                    check="A5",
                    severity="info",
                    subject=name,
                    message=(
                        "subscribed by string, so a misspelling here would fail "
                        "silently rather than at import"
                    ),
                    hint="a BaseEvent subclass makes that class of typo impossible",
                )
            )

        return tuple(findings)

    # --------------------------------------------------------------- container

    def inspect_container(self, container: IContainer) -> tuple[Finding, ...]:
        """
        @brief Checks C1–C3: can everything registered actually be built?

        @details Static throughout — constructor signatures are read, never
        called. `resolve()` would answer the same question far more simply and
        is not an option: it builds the object.
        """
        findings: list[Finding] = []
        registrations = container.registrations()
        registered = set(registrations)

        for abstract, registration in sorted(
            registrations.items(), key=lambda kv: kv[0].__name__
        ):
            concrete = registration.concrete
            if concrete is None or registration.instantiated:
                # A factory's dependencies are opaque until it runs, and an
                # already-built singleton has proved itself by existing.
                continue

            findings.extend(
                self._unbindable_dependencies(
                    concrete,
                    registered,
                    abstract_check="C1",
                    plain_check="C2",
                )
            )

        findings.extend(self._cycles(registrations))
        return tuple(findings)

    def _unbindable_dependencies(
        self,
        owner: type,
        registered: set[type],
        *,
        abstract_check: str,
        plain_check: str,
    ) -> list[Finding]:
        """
        @brief Constructor dependencies of `owner` that the container cannot
        satisfy — shared by the container check (C1/C2) and the handler
        pre-flight (B1/B2).

        @details The two callers differ only in *what* they are inspecting, not
        in what "unsatisfiable" means, so the check ids are parameters rather
        than the logic being written twice and drifting.
        """
        findings: list[Finding] = []

        for param_name, annotation in self._constructor_dependencies(owner):
            if annotation in registered:
                continue

            if (
                isinstance(annotation, type)
                and issubclass(annotation, ABC)
                and inspect.isabstract(annotation)
            ):
                findings.append(
                    Finding(
                        check=abstract_check,
                        severity="error",
                        subject=f"{owner.__name__}.{param_name}",
                        message=(
                            f"needs {annotation.__name__}, which is abstract "
                            "and is not bound — resolving this raises"
                        ),
                        hint=(
                            f"container.bind({annotation.__name__}, <implementation>)"
                        ),
                    )
                )
                continue

            # EPIC-006 §2.3: the silent one. An unbound *plain* class does not
            # raise — the container constructs the annotation itself and injects
            # that, so the application receives an empty stand-in for its real
            # implementation and simply behaves wrongly.
            findings.append(
                Finding(
                    check=plain_check,
                    severity="warning",
                    subject=f"{owner.__name__}.{param_name}",
                    message=(
                        f"needs {annotation.__name__}, which is not bound. "
                        "This does not raise: the container will construct "
                        f"{annotation.__name__} itself and inject that"
                    ),
                    hint=(
                        f"bind {annotation.__name__} explicitly if a real "
                        "implementation was intended"
                    ),
                )
            )

        return findings

    # ---------------------------------------------------------------- handlers

    def inspect_handlers(
        self,
        handlers: Iterable[type],
        container: IContainer,
    ) -> tuple[Finding, ...]:
        """
        @brief Checks B1–B3: can every dispatchable handler actually be built?

        @details `Dispatcher.dispatch()` resolves the handler class straight
        from the container, with no registration step. Nothing binds a handler,
        so `inspect_container()` never sees one — and a handler whose
        constructor dependency is unbound therefore fails **only when a user
        triggers that command**, in production, on a real request. This pulls
        that failure forward to boot.

        Same definition of "unsatisfiable" as C1/C2, deliberately: the ids
        differ so a report line says which surface it came from, but a
        dependency that cannot be bound is one thing, not two.

        @param handlers The classes to check — from `discover_handlers()` or
            named explicitly by the application.
        """
        findings: list[Finding] = []
        registered = set(container.registrations())

        for handler in sorted(handlers, key=lambda h: h.__qualname__):
            findings.extend(
                self._unbindable_dependencies(
                    handler,
                    registered,
                    abstract_check="B1",
                    plain_check="B2",
                )
            )

            # B3: "what does this actually depend on" is a question people ask
            # of a DI container and could not previously answer for a handler,
            # since handlers appear in no registry.
            dependencies = self._constructor_dependencies(handler)
            if dependencies:
                findings.append(
                    Finding(
                        check="B3",
                        severity="info",
                        subject=handler.__qualname__,
                        message=f"dispatchable, {len(dependencies)} dependencies",
                        hint=", ".join(
                            f"{name}: {getattr(annotation, '__name__', annotation)}"
                            for name, annotation in dependencies
                        ),
                    )
                )

        return tuple(findings)

    def _cycles(self, registrations: Any) -> list[Finding]:
        """@brief Check C3 — constructor dependency cycles, named in full."""
        edges: dict[type, list[type]] = {}
        for abstract, registration in registrations.items():
            concrete = registration.concrete
            if concrete is None:
                continue
            edges[abstract] = [
                annotation
                for _name, annotation in self._constructor_dependencies(concrete)
                if isinstance(annotation, type)
            ]

        findings: list[Finding] = []
        seen: set[type] = set()

        def walk(node: type, path: list[type]) -> None:
            if node in path:
                cycle = path[path.index(node) :] + [node]
                key = frozenset(cycle)
                if key in seen_cycles:
                    return
                seen_cycles.add(key)
                findings.append(
                    Finding(
                        check="C3",
                        severity="error",
                        subject=" → ".join(t.__name__ for t in cycle),
                        message="circular constructor dependency",
                        hint=(
                            "break the cycle, or make one side depend on a "
                            "narrower interface"
                        ),
                    )
                )
                return
            if node in seen:
                return
            for nxt in edges.get(node, ()):
                walk(nxt, [*path, node])
            seen.add(node)

        seen_cycles: set[frozenset[type]] = set()
        for start in list(edges):
            walk(start, [])
        return findings

    @staticmethod
    def _constructor_dependencies(concrete: type) -> list[tuple[str, Any]]:
        """
        @brief `(param_name, annotation)` for each injectable constructor
        parameter. Parameters with defaults are skipped — the container is not
        obliged to supply them.

        @details `eval_str=True` — found via `EPIC-007D`'s `DemoFaultsExtension`,
        the first constructor this checker was ever run against that (a) uses
        `from __future__ import annotations` and (b) is registered transient,
        so `inspect_container()` actually reads it. Without `eval_str`,
        `inspect.signature()` returns each annotation as the literal source
        string (`"SystemClock"`, not the class) under postponed evaluation —
        `annotation in registered` is then false for every dependency
        regardless of whether it is actually bound, and the one case that
        reaches a finding crashes formatting it (`str` has no `__name__`).
        This was latent rather than theoretical: nothing in this repository's
        own tests exercised a postponed-annotations class through
        `inspect_container()` before this one did.
        """
        try:
            # The class, not `concrete.__init__`: `signature()` on a class
            # already resolves the constructor and drops `self`, and reaching
            # for the dunder is unsound anyway — an instance's `__init__` can
            # come from an incompatible subclass, which mypy rejects outright.
            signature = inspect.signature(concrete, eval_str=True)
        except (TypeError, ValueError, NameError):
            # Builtins and C extensions have no introspectable signature; a
            # forward reference that cannot be resolved in the class's own
            # module (e.g. a TYPE_CHECKING-only import) raises NameError for
            # the whole signature, not just that parameter. Neither is a
            # finding: it says nothing about whether the wiring is correct.
            return []

        found: list[tuple[str, Any]] = []
        for name, parameter in signature.parameters.items():
            if name == "self" or parameter.default is not inspect.Parameter.empty:
                continue
            if parameter.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue
            if parameter.annotation is inspect.Parameter.empty:
                continue
            found.append((name, parameter.annotation))
        return found

    # --------------------------------------------------------------- lifecycle

    def inspect_lifecycle(
        self,
        *,
        extension_manager: Any = None,
        hosted_services: Any = None,
        scheduler: Any = None,
    ) -> tuple[Finding, ...]:
        """
        @brief Checks D1–D3: did everything registered actually come up?

        @details Each subsystem is optional so an application that does not use
        one is not obliged to fabricate it.
        """
        findings: list[Finding] = []

        if extension_manager is not None:
            findings.extend(self._extensions(extension_manager))
        if hosted_services is not None:
            findings.extend(self._hosted_services(hosted_services))
        if scheduler is not None:
            findings.extend(self._scheduler(scheduler))

        return tuple(findings)

    @staticmethod
    def _extensions(manager: Any) -> list[Finding]:
        """
        @brief D1 — registered but never initialised.

        @details `ExtensionManager` defers an extension whose declared
        dependencies are not yet registered, and retries on every later
        `register()`. If the dependency never arrives, the extension sits in
        `registered_extensions` forever without ever being initialised, and
        nothing says so — the application starts, minus a feature.
        """
        registered = list(getattr(manager, "registered_extensions", []))
        initialized = {
            ext.descriptor.name
            for ext in getattr(manager, "initialized_extensions", [])
        }
        present = {ext.descriptor.name for ext in registered}

        findings: list[Finding] = []
        for ext in registered:
            descriptor = ext.descriptor
            if not descriptor.enabled or descriptor.name in initialized:
                continue

            missing = [d for d in descriptor.dependencies if d not in present]
            if missing:
                findings.append(
                    Finding(
                        check="D1",
                        severity="error",
                        subject=descriptor.name,
                        message=(
                            "registered but never initialised — it declares "
                            f"{', '.join(missing)}, which was never registered"
                        ),
                        hint=f"register {missing[0]} before {descriptor.name}",
                    )
                )
            else:
                findings.append(
                    Finding(
                        check="D1",
                        severity="error",
                        subject=descriptor.name,
                        message=(
                            "registered but never initialised, though all its "
                            "declared dependencies are present"
                        ),
                        hint="a dependency cycle between extensions will do this",
                    )
                )
        return findings

    @staticmethod
    def _hosted_services(manager: Any) -> list[Finding]:
        """@brief D2 — registered but not started."""
        registered: Sequence[Any] = getattr(manager, "services", [])
        started = {id(s) for s in getattr(manager, "started_services", [])}

        return [
            Finding(
                check="D2",
                severity="warning",
                subject=type(service).__name__,
                message="registered as a hosted service but never started",
                hint="start() not called, or it failed and was rolled back",
            )
            for service in registered
            if id(service) not in started
        ]

    @staticmethod
    def _scheduler(scheduler: Any) -> list[Finding]:
        """
        @brief D3 — a job that will never fire.

        @details `subject` reads `job.fn` — `runtime.scheduler.scheduler.ScheduledJob`'s
        actual callable attribute (`REF-004`: this read `job.job_func`, an attribute that
        class has never had, since before this docstring existed; every real dead job named
        itself `"anonymous job"`). The only test exercising this check used a duck-typed fake
        with the same wrong attribute name, so nothing caught it.
        """
        return [
            Finding(
                check="D3",
                severity="warning",
                subject=getattr(
                    getattr(job, "fn", None), "__qualname__", "anonymous job"
                ),
                message="scheduled, but has no next run time — it will never fire",
            )
            for job in getattr(scheduler, "jobs", [])
            if getattr(job, "next_run", None) is None
        ]

    # ------------------------------------------------------------------ facade

    def inspect(
        self,
        *,
        bus: IEventBus | None = None,
        container: IContainer | None = None,
        extension_manager: Any = None,
        hosted_services: Any = None,
        scheduler: Any = None,
        expected_unheard: Iterable[str] = (),
        handlers: Iterable[type] = (),
    ) -> WiringReport:
        """@brief Runs every check for which a subsystem was supplied."""
        findings: list[Finding] = []

        if bus is not None:
            findings.extend(self.inspect_events(bus, expected_unheard=expected_unheard))
        if container is not None:
            findings.extend(self.inspect_container(container))
            # Handlers need the container to know what is bound, so this is
            # only meaningful alongside it.
            findings.extend(self.inspect_handlers(handlers, container))

        findings.extend(
            self.inspect_lifecycle(
                extension_manager=extension_manager,
                hosted_services=hosted_services,
                scheduler=scheduler,
            )
        )

        return WiringReport(findings=tuple(findings))
