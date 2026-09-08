import QtQuick
import QtQuick.Layouts
import Sagittarius.UI 1.0

// Tasks & threads -- EPIC-007E section 3: task table, pool saturation,
// queue depth, scheduler. Exclusive slots (ExclusiveAction.held_slot(),
// EPIC-007B) have no field in StateSnapshot yet -- EPIC-007D's own
// documented gap, not shown here because there is nothing to show
// honestly.
Rectangle {
    id: root
    color: Theme.bg

    readonly property bool notAttached: !viewModel || viewModel.connectionState === "not_attached"

    // "progress"/"ageSeconds" left default-aligned, not right -- BUG-013:
    // AppDataTable renders a right-aligned column immediately followed by
    // a left-aligned one ("error", last here) with zero gap, fusing the
    // two values -- unavoidable for this column order without either
    // reordering "error" away from the end or giving up right-alignment
    // on the numeric columns before it.
    readonly property var taskColumns: [
        { key: "name", title: "Task", weight: 3 },
        { key: "state", title: "State", weight: 1 },
        {
            key: "progress", title: "Progress", weight: 1,
            formatter: function(v) { return (v * 100).toFixed(0) + "%" }
        },
        {
            key: "ageSeconds", title: "Age", weight: 1,
            formatter: function(v) { return v.toFixed(0) + "s" }
        },
        { key: "error", title: "Error", weight: 3 }
    ]

    readonly property var poolColumns: [
        { key: "name", title: "Pool", weight: 2 },
        { key: "inFlight", title: "In flight", weight: 1, align: Text.AlignRight },
        { key: "maxWorkers", title: "Max", weight: 1, align: Text.AlignRight },
        { key: "queueDepth", title: "Queue", weight: 1, align: Text.AlignRight },
        { key: "submitted", title: "Submitted", weight: 1, align: Text.AlignRight },
        { key: "completed", title: "Completed", weight: 1, align: Text.AlignRight }
    ]

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spaceLg
        spacing: Theme.spaceLg

        BaseCard {
            id: boundsCard
            Layout.fillWidth: true
            Layout.preferredHeight: 72
            title: "Bounds"
            icon: "gauge"

            RowLayout {
                anchors.fill: parent
                anchors.margins: Theme.spaceMd
                spacing: Theme.spaceLg

                Text {
                    text: "retained tasks: " + (viewModel ? viewModel.retainedTasks : 0)
                          + "/" + (viewModel ? viewModel.retainedTaskLimit : 0)
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeMd
                    textFormat: Text.PlainText
                }
                Text {
                    text: "scheduler jobs: " + (viewModel ? viewModel.schedulerJobs : 0)
                          + " (" + (viewModel ? viewModel.schedulerJobsWithoutNextRun : 0)
                          + " without next run)"
                    color: Theme.muted
                    font.pixelSize: Theme.fontSizeSm
                    textFormat: Text.PlainText
                }
            }
        }

        AppDataTable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: "Tasks"
            icon: "list-checks"
            columns: taskColumns
            model: viewModel ? viewModel.tasks : null
            emptyText: root.notAttached ? "Not attached — nothing to show" : "No retained tasks"
        }

        AppDataTable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: "Thread pools"
            icon: "table"
            columns: poolColumns
            model: viewModel ? viewModel.threadPools : null
            emptyText: root.notAttached ? "Not attached — nothing to show" : "No thread pools reported"
        }
    }
}
