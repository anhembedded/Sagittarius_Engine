import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Sagittarius.UI 1.0

// `EPIC-008B` §3 -- the connect flow, composed from existing kit
// primitives (`TextField`+`FieldBackground`, `StatefulButton`) per
// `EPIC-008A` §5's own resolution: a one-off attach form is not two
// consumers, so it earns no new kit component
// (`ActionCard/NOTES.md`'s promotion rule). `reference/handoff.md` §5.
Rectangle {
    id: root
    color: Theme.bg

    function _submit() {
        var address = addressField.text.trim()
        if (address.length > 0) {
            viewModel.requestConnect(address)
        }
    }

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(560, parent.width - 80)
        spacing: Theme.spaceLg

        Text {
            objectName: "connectFlowTitle"
            text: viewModel.changingTarget ? "Change target" : "Attach to a running process"
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeLg
            font.bold: true
            textFormat: Text.PlainText
        }

        Text {
            objectName: "connectFlowChangingTargetNote"
            visible: viewModel.changingTarget
            text: "Currently attached to " + viewModel.currentTarget + ". Connecting somewhere"
                + " else drops this connection first; the tool does not hold two at a time."
            color: Theme.muted
            font.pixelSize: Theme.fontSizeSm
            wrapMode: Text.WordWrap
            textFormat: Text.PlainText
            Layout.fillWidth: true
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spaceSm

            TextField {
                id: addressField
                objectName: "connectFlowAddressField"
                Layout.fillWidth: true
                placeholderText: "ws://host:port or wss://host:port?token=..."
                color: Theme.textPrimary
                font.family: Theme.fontFamilyMono
                font.pixelSize: Theme.fontSizeMd
                background: FieldBackground {}
                Keys.onReturnPressed: root._submit()
            }

            StatefulButton {
                objectName: "connectFlowSubmitButton"
                text: viewModel.changingTarget ? "Connect instead" : "Connect"
                enabled: addressField.text.trim().length > 0
                onClicked: root._submit()
            }

            StatefulButton {
                objectName: "connectFlowCancelButton"
                text: "Cancel"
                visible: viewModel.changingTarget
                onClicked: viewModel.requestCancel()
            }
        }

        Text {
            text: "ws://host:port for a local or trusted host, wss://host:port?token=… where"
                + " the backend requires a console token. The address is the whole target —"
                + " there is no separate host, port or credential field to keep in sync."
            color: Theme.muted
            font.pixelSize: Theme.fontSizeSm
            wrapMode: Text.WordWrap
            textFormat: Text.PlainText
            Layout.fillWidth: true
        }

        ColumnLayout {
            Layout.fillWidth: true
            visible: viewModel.recents.length > 0
            spacing: Theme.spaceXs

            Text {
                text: "RECENT"
                color: Theme.muted
                font.pixelSize: Theme.fontSizeSm
                font.bold: true
                textFormat: Text.PlainText
            }

            Repeater {
                model: viewModel.recents

                delegate: Rectangle {
                    id: row
                    required property var modelData
                    objectName: "connectFlowRecentRow"
                    Layout.fillWidth: true
                    implicitHeight: 40
                    color: Theme.surface
                    border.color: Theme.border
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Theme.spaceSm
                        anchors.rightMargin: Theme.spaceSm
                        spacing: Theme.spaceSm

                        Text {
                            objectName: "connectFlowRecentAddress"
                            text: row.modelData.address
                            color: Theme.textPrimary
                            font.family: Theme.fontFamilyMono
                            font.pixelSize: Theme.fontSizeSm
                            textFormat: Text.PlainText
                            elide: Text.ElideMiddle
                            Layout.fillWidth: true
                        }
                        Text {
                            text: row.modelData.lastUsedLabel
                            color: Theme.muted
                            font.pixelSize: Theme.fontSizeSm
                            textFormat: Text.PlainText
                        }
                        StatefulButton {
                            objectName: "connectFlowRecentButton"
                            text: row.modelData.isCurrent ? "attached" : "connect"
                            enabled: !row.modelData.isCurrent
                            onClicked: viewModel.requestConnect(row.modelData.address)
                        }
                    }
                }
            }
        }
    }
}
