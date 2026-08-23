import QtQuick
import Sagittarius.UI 1.0

// Minimal probe: a lone DateTimePicker. The calendar popup itself
// (objectName "calendarPopup") must be opened via its own open() method
// from the test -- it is not visible until then, same as real usage.
Item {
    id: root
    width: 260
    height: 400

    property string text: "2020-01-01 00:00"

    DateTimePicker {
        id: picker
        objectName: "probeDateTimePicker"
        text: root.text
        onTextEdited: (value) => root.text = value
    }
}
