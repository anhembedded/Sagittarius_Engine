"""Every module under `sagittarius_engine/` must import cleanly.

Why this exists: on 2026-08-23 an audit found
`sagittarius_engine/infrastructure/persistence/__init__.py` re-exporting
`IThreadManager` from a file that commit `85e5576` had moved to
`interfaces/`. The package had raised `ModuleNotFoundError` on import ever
since — for months — and the full test suite stayed green the whole time,
because no test and no shipped code ever imported it.

That is the general shape of the bug: a refactor moves a symbol, leaves a
re-export behind, and nothing notices until a consumer hits it and gets an
error naming a file that hasn't existed for months. A test that merely
*imports everything* catches the entire class, costs milliseconds, and needs
no maintenance.

It also catches annotation-resolution breakage that varies by Python
version, which is how the sibling `ITaskHandle` bug (an annotation naming a
type the module never imported) stayed invisible: under Python 3.14's
deferred annotations it was harmless at import, but on any earlier version
it was a hard `NameError` at class-definition time. Running this test across
the supported Python matrix is what makes that visible.
"""

from __future__ import annotations

import importlib
import pkgutil

import pytest

import sagittarius_engine


def _all_module_names() -> list[str]:
    return sorted(
        m.name
        for m in pkgutil.walk_packages(
            sagittarius_engine.__path__, prefix="sagittarius_engine."
        )
    )


@pytest.mark.parametrize("module_name", _all_module_names())
def test_module_imports_cleanly(module_name: str) -> None:
    try:
        importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001 — reporting the failure *is* the test
        pytest.fail(
            f"`import {module_name}` raised {type(exc).__name__}: {exc}\n\n"
            "A module in the shipped package cannot be imported. Most often this "
            "is a re-export left behind by a refactor that moved the real symbol "
            "elsewhere — fix the re-export or delete the dead module."
        )


#: Interface members whose annotations deliberately do not resolve at runtime.
#: Each is a `TYPE_CHECKING`-guarded forward reference used to break a genuine
#: circular import — the correct idiom, not a defect. They are listed rather
#: than skipped wholesale so that a *new* unresolvable annotation still fails.
#:
#: The cost is real and worth stating: `typing.get_type_hints()` raises on
#: these. `StdLibContainer` handles that correctly (falls back to the raw
#: annotation, then raises `DependencyResolutionError` if it still can't
#: resolve). `PydanticValidationMiddleware` does not — it swallows the same
#: failure and silently skips validation. See TASK-026.
KNOWN_FORWARD_REF_MEMBERS: frozenset[str] = frozenset(
    {
        "IModule.register",  # -> "App"
        "IModule.boot",  # -> "App"
        "IModule.shutdown",  # -> "App"
        "ITaskManager.spawn",  # -> "CancellationToken"
    }
)


def test_annotations_resolve_on_public_interfaces() -> None:
    """Catches the `ITaskHandle` shape: a type used in an annotation that its
    own module never imports, and that no `TYPE_CHECKING` block declares.

    Python 3.14 defers annotation evaluation, so such a module imports fine and
    the suite stays green. The breakage appears only when something actually
    resolves the hints — `typing.get_type_hints`, the DI container reading
    constructor types, pydantic. This test forces that resolution.

    Scoped to `sagittarius_engine.interfaces`: the surface consumers type
    against. Broad enough to guard the public contract, narrow enough not to
    trip over third-party Qt annotations.
    """
    import typing

    from sagittarius_engine import interfaces

    failures: list[str] = []
    for name in getattr(interfaces, "__all__", []):
        obj = getattr(interfaces, name, None)
        if not isinstance(obj, type):
            continue
        for attr_name, attr in vars(obj).items():
            if not callable(attr) or not hasattr(attr, "__annotations__"):
                continue
            if f"{name}.{attr_name}" in KNOWN_FORWARD_REF_MEMBERS:
                continue
            try:
                typing.get_type_hints(attr)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{name}.{attr_name}: {type(exc).__name__}: {exc}")

    assert not failures, (
        "Annotations on public interface members do not resolve:\n  "
        + "\n  ".join(failures)
        + "\n\nA name used in an annotation is not importable in its module's "
        "namespace. Under Python 3.14 this stays silent at import time; anything "
        "reading type hints still breaks. Either import the name (add a "
        "`TYPE_CHECKING` block if it would be circular) or, if the forward "
        "reference is deliberate, add it to KNOWN_FORWARD_REF_MEMBERS with the "
        "reason."
    )
