import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Sagittarius.UI 1.0

// Reusable modal dialog shell (EPIC-001C) — token-driven chrome (title bar
// with close button, scrollable body, right-aligned action footer) around
// a QML Popup. Replaces the independently-duplicated Popup+background
// recipe already seen in DateTimePicker.qml's calendar popup, and (per
// BOT-087/088 in the reference consumer) every screen popup migrated onto
// OverlayHost by hand.
//
// Dynamic sizing only (qml-rule.md §2.2) — never a fixed pixel width or
// height: `width` targets `maxWidth` but yields to a small overlay,
// `height` follows real content up to a fraction of the overlay's own
// bounds. Composes with OverlayHost.qml: anchors to `Overlay.overlay`, so
// it centers correctly whether hosted full-window (OverlayHost) or inside
// a plain QQuickWidget during a standalone preview/gallery render.
//
// Usage (inside a document loaded via OverlayHost.load_content, which must
// expose `hasOpenModal`):
//     Item {
//         id: root
//         readonly property bool hasOpenModal: confirmModal.opened
//         AppModal {
//             id: confirmModal
//             title: "Confirm Action"
//             actions: [
//                 StatefulButton { text: "Cancel"; onClicked: confirmModal.close() },
//                 StatefulButton {
//                     text: "Confirm"
//                     accentBorder: Theme.success
//                     onClicked: { /* ... */ confirmModal.close() }
//                 }
//             ]
//             Text {
//                 Layout.fillWidth: true
//                 text: "Are you sure you want to continue?"
//                 color: Theme.textPrimary
//                 wrapMode: Text.WordWrap
//                 textFormat: Text.PlainText
//             }
//         }
//     }
Popup {
    id: root

    property string title: ""
    //: Default content property — plain QML children declared inside
    //: `AppModal { ... }` land here, stacked vertically. Consumers do not
    //: assign this directly; it exists so ordinary child-item declaration
    //: works without a named property, the same idiom Popup itself uses
    //: for `contentData`.
    default property alias bodyData: bodyColumn.data
    //: Footer actions, left declared = left rendered (a spacer already
    //: pushes them to the right — see `actionsRow` below). Typically
    //: `StatefulButton` instances.
    property alias actions: actionsRow.data
    property real maxWidth: 480
    //: Fraction of the hosting overlay's height a modal may occupy before
    //: its body starts scrolling instead of growing further.
    property real maxHeightFraction: 0.85

    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    anchors.centerIn: Overlay.overlay
    padding: 0

    width: Math.min(root.maxWidth, Overlay.overlay ? Overlay.overlay.width * 0.9 : root.maxWidth)
    height: Math.min(
        implicitHeight,
        Overlay.overlay ? Overlay.overlay.height * root.maxHeightFraction : 480
    )

    background: Rectangle {
        color: Theme.bgCard
        border.color: Theme.border
        border.width: 1
        radius: Theme.radiusMd
    }

    contentItem: ColumnLayout {
        spacing: 0

        // ---- Header ------------------------------------------------
        Rectangle {
            id: header
            Layout.fillWidth: true
            Layout.preferredHeight: 44
            color: Theme.bgCardHeader
            radius: Theme.radiusMd

            // Square off the header's bottom corners, same trick every
            // other card-shaped kit component already uses.
            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: parent.radius
                color: parent.color
            }
            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: Theme.border
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.spaceLg
                anchors.rightMargin: Theme.spaceSm
                spacing: Theme.spaceSm

                Text {
                    Layout.fillWidth: true
                    text: root.title
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeMd
                    font.bold: true
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                }

                StatefulButton {
                    objectName: "btnCloseModal"
                    text: "✕"
                    implicitWidth: 24
                    implicitHeight: 24
                    fontSize: 12
                    onClicked: root.close()
                }
            }
        }

        // ---- Body ----------------------------------------------------
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth
            ScrollBar.vertical.policy: ScrollBar.AsNeeded

            ColumnLayout {
                id: bodyColumn
                width: parent.width
                spacing: Theme.spaceMd

                // A dialog with no declared body still needs sane
                // top/bottom breathing room, provided here rather than by
                // every consumer repeating the same margin.
                Item { Layout.preferredHeight: Theme.spaceLg }
            }
        }

        // ---- Footer (only takes space when actions exist) ------------
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: actionsRow.children.length > 1 ? 52 : 0
            visible: actionsRow.children.length > 1
            color: "transparent"

            RowLayout {
                id: actionsRow
                anchors.fill: parent
                anchors.margins: Theme.spaceMd
                spacing: Theme.spaceSm

                Item { Layout.fillWidth: true }
            }
        }
    }
}
