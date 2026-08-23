"""Staleness guard for `.agents/` (EPIC-002D): a backtick-quoted class name,
module path, or file/dir path in a rule/context doc that no longer resolves
against the real tree is exactly the failure mode that let `AppRunner` (a
phantom class) and `extensions/sqlalchemy` (a renamed package) sit wrong in
`.agents/context/` for three weeks, undetected, until EPIC-002's audit.

Scope and honesty about its limits: this catches *structural* staleness — a
name or path that used to resolve and no longer does. It does NOT catch pure
prose errors with no checkable shape (e.g. the wrong repository name once
written as `Sagittarius_ForkBoy` — not a class, not a path, nothing to
resolve against). That class of error still needs a human/AI reader, same as
before. False positives here are an accepted, bounded cost (an explicit
ignore-list); an unchecked doc is not.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / ".agents"

#: Backtick-quoted tokens that look like a path/class/module but are not —
#: generic placeholders used in examples, or third-party/stdlib names this
#: check deliberately doesn't resolve against (see module docstring: only
#: `sagittarius_engine`/`examples` dotted paths are checked). Extend this set
#: rather than weakening the checks below.
IGNORE_TOKENS: frozenset[str] = frozenset(
    {
        "ClassName",
        "MyClass",
        "ModuleName",
        "HandlerClass",
        "CommandClass",
        "TContext",
        "TInput",
        "TOutput",
        "EventName",
        # IExtension lifecycle method names and descriptor attributes, quoted
        # bare in prose about the interface shape (context/project.md,
        # context/troubleshooting.md) — not package/class names to resolve.
        "register",
        "boot",
        "shutdown",
        "initialize",
        "start",
        "stop",
        "dispose",
        "name",
        "priority",
        "dependencies",
        "optional_dependencies",
        # Third-party/stdlib names referenced by their own name, not a
        # repo-local package this checker resolves against.
        "asyncio",
        "pytest",
        "qtbot",
        "QApplication",
        "QtWidgets",
        "argparse",
        "getattr",
        "dataclasses",
        "TypeError",  # Python builtin, quoted in lint.md's UP045 corruption story.
        "Optional",
        "Union",
        "TypeVar",
        "Generics",
        # This repo's own name, quoted for emphasis — not a class.
        "Sagittarius_Engine",
        # Informal shorthand for the messaging interface, used throughout
        # context/ prose — the real names are IEventBus/MemoryEventBus/etc.
        "EventBus",
        # IExtension's async lifecycle hooks (interfaces/i_extension.py) —
        # real methods, not classes or packages.
        "boot_async",
        "shutdown_async",
        # git branch names in build.md, not paths.
        "main",
        "develop",
        # A specific example config key name in configuration.md's prose,
        # not a package.
        "db_url",
        # CLI subcommand names for the sample app's StudentManagementExtension
        # CLI, quoted bare in examples.md.
        "enroll",
        "update",
        "remove",
        "list",
        "search",
        "report",
        # pytest.ini/pyproject.toml config key, not a path.
        "testpaths",
        # Deliberately-fictional predecessor test directories, cited in
        # testing.md for contrast with the real layout — never meant to
        # resolve.
        "tests/sanity/",
        "tests/unit/",
        "tests/integration/",
        # Python builtins, quoted in api.md's "not a bool/True" correction.
        "bool",
        "True",
        # Names a doc explicitly quotes *because* they're wrong — each is
        # part of a "corrected 2026-08-23, previous version said `X`"
        # sentence documenting a real bug this same audit found and fixed.
        # Keeping them quoted (rather than deleting the sentence) is the
        # traceability doc-code-sync.md asks for; flagging them here would
        # be checking a claim the doc itself already says is false.
        "IConnector",
        "ReceiveAuditUseCase",
        "StudentAddedEvent",
        "TerminalMenu",
        # Same category, but a *path*: build.md cites this one precisely
        # because CI still runs it and it no longer exists (moved to
        # tests/runtime/ in 843137a). The dangling-ness is the documented
        # fact — see TASK-020.
        "tests/benchmark_runtime.py",
        # Deleted-feature paths (TASK-024), quoted in project.md's own
        # "there used to be a row here" note explaining the deletion —
        # correctly dangling, same pattern as IConnector/TerminalMenu above.
        "sagittarius_engine.sdk",
        "tools/scaffold.py",
        # A parameter name of App.boot(), quoted in api.md's correction of
        # its documented type — a method argument, not a class or package.
        "auto_discover",
        # A CI job name in build.md and a TOML key in lint.md — neither is a
        # package or a directory.
        "benchmark",
        "select",
    }
)

_BACKTICK_SPAN = re.compile(r"`([^`\n]+)`")
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_BARE_CLASS_NAME = re.compile(r"^I?[A-Z][A-Za-z0-9_]*$")
_BARE_SNAKE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")

#: Real, exact directory names under the searched trees — collected once so
#: the "presented as a package/extension name" check (below) is a set
#: lookup, not a `find` subprocess per token.
_SEARCH_ROOTS = ("sagittarius_engine", "examples", "tools")


def _real_directory_names() -> frozenset[str]:
    names: set[str] = set()
    for root in _SEARCH_ROOTS:
        base = REPO_ROOT / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_dir() and "__pycache__" not in path.parts:
                names.add(path.name)
    return frozenset(names)


_REAL_DIRECTORY_NAMES = _real_directory_names()

#: Package-name tokens in requirements*.txt (e.g. `sqlalchemy>=2.0`), lowercased
#: with the version specifier stripped. `dependencies.md` legitimately lists
#: these by bare name — they're real, just not a *local directory*, which is
#: all `_REAL_DIRECTORY_NAMES` can otherwise verify.
_REQUIREMENTS_SPEC = re.compile(r"^[A-Za-z0-9_.-]+")


def _declared_dependency_names() -> frozenset[str]:
    names: set[str] = set()
    for fname in ("requirements.txt", "requirements-dev.txt", "requirements-docs.txt"):
        path = REPO_ROOT / fname
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = _REQUIREMENTS_SPEC.match(line)
            if match:
                names.add(match.group(0).lower())
    return frozenset(names)


_DECLARED_DEPENDENCY_NAMES = _declared_dependency_names()


def _iter_doc_files() -> list[Path]:
    return sorted(AGENTS_DIR.rglob("*.md"))


def _looks_like_path(token: str) -> bool:
    # A bare "*.md" filename (no "/") is a same-repo doc link too — e.g.
    # "examples.md" linking a sibling file within `.agents/context/`.
    return "/" in token or token.endswith(".md")


#: Bases tried, in order, for a slash-containing (or bare ".md") token.
#: Covers: repo-root-relative paths, the package/examples/tools/Tasks trees,
#: the one real sample app's own doc tree (prose like "the sample app's
#: `docs/module_registration.md`" doesn't repeat the `examples/
#: student_management/` prefix), `.agents/` itself (rule cross-links like
#: `rules/architecture.md`), and the referencing doc's own directory
#: (sibling links like `examples.md` from another file in `context/`).
def _path_bases(doc: Path) -> tuple[Path, ...]:
    return (
        REPO_ROOT,
        REPO_ROOT / "sagittarius_engine",
        REPO_ROOT / "examples",
        REPO_ROOT / "tools",
        REPO_ROOT / "Tasks",
        REPO_ROOT / "examples" / "student_management",
        REPO_ROOT / "examples" / "student_management" / "docs",
        AGENTS_DIR,
        AGENTS_DIR / "rules",
        AGENTS_DIR / "skills",
        doc.parent,
    )


#: Strips a trailing line-number citation: `foo.py:17` and `foo.py:17,31` alike.
_TRAILING_LINE_NUMBER = re.compile(r":\d+(?:[,-]\d+)*$")


def _path_resolves(token: str, doc: Path) -> bool:
    candidate = token.rstrip(".,;:()")
    candidate = _TRAILING_LINE_NUMBER.sub("", candidate)
    if any((base / candidate).exists() for base in _path_bases(doc)):
        return True
    # A bare filename (no directory component) may live in a subdirectory
    # this function's fixed base list doesn't enumerate — e.g. an epic's own
    # `AUDIT_REPORT.md` under `Tasks/epics/EPIC-XXX_.../`. Search the few
    # trees where doc-referenced files actually live, rather than guessing
    # every nesting level up front.
    if "/" not in candidate:
        for root in (AGENTS_DIR, REPO_ROOT / "Tasks", REPO_ROOT / "examples"):
            if root.exists() and next(root.rglob(candidate), None) is not None:
                return True
    return False


def _looks_like_dotted_module(token: str) -> bool:
    if "." not in token or token.endswith(".md"):
        return False
    parts = token.split(".")
    if not (parts[0] == "sagittarius_engine" or parts[0] == "examples"):
        return False
    return all(_IDENTIFIER.match(p) for p in parts)


def _dotted_module_resolves(token: str) -> bool:
    rel = Path(*token.split("."))
    return (REPO_ROOT / rel.with_suffix(".py")).exists() or (
        REPO_ROOT / rel / "__init__.py"
    ).exists()


def _looks_like_bare_class_name(token: str) -> bool:
    # Require a lowercase letter somewhere, so SCREAMING_SNAKE_CASE constants
    # (DEFAULT_EXEMPT_TYPES, SANCTIONED_DEEP_IMPORTS — real, just not classes)
    # don't match true PascalCase class names.
    return (
        bool(_BARE_CLASS_NAME.match(token))
        and len(token) > 2
        and any(c.islower() for c in token)
    )


def _looks_like_bare_package_name(token: str) -> bool:
    """A lowercase snake_case word, presented alone in backticks — the shape
    of 'sqlalchemy' in the old repository.md's "e.g. `audit`, `sqlalchemy`"
    (two separate bare tokens, one real, one not). Length >= 4 to keep
    common short prose words (a stricter length floor than the class-name
    check needs, since this category is inherently noisier)."""
    return bool(_BARE_SNAKE_NAME.match(token)) and len(token) >= 4


def _package_name_resolves(token: str) -> bool:
    return token in _REAL_DIRECTORY_NAMES or token.lower() in _DECLARED_DEPENDENCY_NAMES


def _class_name_resolves(token: str) -> bool:
    # PascalCase-shaped third-party package names (`PySide6`) aren't classes
    # but are still real, verifiable names — check declared deps first.
    if token.lower() in _DECLARED_DEPENDENCY_NAMES:
        return True
    # A real grep, not a cached index — this check's entire value is staying
    # honest about the tree as it exists right now.
    result = subprocess.run(
        [
            "grep",
            "-rlE",
            rf"class {re.escape(token)}\b",
            "sagittarius_engine",
            "examples",
            "tools",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,  # grep exits 1 on "no match", which is a valid answer here
    )
    return bool(result.stdout.strip())


_GIT_HASH = re.compile(r"^[0-9a-f]{7,40}$")


def _looks_like_git_hash(token: str) -> bool:
    return bool(_GIT_HASH.match(token))


#: Ordered (shape-test, resolution-test) pairs. The **first** shape that
#: matches decides how a token is checked — order matters: a slash-bearing
#: token is a path and is never re-tried as a bare class name. Both callables
#: take `(token, doc)` so the table stays uniform, even where `doc` is unused.
_CLASSIFIERS: tuple[
    tuple[Callable[[str, Path], bool], Callable[[str, Path], bool]], ...
] = (
    (lambda t, _d: _looks_like_path(t), _path_resolves),
    (
        lambda t, _d: _looks_like_dotted_module(t),
        lambda t, _d: _dotted_module_resolves(t),
    ),
    (
        lambda t, _d: _looks_like_bare_class_name(t),
        lambda t, _d: _class_name_resolves(t),
    ),
    (
        lambda t, _d: _looks_like_bare_package_name(t),
        lambda t, _d: _package_name_resolves(t),
    ),
)


#: Token shapes that are never a structural reference to anything in this
#: repo: a URL, a multi-word shell command, or an abbreviated git hash.
def _is_uncheckable(token: str) -> bool:
    return "://" in token or " " in token or _looks_like_git_hash(token)


def _resolution_of(token: str, doc: Path) -> bool | None:
    """`True` if the token resolves, `False` if it's a dangling reference,
    `None` if no classifier claims it (prose, not a structural claim)."""
    if not token or token in IGNORE_TOKENS or _is_uncheckable(token):
        return None
    for looks_like, resolves in _CLASSIFIERS:
        if looks_like(token, doc):
            return resolves(token, doc)
    return None


def _find_unresolved_tokens() -> list[tuple[Path, str]]:
    """Structural resolution is only checked within `.agents/context/` — the
    docs whose entire job is describing this repo's real tree (and where the
    original `AppRunner`/`extensions/sqlalchemy` bugs actually lived).

    `.agents/rules/`, `.agents/skills/`, and `.agents/workflows/` are
    deliberately out of scope: they illustrate generic Clean Architecture
    shapes and reference a *different* repo (Sagittarius_Elite_Warrior, e.g.
    `src/domain/`, `src/main.py`) by design, plus QML/Qt vocabulary
    (`Rectangle`, `busy`, `DEFAULT_EXEMPT_TYPES`) that was never meant to
    resolve against this tree. Checking them produces noise, not signal —
    see `.agents/context/testing.md` for this same trade-off documented for
    future readers of this file.
    """
    unresolved: list[tuple[Path, str]] = []
    for doc in _iter_doc_files():
        if doc.relative_to(AGENTS_DIR).parts[0] != "context":
            continue
        text = doc.read_text(encoding="utf-8")
        for match in _BACKTICK_SPAN.finditer(text):
            # Markdown link *display text* — `[`AUDIT_REPORT.md`](../real/path)`
            # — isn't a structural claim; the href carries the real path and
            # a wrong href is a broken link, a different (unchecked) problem.
            before, after = text[: match.start()], text[match.end() :]
            if before.endswith("[") and after.startswith("]("):
                continue
            token = match.group(1).strip()
            if _resolution_of(token, doc) is False:
                unresolved.append((doc, token))
    return unresolved


def test_agents_docs_have_no_unresolved_structural_references():
    unresolved = _find_unresolved_tokens()
    if unresolved:
        lines = [
            f"  {doc.relative_to(REPO_ROOT)}: `{token}`" for doc, token in unresolved
        ]
        pytest.fail(
            "Backtick-quoted class/module/path references that don't resolve "
            "against the real tree:\n" + "\n".join(lines) + "\n\n"
            "If this is a genuine false positive (a placeholder, a third-party "
            "name), add it to IGNORE_TOKENS in this test with a one-line reason "
            "— don't just delete the doc claim."
        )


def test_staleness_check_actually_catches_the_original_bug():
    """Proves this mechanism isn't theater: run it against the exact old
    repository.md content (git commit 0bd461b, since deleted/rewritten) and
    confirm it still flags a real bug that sat undetected in it for three
    weeks: `Sagittarius_ForkBoy` (the wrong repository name), correctly
    caught because it matches the bare-class-name shape and resolves to
    nothing — as a real class, or as a declared dependency.

    What this test does NOT (and, as of the 2026-08-23 dependency-name-aware
    rewrite of `_package_name_resolves`, no longer can) assert: that
    `sqlalchemy` gets flagged. The old text listed `extensions/` as containing
    "e.g. `audit`, `sqlalchemy`" — implying a local `extensions/sqlalchemy/`
    subpackage that never existed. `sqlalchemy` *is* real, though — a real
    pip dependency (`requirements.txt`) — so a checker that (correctly, and
    necessary to stop flooding `dependencies.md` with false positives, see
    `_DECLARED_DEPENDENCY_NAMES`) treats declared-dependency names as
    resolved can no longer distinguish "real pip package, wrongly implied to
    be a local subpackage" from "real pip package, correctly named as a
    dependency". That specific class of contextual error is out of reach for
    a word-existence check and falls under the "pure prose errors with no
    checkable shape" limitation already stated in this module's docstring —
    an honest trade-off, not a regression to paper over."""
    old_doc_path = AGENTS_DIR / "context" / "repository.md"
    old_content = subprocess.run(
        ["git", "show", "0bd461b:.agents/context/repository.md"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    # Reuse the exact same classifier the live check uses — a bespoke copy
    # here could pass while the real one is broken, which is the one failure
    # mode this test exists to rule out.
    unresolved_tokens = {
        match.group(1).strip()
        for match in _BACKTICK_SPAN.finditer(old_content)
        if _resolution_of(match.group(1).strip(), old_doc_path) is False
    }

    assert "Sagittarius_ForkBoy" in unresolved_tokens, (
        "the staleness check should have flagged 'Sagittarius_ForkBoy' (the "
        f"wrong repo name) as an unresolvable bare class-shaped token; "
        f"actual unresolved set: {unresolved_tokens}"
    )
    assert "extensions/" not in unresolved_tokens, (
        "'extensions/' is a real directory and must NOT be flagged — a "
        "false negative here would mean the path check is broken, not lenient"
    )
