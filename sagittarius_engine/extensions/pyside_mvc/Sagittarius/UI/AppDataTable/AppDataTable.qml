import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Sagittarius.UI 1.0

// Schema-driven data table (EPIC-001C) — column definitions are declarative
// data, read by both the header and every row delegate from the exact same
// `columns` array via the same `_weightSum()`/width formula, so alignment
// is structural rather than a promise two delegates happen to keep in sync
// by hand. Satisfies qml-rule.md §2.3's "single source of truth for
// columns" and ui-architecture.md §3's "data tables are schema-driven, not
// per-instance markup" — promoted specifically because 5 hand-rolled
// ListView tables existed independently before this component, none of
// them sharing a column definition with its own header.
//
// Usage:
//     AppDataTable {
//         columns: [
//             { key: "symbol", title: "Symbol", weight: 2 },
//             { key: "qty", title: "Qty", weight: 1, align: Text.AlignRight },
//             { key: "price", title: "Price", weight: 1, align: Text.AlignRight,
//               formatter: function(v) { return "$" + v.toFixed(2) } }
//         ]
//         model: [ { symbol: "BTCUSDT", qty: 0.5, price: 65000 }, ... ]
//     }
BaseCard {
    id: root

    //: Each entry: { key, title, weight (default 1), align (default
    //: Text.AlignLeft), formatter (optional value -> string function) }.
    property var columns: []
    property alias model: rows.model
    property int rowHeight: 36
    property int headerHeight: 32
    //: Alternating row tint for readability on dense tables. Off for short
    //: tables where it reads as noise rather than a scan aid.
    property bool zebra: true
    property string emptyText: "No data"

    //: `title` inherited from BaseCard — left empty by default rather than
    //: invented here: a table's meaning comes from its columns and its
    //: placement, so there is no sensible generic default the way "LOG" is
    //: for LogPanel. A consumer that wants a compact-mode badge letter sets
    //: `title` (or `icon`) at the call site. Card chrome (bgCard fill,
    //: border, radius) also comes from BaseCard now — this file used to
    //: repeat those four lines independently.
    icon: "table"

    function _weightSum() {
        var sum = 0
        for (var i = 0; i < root.columns.length; i++) {
            sum += (root.columns[i].weight || 1)
        }
        return sum || 1
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---- Header ----------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.headerHeight
            color: Theme.bgCardHeader
            radius: Theme.radiusMd

            // Square off the header's bottom corners against the card's
            // own rounded radius, same pattern LogPanel.qml already uses.
            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: parent.radius
                color: parent.color
            }
            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: Theme.border
            }

            Row {
                id: headerRow
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12

                Repeater {
                    model: root.columns
                    delegate: Text {
                        required property var modelData
                        width: (modelData.weight || 1) / root._weightSum() * headerRow.width
                        height: headerRow.height
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: modelData.align !== undefined ? modelData.align : Text.AlignLeft
                        text: modelData.title || modelData.key
                        color: Theme.muted
                        font.pixelSize: Theme.fontSizeSm
                        font.bold: true
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                    }
                }
            }
        }

        // ---- Rows --------------------------------------------------------
        ListView {
            id: rows
            objectName: "appDataTableRows"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            ScrollBar.vertical: ScrollBar {}

            delegate: Rectangle {
                id: rowDelegate
                required property var modelData
                //: A delegate that declares any `required property` opts
                //: out of QML's implicit per-delegate context properties —
                //: `index` must be requested explicitly too, or it resolves
                //: to undefined at runtime (caught rendering the gallery
                //: snapshot; not a hypothetical).
                required property int index
                //: Captured under a distinct name before the inner Repeater
                //: below re-binds `modelData` to the current COLUMN spec —
                //: without this, the row's own data would be shadowed and
                //: unreachable from inside that Repeater's delegate.
                property var rowData: modelData

                width: ListView.view.width
                height: root.rowHeight
                color: root.zebra && (rowDelegate.index % 2 === 1) ? Theme.bgCardHeader : "transparent"

                Row {
                    id: cellsRow
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12

                    Repeater {
                        model: root.columns
                        delegate: Text {
                            required property var modelData
                            readonly property var cellValue: rowDelegate.rowData[modelData.key]

                            width: (modelData.weight || 1) / root._weightSum() * cellsRow.width
                            height: cellsRow.height
                            verticalAlignment: Text.AlignVCenter
                            horizontalAlignment: modelData.align !== undefined ? modelData.align : Text.AlignLeft
                            text: modelData.formatter ? modelData.formatter(cellValue) : String(cellValue)
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontSizeMd
                            // Security & UI Injection Defense (qml-rule.md
                            // §3.3): cell content can be arbitrary data.
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                        }
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: rows.count === 0
                text: root.emptyText
                color: Theme.muted
                font.pixelSize: Theme.fontSizeMd
                textFormat: Text.PlainText
            }
        }
    }
}
