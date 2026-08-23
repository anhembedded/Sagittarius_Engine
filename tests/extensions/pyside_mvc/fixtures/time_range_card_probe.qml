import QtQuick
import Sagittarius.UI 1.0

// Minimal probe: a TimeRangeCard wired to plain properties (not a real
// ViewModel) so a test can drive useCustomTime/from/to and assert the
// signals it emits when the user (or, here, a test) clicks Clear.
Item {
    id: root
    width: 340
    height: 220

    property bool useCustomTime: true
    property string fromDateTime: "2020-01-01 00:00"
    property string toDateTime: "2030-01-01 00:00"

    TimeRangeCard {
        id: card
        objectName: "probeTimeRangeCard"
        useCustomTime: root.useCustomTime
        fromDateTime: root.fromDateTime
        toDateTime: root.toDateTime

        onCustomTimeToggled: (checked) => root.useCustomTime = checked
        onFromDateTimeEdited: (text) => root.fromDateTime = text
        onToDateTimeEdited: (text) => root.toDateTime = text
    }
}
