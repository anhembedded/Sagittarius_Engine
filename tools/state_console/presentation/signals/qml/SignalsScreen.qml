import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Sagittarius.UI 1.0

// Signals -- EPIC-007E section 3 / EPIC-007F, restyled by EPIC-008B subtask
// F onto reference/handoff.md §7.6: one blueprint card per dead letter (not
// a table row), one plate per watched machine (name/key, attempts/rejected
// figures, a declared-states chip row, its own transition log), and three
// separate UI-thread health plates. Both dead letters and state machines
// are independently optional on the wire (StateSnapshot.signals.
// dead_letters/state_machines/ui_thread) -- each section renders its own
// "nothing to show" state rather than a shared screen-wide one, since an
// app can watch a state machine but no DLQ, or the reverse.
//
// `attempted_count`/`declared_states` (state machines) and the per-
// transition `reason` are new EPIC-008F wire fields -- see
// `StateMachineState`/`StateMachineTransition`'s own docstrings for why
// each is real, already-available data rather than new tracking.
//
// Not built: "hatched" rejected-transition rows. `AppDataTable` has a
// solid-tint `rowAccent` hook (already used here, and by three other
// screens this epic restyled) but no diagonal-hatch fill pattern -- the
// same "no per-cell delegate" limitation named for the fourth time this
// epic now. A solid `danger` tint reads as "wrong" exactly as clearly.
Rectangle {
    id: root
    color: Theme.bg

    readonly property bool notAttached: !viewModel || viewModel.connectionState === "not_attached"
    readonly property var deadLetters: viewModel ? viewModel.deadLetters : []
    readonly property var stateMachines: viewModel ? viewModel.stateMachines : []

    readonly property var transitionColumns: [
        {
            key: "ageSeconds", title: "Age", weight: 1,
            formatter: function(v) { return root.formatAgo(v) + " ago" }
        },
        {
            key: "rejected", title: "Result", weight: 1,
            formatter: function(v) { return v ? "REJECTED" : "ACCEPTED" }
        },
        { key: "fromState", title: "From", weight: 2 },
        { key: "toState", title: "To", weight: 2 },
        {
            key: "reason", title: "Reason", weight: 3,
            formatter: function(v) { return v ? v : "—" }
        }
    ]

    //: "3m 34s", "45s" -- the one place on this screen that needs
    //: minute-granularity ages; every other screen's ages round to whole
    //: seconds, so this stays local rather than becoming a kit formatter
    //: for a single consumer.
    function formatAgo(totalSeconds) {
        var whole = Math.max(0, Math.floor(totalSeconds))
        var minutes = Math.floor(whole / 60)
        var seconds = whole % 60
        return minutes > 0 ? (minutes + "m " + seconds + "s") : (seconds + "s")
    }

    function transitionRowAccent(row) {
        return row.rejected ? Theme.danger : null
    }

    //: `reference/handoff.md` §7.6: "one blueprint card per entry, max-width
    //: 1000px, fault-tinted border."
    component DeadLetterCard: Rectangle {
        property var entry: null
        Layout.fillWidth: true
        Layout.maximumWidth: 1000
        implicitHeight: cardColumn.implicitHeight + Theme.spaceLg * 2
        color: Theme.bgCard
        border.color: Theme.danger
        border.width: 1

        ColumnLayout {
            id: cardColumn
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: Theme.spaceLg
            spacing: Theme.spaceSm

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spaceMd

                Text {
                    text: entry ? entry.id : ""
                    color: Theme.danger
                    font.family: Theme.fontFamilyMono
                    font.bold: true
                    font.pixelSize: Theme.fontSizeSm
                    textFormat: Text.PlainText
                }
                Text {
                    Layout.fillWidth: true
                    text: entry ? entry.eventName : ""
                    color: Theme.textPrimary
                    font.bold: true
                    font.pixelSize: 19
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                }
                ColumnLayout {
                    spacing: 0
                    Text {
                        Layout.alignment: Qt.AlignRight
                        text: entry ? "set aside " + root.formatAgo(entry.agoSeconds) + " ago" : ""
                        color: Theme.muted
                        font.pixelSize: Theme.fontSizeSm
                        textFormat: Text.PlainText
                    }
                    Text {
                        Layout.alignment: Qt.AlignRight
                        text: entry ? "after " + entry.retries + " retries" : ""
                        color: Theme.muted
                        font.pixelSize: Theme.fontSizeSm
                        textFormat: Text.PlainText
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spaceLg

                ColumnLayout {
                    spacing: 0
                    Text {
                        text: "FAILING HANDLER"
                        color: Theme.muted
                        font.pixelSize: Theme.fontSizeSm
                        font.bold: true
                        textFormat: Text.PlainText
                    }
                    Text {
                        text: entry ? entry.handler : ""
                        color: Theme.textPrimary
                        font.family: Theme.fontFamilyMono
                        font.pixelSize: Theme.fontSizeSm
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                    }
                }
                ColumnLayout {
                    spacing: 0
                    Text {
                        text: "ERROR"
                        color: Theme.muted
                        font.pixelSize: Theme.fontSizeSm
                        font.bold: true
                        textFormat: Text.PlainText
                    }
                    Text {
                        text: entry ? entry.exceptionType : ""
                        color: Theme.danger
                        font.family: Theme.fontFamilyMono
                        font.pixelSize: Theme.fontSizeSm
                        textFormat: Text.PlainText
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                text: entry ? entry.exceptionMessage : ""
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeMd
                wrapMode: Text.Wrap
                textFormat: Text.PlainText
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: payloadText.implicitHeight + Theme.spaceMd * 2
                color: "transparent"
                // A solid border, not the handoff's own dashed one: QtQuick
                // has no native dashed-border style, and a hand-rolled
                // segment-by-segment approximation is fragile enough (it
                // must re-tile itself on every resize) that it is not worth
                // building for one block on one screen -- the same
                // "no per-cell delegate" class of gap this epic has named
                // several times already, applied here to a border style
                // instead of a table cell.
                border.color: Theme.border
                radius: 2

                Text {
                    id: payloadText
                    anchors.fill: parent
                    anchors.margins: Theme.spaceMd
                    text: entry ? entry.payloadRepr : ""
                    color: Theme.muted
                    font.family: Theme.fontFamilyMono
                    font.pixelSize: Theme.fontSizeSm
                    wrapMode: Text.Wrap
                    textFormat: Text.PlainText
                }
            }

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
        }
    }

    //: `reference/handoff.md` §7.6: "one plate per machine."
    component MachineCard: BaseCard {
        property var machine: null
        Layout.fillWidth: true
        implicitHeight: machineColumn.implicitHeight + Theme.spaceLg * 2
        title: ""

        ColumnLayout {
            id: machineColumn
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: Theme.spaceLg
            spacing: Theme.spaceSm

            Text {
                text: "WATCHED MACHINE"
                color: Theme.muted
                font.pixelSize: Theme.fontSizeSm
                font.bold: true
                font.letterSpacing: 1
                textFormat: Text.PlainText
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spaceLg

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Text {
                        text: machine ? machine.name : ""
                        color: Theme.textPrimary
                        font.bold: true
                        font.pixelSize: Theme.fontSizeLg
                        font.family: Theme.fontFamilyMono
                        textFormat: Text.PlainText
                    }
                    Text {
                        text: "current state · " + (machine ? machine.currentState : "")
                        color: Theme.muted
                        font.pixelSize: Theme.fontSizeSm
                        textFormat: Text.PlainText
                    }
                }
                ColumnLayout {
                    spacing: 0
                    readonly property bool hasRejections: machine && machine.rejectedCount > 0
                    Text {
                        Layout.alignment: Qt.AlignRight
                        text: (machine ? machine.attemptedCount : 0) + " attempts"
                        color: Theme.muted
                        font.pixelSize: Theme.fontSizeSm
                        textFormat: Text.PlainText
                    }
                    Text {
                        Layout.alignment: Qt.AlignRight
                        text: (machine ? machine.rejectedCount : 0) + " rejected"
                        color: parent.hasRejections ? Theme.danger : Theme.muted
                        font.bold: parent.hasRejections
                        font.pixelSize: Theme.fontSizeSm
                        textFormat: Text.PlainText
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spaceXs

                Repeater {
                    model: machine ? machine.declaredStates : []
                    delegate: Rectangle {
                        id: chip
                        required property string modelData
                        readonly property bool isCurrent: machine && machine.currentState === modelData
                        radius: 2
                        color: chip.isCurrent ? Theme.accent : "transparent"
                        border.color: chip.isCurrent ? "transparent" : Theme.border
                        border.width: 1
                        implicitWidth: chipLabel.implicitWidth + 12
                        implicitHeight: chipLabel.implicitHeight + 6

                        Text {
                            id: chipLabel
                            anchors.centerIn: parent
                            text: chip.modelData
                            color: chip.isCurrent ? Theme.onAccent : Theme.muted
                            font.pixelSize: Theme.fontSizeSm
                            textFormat: Text.PlainText
                        }
                    }
                }
                Item { Layout.fillWidth: true }
            }

            AppDataTable {
                Layout.fillWidth: true
                Layout.preferredHeight: 220
                title: "Transitions"
                icon: "list"
                columns: root.transitionColumns
                model: machine ? machine.transitions : null
                rowAccent: root.transitionRowAccent
                emptyText: "No transitions recorded yet"
            }
        }
    }

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

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth

            ColumnLayout {
                width: parent ? parent.width : 0
                spacing: Theme.spaceLg

                // -- Dead-letter queue ------------------------------------
                Text {
                    text: "Dead letters"
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeMd
                    font.bold: true
                    textFormat: Text.PlainText
                }

                Rectangle {
                    visible: root.deadLetters.length === 0
                    Layout.fillWidth: true
                    Layout.maximumWidth: 1000
                    implicitHeight: emptyDlqColumn.implicitHeight + Theme.spaceLg * 2
                    color: Theme.bgCard
                    border.color: Theme.border
                    border.width: 1

                    ColumnLayout {
                        id: emptyDlqColumn
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: Theme.spaceLg
                        spacing: Theme.spaceXs

                        Text {
                            text: "+"
                            color: Theme.muted
                            font.pixelSize: Theme.fontSizeLg
                            textFormat: Text.PlainText
                        }
                        Text {
                            text: root.notAttached ? "Not attached — nothing to show" : "Dead-letter queue empty"
                            color: Theme.textPrimary
                            font.bold: true
                            font.pixelSize: Theme.fontSizeMd
                            textFormat: Text.PlainText
                        }
                        Text {
                            visible: !root.notAttached
                            Layout.fillWidth: true
                            text: "Nothing has exhausted its retries since attach. This is a live"
                                + " confirmation from the current snapshot, not an absence of data."
                            color: Theme.muted
                            font.pixelSize: Theme.fontSizeSm
                            wrapMode: Text.Wrap
                            textFormat: Text.PlainText
                        }
                    }
                }

                Repeater {
                    model: root.deadLetters
                    delegate: DeadLetterCard {
                        required property var modelData
                        entry: modelData
                    }
                }

                // -- State machines ----------------------------------------
                Text {
                    text: "Watched machines"
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeMd
                    font.bold: true
                    textFormat: Text.PlainText
                }

                Rectangle {
                    visible: root.stateMachines.length === 0
                    Layout.fillWidth: true
                    Layout.maximumWidth: 1000
                    implicitHeight: emptyMachinesColumn.implicitHeight + Theme.spaceLg * 2
                    color: Theme.bgCard
                    border.color: Theme.border
                    border.width: 1

                    ColumnLayout {
                        id: emptyMachinesColumn
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: Theme.spaceLg
                        spacing: Theme.spaceXs

                        Text {
                            text: root.notAttached ? "Not attached — nothing to show" : "Nothing being watched"
                            color: Theme.textPrimary
                            font.bold: true
                            font.pixelSize: Theme.fontSizeMd
                            textFormat: Text.PlainText
                        }
                        Text {
                            visible: !root.notAttached
                            Layout.fillWidth: true
                            text: "The backend reports no state machines under observation. Machines are"
                                + " opt-in by name on the host side — this is a healthy, deliberate zero."
                            color: Theme.muted
                            font.pixelSize: Theme.fontSizeSm
                            wrapMode: Text.Wrap
                            textFormat: Text.PlainText
                        }
                    }
                }

                Repeater {
                    model: root.stateMachines
                    delegate: MachineCard {
                        required property var modelData
                        machine: modelData
                    }
                }

                // -- UI-thread health -- absent, not zeroed, for a non-pyside app
                Text {
                    visible: viewModel && viewModel.hasUiThreadHealth
                    text: "UI thread"
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeMd
                    font.bold: true
                    textFormat: Text.PlainText
                }

                RowLayout {
                    visible: viewModel && viewModel.hasUiThreadHealth
                    Layout.fillWidth: true
                    spacing: Theme.spaceLg

                    BaseCard {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 130
                        title: "UI thread freezes"
                        icon: "activity"

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spaceMd
                            spacing: Theme.spaceXs
                            Text {
                                text: viewModel ? String(viewModel.freezeCount) : "0"
                                color: viewModel && viewModel.freezeCount > 0 ? Theme.danger : Theme.textPrimary
                                font.pixelSize: 46
                                font.bold: true
                                textFormat: Text.PlainText
                            }
                            Text {
                                text: "dispatcher stalls > 250ms"
                                color: Theme.muted
                                font.pixelSize: Theme.fontSizeSm
                                wrapMode: Text.Wrap
                                textFormat: Text.PlainText
                            }
                        }
                    }
                    BaseCard {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 130
                        title: "Longest freeze"
                        icon: "clock"

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spaceMd
                            spacing: Theme.spaceXs
                            Text {
                                text: (viewModel ? viewModel.worstFreezeMs.toFixed(0) : "0") + "ms"
                                color: viewModel && viewModel.worstFreezeMs > 0 ? Theme.danger : Theme.textPrimary
                                font.pixelSize: 46
                                font.bold: true
                                textFormat: Text.PlainText
                            }
                            Text {
                                text: "single worst stall"
                                color: Theme.muted
                                font.pixelSize: Theme.fontSizeSm
                                wrapMode: Text.Wrap
                                textFormat: Text.PlainText
                            }
                        }
                    }
                    BaseCard {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 130
                        title: "Cross-thread touches"
                        icon: "alert-triangle"

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: Theme.spaceMd
                            spacing: Theme.spaceXs
                            Text {
                                text: viewModel ? String(viewModel.offThreadMutationCount) : "0"
                                color: viewModel && viewModel.offThreadMutationCount > 0 ? Theme.danger : Theme.textPrimary
                                font.pixelSize: 46
                                font.bold: true
                                textFormat: Text.PlainText
                            }
                            Text {
                                text: "UI mutated off the dispatcher"
                                color: Theme.muted
                                font.pixelSize: Theme.fontSizeSm
                                wrapMode: Text.Wrap
                                textFormat: Text.PlainText
                            }
                        }
                    }
                }

                Text {
                    visible: viewModel && viewModel.hasUiThreadHealth
                        && viewModel.freezeCount === 0 && viewModel.offThreadMutationCount === 0
                    Layout.fillWidth: true
                    text: "Measured since attach, and clean: zero here means watched and healthy,"
                        + " not unmeasured."
                    color: Theme.muted
                    font.pixelSize: Theme.fontSizeSm
                    wrapMode: Text.Wrap
                    textFormat: Text.PlainText
                }

                Item { Layout.preferredHeight: Theme.spaceLg }
            }
        }
    }
}
