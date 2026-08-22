import QtQuick
import Sagittarius.UI 1.0

// Minimal probe: 3 columns, 2 rows, enough to prove the component wires
// columns + model end to end without dragging in a real trading model.
AppDataTable {
    objectName: "table"
    width: 600
    height: 200
    columns: [
        { key: "a", title: "A" },
        { key: "b", title: "B" },
        { key: "c", title: "C" }
    ]
    model: [
        { a: 1, b: 2, c: 3 },
        { a: 4, b: 5, c: 6 }
    ]
}
