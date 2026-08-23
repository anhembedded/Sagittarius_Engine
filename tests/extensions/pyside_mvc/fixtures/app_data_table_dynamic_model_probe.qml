import QtQuick
import Sagittarius.UI 1.0

// Starts with an EMPTY model, populated later via root.tableModel -- unlike
// app_data_table_probe.qml (data set once at construction), this exercises
// the empty -> non-empty model transition that a real screen's ViewModel
// goes through (data arrives asynchronously after the screen first loads).
Item {
    id: root
    width: 600
    height: 200

    property var tableModel: []

    AppDataTable {
        objectName: "table"
        anchors.fill: parent
        columns: [
            { key: "a", title: "A" },
            { key: "b", title: "B" }
        ]
        model: root.tableModel
    }
}
