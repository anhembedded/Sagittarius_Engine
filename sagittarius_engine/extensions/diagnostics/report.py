"""The result type of a wiring inspection.

A report carries *problems*, not a data dump. The wiring graph itself is
already readable through `IEventBus.subscriptions()` and
`IContainer.registrations()`; repeating it here would bury the two or three
lines that need acting on.
"""

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["error", "warning", "info"]

#: Worst first. Used for ordering output, so the line that stops a boot is not
#: below forty advisory ones.
SEVERITY_ORDER: tuple[Severity, ...] = ("error", "warning", "info")


@dataclass(frozen=True)
class Finding:
    """
    @brief One thing wrong, or worth knowing, about how an application is wired.

    @param check The check that produced it (`"A2"`, `"C2"`, …), so a finding
        can be traced back to `EPIC-006` §3 without guessing.
    @param severity `"error"` means it is a defect: something will not work, or
        already silently does not. `"warning"` means it is probably wrong but
        legitimately intentional in some applications. `"info"` is advisory and
        never blocks.
    @param subject What it is about — an event name, a type name, an extension.
    @param message What is wrong, in the terms the reader is thinking in.
    @param hint What to do about it, where that can be worked out. A diagnostic
        that reports a typo without naming the intended spelling has done half
        the job.
    """

    check: str
    severity: Severity
    subject: str
    message: str
    hint: str | None = None

    def __str__(self) -> str:
        line = (
            f"[{self.check}] {self.severity.upper()}: {self.subject} — {self.message}"
        )
        return f"{line}\n        → {self.hint}" if self.hint else line


@dataclass(frozen=True)
class WiringReport:
    """
    @brief Everything one inspection found.

    @details Empty is the good case and is falsy in the obvious way, so
    `if report.errors:` and `if not report.ok:` both read correctly.
    """

    findings: tuple[Finding, ...] = field(default_factory=tuple)

    @property
    def errors(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity == "error")

    @property
    def warnings(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity == "warning")

    @property
    def infos(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity == "info")

    @property
    def ok(self) -> bool:
        """@brief True when nothing is definitely broken. Warnings do not count."""
        return not self.errors

    def sorted_findings(self) -> tuple[Finding, ...]:
        """@brief Worst first, then by check id, then by subject — stable output
        so two runs of an unchanged application diff to nothing."""
        return tuple(
            sorted(
                self.findings,
                key=lambda f: (
                    SEVERITY_ORDER.index(f.severity),
                    f.check,
                    f.subject,
                ),
            )
        )

    def format(self) -> str:
        """@brief The human-readable report."""
        if not self.findings:
            return "Wiring OK — no findings."

        lines = [
            f"Wiring report: {len(self.errors)} error(s), "
            f"{len(self.warnings)} warning(s), {len(self.infos)} info."
        ]
        lines += [f"  {f}" for f in self.sorted_findings()]
        return "\n".join(lines)
