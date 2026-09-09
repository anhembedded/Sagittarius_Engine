import QtQuick
import QtQuick.Layouts
import Sagittarius.UI 1.0

// Container -- EPIC-007E section 3, restyled by EPIC-008B subtask D onto
// reference/handoff.md §7.4: sortable Registrations/Never-built tables
// (one persistent AppDataTable, filtered, so a sort survives both a
// refresh and a tab switch -- same shape EventsScreen.qml already uses)
// and an Open-scopes plate with real fault-threshold styling.
//
// The Open-scopes *table* (`scope · age · resolved in this scope`) is not
// built: ContainerState carries only a count, not per-scope identity or
// age -- adding that means tracking scope creation in the container
// runtime itself, a bigger change than exposing data a collector already
// has access to (this repo's own EPIC-008B §4 precedent for "extend the
// wire protocol"). Left as a real, named gap rather than approximated.
//
// Unbound dependencies and cycles are WiringInspector findings, not part
// of StateSnapshot yet (EPIC-007C's own documented gap) -- still not shown
// here because there is nothing to show honestly.
Rectangle {
    id: root
    color: Theme.bg

    readonly property bool notAttached: !viewModel || viewModel.connectionState === "not_attached"
    readonly property var allRegistrations: viewModel ? viewModel.registrations : []
    readonly property var neverBuiltRegistrations: root.allRegistrations.filter(function(r) { return !r.instantiated })

    property string activeTab: "registrations"
    readonly property var filteredRegistrations: root.activeTab === "neverBuilt" ? root.neverBuiltRegistrations : root.allRegistrations

    //: reference/handoff.md §7.4's own threshold: the open-scopes count (and,
    //: in the full design, its table rows) turns fault above this.
    readonly property int openScopesFaultThreshold: 24
    readonly property bool openScopesFault: viewModel && viewModel.openScopes > root.openScopesFaultThreshold

    readonly property var registrationColumns: [
        { key: "abstract", title: "Abstraction", weight: 3 },
        { key: "concrete", title: "Implementation", weight: 3 },
        {
            key: "lifetime", title: "Lifetime", weight: 1,
            formatter: function(v) { return v ? v.charAt(0).toUpperCase() + v.slice(1) : "" }
        },
        {
            key: "instantiated", title: "Instance", weight: 2,
            formatter: function(v) { return v ? "instance built" : "never resolved" }
        }
    ]

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spaceLg
        spacing: Theme.spaceLg

        Text {
            text: "Container"
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeLg
            font.bold: true
            textFormat: Text.PlainText
        }

        SectionSubTabs {
            Layout.fillWidth: true
            activeTabId: root.activeTab
            tabs: [
                { id: "registrations", label: "Registrations", count: root.allRegistrations.length },
                { id: "neverBuilt", label: "Never built", count: root.neverBuiltRegistrations.length },
                { id: "openScopes", label: "Open scopes", count: viewModel ? viewModel.openScopes : 0 }
            ]
            onTabSelected: (id) => root.activeTab = id
        }

        AppDataTable {
            visible: root.activeTab === "registrations" || root.activeTab === "neverBuilt"
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: "Registrations"
            icon: "box"
            columns: root.registrationColumns
            model: root.filteredRegistrations
            emptyText: root.notAttached
                ? "Not attached — nothing to show"
                : (root.activeTab === "neverBuilt"
                    ? "Every registration has been resolved at least once"
                    : "No registrations reported")
        }

        ColumnLayout {
            visible: root.activeTab === "openScopes"
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.spaceMd

            Rectangle {
                Layout.preferredWidth: 330
                Layout.preferredHeight: 150
                color: Theme.bgCard
                border.color: root.openScopesFault ? Theme.danger : Theme.border
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spaceMd
                    spacing: Theme.spaceXs

                    Text {
                        text: "OPEN SCOPES"
                        color: Theme.muted
                        font.pixelSize: Theme.fontSizeSm
                        font.bold: true
                        textFormat: Text.PlainText
                    }
                    Text {
                        objectName: "containerOpenScopesFigure"
                        text: viewModel ? String(viewModel.openScopes) : "0"
                        color: root.openScopesFault ? Theme.danger : Theme.textPrimary
                        font.pixelSize: Theme.fontSizeXl
                        font.bold: true
                        textFormat: Text.PlainText
                    }
                    Text {
                        objectName: "containerOpenScopesNote"
                        // Three real states, not two: a healthy count below
                        // the threshold reads as churn ("steady"); above it,
                        // "climbing" is only honest while the count is
                        // actually still rising past what it was at attach
                        // -- a leak seeded once, before attach, is elevated
                        // and stuck, not currently climbing, and claiming
                        // either "steady...closed" or "climbing" for that
                        // case would both be a specific, false claim about
                        // what is happening right now.
                        text: !root.openScopesFault
                            ? "steady · opened and closed with each request"
                            : (viewModel && viewModel.openScopesClimbing
                                ? "climbing since attach · none closed"
                                : "elevated since attach · not decreasing")
                        color: root.openScopesFault ? Theme.danger : Theme.muted
                        font.pixelSize: Theme.fontSizeSm
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
                }
            }

            Text {
                Layout.preferredWidth: 480
                text: "A scope should close when the unit of work that opened it ends. A count"
                    + " that only climbs means something is holding one open."
                color: Theme.muted
                font.pixelSize: Theme.fontSizeSm
                wrapMode: Text.Wrap
                textFormat: Text.PlainText
            }

            Item { Layout.fillHeight: true }
        }
    }
}
