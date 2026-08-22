import QtQuick
import QtQuick.Controls

// Shared checkbox styling (promoted from DevBoardPanel.qml's local
// `component StyledCheck` block). Usage: `StyledCheck { text: "..."; checked: ...; onToggled: ... }`.
CheckBox {
    id: check

    contentItem: Text {
        leftPadding: check.indicator.width + 6
        text: check.text
        color: Theme.textPrimary
        font.pixelSize: 12
        verticalAlignment: Text.AlignVCenter
    }

    indicator: Rectangle {
        implicitWidth: 16
        implicitHeight: 16
        y: (check.height - height) / 2
        radius: 3
        color: check.checked ? Theme.accent : Theme.stateIdleBg
        border.color: check.checked ? Theme.accent : Theme.border
        border.width: 1
    }
}
