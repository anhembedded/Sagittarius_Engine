import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Sagittarius.UI 1.0

// Runtime state console -- Overview screen. Restyled by `EPIC-008B` §4 onto
// `reference/handoff.md` §7.1/§7.2: two sub-tabs (Status/Modules), three
// plates (Connection/Lifecycle/Signals) plus a worker-pools table for
// Status, a modules table for Modules.
//
// Two things the design calls for are deliberately not built here, named
// rather than silently dropped:
// - The Signals plate's per-row "jump to offending section+sub-tab" links.
//   `OverviewView` is one screen inside `PresenterManager`'s stack with no
//   channel to the shell's own navigation -- and the *sections* it would
//   jump to (Events/Container/Tasks/Signals) have no sub-tabs yet either
//   (`EPIC-008` subtasks C-F). The counts themselves are real; only the
//   click-through is missing.
// - Colour-tagged worker-pool cells (`AppDataTable` cells are plain text,
//   no per-cell delegate) -- `rowAccent` (an existing, already-shipped
//   hook, not a new one) tints the whole row instead when a pool breaches
//   a threshold, which surfaces the same fault without inventing a
//   kit-level feature for a single consumer.
Rectangle {
    id: root
    color: Theme.bg

    readonly property bool notAttached: !viewModel || viewModel.connectionState === "not_attached"
    readonly property bool attachedReading: viewModel && viewModel.connectionState === "attached_reading"

    readonly property color connectionColor: root.notAttached
        ? Theme.danger
        : (root.attachedReading ? Theme.success : Theme.warning)
    readonly property string connectionStateName: root.notAttached
        ? "Not attached"
        : (root.attachedReading ? "Attached — reading" : "Attached — idle")
    readonly property string connectionNote: root.notAttached
        ? (viewModel && viewModel.detachReason ? viewModel.detachReason : "no target attached")
        : (root.attachedReading ? "snapshot stream live" : "handshake complete · no snapshot yet")
    readonly property string ageText: (!viewModel || viewModel.snapshotAgeSeconds < 0)
        ? "last snapshot —"
        : "last snapshot " + viewModel.snapshotAgeSeconds.toFixed(0) + "s ago"
    readonly property int signalsTotal: viewModel && viewModel.signalCounts
        ? viewModel.signalCounts.overview || 0 : 0

    property string activeTab: "status"

    readonly property var threadPoolColumns: [
        { key: "name", title: "Pool", weight: 2 },
        { key: "occupancyText", title: "Occupancy", weight: 1, align: Text.AlignRight },
        { key: "inFlight", title: "In flight", weight: 1, align: Text.AlignRight },
        { key: "maxWorkers", title: "Max", weight: 1, align: Text.AlignRight },
        { key: "queueDepth", title: "Queued", weight: 1, align: Text.AlignRight },
        { key: "submitted", title: "Submitted", weight: 1, align: Text.AlignRight },
        { key: "completed", title: "Completed", weight: 1, align: Text.AlignRight }
    ]

    //: `reference/handoff.md` §7.1: occupancy/in-flight fault at 100%,
    //: queued fault above 20 -- tinting the whole row, see this file's own
    //: header comment for why not per-cell.
    function poolRowAccent(row) {
        return (row.occupancyPercent >= 100 || row.queueDepth > 20) ? Theme.danger : null
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spaceLg
        spacing: Theme.spaceLg

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spaceLg

            Text {
                objectName: "overviewTabStatus"
                text: "Status"
                color: root.activeTab === "status" ? Theme.accent900 : Theme.muted
                font.bold: true
                font.pixelSize: Theme.fontSizeMd
                textFormat: Text.PlainText

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.activeTab = "status"
                }
            }

            Text {
                objectName: "overviewTabModules"
                text: "Modules (" + (viewModel ? viewModel.modules.length : 0) + ")"
                color: root.activeTab === "modules" ? Theme.accent900 : Theme.muted
                font.bold: true
                font.pixelSize: Theme.fontSizeMd
                textFormat: Text.PlainText

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.activeTab = "modules"
                }
            }

            Item { Layout.fillWidth: true }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.border
        }

        // -------------------------------------------------------- Status tab

        RowLayout {
            visible: root.activeTab === "status"
            Layout.fillWidth: true
            spacing: Theme.spaceLg

            BaseCard {
                id: connectionCard
                Layout.fillWidth: true
                Layout.preferredHeight: 150
                title: "Connection"
                icon: "activity"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spaceMd
                    spacing: Theme.spaceXs

                    Text {
                        objectName: "overviewConnectionState"
                        text: root.connectionStateName
                        color: root.connectionColor
                        font.pixelSize: Theme.fontSizeXl
                        font.bold: true
                        textFormat: Text.PlainText
                    }
                    Text {
                        text: root.connectionNote
                        color: Theme.muted
                        font.family: Theme.fontFamilyMono
                        font.pixelSize: Theme.fontSizeSm
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    Text {
                        text: root.ageText
                        color: Theme.muted
                        font.family: Theme.fontFamilyMono
                        font.pixelSize: Theme.fontSizeSm
                        textFormat: Text.PlainText
                    }
                    Text {
                        objectName: "overviewSnapshotsReceived"
                        text: "snapshots received " + (viewModel ? viewModel.snapshotsReceived : 0)
                        color: Theme.muted
                        font.family: Theme.fontFamilyMono
                        font.pixelSize: Theme.fontSizeSm
                        textFormat: Text.PlainText
                    }
                    Item { Layout.fillHeight: true }
                }
            }

            BaseCard {
                id: lifecycleCard
                Layout.fillWidth: true
                Layout.preferredHeight: 150
                title: "Lifecycle"
                icon: "layers"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spaceMd
                    spacing: Theme.spaceXs

                    Text {
                        text: viewModel ? viewModel.lifecycleState : ""
                        color: Theme.textPrimary
                        font.pixelSize: Theme.fontSizeXl
                        font.bold: true
                        textFormat: Text.PlainText
                    }
                    Text {
                        objectName: "overviewExtensionsSummary"
                        text: (viewModel ? viewModel.extensionsInitialized : 0)
                            + "/" + (viewModel ? viewModel.extensionsRegistered : 0)
                            + " modules initialized"
                        color: Theme.muted
                        font.pixelSize: Theme.fontSizeSm
                        textFormat: Text.PlainText
                    }
                    Flow {
                        objectName: "overviewModuleGrid"
                        Layout.fillWidth: true
                        spacing: 3

                        Repeater {
                            model: viewModel ? viewModel.modules : []
                            delegate: Rectangle {
                                id: moduleCell
                                required property var modelData
                                objectName: "overviewModuleCell"
                                width: 11
                                height: 11
                                color: moduleCell.modelData.ready ? Theme.accent : "transparent"
                                border.color: Theme.border
                                border.width: moduleCell.modelData.ready ? 0 : 1

                                MouseArea {
                                    id: moduleCellHover
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    ToolTip.visible: moduleCellHover.containsMouse
                                    ToolTip.text: moduleCell.modelData.name + " · "
                                        + (moduleCell.modelData.ready ? "ready" : "initializing")
                                }
                            }
                        }
                    }
                    Item { Layout.fillHeight: true }
                }
            }

            BaseCard {
                id: signalsCard
                Layout.fillWidth: true
                Layout.preferredHeight: 150
                title: "Signals"
                icon: "alert-triangle"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spaceMd
                    spacing: Theme.spaceXs

                    Text {
                        objectName: "overviewSignalsFigure"
                        text: root.signalsTotal > 0 ? (root.signalsTotal + " open") : "All clear"
                        color: root.signalsTotal > 0 ? Theme.danger : Theme.textPrimary
                        font.pixelSize: Theme.fontSizeXl
                        font.bold: true
                        textFormat: Text.PlainText
                    }

                    Repeater {
                        model: [
                            { key: "events", label: "undeclared event names" },
                            { key: "container", label: "scope leak suspected" },
                            { key: "tasks", label: "failed tasks / broken jobs" },
                            { key: "signals", label: "dead letters + rejections" }
                        ]
                        delegate: RowLayout {
                            id: signalRow
                            required property var modelData
                            readonly property int count: viewModel && viewModel.signalCounts
                                ? (viewModel.signalCounts[signalRow.modelData.key] || 0) : 0
                            Layout.fillWidth: true
                            spacing: Theme.spaceSm

                            Text {
                                text: String(signalRow.count)
                                color: signalRow.count > 0 ? Theme.danger : Theme.muted
                                font.family: Theme.fontFamilyMono
                                font.pixelSize: Theme.fontSizeSm
                                textFormat: Text.PlainText
                            }
                            Text {
                                text: signalRow.modelData.label
                                color: signalRow.count > 0 ? Theme.textPrimary : Theme.muted
                                font.pixelSize: Theme.fontSizeSm
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                    }
                    Item { Layout.fillHeight: true }
                }
            }
        }

        AppDataTable {
            visible: root.activeTab === "status"
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: "Worker pools"
            icon: "table"
            columns: root.threadPoolColumns
            model: viewModel ? viewModel.threadPools : null
            rowAccent: root.poolRowAccent
            emptyText: root.notAttached ? "Not attached — nothing to show" : "No thread pools reported"
        }

        // ------------------------------------------------------- Modules tab

        Rectangle {
            visible: root.activeTab === "modules"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.maximumWidth: 760
            color: Theme.bgCard
            border.color: Theme.border
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 32
                    Layout.leftMargin: Theme.spaceMd
                    Layout.rightMargin: Theme.spaceMd
                    spacing: Theme.spaceMd

                    Text {
                        text: "#"
                        color: Theme.muted
                        font.pixelSize: Theme.fontSizeSm
                        textFormat: Text.PlainText
                        Layout.preferredWidth: 28
                    }
                    Text {
                        text: "module"
                        color: Theme.muted
                        font.pixelSize: Theme.fontSizeSm
                        textFormat: Text.PlainText
                        Layout.fillWidth: true
                    }
                    Text {
                        text: "state"
                        color: Theme.muted
                        font.pixelSize: Theme.fontSizeSm
                        textFormat: Text.PlainText
                        Layout.preferredWidth: 120
                    }
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

                Text {
                    visible: !viewModel || viewModel.modules.length === 0
                    text: root.notAttached ? "Not attached — nothing to show" : "No modules reported"
                    color: Theme.muted
                    font.pixelSize: Theme.fontSizeSm
                    textFormat: Text.PlainText
                    Layout.margins: Theme.spaceMd
                }

                ListView {
                    objectName: "overviewModulesList"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: viewModel ? viewModel.modules : []
                    delegate: RowLayout {
                        id: moduleRow
                        required property var modelData
                        required property int index
                        width: ListView.view.width
                        height: 32
                        spacing: Theme.spaceMd

                        Text {
                            text: String(moduleRow.index + 1)
                            color: Theme.muted
                            font.family: Theme.fontFamilyMono
                            font.pixelSize: Theme.fontSizeSm
                            textFormat: Text.PlainText
                            Layout.preferredWidth: 28
                            Layout.leftMargin: Theme.spaceMd
                        }
                        Text {
                            objectName: "overviewModuleRowName"
                            text: moduleRow.modelData.name
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontSizeSm
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Rectangle {
                            objectName: "overviewModuleRowStateTag"
                            radius: 2
                            color: moduleRow.modelData.ready ? Theme.accent100 : "transparent"
                            implicitWidth: stateLabel.implicitWidth + 12
                            implicitHeight: stateLabel.implicitHeight + 6
                            Layout.preferredWidth: 120
                            Layout.rightMargin: Theme.spaceMd

                            Text {
                                id: stateLabel
                                anchors.centerIn: parent
                                text: moduleRow.modelData.ready ? "initialized" : "initializing"
                                color: moduleRow.modelData.ready ? Theme.accent800 : Theme.danger
                                font.pixelSize: Theme.fontSizeSm
                                textFormat: Text.PlainText
                            }
                        }
                    }
                }
            }
        }
    }
}
