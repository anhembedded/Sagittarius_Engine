import QtQuick
import QtQuick.Layouts
import Sagittarius.UI 1.0

// Events & wiring -- EPIC-007E section 3, restyled by EPIC-008B subtask C
// onto reference/handoff.md §7.3: a sortable table (free from AppDataTable
// -- sortKey/sortAscending live on the one persistent instance below, so a
// sort survives both a snapshot refresh and a tab switch), undeclared rows
// tinted via the already-shipped rowAccent hook (no new per-cell colour
// feature -- same reasoning as EPIC-008B §4's Overview restyle), and a
// WIRING BUG banner.
//
// Only two sub-tabs are built (All / Undeclared), not the four
// reference/handoff.md §7 names ("With failures", "Never emitted" too):
// EventCollector's own docstring says `emits`/`failures` are always 0 --
// nothing in this engine counts them per event yet (a RuntimeMonitor gap,
// named there, not invented here). Building tabs against data that can
// never vary would be decoration, not information; this screen's own
// acceptance criteria (sort persistence, undeclared visibility) need
// neither.
Rectangle {
    id: root
    color: Theme.bg

    readonly property bool notAttached: !viewModel || viewModel.connectionState === "not_attached"
    readonly property var allEvents: viewModel ? viewModel.events : []
    readonly property var undeclaredEvents: root.allEvents.filter(function(e) { return !e.registered })

    property string activeTab: "all"
    readonly property var filteredEvents: root.activeTab === "undeclared" ? root.undeclaredEvents : root.allEvents

    // "declaration" placed before the right-aligned numeric columns rather
    // than after -- BUG-013 (the original screen's own finding, reproduced
    // here the same way it originally fixed it for "registered"):
    // AppDataTable renders a right-aligned column immediately followed by
    // a left-aligned one with zero gap between them, fusing the two
    // values (and their headers) into one string.
    readonly property var eventColumns: [
        { key: "name", title: "Event", weight: 3 },
        {
            key: "module", title: "Declared by", weight: 2,
            formatter: function(v) { return v ? v : "—" }
        },
        { key: "declaration", title: "Declaration", weight: 1 },
        { key: "handlerCount", title: "Handlers", weight: 1, align: Text.AlignRight },
        { key: "emits", title: "Emitted", weight: 1, align: Text.AlignRight },
        { key: "failures", title: "Failed", weight: 1, align: Text.AlignRight }
    ]

    function eventRowAccent(row) {
        return row.registered ? null : Theme.danger
    }

    //: `expandedDelegate`'s contract: its root item must declare
    //: `property var rowData` -- AppDataTable keeps it live-bound to the
    //: expanded row's current data via an internal `Binding`.
    //: `Item`, not `Rectangle` -- the tinted background and the detail text
    //: are independent siblings, not parent/child: QML's `opacity` is
    //: multiplicative onto every descendant, so nesting the text inside the
    //: tinted `Rectangle` was making it render at its dim 8% opacity too.
    //: Found via `EPIC-008E`'s own screenshot review of its own, near-
    //: identical `FailedTaskDetail` -- the same mistake, shipped here first.
    component UndeclaredDetail: Item {
        property var rowData: null
        implicitHeight: detailText.implicitHeight + Theme.spaceMd * 2

        Rectangle {
            anchors.fill: parent
            color: Theme.dangerFill
            opacity: 0.08
            border.color: Theme.danger
            border.width: 1
        }

        Text {
            id: detailText
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: Theme.spaceMd
            text: rowData
                ? "subscribed by " + (rowData.handlers.length > 0 ? rowData.handlers.join(", ") : "—")
                    + " · never declared"
                    + (rowData.nearMatch ? " · did you mean “" + rowData.nearMatch + "”?" : "")
                : ""
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeSm
            wrapMode: Text.Wrap
            textFormat: Text.PlainText
        }
    }
    readonly property Component undeclaredDetailComponent: Component { UndeclaredDetail {} }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spaceLg
        spacing: Theme.spaceLg

        Text {
            text: "Events & wiring"
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeLg
            font.bold: true
            textFormat: Text.PlainText
        }

        SectionSubTabs {
            Layout.fillWidth: true
            activeTabId: root.activeTab
            tabs: [
                { id: "all", label: "All", count: root.allEvents.length },
                { id: "undeclared", label: "Undeclared", count: root.undeclaredEvents.length }
            ]
            onTabSelected: (id) => root.activeTab = id
        }

        Item {
            objectName: "eventsWiringBugBanner"
            // reference/handoff.md §7.3: shown "when any undeclared name
            // exists and the tab is All or Undeclared" -- both of this
            // screen's two tabs, so just the first half of that condition.
            visible: root.undeclaredEvents.length > 0
            Layout.fillWidth: true
            implicitHeight: bannerText.implicitHeight + Theme.spaceMd * 2

            // `Item`, not `Rectangle` -- see `UndeclaredDetail`'s own
            // comment above: the tint's opacity must not multiply onto
            // `bannerText` too.
            Rectangle {
                anchors.fill: parent
                color: Theme.dangerFill
                opacity: 0.1
                border.color: Theme.danger
                border.width: 1
            }

            RowLayout {
                anchors.fill: parent
                anchors.margins: Theme.spaceMd
                spacing: Theme.spaceSm

                Rectangle {
                    Layout.alignment: Qt.AlignTop
                    radius: 2
                    color: Theme.dangerFill
                    implicitWidth: stampLabel.implicitWidth + 10
                    implicitHeight: stampLabel.implicitHeight + 6

                    Text {
                        id: stampLabel
                        anchors.centerIn: parent
                        text: "WIRING BUG"
                        color: Theme.onDanger
                        font.bold: true
                        font.pixelSize: Theme.fontSizeSm
                        textFormat: Text.PlainText
                    }
                }
                Text {
                    id: bannerText
                    Layout.fillWidth: true
                    text: root.undeclaredEvents.length + " subscription"
                        + (root.undeclaredEvents.length === 1 ? "" : "s") + " point"
                        + (root.undeclaredEvents.length === 1 ? "s" : "") + " at names that were never"
                        + " declared: " + root.undeclaredEvents.map(function(e) { return e.name }).join(", ")
                        + ". No module ever declared these names, so nothing will ever emit them."
                        + " The subscription is legal, silent, and dead — no error, no log line,"
                        + " just a handler that never runs."
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeSm
                    wrapMode: Text.Wrap
                    textFormat: Text.PlainText
                }
            }
        }

        AppDataTable {
            objectName: "eventsTable"
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: "Declared <-> subscribed"
            icon: "git-branch"
            columns: root.eventColumns
            model: root.filteredEvents
            rowIdKey: "name"
            rowAccent: root.eventRowAccent
            expandedDelegate: root.undeclaredDetailComponent
            expandPredicate: function(row) { return !row.registered }
            emptyText: root.notAttached
                ? "Not attached — nothing to show"
                : (root.activeTab === "undeclared"
                    ? "Every subscribed name is declared"
                    : "No events reported")
        }
    }
}
