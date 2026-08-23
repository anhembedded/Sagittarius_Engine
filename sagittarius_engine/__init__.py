from sagittarius_engine.interfaces.i_extension import ExtensionDescriptor, IExtension
from sagittarius_engine.kernel.app import App
from sagittarius_engine.kernel.context import EngineContext

# `BaseRepository` and `ICommand`/`IQuery` were removed from this re-export
# list 2026-08-23 (TASK-031). The original diagnosis was that only
# `BaseRepository` (extensions.persistence) caused unconditional coupling to
# an optional extension; that was incomplete, caught by this file's own
# regression test failing after only `BaseRepository` was dropped. The real
# cause is structural: `sagittarius_engine.extensions.__init__` is a barrel
# that eagerly imports every extension's public symbols (including
# persistence's `ISession`, via `health.health_check_query`), and Python
# always executes a parent package's `__init__.py` before any of its
# submodules — so importing `extensions.cqrs` for `ICommand`/`IQuery` alone
# was enough to trigger the whole barrel regardless of which name was asked
# for. There is no partial import possible through that package structure;
# the only way to decouple the root from `extensions.persistence` was to stop
# importing anything from `sagittarius_engine.extensions.*` here at all.
# Verified zero usage of any of the three names anywhere in this repo
# (source, tests, examples) via this top-level path — every real usage
# already imports from `sagittarius_engine.extensions.cqrs` /
# `sagittarius_engine.extensions.persistence` directly, both unchanged.
# See TASK-034 for the barrel's own eager-import design, which is the
# larger, separate architecture question this finding surfaced.

__all__ = [
    "App",
    "EngineContext",
    "IExtension",
    "ExtensionDescriptor",
]
