import QtQuick
import Sagittarius.UI 1.0

// Minimal probe -- loaded against a standalone QQmlEngine with its own
// directly-injected "Theme" (see test_live_connection_band.py), not the
// shared configure_app_qml()/get_theme_bridge() singleton every other kit
// test uses. That singleton is first-call-wins for the whole pytest
// process and every existing fixture in this suite locks it to an
// all-#000000 placeholder palette -- useless for proving a colour MAPPING
// is correct, since every candidate colour would be identical black.
LiveConnectionBand {
    objectName: "band"
    width: 900
    state: "reading"
    stateLabel: "Attached · reading"
    stateNote: "snapshot stream live · ~1/s"
    ageLabel: "last snapshot"
    ageValue: "00:01 ago"
    targetText: "ws://127.0.0.1:8781"
    actionLabel: "Detach"
    heartbeatTicks: [0.2, 0.6, 1.0]
}
