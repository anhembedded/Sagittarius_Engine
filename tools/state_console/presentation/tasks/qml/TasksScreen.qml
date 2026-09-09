import QtQuick
import QtQuick.Layouts
import Sagittarius.UI 1.0

// Tasks & threads -- EPIC-007E section 3, restyled by EPIC-008B subtask E
// onto reference/handoff.md §7.5: a sortable Tasks table with an
// expandable failed-row detail (error type, message, and a *real* stack --
// EPIC-008E extended BackgroundTask/TaskSnapshot/TaskRecord to capture
// traceback.format_exc() at the moment a task actually fails, since this
// section's own Definition of Done is "a failed task's stack is readable
// after a click"), a Thread pools table with a real outstanding column,
// and a Limits tab (task registry cap, scheduler figures, a real per-job
// table -- EPIC-008E also gave ITrigger.describe() and LifecycleState.jobs
// to `sagittarius_engine` for this).
//
// Not built: the handoff's "paused" scheduler figure. Nothing in this
// engine's Scheduler can pause a job -- there is no such state to count,
// so showing "0 paused" would claim a capability that does not exist
// rather than report an honest zero of one that does (unlike, say, this
// screen's own "broken" figure, which is a real, always-measured count).
// Named here rather than silently dropped, same as every other handoff
// gap this epic has found.
Rectangle {
    id: root
    color: Theme.bg

    readonly property bool notAttached: !viewModel || viewModel.connectionState === "not_attached"
    readonly property var tasks: viewModel ? viewModel.tasks : []
    readonly property var threadPools: viewModel ? viewModel.threadPools : []
    readonly property var jobs: viewModel ? viewModel.jobs : []

    property string activeTab: "tasks"

    // "owner" placed before the right-aligned Progress/Elapsed block, not
    // after -- BUG-013 (this repo's own repeat finding, first hit and fixed
    // in EventsScreen.qml/ContainerScreen.qml: AppDataTable renders a
    // right-aligned column immediately followed by a left-aligned one with
    // zero gap, fusing the two values -- caught here too, via this
    // subtask's own screenshot review, by the exact same symptom
    // ("ElapsedOwner"/"2sSagittariusBgTask_0") those two screens' own
    // history already named.
    readonly property var taskColumns: [
        { key: "name", title: "Task", weight: 3 },
        {
            key: "state", title: "State", weight: 1,
            formatter: function(v) { return v ? v.charAt(0).toUpperCase() + v.slice(1) : "" }
        },
        {
            key: "owner", title: "Owner", weight: 2,
            formatter: function(v) { return v ? v : "—" }
        },
        {
            key: "progress", title: "Progress", weight: 1, align: Text.AlignRight,
            formatter: function(v) { return (v * 100).toFixed(0) + "%" }
        },
        {
            key: "ageSeconds", title: "Elapsed", weight: 1, align: Text.AlignRight,
            formatter: function(v) { return v.toFixed(0) + "s" }
        }
    ]

    readonly property var poolColumns: [
        { key: "name", title: "Pool", weight: 2 },
        { key: "inFlight", title: "In flight", weight: 1, align: Text.AlignRight },
        { key: "maxWorkers", title: "Max", weight: 1, align: Text.AlignRight },
        { key: "queueDepth", title: "Queue", weight: 1, align: Text.AlignRight },
        { key: "submitted", title: "Submitted", weight: 1, align: Text.AlignRight },
        { key: "completed", title: "Completed", weight: 1, align: Text.AlignRight },
        { key: "outstanding", title: "Outstanding", weight: 1, align: Text.AlignRight }
    ]

    // "state" placed before the right-aligned "Next fire", not after --
    // BUG-013 again (see `taskColumns`' own comment above).
    readonly property var jobColumns: [
        { key: "name", title: "Job", weight: 2 },
        { key: "trigger", title: "Trigger", weight: 2 },
        { key: "state", title: "State", weight: 1 },
        {
            // Loose `== null` on purpose: a Python `None` in a `QVariantList`
            // can surface to QML as `undefined` rather than `null` -- found
            // via this exact formatter returning "in NaNs" for a broken job
            // under a real test, not a hypothetical.
            key: "nextFireSeconds", title: "Next fire", weight: 1, align: Text.AlignRight,
            formatter: function(v) { return v == null ? "none — dead" : "in " + Math.max(0, Math.round(v)) + "s" }
        }
    ]

    function taskRowAccent(row) {
        return row.state === "failed" ? Theme.danger : null
    }

    function jobRowAccent(row) {
        return row.nextFireSeconds == null ? Theme.danger : null
    }

    //: `expandedDelegate`'s contract: its root item must declare
    //: `property var rowData` -- AppDataTable keeps it live-bound to the
    //: expanded row's current data via an internal `Binding`.
    //: reference/handoff.md §7.5: "error type in fault caps, the message,
    //: then the stack lines in mono 12px, inside a fault @ 5% panel with a
    //: 3px fault left border."
    //: `Item`, not `Rectangle` -- the background tint and the text content
    //: are independent siblings, not parent/child. QML's `opacity` is
    //: multiplicative onto every descendant, so the tint's own `opacity`
    //: (a background *fill* strength) would otherwise dim the error text
    //: right along with it -- caught via this subtask's own screenshot
    //: review: the first version nested `detailColumn` inside the tinted
    //: `Rectangle` and the stack came out all but invisible.
    component FailedTaskDetail: Item {
        property var rowData: null
        implicitHeight: detailColumn.implicitHeight + Theme.spaceMd * 2

        Rectangle {
            anchors.fill: parent
            color: Theme.dangerFill
            opacity: 0.05
        }

        Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 3
            color: Theme.danger
        }

        ColumnLayout {
            id: detailColumn
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: Theme.spaceMd
            anchors.leftMargin: Theme.spaceMd + 3
            spacing: Theme.spaceXs

            Text {
                text: rowData && rowData.errorType ? rowData.errorType.toUpperCase() : "ERROR"
                color: Theme.danger
                font.bold: true
                font.pixelSize: Theme.fontSizeSm
                textFormat: Text.PlainText
            }
            Text {
                Layout.fillWidth: true
                text: rowData ? rowData.error : ""
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeSm
                wrapMode: Text.Wrap
                textFormat: Text.PlainText
            }
            Text {
                Layout.fillWidth: true
                visible: rowData && rowData.stack
                text: rowData ? rowData.stack : ""
                color: Theme.textPrimary
                font.family: Theme.fontFamilyMono
                font.pixelSize: 12
                wrapMode: Text.Wrap
                textFormat: Text.PlainText
            }
        }
    }
    readonly property Component failedTaskDetailComponent: Component { FailedTaskDetail {} }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spaceLg
        spacing: Theme.spaceLg

        Text {
            text: "Tasks & threads"
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeLg
            font.bold: true
            textFormat: Text.PlainText
        }

        SectionSubTabs {
            Layout.fillWidth: true
            activeTabId: root.activeTab
            tabs: [
                { id: "tasks", label: "Tasks", count: root.tasks.length },
                { id: "pools", label: "Thread pools", count: root.threadPools.length },
                { id: "limits", label: "Limits" }
            ]
            onTabSelected: (id) => root.activeTab = id
        }

        // -------------------------------------------------------- Tasks tab

        ColumnLayout {
            visible: root.activeTab === "tasks"
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.spaceXs

            Text {
                visible: root.tasks.some(function(t) { return t.state === "failed" })
                text: "Click the failed row to read its exception and stack."
                color: Theme.muted
                font.pixelSize: Theme.fontSizeSm
                textFormat: Text.PlainText
            }

            AppDataTable {
                objectName: "tasksTable"
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: "Tasks"
                icon: "list-checks"
                columns: root.taskColumns
                model: root.tasks
                rowIdKey: "id"
                rowAccent: root.taskRowAccent
                expandedDelegate: root.failedTaskDetailComponent
                expandPredicate: function(row) { return row.state === "failed" }
                emptyText: root.notAttached
                    ? "Not attached — nothing to show"
                    : "No tracked tasks — the registry is holding 0 of "
                        + (viewModel ? viewModel.retainedTaskLimit : 0) + " slots"
            }
        }

        // -------------------------------------------------- Thread pools tab

        AppDataTable {
            visible: root.activeTab === "pools"
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: "Thread pools"
            icon: "table"
            columns: root.poolColumns
            model: root.threadPools
            emptyText: root.notAttached ? "Not attached — nothing to show" : "No thread pools reported"
        }

        // -------------------------------------------------------- Limits tab

        ColumnLayout {
            visible: root.activeTab === "limits"
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.spaceLg

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spaceLg

                BaseCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 150
                    title: "Task registry"
                    icon: "list-checks"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spaceMd
                        spacing: Theme.spaceXs

                        Text {
                            objectName: "limitsRegistryFigure"
                            text: (viewModel ? viewModel.retainedTasks : 0) + " / "
                                + (viewModel ? viewModel.retainedTaskLimit : 0)
                            color: Theme.textPrimary
                            font.pixelSize: 42
                            font.bold: true
                            textFormat: Text.PlainText
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            height: 6
                            radius: 3
                            color: Theme.border

                            Rectangle {
                                readonly property real fraction: viewModel && viewModel.retainedTaskLimit > 0
                                    ? Math.min(1, viewModel.retainedTasks / viewModel.retainedTaskLimit)
                                    : 0
                                anchors.left: parent.left
                                anchors.top: parent.top
                                anchors.bottom: parent.bottom
                                width: parent.width * fraction
                                radius: 3
                                color: Theme.accent
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: "Retained tasks are bounded so a long-running process cannot grow this"
                                + " list without limit — the oldest finished tasks are dropped once the cap"
                                + " is reached."
                            color: Theme.muted
                            font.pixelSize: Theme.fontSizeSm
                            wrapMode: Text.Wrap
                            textFormat: Text.PlainText
                        }
                        Item { Layout.fillHeight: true }
                    }
                }

                BaseCard {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 150
                    title: "Scheduler"
                    icon: "clock"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: Theme.spaceMd
                        spacing: Theme.spaceXs

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spaceLg

                            ColumnLayout {
                                spacing: 0
                                Text {
                                    text: viewModel ? String(viewModel.schedulerJobs) : "0"
                                    color: Theme.textPrimary
                                    font.pixelSize: 30
                                    font.bold: true
                                    textFormat: Text.PlainText
                                }
                                Text {
                                    text: "jobs"
                                    color: Theme.muted
                                    font.pixelSize: Theme.fontSizeSm
                                    textFormat: Text.PlainText
                                }
                            }
                            ColumnLayout {
                                spacing: 0
                                readonly property bool broken: viewModel && viewModel.schedulerJobsWithoutNextRun > 0
                                Text {
                                    objectName: "limitsBrokenFigure"
                                    text: viewModel ? String(viewModel.schedulerJobsWithoutNextRun) : "0"
                                    color: parent.broken ? Theme.danger : Theme.textPrimary
                                    font.pixelSize: 30
                                    font.bold: true
                                    textFormat: Text.PlainText
                                }
                                Text {
                                    text: "broken"
                                    color: Theme.muted
                                    font.pixelSize: Theme.fontSizeSm
                                    textFormat: Text.PlainText
                                }
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: "Broken means the job is still registered but has no next fire time —"
                                + " it will never run again and nothing will say so."
                            color: Theme.muted
                            font.pixelSize: Theme.fontSizeSm
                            wrapMode: Text.Wrap
                            textFormat: Text.PlainText
                        }
                        Item { Layout.fillHeight: true }
                    }
                }
            }

            AppDataTable {
                objectName: "limitsJobsTable"
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: "Jobs"
                icon: "clock"
                columns: root.jobColumns
                model: root.jobs
                rowAccent: root.jobRowAccent
                emptyText: root.notAttached ? "Not attached — nothing to show" : "No scheduler jobs registered"
            }
        }
    }
}
