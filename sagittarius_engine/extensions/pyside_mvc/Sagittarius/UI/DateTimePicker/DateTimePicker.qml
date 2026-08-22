import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Sagittarius.UI 1.0

// A reusable DateTime picker component with a manual text field and a popup calendar.
// Supports manual typing ("yyyy-MM-dd HH:mm") or picking via a Windows-like popup calendar.
Item {
    id: control

    property string text: ""
    property string placeholderText: "yyyy-MM-dd HH:mm"
    property bool readOnly: false

    signal textEdited(string text)

    implicitWidth: 200
    implicitHeight: 32

    // Internal date state
    property var selectedDate: new Date()
    property bool _updatingText: false

    // Sync text changes -> selectedDate
    onTextChanged: {
        if (_updatingText) return;
        let parsed = Date.parse(control.text.replace(" ", "T"));
        if (!isNaN(parsed)) {
            selectedDate = new Date(parsed);
            if (!calendarPopup.opened) {
                updateCalendarFromDate();
            }
        }
    }

    function updateCalendarFromDate() {
        monthGrid.month = selectedDate.getMonth();
        monthGrid.year = selectedDate.getFullYear();
        spinHour.value = selectedDate.getHours();
        spinMinute.value = selectedDate.getMinutes();
    }

    function formatDate(d) {
        let pad = function(n) { return n < 10 ? '0' + n : n; };
        return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
               ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
    }

    function parseAndApplyText(str) {
        let match = str.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})$/);
        if (match) {
            let d = new Date(parseInt(match[1]), parseInt(match[2]) - 1, parseInt(match[3]), parseInt(match[4]), parseInt(match[5]));
            if (!isNaN(d.getTime())) {
                selectedDate = d;
                _updatingText = true;
                control.text = formatDate(d);
                _updatingText = false;
                updateCalendarFromDate();
                return true;
            }
        }
        return false;
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        TextField {
            id: textField
            Layout.fillWidth: true
            Layout.fillHeight: true
            placeholderText: control.placeholderText
            color: Theme.textPrimary
            font.pixelSize: 12
            enabled: control.enabled
            readOnly: control.readOnly

            background: FieldBackground {
                // To merge seamlessly with the right button, hide right border
                Rectangle {
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: 1
                    color: Theme.bgCard
                }
            }

            text: control.text
            onTextEdited: {
                // Update parent text immediately so bindings work, but we only "chug" it on editingFinished
                _updatingText = true;
                control.text = text;
                _updatingText = false;
                control.textEdited(text);
            }

            onEditingFinished: {
                if (text === "") {
                    _updatingText = true;
                    control.text = "";
                    _updatingText = false;
                } else {
                    if (!parseAndApplyText(text)) {
                        // Revert to valid text
                        text = control.text;
                    }
                }
            }
        }

        Button {
            id: calendarButton
            Layout.preferredWidth: 32
            Layout.fillHeight: true
            enabled: control.enabled

            contentItem: Image {
                source: "image://icons/clock/muted"
                fillMode: Image.PreserveAspectFit
                sourceSize.width: 14
                sourceSize.height: 14
                horizontalAlignment: Image.AlignHCenter
                verticalAlignment: Image.AlignVCenter
                opacity: calendarButton.enabled ? 1.0 : 0.4
            }

            background: Rectangle {
                // Bespoke idle shade, distinct from every existing state/bg
                // token — tokenizing it would silently change the look;
                // needs a real design decision, not a drive-by remap.
                color: calendarButton.hovered && calendarButton.enabled ? Theme.stateHoverBg : "#131418"  // token-exempt
                border.width: 1
                border.color: Theme.border
                radius: 4
                // square left corners
                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: 4
                    color: parent.color
                }
                opacity: calendarButton.enabled ? 1.0 : 0.6
            }

            onClicked: {
                if (calendarPopup.opened) {
                    calendarPopup.close();
                } else {
                    if (control.text !== "") {
                        parseAndApplyText(control.text);
                    } else {
                        // Default to now
                        selectedDate = new Date();
                        updateCalendarFromDate();
                    }
                    calendarPopup.open();
                }
            }
        }
    }

    Popup {
        id: calendarPopup
        y: control.height + 4
        x: control.width - width
        width: 260
        padding: 12
        
        background: Rectangle {
            color: Theme.bgCard
            border.color: Theme.border
            border.width: 1
            radius: 8
        }

        contentItem: ColumnLayout {
            spacing: 12

            // Header (Month / Year)
            RowLayout {
                Layout.fillWidth: true
                Button {
                    text: "‹"
                    implicitWidth: 24
                    implicitHeight: 24
                    contentItem: Text { 
                        text: parent.text; color: Theme.textPrimary; 
                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter;
                        font.pixelSize: 14
                    }
                    background: Rectangle { color: parent.hovered ? Theme.stateHoverBg : "transparent"; radius: 4 }
                    onClicked: {
                        if (monthGrid.month === 0) {
                            monthGrid.month = 11;
                            monthGrid.year--;
                        } else {
                            monthGrid.month--;
                        }
                    }
                }
                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: Qt.formatDateTime(new Date(monthGrid.year, monthGrid.month, 1), "MMMM yyyy")
                    color: Theme.textPrimary
                    font.pixelSize: 12
                    font.bold: true
                }
                Button {
                    text: "›"
                    implicitWidth: 24
                    implicitHeight: 24
                    contentItem: Text { 
                        text: parent.text; color: Theme.textPrimary; 
                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter;
                        font.pixelSize: 14
                    }
                    background: Rectangle { color: parent.hovered ? Theme.stateHoverBg : "transparent"; radius: 4 }
                    onClicked: {
                        if (monthGrid.month === 11) {
                            monthGrid.month = 0;
                            monthGrid.year++;
                        } else {
                            monthGrid.month++;
                        }
                    }
                }
            }

            // Days of week
            DayOfWeekRow {
                locale: monthGrid.locale
                Layout.fillWidth: true
                delegate: Text {
                    text: model.shortName
                    color: Theme.muted
                    font.pixelSize: 10
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                }
            }

            // Month Grid
            MonthGrid {
                id: monthGrid
                Layout.fillWidth: true
                month: control.selectedDate.getMonth()
                year: control.selectedDate.getFullYear()

                delegate: Rectangle {
                    implicitWidth: 32
                    implicitHeight: 32
                    radius: 16
                    
                    property bool isSelected: model.month === monthGrid.month && 
                                              model.day === control.selectedDate.getDate() && 
                                              monthGrid.year === control.selectedDate.getFullYear()

                    color: isSelected ? Theme.accent : (hoverHandler.hovered ? Theme.stateHoverBg : "transparent")

                    Text {
                        anchors.centerIn: parent
                        text: model.day
                        // Selected-day white and other-month grey are
                        // bespoke contrast shades with no matching semantic
                        // token today — same reasoning as the idle-bg
                        // exemption above.
                        color: parent.isSelected ? "#ffffff" : (model.month === monthGrid.month ? Theme.textPrimary : "#4b5162")  // token-exempt
                        font.pixelSize: 11
                    }

                    HoverHandler { id: hoverHandler }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            // Update internal date state without closing popup yet
                            let d = new Date(model.year, model.month, model.day, spinHour.value, spinMinute.value);
                            control.selectedDate = d;
                            monthGrid.month = model.month;
                            monthGrid.year = model.year;
                        }
                    }
                }
            }

            // Time Spinners
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Item { Layout.fillWidth: true } // spacer left

                Text {
                    text: "Time"
                    color: Theme.muted
                    font.pixelSize: 11
                }

                // Custom simple spinbox alternative using TextField for Hour
                TextField {
                    id: spinHour
                    property int value: 0
                    Layout.preferredWidth: 36
                    Layout.preferredHeight: 24
                    text: (value < 10 ? "0" : "") + value
                    color: Theme.textPrimary
                    font.pixelSize: 12
                    horizontalAlignment: TextInput.AlignHCenter
                    background: FieldBackground { implicitHeight: 24 }
                    validator: IntValidator { bottom: 0; top: 23 }
                    onEditingFinished: {
                        let parsed = parseInt(text);
                        if (!isNaN(parsed) && parsed >= 0 && parsed <= 23) {
                            value = parsed;
                        } else {
                            text = (value < 10 ? "0" : "") + value;
                        }
                    }
                }

                Text {
                    text: ":"
                    color: Theme.textPrimary
                    font.pixelSize: 12
                }

                // Minute
                TextField {
                    id: spinMinute
                    property int value: 0
                    Layout.preferredWidth: 36
                    Layout.preferredHeight: 24
                    text: (value < 10 ? "0" : "") + value
                    color: Theme.textPrimary
                    font.pixelSize: 12
                    horizontalAlignment: TextInput.AlignHCenter
                    background: FieldBackground { implicitHeight: 24 }
                    validator: IntValidator { bottom: 0; top: 59 }
                    onEditingFinished: {
                        let parsed = parseInt(text);
                        if (!isNaN(parsed) && parsed >= 0 && parsed <= 59) {
                            value = parsed;
                        } else {
                            text = (value < 10 ? "0" : "") + value;
                        }
                    }
                }
                Item { Layout.fillWidth: true } // spacer right
            }

            // Footer
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 4
                Item { Layout.fillWidth: true } // spacer
                Button {
                    text: "Apply"
                    contentItem: Text {
                        text: parent.text
                        color: Theme.bg
                        font.pixelSize: 11
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        implicitHeight: 24
                        implicitWidth: 60
                        color: Theme.accent
                        radius: 4
                        opacity: parent.hovered ? 0.9 : 1.0
                    }
                    onClicked: {
                        // Complete editing hour/minute if focused
                        spinHour.editingFinished();
                        spinMinute.editingFinished();
                        
                        let d = new Date(control.selectedDate);
                        d.setHours(spinHour.value);
                        d.setMinutes(spinMinute.value);
                        control.selectedDate = d;
                        
                        control._updatingText = true;
                        control.text = control.formatDate(d);
                        control._updatingText = false;
                        
                        // Fire an edit signal so users know text changed via popup
                        control.textEdited(control.text);
                        
                        calendarPopup.close();
                    }
                }
            }
        }
    }
}
