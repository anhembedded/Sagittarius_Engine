"""Integration tests for TASK-012: DI Container Scoped Lifecycle."""

import threading

from sagittarius_engine.infrastructure.container.std_container import StdLibContainer


class IService:
    pass


class ConcreteService(IService):
    def __init__(self) -> None:
        self.id = id(self)


class TestScopedLifecycle:
    def test_scoped_resolves_same_instance_within_scope(self) -> None:
        container = StdLibContainer()
        container.scoped(IService, ConcreteService)

        with container.create_scope():
            a = container.resolve(IService)
            b = container.resolve(IService)
            assert a is b, (
                "Within a scope, scoped dependency must be the same instance."
            )

    def test_different_scopes_produce_different_instances(self) -> None:
        container = StdLibContainer()
        container.scoped(IService, ConcreteService)

        with container.create_scope():
            a = container.resolve(IService)

        with container.create_scope():
            b = container.resolve(IService)

        assert a is not b, "Different scopes must produce different instances."

    def test_concurrent_scopes_are_isolated(self) -> None:
        """Validate that two concurrent scopes (e.g., two HTTP requests) do not share instances."""
        container = StdLibContainer()
        container.scoped(IService, ConcreteService)

        # Store actual object references (not id()) to prevent CPython from reusing
        # memory addresses after one scope's ConcreteService is GC'd.
        results: list[IService] = []

        def resolve_in_scope() -> None:
            with container.create_scope():
                svc = container.resolve(IService)
                results.append(svc)

        t1 = threading.Thread(target=resolve_in_scope)
        t2 = threading.Thread(target=resolve_in_scope)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(results) == 2
        assert results[0] is not results[1], (
            "Concurrent scopes must produce different instances."
        )

    def test_outside_scope_falls_back_to_transient(self) -> None:
        """Scoped dependency outside a scope should fall back to Transient resolution."""
        container = StdLibContainer()
        container.scoped(IService, ConcreteService)

        # Outside any scope, the scoped registry is inactive → falls back to _resolve
        a = container.resolve(IService)
        b = container.resolve(IService)
        # Transient: new instance each time
        assert a is not b, "Without a scope, scoped dependency resolves as Transient."


class TestOpenScopeCount:
    """EPIC-007B: `open_scope_count()` — a count that only rises is a
    `with create_scope():` block that never exits."""

    def test_starts_at_zero(self) -> None:
        container = StdLibContainer()
        assert container.open_scope_count() == 0

    def test_rises_while_a_scope_is_entered_and_falls_back_on_exit(self) -> None:
        container = StdLibContainer()
        assert container.open_scope_count() == 0

        with container.create_scope():
            assert container.open_scope_count() == 1

        assert container.open_scope_count() == 0

    def test_nested_and_sequential_scopes_both_count_correctly(self) -> None:
        container = StdLibContainer()

        with container.create_scope():
            assert container.open_scope_count() == 1
            with container.create_scope():
                assert container.open_scope_count() == 2
            assert container.open_scope_count() == 1
        assert container.open_scope_count() == 0

        with container.create_scope():
            assert container.open_scope_count() == 1
        assert container.open_scope_count() == 0

    def test_a_scope_entered_and_never_exited_stays_counted(self) -> None:
        """The honest-leak-detector property: this is the signal
        open_scope_count() exists to surface, not a bug to self-correct."""
        container = StdLibContainer()
        scope = container.create_scope()
        scope.__enter__()

        assert container.open_scope_count() == 1
        # Deliberately no __exit__() -- simulates code that forgot to.
        assert container.open_scope_count() == 1

    def test_a_scope_constructed_but_never_entered_is_not_counted(self) -> None:
        """create_scope() alone must not count as "open" -- only entering the
        `with` block does. StdLibContainer's own internal `_scope_context`
        (used only for resolve() lookups) relies on exactly this distinction."""
        container = StdLibContainer()
        container.create_scope()  # constructed, never entered
        assert container.open_scope_count() == 0

    def test_the_interface_default_is_zero_so_a_foreign_container_still_works(
        self,
    ) -> None:
        from sagittarius_engine.interfaces.i_container import IContainer

        class ForeignContainer(IContainer):
            def bind(self, abstract, concrete):
                pass

            def singleton(self, abstract, instance_or_factory):
                pass

            def scoped(self, abstract, concrete):
                pass

            def resolve(self, abstract):
                raise NotImplementedError

            def create_scope(self):
                raise NotImplementedError

        assert ForeignContainer().open_scope_count() == 0
