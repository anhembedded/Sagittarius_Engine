"""Wiring diagnostics — `EPIC-006`.

Compares what an application declared against what it actually wired, and
reports the difference. The point is to move a whole class of defect from
"runtime, intermittent, silent" to "boot, deterministic, loud":

@code
from sagittarius_engine.extensions.diagnostics import WiringInspector

report = WiringInspector().inspect(bus=event_bus, container=container)
print(report.format())
if not report.ok:
    raise SystemExit(1)
@endcode
"""

from .extension import DiagnosticsError, DiagnosticsExtension
from .inspector import WiringInspector
from .report import Finding, Severity, WiringReport

__all__ = [
    "DiagnosticsExtension",
    "DiagnosticsError",
    "WiringInspector",
    "WiringReport",
    "Finding",
    "Severity",
]
