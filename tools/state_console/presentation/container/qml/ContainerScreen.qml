import QtQuick
import QtQuick.Layouts
import Sagittarius.UI 1.0

// Container -- EPIC-007E section 3: registrations, lifetimes, what is
// built. Unbound dependencies and cycles are WiringInspector findings, not
// part of StateSnapshot yet (EPIC-007C's own documented gap) -- not shown
// here because there is nothing to show honestly.
Rectangle {
    id: root
    color: Theme.bg

    readonly property bool notAttached: !viewModel || viewModel.connectionState === "not_attached"

    readonly property var registrationColumns: [
        { key: "abstract", title: "Abstract", weight: 3 },
        { key: "concrete", title: "Concrete", weight: 3 },
        { key: "lifetime", title: "Lifetime", weight: 1 },
        {
            key: "instantiated", title: "Built", weight: 1,
            formatter: function(v) { return v ? "yes" : "no" }
        }
    ]

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spaceLg
        spacing: Theme.spaceLg

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spaceMd

            Text {
                text: "Container"
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeLg
                font.bold: true
                textFormat: Text.PlainText
                Layout.fillWidth: true
            }
            Text {
                text: "open scopes: " + (viewModel ? viewModel.openScopes : 0)
                color: Theme.muted
                font.pixelSize: Theme.fontSizeSm
                textFormat: Text.PlainText
            }
        }

        AppDataTable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: "Registrations"
            icon: "box"
            columns: registrationColumns
            model: viewModel ? viewModel.registrations : null
            emptyText: root.notAttached ? "Not attached — nothing to show" : "No registrations reported"
        }
    }
}
