"""
@brief The one rule for what a `QQuickWidget` paints where its QML scene
paints nothing: an **opaque** colour, read from a design token.

@details
`QQuickWidget` has two rendering paths, and they disagree about what a
transparent clear colour means:

- **Software** (`QT_QPA_PLATFORM=offscreen`, `QT_QUICK_BACKEND=software`, and
  every `QWidget.grab()`/`render()` — i.e. every headless test): the scene
  is drawn with `QPainter` on top of the backing store the parent widget
  already painted, so a transparent region shows the parent's background.
- **Texture / RHI** (every real desktop session — xcb, wayland, windows):
  the widget is a render-to-texture widget. `QWidgetPrivate::drawWidget`
  *punches a hole* in the backing store under it (fills the rect with
  `Qt::transparent`, `CompositionMode_Source`) and the backing-store
  compositor draws the texture **without blending** over a target it has
  cleared to `Qt::black` (or to transparent when the top-level has
  `WA_TranslucentBackground`). A transparent region therefore shows
  **black** on X11 and **whatever window is behind** on Wayland — never the
  parent widget's background, whatever the parent painted.

So "transparent so the parent surface shows through" is only true on the
path no user ever sees. Every headless test passes while the real app is
wrong — the reference consumer shipped exactly that defect across ten
hand-rolled hosts (`Sagittarius_Elite_Warrior` `BUG-102`/`BUG-115`).

The rule this module encodes: **an embedded QML scene is opaque, and its
background is a design token** — the same token the surrounding widget
paints, read from the same `Theme` bridge, so the two cannot drift. Both
rendering paths then produce the same pixels, and a headless test is
evidence again.
"""

from __future__ import annotations

from PySide6.QtGui import QColor

from sagittarius_engine.extensions.pyside_mvc.tokens.theme_bridge import (
    get_theme_bridge,
)

#: The application-background token — the right default for a whole route
#: hosted by `QmlHostView`, which sits directly on the app background. A
#: widget embedded inside a card/panel passes that surface's own token
#: (`"bgCard"`, ...) instead.
DEFAULT_BACKGROUND = "bg"

_OPAQUE_ALPHA = 255


def resolve_opaque_background(token: str) -> QColor:
    """
    @brief Resolves `token` through the shared theme bridge into a colour a
    `QQuickWidget` may legally clear to.

    @param token A colour token name the app supplied to `configure_app_qml()`
        (or the bridge otherwise holds) — `"bg"`, `"bgCard"`, ...
    @return An opaque `QColor`.
    @raise KeyError If the bridge holds no such token. Named, not silent: a
        `QQmlPropertyMap` answers a missing key with an invalid variant,
        which would become an invalid colour and a black rectangle nobody
        can trace back to a typo.
    @raise ValueError If the token's value is not a valid colour, or is not
        fully opaque — a translucent clear colour re-creates the exact
        defect described in the module docstring, so it is refused at
        construction, where the caller is, rather than discovered on a
        user's screen.
    """
    bridge = get_theme_bridge()
    if not bridge.contains(token):
        raise KeyError(f"no theme token named {token!r} for a QML background")
    colour = QColor(str(bridge.value(token)))
    if not colour.isValid():
        raise ValueError(
            f"theme token {token!r} is not a colour "
            f"({bridge.value(token)!r}) — a QML background must be a colour token"
        )
    if colour.alpha() != _OPAQUE_ALPHA:
        raise ValueError(
            f"theme token {token!r} ({colour.name(QColor.NameFormat.HexArgb)}) is "
            "not opaque — an embedded QML scene must clear to an opaque colour; "
            "on the texture rendering path a transparent clear colour renders "
            "black (X11) or see-through (Wayland), never the parent widget"
        )
    return colour
