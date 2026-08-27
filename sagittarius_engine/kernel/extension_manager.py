from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_engine_context import IEngineContext
    from sagittarius_engine.kernel.i_kernel_context import IKernelContext
from sagittarius_engine.exceptions import (
    ExtensionCircularDependencyError,
    ExtensionDependencyError,
)
from sagittarius_engine.interfaces.i_extension import ExtensionDescriptor, IExtension
from sagittarius_engine.interfaces.i_module import IModule
from sagittarius_engine.interfaces.i_trace_recorder import Lane
from sagittarius_engine.kernel.events import (
    ExtensionDisposed,
    ExtensionInitializing,
    ExtensionStarted,
    ExtensionStopped,
)


class ModuleExtensionAdapter(IExtension[Any]):
    """
    @brief Adapts a legacy IModule to the IExtension interface.
    """

    def __init__(self, legacy_module: IModule):
        self.legacy_module = legacy_module
        deps = getattr(legacy_module, "dependencies", [])
        opt_deps = getattr(legacy_module, "optional_dependencies", [])
        prio = getattr(legacy_module, "priority", 0)
        enabled = getattr(legacy_module, "enabled", True)
        self._descriptor = ExtensionDescriptor(
            name=legacy_module.__class__.__name__,
            dependencies=deps if isinstance(deps, list) else [],
            optional_dependencies=opt_deps if isinstance(opt_deps, list) else [],
            priority=prio if isinstance(prio, int) else 0,
            enabled=enabled if isinstance(enabled, bool) else True,
        )

    @property
    def descriptor(self) -> ExtensionDescriptor:
        return self._descriptor

    def register(self, context: "IEngineContext") -> None:
        kernel_ctx = cast("IKernelContext", context)
        self.legacy_module.register(kernel_ctx.app)

    def boot(self, context: "IEngineContext") -> None:
        kernel_ctx = cast("IKernelContext", context)
        self.legacy_module.boot(kernel_ctx.app)

    def shutdown(self, context: "IEngineContext") -> None:
        kernel_ctx = cast("IKernelContext", context)
        # Check for backwards compatibility with modules written before IModule had shutdown
        if hasattr(self.legacy_module, "shutdown"):
            self.legacy_module.shutdown(kernel_ctx.app)

    def __getattr__(self, name: str) -> object:
        return getattr(self.legacy_module, name)


def create_module_extension_adapter(legacy_module: IModule) -> ModuleExtensionAdapter:
    """
    @brief Dynamically creates an adapter class that retains the original class name.
    """
    cls_name = legacy_module.__class__.__name__
    # Dynamically create subclass of ModuleExtensionAdapter named cls_name
    dynamic_cls = type(cls_name, (ModuleExtensionAdapter,), {})
    return dynamic_cls(legacy_module)


class ExtensionManager:
    """
    @brief Orchestrates the extension lifecycle with dependency awareness.
    """

    def __init__(self, context: "IKernelContext") -> None:
        self.context = context
        self.registered_extensions: list[IExtension[Any]] = []
        self.sorted_extensions: list[IExtension[Any]] = []
        self.initialized_extensions: list[IExtension[Any]] = []

    def register(self, extension_or_module: IExtension[Any] | IModule) -> None:
        """
        @brief Registers an IExtension or adapts a legacy IModule.

        @param extension_or_module Must be an instance of IExtension or IModule.
            Passing any other type will raise TypeError immediately.
        @raises TypeError If the object does not implement IExtension or IModule.
        """
        if isinstance(extension_or_module, IExtension):
            ext = extension_or_module
        elif isinstance(extension_or_module, IModule):
            ext = create_module_extension_adapter(extension_or_module)
        else:
            raise TypeError(
                f"Cannot register '{type(extension_or_module).__name__}': "
                "object must implement IExtension or IModule. "
                "Wrap duck-typed objects in a ModuleExtensionAdapter manually."
            )

        self.registered_extensions.append(ext)

        # Try to initialize any available extensions immediately to support instant resolution
        try:
            self._try_initialize_available()
        except (RuntimeError, ValueError, TypeError, ImportError) as e:
            self._rollback()
            raise e

    def _emit(self, event_name: str, event_data: object) -> None:
        try:
            self.context.event_bus.emit(event_name, event_data)
        except (RuntimeError, ValueError) as e:
            self.context.logger.error(f"Failed to emit event: {e}")

    def _try_initialize_available(self) -> None:
        """
        @brief Scans and initializes deferred extensions whose dependencies have been registered and initialized.
        """
        initialized_names = {ext.descriptor.name for ext in self.initialized_extensions}
        enabled_exts = [
            ext
            for ext in self.registered_extensions
            if ext.descriptor.enabled and ext.descriptor.name not in initialized_names
        ]

        # ⚡ Bolt: Sort once outside the loop to avoid redundant O(N log N) overhead
        # Sort by priority descending to initialize higher priority items first
        pending_exts = sorted(
            enabled_exts, key=lambda e: e.descriptor.priority, reverse=True
        )

        while True:
            initialized_any = False
            next_pending = []

            for ext in pending_exts:
                name = ext.descriptor.name

                # We no longer need to check if name in initialized_names
                # because pending_exts only contains un-initialized extensions.

                # Check if all required dependencies are initialized
                deps_satisfied = True
                for dep in ext.descriptor.dependencies:
                    if dep not in initialized_names:
                        deps_satisfied = False
                        break

                # Check if registered or pending optional dependencies are initialized
                if deps_satisfied:
                    for dep in ext.descriptor.optional_dependencies:
                        if dep not in initialized_names:
                            deps_satisfied = False
                            break

                if deps_satisfied:
                    self.context.logger.info(f"Initializing extension '{name}'...")
                    self._emit(
                        ExtensionInitializing.event_name, ExtensionInitializing(name)
                    )
                    ext.initialize(self.context)
                    self.initialized_extensions.append(ext)
                    initialized_names.add(name)
                    initialized_any = True
                else:
                    next_pending.append(ext)

            if not initialized_any:
                break

            pending_exts = next_pending

    def _build_and_sort(self) -> list[IExtension[Any]]:
        """
        @brief Topologically sorts registered and enabled extensions based on dependencies.
        """
        enabled_exts = [
            ext for ext in self.registered_extensions if ext.descriptor.enabled
        ]
        ext_by_name = {ext.descriptor.name: ext for ext in enabled_exts}

        visiting = set()
        visited = set()
        result = []

        def dfs(name: str):
            if name in visiting:
                raise ExtensionCircularDependencyError(
                    f"Circular dependency detected involving extension '{name}'"
                )
            if name in visited:
                return

            ext = ext_by_name.get(name)
            if not ext:
                return

            visiting.add(name)

            # Validate and traverse required dependencies
            for dep in ext.descriptor.dependencies:
                if dep not in ext_by_name:
                    raise ExtensionDependencyError(
                        f"Extension '{name}' requires missing dependency '{dep}'"
                    )
                dfs(dep)

            # Traverse optional dependencies
            for dep in ext.descriptor.optional_dependencies:
                if dep in ext_by_name:
                    dfs(dep)

            visiting.remove(name)
            visited.add(name)
            result.append(ext)

        # Sort by priority descending to process higher priority items first
        sorted_by_priority = sorted(
            enabled_exts, key=lambda e: e.descriptor.priority, reverse=True
        )
        for ext in sorted_by_priority:
            dfs(ext.descriptor.name)

        return result

    def initialize_and_start(self) -> None:
        """
        @brief Resolves dependencies, initializes remaining extensions, and boots them.
        @details Performs safe rollback/disposal on initialization failure.
        """
        self.sorted_extensions = self._build_and_sort()

        # 1. Initialize stage for any remaining deferred extensions
        for ext in self.sorted_extensions:
            if ext not in self.initialized_extensions:
                name = ext.descriptor.name
                self.context.logger.info(f"Initializing extension '{name}'...")
                self._emit(
                    ExtensionInitializing.event_name, ExtensionInitializing(name)
                )
                # EPIC-005B. Per-extension spans are what turn "why does
                # startup take four seconds?" into a bar chart. Guarded rather
                # than routed through a no-op object: EPIC-005A measured the
                # guard at ~3 ns over an empty call site, the object at ~27 ns.
                recorder = self.context.recorder
                started = (
                    recorder.span_begin(Lane.EXTENSION, name, cat="initialize")
                    if recorder is not None
                    else 0
                )
                try:
                    ext.initialize(self.context)
                    self.initialized_extensions.append(ext)
                except (RuntimeError, ValueError, TypeError, ImportError) as e:
                    self.context.logger.error(
                        f"Failed to initialize extension '{name}': {e}. Rolling back..."
                    )
                    self._rollback()
                    raise e
                finally:
                    # In `finally`, so an extension that failed to initialise
                    # still appears in the trace. A span that vanished when its
                    # body raised would hide the slow-then-failing extension
                    # someone opened a tracer to find.
                    if recorder is not None:
                        recorder.span_end(
                            Lane.EXTENSION, name, started, cat="initialize"
                        )

        # 2. Start stage
        for ext in self.sorted_extensions:
            name = ext.descriptor.name
            self.context.logger.info(f"Starting extension '{name}'...")
            recorder = self.context.recorder
            if recorder is None:
                ext.start(self.context)
            else:
                started = recorder.span_begin(Lane.EXTENSION, name, cat="start")
                try:
                    ext.start(self.context)
                finally:
                    recorder.span_end(Lane.EXTENSION, name, started, cat="start")
            self._emit(ExtensionStarted.event_name, ExtensionStarted(name))
            # 3. Schedule async boot hook if AsyncRuntime is available
            self._schedule_boot_async(ext)

    def _schedule_boot_async(self, ext: IExtension[Any]) -> None:
        """
        @brief Schedules boot_async() on the AsyncRuntime if available.
        @details No-op if the extension's boot_async is the base class no-op.
        """
        try:
            async_runtime = getattr(self.context, "async_runtime", None)
            if (
                async_runtime is None
                or not async_runtime.loop
                or not async_runtime.loop.is_running()
            ):
                return
            # Only schedule if the extension actually overrides boot_async
            if type(ext).boot_async is IExtension.boot_async:
                return
            async_runtime.run_coroutine(ext.boot_async(self.context))
        except (RuntimeError, ValueError, TypeError) as e:
            self.context.logger.warning(
                f"[AsyncLifecycle] Could not schedule boot_async for '{ext.descriptor.name}': {e}"
            )

    def _schedule_shutdown_async(self, ext: IExtension[Any]) -> None:
        """
        @brief Schedules shutdown_async() on the AsyncRuntime and blocks until complete.
        """
        try:
            async_runtime = getattr(self.context, "async_runtime", None)
            if (
                async_runtime is None
                or not async_runtime.loop
                or not async_runtime.loop.is_running()
            ):
                return
            if type(ext).shutdown_async is IExtension.shutdown_async:
                return
            future = async_runtime.run_coroutine(ext.shutdown_async(self.context))
            future.result(timeout=10.0)
        except (RuntimeError, ValueError, TimeoutError) as e:
            self.context.logger.warning(
                f"[AsyncLifecycle] Could not run shutdown_async for '{ext.descriptor.name}': {e}"
            )

    def _rollback(self) -> None:
        """
        @brief Safe cleanup of initialized extensions in reverse order on failure.
        """
        for ext in reversed(self.initialized_extensions):
            name = ext.descriptor.name
            self.context.logger.info(f"Disposing extension '{name}' due to rollback...")
            try:
                ext.dispose(self.context)
                self._emit(ExtensionDisposed.event_name, ExtensionDisposed(name))
            except (RuntimeError, ValueError, TypeError) as e:
                self.context.logger.error(
                    f"Error during rollback disposal of '{name}': {e}"
                )
        # Clear initialized list since they are now rolled back
        self.initialized_extensions.clear()

    def stop_and_dispose(self) -> None:
        """
        @brief Stops and disposes extensions in reverse dependency order.
        """
        for ext in reversed(self.sorted_extensions):
            name = ext.descriptor.name
            # Run async shutdown before sync shutdown
            self._schedule_shutdown_async(ext)
            self.context.logger.info(f"Stopping extension '{name}'...")
            try:
                ext.stop(self.context)
                self._emit(ExtensionStopped.event_name, ExtensionStopped(name))
            except (RuntimeError, ValueError, TypeError) as e:
                self.context.logger.error(f"Error stopping extension '{name}': {e}")

            self.context.logger.info(f"Disposing extension '{name}'...")
            try:
                ext.dispose(self.context)
                self._emit(ExtensionDisposed.event_name, ExtensionDisposed(name))
            except (RuntimeError, ValueError, TypeError) as e:
                self.context.logger.error(f"Error disposing extension '{name}': {e}")

        self.sorted_extensions.clear()
        self.initialized_extensions.clear()
