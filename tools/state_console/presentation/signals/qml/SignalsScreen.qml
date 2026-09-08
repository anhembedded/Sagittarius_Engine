import QtQuick
import QtQuick.Layouts
import Sagittarius.UI 1.0

// Signals -- EPIC-007E section 3 / EPIC-007F: the dead-letter queue and
// state-machine panels. Both sections are independently optional on the
// wire (StateSnapshot.signals.dead_letters/state_machines/ui_thread) --
// each table renders its own "nothing to show" state rather than a shared
// screen-wide one, since an app can watch a state machine but no DLQ, or
// the reverse.
Rectangle {
    id: root
    color: Theme.bg

    readonly property bool notAttached: !viewModel || viewModel.connectionState === "not_attached"

    readonly property var dlqColumns: [
        { key: "eventName", title: "Event", weight: 2 },
        { key: "exceptionType", title: "Exception", weight: 1 },
        { key: "exceptionMessage", title: "Message", weight: 3 },
        { key: "handler", title: "Handler", weight: 2 },
        { key: "retries", title: "Retries", weight: 1, align: Text.AlignRight }
    ]

    readonly property var transitionColumns: [
        { key: "machine", title: "Machine", weight: 2 },
        { key: "fromState", title: "From", weight: 2 },
        { key: "toState", title: "To", weight: 2 },
        { key: "event", title: "Event", weight: 1 },
        {
            key: "rejected", title: "Result", weight: 1,
            formatter: function(v) { return v ? "REJECTED" : "ok" }
        }
    ]

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spaceLg
        spacing: Theme.spaceLg

        Text {
            text: "Signals"
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeLg
            font.bold: true
            textFormat: Text.PlainText
        }

        // -- Dead-letter queue -------------------------------------------
        BaseCard {
            Layout.fillWidth: true
            Layout.preferredHeight: 220
            title: "Dead-letter queue"
            icon: "inbox"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.spaceMd
                spacing: Theme.spaceSm

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spaceMd

                    StatefulButton {
                        text: "Reprocess"
                        enabled: false
                        accentBorder: Theme.danger
                    }
                    Text {
                        Layout.fillWidth: true
                        text: viewModel ? viewModel.reprocessDisabledReason : ""
                        color: Theme.muted
                        font.pixelSize: Theme.fontSizeSm
                        wrapMode: Text.WordWrap
                        textFormat: Text.PlainText
                    }
                }

                AppDataTable {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    columns: dlqColumns
                    model: viewModel ? viewModel.deadLetters : null
                    emptyText: root.notAttached
                               ? "Not attached — nothing to show"
                               : "No dead-lettered events"
                }
            }
        }

        // -- State machines -------------------------------------------
        BaseCard {
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: "State machines"
            icon: "git-commit"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.spaceMd
                spacing: Theme.spaceSm

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.spaceLg
                    visible: viewModel && viewModel.stateMachines.length > 0

                    Repeater {
                        model: viewModel ? viewModel.stateMachines : []
                        delegate: Text {
                            required property var modelData
                            text: modelData.name + ": " + modelData.currentState
                                  + " (" + modelData.rejectedCount + " rejected)"
                            color: modelData.rejectedCount > 0 ? Theme.danger : Theme.textPrimary
                            font.pixelSize: Theme.fontSizeSm
                            textFormat: Text.PlainText
                        }
                    }
                }

                AppDataTable {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    title: "Transitions"
                    icon: "list"
                    columns: transitionColumns
                    model: viewModel ? viewModel.transitions : null
                    emptyText: root.notAttached
                               ? "Not attached — nothing to show"
                               : "No watched state machines"
                    rowAccent: function(rowData) {
                        return rowData.rejected ? Theme.danger : null
                    }
                }
            }
        }

        // -- UI-thread health -- absent, not zeroed, for a non-pyside app
        BaseCard {
            Layout.fillWidth: true
            Layout.preferredHeight: 72
            title: "UI thread health"
            icon: "activity"
            visible: viewModel && viewModel.hasUiThreadHealth

            RowLayout {
                anchors.fill: parent
                anchors.margins: Theme.spaceMd
                spacing: Theme.spaceLg

                Text {
                    text: "freezes: " + (viewModel ? viewModel.freezeCount : 0)
                          + " (worst " + (viewModel ? viewModel.worstFreezeMs.toFixed(0) : 0) + "ms)"
                    color: viewModel && viewModel.freezeCount > 0 ? Theme.danger : Theme.textPrimary
                    font.pixelSize: Theme.fontSizeMd
                    textFormat: Text.PlainText
                }
                Text {
                    text: "off-thread mutations: " + (viewModel ? viewModel.offThreadMutationCount : 0)
                    color: viewModel && viewModel.offThreadMutationCount > 0 ? Theme.danger : Theme.muted
                    font.pixelSize: Theme.fontSizeSm
                    textFormat: Text.PlainText
                }
            }
        }
    }
}
