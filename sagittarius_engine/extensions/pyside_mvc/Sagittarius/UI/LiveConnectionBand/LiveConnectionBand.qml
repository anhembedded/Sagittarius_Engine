import QtQuick
import QtQuick.Layouts
import Sagittarius.UI 1.0

// `EPIC-008A` — the always-visible status band a console-style tool shows
// above its content: "am I attached to a live source right now, and if
// not, why?" (reference/handoff.md §4). Built directly on Rectangle/
// RowLayout, like StatefulButton.qml is built directly on Button — this
// IS the kit, not a consumer reaching past it (ui-architecture.md §1.1's
// escape-hatch restriction is for consumer code, not for a new component
// being added to the kit itself).
//
// Tiered per ui-architecture.md §1.2: `state` is a small closed vocabulary
// this component owns colour/pulse-speed for (tier 1) — a consumer never
// passes a colour. Every piece of TEXT is tier 2 (supplied per use,
// because "what is on the other end of this connection" is tier 3 — the
// component knows a `state` enum and strings to show, nothing about
// backends, sockets, or snapshots).
//
// Usage:
//     LiveConnectionBand {
//         state: "reading"                    // one of: reading, idle,
//                                              // connecting, failed,
//                                              // stale, cold
//         stateLabel: "Attached · reading"
//         stateNote: "snapshot stream live · ~1/s"
//         ageLabel: "last snapshot"
//         ageValue: "00:01 ago"
//         targetText: "ws://127.0.0.1:8781"
//         actionLabel: "Detach"
//         heartbeatTicks: [0.2, 0.6, 0.9, 0.4, 1.0]   // newest last
//         onActionRequested: connection.detach()
//         onChangeTargetRequested: connectFlow.open()
//     }
Rectangle {
    id: root
    implicitHeight: 62
    color: Theme.surface

    //: One of "reading"/"idle"/"connecting"/"failed"/"stale"/"cold" — the
    //: six-state connection model. Anything else falls back to the
    //: `Theme.muted` mapping below rather than raising, so a consumer
    //: typo reads as "obviously wrong grey", not a crash.
    property string state: "cold"
    property string stateLabel: ""
    property string stateNote: ""
    property string ageLabel: ""
    property string ageValue: ""
    property string targetText: ""
    property string actionLabel: ""
    //: Newest-last activity samples in [0, 1] — one appended per received
    //: snapshot. This component only draws whatever numbers it is handed;
    //: it has no notion of what produced them (tier 3).
    property var heartbeatTicks: []
    property int maxHeartbeatTicks: 44

    signal actionRequested()
    signal changeTargetRequested()

    //: Named so it is directly invokable (incl. from a test) with no
    //: argument, the same reasoning `AppRail._selectRow(id)` documents —
    //: a plain QML `function` is a far more permissive invocation target
    //: than a C++ signal like `MouseArea.clicked(mouse)`, which needs a
    //: real `QQuickMouseEvent` no test can construct. Applied here
    //: retroactively: this component predates `AppRail`, so its own
    //: change-target click shipped untested (see the "reviewed by
    //: inspection" note this replaces in `test_live_connection_band.py`)
    //: before that pattern existed.
    function _requestChangeTarget() {
        root.changeTargetRequested()
    }

    readonly property var _stateColors: ({
        reading: Theme.accent,
        idle: Theme.accent700,
        connecting: Theme.accent700,
        failed: Theme.danger,
        stale: Theme.danger,
        cold: Theme.danger
    })
    readonly property color _stateColor: root._stateColors[root.state] || Theme.muted

    //: Pulse period in ms per state; a state absent from this map (stale/
    //: failed/cold) does not pulse at all — reference/handoff.md §8's own
    //: animation table lists a duration only for reading/idle/connecting
    //: ("none otherwise").
    readonly property var _pulseDurations: ({
        reading: 1000,
        idle: 1600,
        connecting: 700
    })
    readonly property int _pulseDuration: root._pulseDurations[root.state] || 0

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            objectName: "connectionStateStripe"
            Layout.preferredWidth: 5
            Layout.fillHeight: true
            color: root._stateColor
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: Theme.spaceLg
            Layout.rightMargin: Theme.spaceLg
            spacing: Theme.spaceLg

            Rectangle {
                id: stateDot
                objectName: "connectionStateDot"
                width: 10
                height: 10
                radius: 5
                color: root._stateColor

                SequentialAnimation on opacity {
                    running: root._pulseDuration > 0
                    loops: Animation.Infinite
                    NumberAnimation { from: 1.0; to: 0.25; duration: root._pulseDuration / 2 }
                    NumberAnimation { from: 0.25; to: 1.0; duration: root._pulseDuration / 2 }
                }
            }

            ColumnLayout {
                spacing: 2

                Text {
                    objectName: "connectionStateLabel"
                    text: root.stateLabel
                    color: root._stateColor
                    font.pixelSize: Theme.fontSizeMd
                    font.bold: true
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                }
                Text {
                    objectName: "connectionStateNote"
                    text: root.stateNote
                    color: Theme.muted
                    font.pixelSize: Theme.fontSizeSm
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                }
            }

            //: The heartbeat ribbon — one tick per received snapshot, newest
            //: on the right and full-opacity; older ticks fade. A flat row
            //: (empty `heartbeatTicks`) reads as "not currently reading",
            //: which is already true by construction — a consumer only
            //: feeds ticks while attached and reading.
            Row {
                id: ribbon
                objectName: "heartbeatRibbon"
                Layout.preferredWidth: root.maxHeartbeatTicks * 4
                Layout.fillHeight: true
                spacing: 2

                Repeater {
                    model: root.heartbeatTicks
                    delegate: Rectangle {
                        id: tick
                        objectName: "heartbeatTick"
                        required property var modelData
                        required property int index
                        anchors.bottom: parent ? parent.bottom : undefined
                        width: 3
                        height: Math.max(4, modelData * 24)
                        color: root._stateColor
                        opacity: tick.index === root.heartbeatTicks.length - 1 ? 1.0 : 0.35
                    }
                }
            }

            ColumnLayout {
                spacing: 2

                Text {
                    objectName: "connectionAgeLabel"
                    text: root.ageLabel
                    color: Theme.muted
                    font.pixelSize: Theme.fontSizeSm
                    textFormat: Text.PlainText
                }
                Text {
                    objectName: "connectionAgeValue"
                    text: root.ageValue
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeMd
                    textFormat: Text.PlainText
                }
            }

            Item { Layout.fillWidth: true }

            RowLayout {
                spacing: Theme.spaceSm

                Text {
                    objectName: "connectionTargetText"
                    text: root.targetText
                    color: Theme.textPrimary
                    font.family: Theme.fontFamilyMono
                    font.pixelSize: Theme.fontSizeSm
                    textFormat: Text.PlainText
                    elide: Text.ElideMiddle
                    Layout.maximumWidth: 260
                }
                Text {
                    objectName: "connectionChangeTargetLink"
                    text: "change…"
                    color: Theme.accent
                    font.pixelSize: Theme.fontSizeSm
                    textFormat: Text.PlainText

                    MouseArea {
                        objectName: "connectionChangeTargetArea"
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root._requestChangeTarget()
                    }
                }
            }

            StatefulButton {
                objectName: "connectionActionButton"
                text: root.actionLabel
                onClicked: root.actionRequested()
            }
        }
    }
}
