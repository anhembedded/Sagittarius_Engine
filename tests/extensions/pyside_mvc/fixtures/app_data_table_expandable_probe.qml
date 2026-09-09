import QtQuick
import Sagittarius.UI 1.0

// EPIC-008A: per-row expansion, tracked by identity (`rowIdKey`) not index.
// Row "row-2" is the only one `expandPredicate` allows to expand, mirroring
// the real use case (only a Failed task's row opens).
AppDataTable {
    objectName: "table"
    width: 600
    height: 200
    rowIdKey: "id"
    columns: [
        { key: "name", title: "Name" },
        { key: "state", title: "State" }
    ]
    model: [
        { id: "row-1", name: "alpha", state: "Running" },
        { id: "row-2", name: "beta", state: "Failed" }
    ]
    expandPredicate: function (row) { return row.state === "Failed" }
    expandedDelegate: Component {
        Rectangle {
            objectName: "expansionProbe"
            property var rowData: null
            width: parent ? parent.width : 0
            height: 40

            Text {
                objectName: "expansionProbeText"
                text: rowData ? rowData.name : ""
            }
        }
    }
}
