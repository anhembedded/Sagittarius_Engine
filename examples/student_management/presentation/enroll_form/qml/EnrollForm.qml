import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Sagittarius.UI 1.0

// IView prototype (TASK: dual QML/QWidget rendering) -- deliberately the
// smallest real screen in this app: 3 text fields + a GPA field + one
// button, nothing else. Its QWidget counterpart (WidgetEnrollFormView)
// builds the equivalent with a QFormLayout; both drive the exact same
// EnrollFormViewModel/EnrollFormPresenter with no changes to either.
Rectangle {
    id: root
    color: Theme.bg
    implicitWidth: 360
    implicitHeight: 260

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spaceLg
        spacing: Theme.spaceSm

        Text {
            text: "Enroll Student"
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeLg
            font.bold: true
        }

        TextField {
            id: fullNameField
            Layout.fillWidth: true
            placeholderText: "Full name"
            text: viewModel.fullName
            background: FieldBackground {}
            onTextEdited: viewModel.fullName = text
        }

        TextField {
            id: emailField
            Layout.fillWidth: true
            placeholderText: "Email"
            text: viewModel.email
            background: FieldBackground {}
            onTextEdited: viewModel.email = text
        }

        TextField {
            id: majorField
            Layout.fillWidth: true
            placeholderText: "Major"
            text: viewModel.major
            background: FieldBackground {}
            onTextEdited: viewModel.major = text
        }

        TextField {
            id: gpaField
            Layout.fillWidth: true
            placeholderText: "GPA (0.0 - 4.0)"
            text: viewModel.gpa === 0.0 ? "" : String(viewModel.gpa)
            background: FieldBackground {}
            onTextEdited: viewModel.gpa = parseFloat(text) || 0.0
        }

        Item { Layout.fillHeight: true }

        StatefulButton {
            objectName: "btnSubmitEnrollForm"
            text: "Enroll"
            accentBorder: Theme.success
            Layout.alignment: Qt.AlignRight
            onClicked: viewModel.submit()
        }
    }
}
