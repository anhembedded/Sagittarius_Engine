from sagittarius_engine.interfaces.i_extension import ExtensionDescriptor, IExtension
from sagittarius_engine.kernel.app import App
from sagittarius_engine.kernel.context import EngineContext

# `BaseRepository` and `ICommand`/`IQuery` were removed from this re-export
# list 2026-08-23 (TASK-031). The original diagnosis was that only
# `BaseRepository` (extensions.persistence) caused unconditional coupling to
# an optional extension; that was incomplete, caught by this file's own
# regression test failing after only `BaseRepository` was dropped. The real
# cause was structural: `sagittarius_engine.extensions.__init__` *was* a
# barrel that eagerly imported every extension's public symbols (including
# persistence's `ISession`, via `health.health_check_query`), and Python
# always executes a parent package's `__init__.py` before any of its
# submodules — so importing `extensions.cqrs` for `ICommand`/`IQuery` alone
# was enough to trigger the whole barrel regardless of which name was asked
# for. There was no partial import possible through that package structure
# at the time; the only way to decouple the root from `extensions.persistence`
# was to stop importing anything from `sagittarius_engine.extensions.*` here.
# Verified zero usage of any of the three names anywhere in this repo
# (source, tests, examples) via this top-level path — every real usage
# already imports from `sagittarius_engine.extensions.cqrs` /
# `sagittarius_engine.extensions.persistence` directly, both unchanged.
# TASK-034 later made the barrel itself lazy (PEP 562 `__getattr__`), so a
# deep import of any single extension no longer pulls in its siblings
# either — this file's own workaround stays in place regardless, since
# nothing depends on re-exporting these three names from the root.

__all__ = [
    "App",
    "EngineContext",
    "IExtension",
    "ExtensionDescriptor",
]
