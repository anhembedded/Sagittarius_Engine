import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Shared button with a standardized enabled/disabled/hover/active visual
// recipe. Promoted out of DevBoardPanel.qml/DatabaseScreen.qml (the
// enabled/disabled/hover part — the same ~6-line background block, plus 2-3
// more `opacity: enabled ? 1.0 : <magic number>` copies per button, was
// reimplemented 7+ times with inconsistent disabled-opacity constants
// 0.4/0.45/0.5/0.6 that didn't even agree with each other within one
// button) and Sidebar.qml's `navButton`/`bottomNavButton` (the `isActive`
// part — those were a second, near-identical ~55-line block each,
// independently typing out the same "selected nav item" tint). `isActive`
// and `enabled` are independent, orthogonal booleans on this one component
// — a button can be selected-but-busy, for instance — rather than two
// separate button types for the two concerns.
//
// Usage:
//     StatefulButton {
//         iconSource: "clock"          // -> image://icons/clock/muted
//         text: "Load History"
//         accentBorder: Theme.border   // or Theme.success / Theme.danger
//         onClicked: viewModel.requestLoadHistory()
//     }
//     StatefulButton {
//         iconSource: modelData.icon
//         text: modelData.label
//         iconSize: 18
//         fontSize: 13
//         accentBorder: Theme.stateNavBorder
//         isActive: modelData.route === viewModel.activeRoute
//         onClicked: viewModel.navigate(modelData.route)
//     }
Button {
    id: root

    //: Icon name only (no color suffix) — resolved against the app's
    //: `image://icons/<name>/<iconTint>` provider. Empty string omits the
    //: icon.
    property string iconSource: ""
    property string iconTint: root.isActive ? "accent" : "muted"
    property string hoverIconTint: root.iconTint
    property color accentBorder: Theme.border
    property color hoverBorderColor: root.isActive ? Theme.accent : root.accentBorder
    property color textColor: root.isActive ? Theme.accent : Theme.textPrimary
    property color hoverTextColor: root.textColor
    property color idleBgColor: Theme.stateIdleBg
    property color hoverBgColor: Theme.stateHoverBg
    property int iconSize: 13
    property int fontSize: 11
    property bool fontBold: false
    property int contentSpacing: 5
    property bool isActive: false
    property bool textFillWidth: false

    implicitHeight: 32

    contentItem: RowLayout {
        spacing: root.contentSpacing

        Image {
            visible: root.iconSource !== ""
            source: root.iconSource === "" ? "" : "image://icons/" + root.iconSource + "/" + (root.hovered && root.enabled ? root.hoverIconTint : root.iconTint)
            sourceSize.width: root.iconSize
            sourceSize.height: root.iconSize
            Layout.preferredWidth: root.iconSize
            Layout.preferredHeight: root.iconSize
            opacity: root.enabled ? 1.0 : Theme.stateDisabledOpacity
        }

        Text {
            text: root.text
            color: root.isActive ? Theme.accent : (root.hovered && root.enabled ? root.hoverTextColor : root.textColor)
            font.pixelSize: root.fontSize
            font.bold: root.fontBold
            opacity: root.enabled ? 1.0 : Theme.stateDisabledOpacity
            Layout.fillWidth: root.textFillWidth
            elide: root.textFillWidth ? Text.ElideRight : Text.ElideNone
        }
    }

    background: Rectangle {
        implicitHeight: root.implicitHeight
        radius: 6
        color: root.isActive
               ? Theme.stateActiveTint
               : (root.hovered && root.enabled ? root.hoverBgColor : root.idleBgColor)
        border.color: root.isActive ? Theme.accent : (root.hovered && root.enabled ? root.hoverBorderColor : root.accentBorder)
        border.width: 1
        opacity: root.enabled ? 1.0 : Theme.stateDisabledOpacity
    }
}
