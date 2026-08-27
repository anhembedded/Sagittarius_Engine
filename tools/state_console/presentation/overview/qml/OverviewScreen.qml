import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Sagittarius.UI 1.0

// Runtime state console -- Overview screen (EPIC-007E). Combines the
// "Overview" and "Not attached" screens from the epic's own screen table
// into one: the connection-state banner at the top is always visible, per
// EPIC-007E section 4 ("the disconnected state is a designed screen, not a
// fallback"). The other four detail screens (events & wiring, container,
// tasks & threads, signals) are not built yet -- see this milestone's
// Outcome section.
Rectangle {
    id: root
    color: Theme.bg

    readonly property bool notAttached: !viewModel || viewModel.connectionState === "not_attached"
    readonly property bool attachedReading: viewModel && viewModel.connectionState === "attached_reading"

    readonly property color statusColor: notAttached ? Theme.danger : (attachedReading ? Theme.success : Theme.warning)
    readonly property string statusText: notAttached
        ? "Not attached" + (viewModel && viewModel.detachReason ? " — " + viewModel.detachReason : "")
        : (attachedReading ? "Attached — reading" : "Attached — idle")
    readonly property string ageText: (!viewModel || viewModel.snapshotAgeSeconds < 0)
        ? ""
        : "last snapshot " + viewModel.snapshotAgeSeconds.toFixed(0) + "s ago"

    readonly property var threadPoolColumns: [
        { key: "name", title: "Pool", weight: 2 },
        { key: "inFlight", title: "In flight", weight: 1, align: Text.AlignRight },
        { key: "maxWorkers", title: "Max", weight: 1, align: Text.AlignRight },
        { key: "queueDepth", title: "Queue", weight: 1, align: Text.AlignRight }
    ]

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spaceLg
        spacing: Theme.spaceLg

        BaseCard {
            id: statusCard
            Layout.fillWidth: true
            Layout.preferredHeight: 64
            title: "Runtime State Console"
            icon: "activity"

            RowLayout {
                anchors.fill: parent
                anchors.margins: Theme.spaceMd
                spacing: Theme.spaceMd

                // A single-level BaseCard-derivation would be the sanctioned
                // escape hatch (ui-architecture.md section 1.1) for a
                // reusable status dot; this one is a single fixed-size
                // indicator inside one screen's own composition, not
                // repeated anywhere else, so a plain Rectangle stays inside
                // this card's own content rather than promoting a
                // one-off shape into the kit.
                Rectangle {
                    width: 10
                    height: 10
                    radius: 5
                    color: root.statusColor
                }

                Text {
                    text: root.statusText
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeMd
                    textFormat: Text.PlainText
                    Layout.fillWidth: true
                }

                Text {
                    text: root.ageText
                    color: Theme.muted
                    font.pixelSize: Theme.fontSizeSm
                    textFormat: Text.PlainText
                }
            }
        }

        BaseCard {
            id: lifecycleCard
            Layout.fillWidth: true
            Layout.preferredHeight: 72
            title: "Lifecycle"
            icon: "layers"
            visible: !root.notAttached

            RowLayout {
                anchors.fill: parent
                anchors.margins: Theme.spaceMd
                spacing: Theme.spaceLg

                Text {
                    text: "state: " + (viewModel ? viewModel.lifecycleState : "")
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeMd
                    textFormat: Text.PlainText
                }
                Text {
                    text: "extensions: " + (viewModel ? viewModel.extensionsInitialized : 0)
                          + "/" + (viewModel ? viewModel.extensionsRegistered : 0)
                    color: Theme.muted
                    font.pixelSize: Theme.fontSizeSm
                    textFormat: Text.PlainText
                }
            }
        }

        AppDataTable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: "Thread pools"
            icon: "table"
            columns: threadPoolColumns
            model: viewModel ? viewModel.threadPools : null
            emptyText: root.notAttached ? "Not attached — nothing to show" : "No thread pools reported"
        }
    }
}
