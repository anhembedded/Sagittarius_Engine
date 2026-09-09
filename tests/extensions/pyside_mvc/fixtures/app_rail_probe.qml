import QtQuick
import Sagittarius.UI 1.0

// EPIC-008A: three sections, one already active, two carrying badges, one
// section (Overview) with none -- enough to prove active/inactive styling
// and badge visibility both ways.
AppRail {
    objectName: "rail"
    width: 218
    height: 300
    activeSectionId: "events"
    sections: [
        { id: "overview", label: "Overview", badgeCount: 0 },
        { id: "events", label: "Events", badgeCount: 2 },
        { id: "signals", label: "Signals", badgeCount: 10 }
    ]
}
