import QtQuick
import QtQuick.Layouts
import Sagittarius.UI 1.0

// Events & wiring -- EPIC-007E section 3. The declared <-> subscribed join
// EventCollector (EPIC-007A/C) already computes server-side; this screen
// only renders it.
Rectangle {
    id: root
    color: Theme.bg

    readonly property bool notAttached: !viewModel || viewModel.connectionState === "not_attached"

    // "registered" placed before the right-aligned numeric columns rather
    // than after -- BUG-013: AppDataTable renders a right-aligned column
    // immediately followed by a left-aligned one with zero gap between
    // them, fusing the two values into one string.
    readonly property var eventColumns: [
        { key: "name", title: "Event", weight: 3 },
        { key: "module", title: "Module", weight: 3 },
        {
            key: "registered", title: "Registered", weight: 1,
            formatter: function(v) { return v ? "yes" : "NO" }
        },
        { key: "handlerCount", title: "Handlers", weight: 1, align: Text.AlignRight },
        { key: "emits", title: "Emits", weight: 1, align: Text.AlignRight },
        { key: "failures", title: "Failures", weight: 1, align: Text.AlignRight }
    ]

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

        AppDataTable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: "Declared <-> subscribed"
            icon: "git-branch"
            columns: eventColumns
            model: viewModel ? viewModel.events : null
            emptyText: root.notAttached ? "Not attached — nothing to show" : "No events reported"
        }
    }
}
