"""
@brief Static guard that every component registered in the kit's `qmldir`
actually appears in the gallery — the enforcement mechanism behind
`ui-architecture.md` §6.2's "every kit component must be reachable from a
single runnable gallery".

@details
Without this the gallery decays exactly the way a hand-maintained catalogue
always does: a component is added, the gallery is not updated, and the one
artefact meant to answer "what does this kit offer, and what does it look
like?" quietly stops answering it. `EPIC-001C` shipped the gallery
requirement as prose; this makes it checkable.

Deliberately a *presence* check, not a quality one. It cannot tell whether a
component is demonstrated well — only that someone had to look at it when
they added it. That is the cheap 80%: the expensive failure is a component
nobody ever sees, not one whose demo is thin.

Reads `qmldir` rather than listing directories, on purpose: `qmldir` is the
kit's public type list. A `.qml` file that is not registered there is
internal (a sub-component of some other component) and has no business being
in the gallery; a directory that exists only as a placeholder (see the
`ActionCard`/`FormCard`/`StreamCard`/`TableCard` NOTES.md candidates) is
correctly ignored for the same reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: `qmldir` type lines look like `AppDataTable 1.0 AppDataTable/AppDataTable.qml`.
#: The leading `module …` line and any comment/blank line must not match.
_QMLDIR_TYPE_RE = re.compile(r"^\s*([A-Z]\w*)\s+\d+\.\d+\s+\S+\.qml\s*$")

#: Types exempt from needing a gallery entry, each for a structural reason
#: rather than convenience:
#:   BaseCard — abstract base, has no standalone appearance; it is shown
#:              through every card that derives from it.
DEFAULT_EXEMPT_TYPES: frozenset[str] = frozenset({"BaseCard"})


@dataclass(frozen=True)
class MissingFromGalleryFinding:
    """One registered kit type absent from the gallery."""

    type_name: str
    qmldir: Path
    gallery: Path


def registered_types(qmldir_path: Path) -> list[str]:
    """
    @brief Returns every type name declared in a `qmldir`, in file order.
    @details The `module <name>` header line is skipped by the pattern
    rather than by position, so a reordered or commented `qmldir` still
    parses correctly.
    """
    return [
        match.group(1)
        for line in qmldir_path.read_text(encoding="utf-8").splitlines()
        if (match := _QMLDIR_TYPE_RE.match(line)) is not None
    ]


def find_types_missing_from_gallery(
    qmldir_path: Path,
    gallery_path: Path,
    exempt_types: frozenset[str] = DEFAULT_EXEMPT_TYPES,
) -> list[MissingFromGalleryFinding]:
    """
    @brief Returns every `qmldir`-registered type that never appears as a
    declaration in the gallery.

    @param qmldir_path The kit's `qmldir`.
    @param gallery_path The gallery `.qml`.
    @param exempt_types Types that legitimately have no standalone gallery
    entry — see `DEFAULT_EXEMPT_TYPES`. Adding to this set is a design
    decision, not a shortcut for "I did not get around to it".
    @return Findings in `qmldir` declaration order.
    """
    gallery_source = gallery_path.read_text(encoding="utf-8")

    findings: list[MissingFromGalleryFinding] = []
    for type_name in registered_types(qmldir_path):
        if type_name in exempt_types:
            continue
        # Matches a real declaration (`AppModal {`), not a mention in a
        # comment or inside a longer identifier — `\b` on the left stops
        # `StatefulButton` from satisfying a search for `Button`.
        if re.search(rf"\b{re.escape(type_name)}\s*\{{", gallery_source):
            continue
        findings.append(
            MissingFromGalleryFinding(
                type_name=type_name, qmldir=qmldir_path, gallery=gallery_path
            )
        )

    return findings


def format_findings(findings: list[MissingFromGalleryFinding]) -> str:
    """Renders findings as a human-readable block for an assertion failure
    message — the missing type and where it was expected."""
    header = (
        f"{len(findings)} kit component(s) registered in qmldir but absent "
        "from the gallery:"
    )
    lines = [header]
    for finding in findings:
        lines.append(
            f"  {finding.type_name} — declared in {finding.qmldir}, "
            f"never instantiated in {finding.gallery}"
        )
    return "\n".join(lines)
