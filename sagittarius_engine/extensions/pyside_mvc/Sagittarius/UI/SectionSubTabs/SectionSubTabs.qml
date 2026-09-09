import QtQuick
import QtQuick.Layouts
import Sagittarius.UI 1.0

// `EPIC-008B` -- a row of sub-tabs beneath a section header, each showing a
// count (`reference/handoff.md` §6: "sub-tab row below with a 1px bottom
// rule, active tab: accent 2px underline + accent-900 text, inactive 50%
// ink, each tab shows a count in mono at 60% opacity"). Promoted here once
// three screens (Overview, Events & wiring, Container) had each
// independently built the identical row -- this repo's own two-consumer
// promotion rule (`ActionCard/NOTES.md`), satisfied for real this time,
// unlike the connect-flow primitives `EPIC-008A` §5 declined to promote
// with only one consumer.
//
// Tiered per `ui-architecture.md` §1.2: the active-tab underline/colour
// mechanics are tier 1 (inside this component); which tabs exist, their
// labels and counts are tier 2 (`tabs`, the same schema-driven array shape
// `AppRail.sections`/`AppDataTable.columns` already use). What a tab
// *means* -- filtering a model, computing a count -- is tier 3, entirely
// the consumer's; this component has no idea what "undeclared" or "never
// built" means.
//
// Usage:
//     SectionSubTabs {
//         Layout.fillWidth: true
//         tabs: [
//             { id: "all", label: "All", count: 25 },
//             { id: "undeclared", label: "Undeclared", count: 2 }
//         ]
//         activeTabId: "all"
//         onTabSelected: (id) => root.activeTab = id
//     }
Item {
    id: root
    implicitHeight: mainColumn.implicitHeight

    //: Each entry: `{ id, label, count }`. `count` is optional — a tab
    //: with no count concept at all (`reference/handoff.md` §7.1's own
    //: "Status · Modules (12)": Status carries no parenthetical, Modules
    //: does) omits the key entirely and shows no count text. This is
    //: distinct from `AppRail.badgeCount`'s "0 means no badge": here a
    //: present `count` of 0 still renders ("Undeclared (0)" is real
    //: information — nothing wrong yet), it is the key's *absence* that
    //: means "this tab has no count".
    property var tabs: []
    property string activeTabId: ""

    signal tabSelected(string id)

    //: Named so it is directly invokable (incl. from a test) with a
    //: `QVariant` argument -- same reasoning as `AppRail._selectRow(id)`.
    function _selectTab(id) {
        root.tabSelected(id)
    }

    ColumnLayout {
        id: mainColumn
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spaceLg

            Repeater {
                model: root.tabs

                delegate: Item {
                    id: tabItem
                    required property var modelData
                    objectName: "subTab_" + tabItem.modelData.id
                    readonly property bool active: tabItem.modelData.id === root.activeTabId
                    readonly property bool hasCount: tabItem.modelData.count !== undefined
                        && tabItem.modelData.count !== null
                    implicitWidth: content.implicitWidth
                    implicitHeight: content.implicitHeight + Theme.spaceXs + 2

                    RowLayout {
                        id: content
                        anchors.top: parent.top
                        anchors.left: parent.left
                        spacing: Theme.spaceXs

                        Text {
                            objectName: "subTabLabel"
                            text: tabItem.modelData.label
                            color: tabItem.active ? Theme.accent900 : Theme.muted
                            font.bold: true
                            font.pixelSize: Theme.fontSizeMd
                            textFormat: Text.PlainText
                        }
                        Text {
                            objectName: "subTabCount"
                            visible: tabItem.hasCount
                            text: tabItem.hasCount ? String(tabItem.modelData.count) : ""
                            color: tabItem.active ? Theme.accent900 : Theme.muted
                            opacity: 0.6
                            font.family: Theme.fontFamilyMono
                            font.pixelSize: Theme.fontSizeSm
                            textFormat: Text.PlainText
                        }
                    }

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        height: 2
                        color: tabItem.active ? Theme.accent : "transparent"
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root._selectTab(tabItem.modelData.id)
                    }
                }
            }

            Item { Layout.fillWidth: true }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.border
        }
    }
}
