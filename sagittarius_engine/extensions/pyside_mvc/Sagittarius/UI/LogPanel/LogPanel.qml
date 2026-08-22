import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Sagittarius.UI 1.0

// Reusable log panel (BOT-030 Phase 3). Shared by the Database sync log and
// the Dev Board system monitor — both show the same timestamped, leveled
// lines, so they share one component instead of two near-identical copies.
//
// Usage:
//     LogPanel { title: "SYSTEM MONITOR"; logModel: viewModel.logModel }
BaseCard {
    id: root

    //: `title`/`icon`/`compact` and the card chrome (bgCard fill, border,
    //: radius) all come from BaseCard now — this file used to redeclare
    //: `title` and repeat the same four chrome lines independently.
    title: "LOG"
    icon: "scroll-text"

    property alias logModel: logList.model
    property bool autoScroll: true

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---- Header ----------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            color: Theme.bgCardHeader
            radius: 8

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
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                Text {
                    text: root.title
                    color: Theme.accent
                    font.pixelSize: 12
                    font.bold: true
                }

                Rectangle {
                    radius: 3
                    color: Theme.stateIdleBg
                    border.color: Theme.border
                    border.width: 1
                    Layout.preferredWidth: countText.implicitWidth + 12
                    Layout.preferredHeight: 18
                    Text {
                        id: countText
                        anchors.centerIn: parent
                        text: logList.count + " EVENTS"
                        color: Theme.muted
                        font.pixelSize: 9
                        font.bold: true
                    }
                }

                Item { Layout.fillWidth: true }

                // EPIC-001C: migrated from a hand-rolled Button to the
                // kit's own StatefulButton — same icon+text+idle/hover/
                // border shape this button already had, just no longer a
                // second independent copy of that recipe. Corner radius
                // moves from a legacy 4px to StatefulButton's real
                // Theme.radiusMd default (6px) rather than being preserved
                // as an override — the old value was never token-backed.
                StatefulButton {
                    id: copyButton
                    objectName: "btnCopyLog"
                    text: "Copy"
                    iconSource: "copy"
                    iconSize: 12
                    fontSize: 11
                    implicitHeight: 24
                    // Whole-log copy, independent of any text selection —
                    // the per-line message Text below is individually
                    // selectable/copyable too (see delegate), this is the
                    // "grab everything" shortcut.
                    onClicked: logList.model.copyAllToClipboard()
                }

                StatefulButton {
                    id: clearButton
                    objectName: "btnClearLog"
                    text: "Clear"
                    iconSource: "trash-2"
                    iconSize: 12
                    fontSize: 11
                    implicitHeight: 24
                    // Clearing the on-screen log is a pure UI concern — no
                    // Presenter round-trip, same as MonitorCard did.
                    onClicked: logList.model.clear()
                }
            }
        }

        // ---- Lines -----------------------------------------------------
        ListView {
            id: logList
            objectName: "logList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: 8
            clip: true
            spacing: 2

            // Follows the newest line, but only while the user is already at
            // the bottom — otherwise scrolling back to read history would be
            // yanked away on every new message.
            onCountChanged: if (root.autoScroll && atYEnd) positionViewAtEnd()

            ScrollBar.vertical: ScrollBar {}

            delegate: RowLayout {
                width: ListView.view.width
                spacing: 6

                Image {
                    source: "image://icons/" + model.icon + "/"
                            + (model.level === "error" ? "danger"
                               : model.level === "success" ? "success" : "muted")
                    sourceSize.width: 12
                    sourceSize.height: 12
                    Layout.preferredWidth: 12
                    Layout.preferredHeight: 12
                    Layout.alignment: Qt.AlignTop
                    Layout.topMargin: 2
                }

                // TextEdit (not Text) so a line's content is selectable/
                // copyable with the mouse + Ctrl+C, matching a normal
                // console/log viewer — plain Text has no selection support
                // at all. readOnly keeps it display-only otherwise (no
                // cursor blinking, no edits reach the model).
                TextEdit {
                    text: "[" + model.timestamp + "]"
                    color: Theme.muted
                    font.family: "Consolas"
                    font.pixelSize: 11
                    Layout.alignment: Qt.AlignTop
                    readOnly: true
                    selectByMouse: true
                    persistentSelection: true
                    selectionColor: Theme.accent
                }

                TextEdit {
                    text: model.message
                    color: model.level === "error" ? Theme.danger : Theme.textPrimary
                    font.family: "Consolas"
                    font.pixelSize: 11
                    wrapMode: TextEdit.WrapAtWordBoundaryOrAnywhere
                    Layout.fillWidth: true
                    readOnly: true
                    selectByMouse: true
                    persistentSelection: true
                    selectionColor: Theme.accent
                }
            }
        }
    }
}
