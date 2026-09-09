import QtQuick
import QtQuick.Layouts
import Sagittarius.UI 1.0

// `EPIC-008A` — a fixed, always-visible section rail: an indexed list of
// routes, one active at a time, each optionally carrying a small "signal
// count" badge (reference/handoff.md §6's rail: "SECTIONS" label, five
// numbered rows, a fault badge on a row with signals > 0).
//
// Tiered per ui-architecture.md §1.2: sequential numbering and the
// active/hover/badge rendering mechanics are tier 1 (inside this
// component); which sections exist, their labels, and their badge counts
// are tier 2 (`sections`, a plain data array — the same schema-driven
// shape `AppDataTable.columns` already uses, per §3's "data tables are
// schema-driven" reasoning generalized to a nav list). Footer content
// (target/process info, an appearance toggle) is consumer domain — a
// generic `footer` slot, never a hardcoded process/build info-block,
// keeps this component ignorant of what it's a rail for (tier 3).
//
// Usage:
//     AppRail {
//         sections: [
//             { id: "overview", label: "Overview", badgeCount: 0 },
//             { id: "events", label: "Events && wiring", badgeCount: 2 },
//             { id: "signals", label: "Signals", badgeCount: 10 }
//         ]
//         activeSectionId: "overview"
//         onSectionSelected: (id) => shell.navigateTo(id)
//         footer: Text { text: "Read-only." }
//     }
Rectangle {
    id: root
    implicitWidth: 218
    color: Theme.surface

    //: Each entry: `{ id, label, badgeCount (default 0) }`. `badgeCount`
    //: absent or `<= 0` means no badge — a section with nothing wrong
    //: reads as calm, not zeroed-and-shown (`reference/handoff.md`'s own
    //: "zero rows are muted, not hidden" principle, applied here as
    //: "no badge" rather than a "0" badge).
    property var sections: []
    property string activeSectionId: ""
    //: Optional consumer-supplied footer content (target/process info, an
    //: appearance toggle, …) — this component has no opinion on what one
    //: looks like.
    property Item footer: null

    signal sectionSelected(string id)

    //: Named so it is directly invokable (incl. from a test) with a
    //: `QVariant` argument — the same reason `LiveConnectionBand`'s
    //: click-only interactions could NOT be invoked this way. A plain QML
    //: `function` is a far more permissive invocation target than a C++
    //: signal like `MouseArea.clicked(mouse)`.
    function _selectRow(id) {
        root.sectionSelected(id)
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Text {
            objectName: "railHeading"
            text: "SECTIONS"
            color: Theme.muted
            font.pixelSize: Theme.fontSizeSm
            font.bold: true
            font.letterSpacing: 1
            textFormat: Text.PlainText
            Layout.topMargin: Theme.spaceMd
            Layout.leftMargin: Theme.spaceMd
            Layout.bottomMargin: Theme.spaceSm
        }

        Repeater {
            model: root.sections

            delegate: Rectangle {
                id: row
                required property var modelData
                required property int index
                objectName: "railRow_" + row.modelData.id

                readonly property bool active: row.modelData.id === root.activeSectionId
                readonly property int badgeCount: row.modelData.badgeCount || 0

                Layout.fillWidth: true
                Layout.preferredHeight: 36
                color: row.active
                    ? Theme.accent200
                    : (hover.hovered ? Qt.rgba(Theme.inkR / 255, Theme.inkG / 255, Theme.inkB / 255, 0.06) : "transparent")

                Rectangle {
                    visible: row.active
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: 3
                    color: Theme.accent
                }

                HoverHandler { id: hover }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root._selectRow(row.modelData.id)
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.spaceMd
                    anchors.rightMargin: Theme.spaceMd
                    spacing: Theme.spaceSm

                    Text {
                        objectName: "railRowIndex"
                        text: String(row.index + 1).padStart(2, "0")
                        color: Theme.muted
                        font.family: "monospace"
                        font.pixelSize: Theme.fontSizeSm
                        textFormat: Text.PlainText
                    }
                    Text {
                        objectName: "railRowLabel"
                        text: row.modelData.label
                        color: row.active ? Theme.accent900 : Theme.textPrimary
                        font.pixelSize: Theme.fontSizeMd
                        font.bold: true
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    Rectangle {
                        objectName: "railRowBadge"
                        visible: row.badgeCount > 0
                        radius: 2
                        color: Theme.dangerFill
                        implicitWidth: badgeLabel.implicitWidth + 10
                        implicitHeight: badgeLabel.implicitHeight + 6

                        Text {
                            id: badgeLabel
                            anchors.centerIn: parent
                            text: String(row.badgeCount)
                            color: Theme.onDanger
                            font.family: "monospace"
                            font.pixelSize: Theme.fontSizeSm
                            font.bold: true
                            textFormat: Text.PlainText
                        }
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }

        //: A generic slot for consumer-owned footer content — reparented
        //: in via `Binding`, not owned or constructed here (tier 3: this
        //: component has no idea what a "target" or "process" is).
        Item {
            id: footerSlot
            objectName: "railFooterSlot"
            Layout.fillWidth: true
            implicitHeight: root.footer ? root.footer.implicitHeight : 0
        }

        Binding {
            target: root.footer
            property: "parent"
            value: footerSlot
            when: root.footer !== null
        }
        Binding {
            target: root.footer
            property: "width"
            value: footerSlot.width
            when: root.footer !== null
        }
    }
}
