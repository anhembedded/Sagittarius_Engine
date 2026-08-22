import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Sagittarius.UI 1.0

BaseCard {
    id: root

    property bool useCustomTime: false
    property string fromDateTime: ""
    property string toDateTime: ""
    property bool readOnly: false

    signal customTimeToggled(bool checked)
    signal fromDateTimeEdited(string text)
    signal toDateTimeEdited(string text)

    // Optional: allow hiding the title
    property string title: "TIME RANGE"

    color: Theme.bgCard
    border.color: Theme.border
    border.width: 1
    radius: 8

    implicitHeight: layout.implicitHeight + 28
    implicitWidth: 300

    function setDisabled(disabled) {
        opacity = disabled ? 0.6 : 1.0
        root.readOnly = disabled
    }

    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: 14
        spacing: 10

        Text {
            text: root.title
            color: Theme.accent
            font.pixelSize: 11
            font.bold: true
            font.letterSpacing: 1
            Layout.fillWidth: true
            visible: root.title !== ""
        }

        Switch {
            id: customTimeSwitch
            text: "Use Custom Time Range"
            checked: root.useCustomTime
            enabled: !root.readOnly
            onToggled: root.customTimeToggled(checked)
            contentItem: Text {
                leftPadding: customTimeSwitch.indicator.width + 8
                text: customTimeSwitch.text
                color: Theme.textPrimary
                font.pixelSize: 12
                verticalAlignment: Text.AlignVCenter
            }
            indicator: Rectangle {
                implicitWidth: 36
                implicitHeight: 20
                y: (customTimeSwitch.height - height) / 2
                radius: 10
                color: customTimeSwitch.checked ? Theme.accent : Theme.stateIdleBg
                border.color: customTimeSwitch.checked ? Theme.accent : Theme.border
                
                Rectangle {
                    x: customTimeSwitch.checked ? parent.width - width - 2 : 2
                    y: 2
                    width: 16
                    height: 16
                    radius: 8
                    color: Theme.textPrimary
                    
                    Behavior on x { NumberAnimation { duration: 150; easing.type: Easing.InOutQuad } }
                }
            }
        }

        DateTimePicker {
            Layout.fillWidth: true
            enabled: root.useCustomTime && !root.readOnly
            text: root.fromDateTime
            onTextEdited: (text) => root.fromDateTimeEdited(text)
            placeholderText: "From  yyyy-MM-dd HH:mm"
        }

        DateTimePicker {
            Layout.fillWidth: true
            enabled: root.useCustomTime && !root.readOnly
            text: root.toDateTime
            onTextEdited: (text) => root.toDateTimeEdited(text)
            placeholderText: "To  yyyy-MM-dd HH:mm"
        }
    }
}
