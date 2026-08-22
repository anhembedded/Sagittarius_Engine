import QtQuick
import Sagittarius.UI 1.0

// Standalone probe: opens immediately so a test can assert real popup
// state (opened, dynamic width, action buttons present) without needing a
// full OverlayHost.
Item {
    id: root
    width: 800
    height: 600
    readonly property bool hasOpenModal: modal.opened

    AppModal {
        id: modal
        objectName: "probeModal"
        title: "Probe Modal"
        actions: [
            StatefulButton { objectName: "btnCancel"; text: "Cancel"; onClicked: modal.close() },
            StatefulButton { objectName: "btnConfirm"; text: "Confirm"; onClicked: modal.close() }
        ]

        Text { text: "probe body"; color: Theme.textPrimary }
    }

    Component.onCompleted: modal.open()
}
