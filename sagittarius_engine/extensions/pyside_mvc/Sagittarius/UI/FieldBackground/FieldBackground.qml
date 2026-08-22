import QtQuick

// Shared field background (promoted from DevBoardPanel.qml/DatabaseScreen.qml,
// which each used to define this as an identical local `component` block).
// Usage: `background: FieldBackground {}` on any ComboBox/TextField.
Rectangle {
    // token-exempt: sanctioned compatibility fallback (ui-architecture.md
    // §2.2) — this guards against `Theme` not being registered yet (e.g. a
    // preview loaded standalone), not a stand-in for a missing token.
    color: Theme && Theme.stateIdleBg ? Theme.stateIdleBg : "#181a24"  // token-exempt
    border.color: Theme && Theme.border ? Theme.border : "#2a2d3d"  // token-exempt
    border.width: 1
    radius: Theme && Theme.radiusMd ? Theme.radiusMd : 6
    implicitHeight: 32
}
