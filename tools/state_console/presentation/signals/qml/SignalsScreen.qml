import QtQuick
import QtQuick.Layouts
import Sagittarius.UI 1.0

// Signals -- EPIC-007E section 3: dead-letter queue and state machines.
// StateSnapshot carries no field for either yet (that is EPIC-007F's
// work), so this screen says so honestly instead of rendering an empty
// table -- the same "not attached" discipline EPIC-005 section 2's D1
// exists to enforce, applied to a missing data source instead of a
// missing connection.
Rectangle {
    id: root
    color: Theme.bg

    readonly property bool notAttached: !viewModel || viewModel.connectionState === "not_attached"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spaceLg
        spacing: Theme.spaceLg

        BaseCard {
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: "Signals"
            icon: "activity"

            ColumnLayout {
                anchors.centerIn: parent
                spacing: Theme.spaceSm

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: root.notAttached
                          ? "Not attached — nothing to show"
                          : "Dead-letter queue and state machines — coming in EPIC-007F"
                    color: Theme.muted
                    font.pixelSize: Theme.fontSizeMd
                    textFormat: Text.PlainText
                }
            }
        }
    }
}
