import QtQuick
import Sagittarius.UI 1.0

// EPIC-008B: two tabs, one active with a nonzero count, one inactive with
// a different count -- enough to prove active/inactive colour and count
// text both ways.
SectionSubTabs {
    objectName: "subTabs"
    width: 400
    height: 40
    activeTabId: "all"
    tabs: [
        { id: "all", label: "All", count: 25 },
        { id: "undeclared", label: "Undeclared", count: 2 }
    ]
}
