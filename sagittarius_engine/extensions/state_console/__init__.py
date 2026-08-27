"""Runtime state console — `EPIC-007`.

Attaches to a running application and serves what is wired, registered and
alive to any connected client, over the transport `sagittarius-trace` already
uses. State only — no time axis; duration questions stay with
`sagittarius-trace` → `.sagtrace` → Perfetto (`ADR-001` §2.1).

@code
from sagittarius_engine.extensions.state_console import StateConsoleExtension

app.use(StateConsoleExtension(port=8781, token=None))
app.boot()
@endcode
"""

from .extension import StateConsoleExtension

__all__ = ["StateConsoleExtension"]
