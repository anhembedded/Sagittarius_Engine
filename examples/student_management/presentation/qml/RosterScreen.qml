import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Sagittarius.UI 1.0

// Student roster screen (EPIC-002B) — composes the widget kit for real:
// AppDataTable (roster rows), BaseCard (stats summary, both full and
// compact via one bound toggle, per BaseCard.qml's own documented
// "app-wide philosophy" usage), AppModal (enroll form). All data comes
// from RosterViewModel; this file owns no application logic.
Rectangle {
    id: root
    color: Theme.bg

    readonly property var rosterColumns: [
        { key: "fullName", title: "Name", weight: 3 },
        { key: "email", title: "Email", weight: 3 },
        { key: "major", title: "Major", weight: 2 },
        {
            key: "gpa", title: "GPA", weight: 1, align: Text.AlignRight,
            formatter: function(v) { return Number(v).toFixed(2) }
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
                text: "Student Roster"
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeLg
                font.bold: true
                Layout.fillWidth: true
            }

            Text {
                text: "Compact stats"
                color: Theme.muted
                font.pixelSize: Theme.fontSizeSm
            }
            Switch {
                checked: viewModel.compactMode
                onToggled: viewModel.compactMode = checked
            }

            StatefulButton {
                text: "Enroll Student"
                accentBorder: Theme.accent
                onClicked: enrollModal.open()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spaceLg

            BaseCard {
                id: statsCard
                title: "Roster Stats"
                icon: "chart-bar"
                compact: viewModel.compactMode
                Layout.preferredWidth: compact ? compactSize : 260
                Layout.preferredHeight: compact ? compactSize : 96

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spaceMd
                    spacing: Theme.spaceXs

                    Text {
                        text: "Total: " + viewModel.totalStudents
                        color: Theme.textPrimary
                        font.pixelSize: Theme.fontSizeMd
                    }
                    Text {
                        text: "Average GPA: " + viewModel.averageGpa.toFixed(2)
                        color: Theme.muted
                        font.pixelSize: Theme.fontSizeSm
                    }
                }
            }
        }

        AppDataTable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: "Roster"
            icon: "table"
            columns: rosterColumns
            model: viewModel.students
            emptyText: "No students enrolled yet"
        }
    }

    AppModal {
        id: enrollModal
        title: "Enroll Student"
        actions: [
            StatefulButton { text: "Cancel"; onClicked: enrollModal.close() },
            StatefulButton {
                text: "Enroll"
                accentBorder: Theme.success
                onClicked: {
                    viewModel.requestEnroll(
                        fullNameField.text, emailField.text, majorField.text,
                        parseFloat(gpaField.text) || 0.0
                    )
                    fullNameField.text = ""
                    emailField.text = ""
                    majorField.text = ""
                    gpaField.text = ""
                    enrollModal.close()
                }
            }
        ]

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Theme.spaceSm

            TextField { id: fullNameField; Layout.fillWidth: true; placeholderText: "Full name" }
            TextField { id: emailField; Layout.fillWidth: true; placeholderText: "Email" }
            TextField { id: majorField; Layout.fillWidth: true; placeholderText: "Major" }
            TextField { id: gpaField; Layout.fillWidth: true; placeholderText: "GPA (0.0 - 4.0)" }
        }
    }
}
