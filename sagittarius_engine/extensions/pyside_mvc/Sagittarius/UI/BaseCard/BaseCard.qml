import QtQuick


// Base for card/panel-shaped QML components (Rectangle-rooted). Gives them
// a consistent, named method contract for reacting to state —
// setActive()/setDisabled() — mirroring the duck-typed apply_ui_mode()/
// set_ui_mode() convention BasePresenter/QmlHostView already use for FSM
// state (see base_presenter.py's _bind_fsm_to_ui, base_view_model.py's
// set_ui_mode). Both are no-ops here: a derived card only overrides the
// one(s) it actually needs to react to (e.g. dim itself, show an overlay,
// pause a live update) — inheriting BaseCard costs nothing for a card that
// never calls or overrides either.
//
// Also owns `title`/`icon`/`compact` — full-size vs. compact display is an
// app-wide philosophy (2026-08-23 design decision), not a per-card
// judgment call, so it lives here rather than being reimplemented per
// card. `title` was previously redeclared independently in LogPanel.qml
// and TimeRangeCard.qml with identical shape — real duplication, now
// pulled up per ui-architecture.md §1.2 ("component owns what's the same
// on every use").
//
// Usage:
//     MyCard.qml:
//         BaseCard {
//             title: "My Card"
//             icon: "chart-bar"   // optional — omit to fall back to the
//                                 // first letter of `title` in compact mode
//             function setDisabled(disabled) {
//                 opacity = disabled ? Theme.stateDisabledOpacity : 1.0
//             }
//             // Ordinary children declared here are the full-size content —
//             // no special property name needed, same as before this change.
//             ColumnLayout { anchors.fill: parent; ... }
//         }
//
//     Elsewhere, driven by one shared app-wide toggle (BaseCard itself
//     holds no opinion on *when* the app is compact — that's tier 2,
//     supplied by the consumer):
//         MyCard { compact: appViewModel.compactModeEnabled }
Rectangle { // card-exempt: this IS the card recipe's definition site — BaseCard cannot derive from itself
    id: root

    //: This card's identity. Declarations, not logic — anything *derived*
    //: from them (see `badgeText`/`showIcon` below) is owned by Python.
    property string title: ""
    property string icon: ""
    //: App-wide compact/full toggle. A plain bindable property, not a
    //: lookup into any global/singleton — the consumer (screen or app)
    //: is responsible for binding every card's `compact` to one shared
    //: source so the whole app switches together. BaseCard itself must
    //: not know that source exists (ui-architecture.md §1.2 tier 3).
    property bool compact: false

    //: Full-size content — ordinary children declared inside a derived
    //: card land here unchanged; this alias only redirects *where* they
    //: attach (into `contentContainer`, not directly onto `root`), so
    //: every existing derived card kept working with zero changes to its
    //: own file when this was introduced.
    default property alias contentData: contentContainer.data

    //: Compact-badge text. A screen with a ViewModel supplies this already
    //: computed (`badgeText: viewModel.someCardBadge`), keeping the
    //: derivation in Python where it is debuggable and unit-tested —
    //: `kit/card_model.py`'s `CardModel` is that implementation, and the
    //: canonical definition of the rule.
    //:
    //: The QML fallback below exists so a card is usable with nothing wired
    //: — gallery, preview, test — not as a second implementation competing
    //: with the Python one.
    //:
    //: An earlier iteration embedded a `CardModel` QObject inside every
    //: card's own QML object tree instead. It worked, but only after three
    //: distinct QML initialisation hazards: an inline
    //: `readonly property CardModel x: CardModel {}` resolving to null; a
    //: `default property alias` swallowing the base's own internal children
    //: into the very container being declared; and, once a card was
    //: subclassed, sibling bindings evaluating before the model existed and
    //: then never re-evaluating. None of the three failed a test — QML
    //: binding errors are runtime warnings, and `QQuickWidget.errors()`
    //: reports parse errors only. Reverted deliberately (2026-08-23): the
    //: principle "derivation belongs in Python" is right, but the delivery
    //: mechanism that already works is a screen-level ViewModel passed in
    //: via context property (exactly how `controlsEnabled` drives every
    //: Backtest toolbar button), not an N-instance QObject embedded in the
    //: view tree.
    property string badgeText: title.length > 0 ? title.charAt(0).toUpperCase() : "?"

    //: Whether the compact badge shows the icon rather than `badgeText`.
    //: Same contract as above: a ViewModel may drive it; the fallback keeps
    //: an unwired card working.
    property bool showIcon: icon !== ""

    //: The size a card *wants* to be when compact. An intent a container
    //: reads, not a size this card applies to itself — geometry belongs to
    //: whoever places the card (ui-architecture.md §4). BaseCard therefore
    //: never touches its own implicitWidth/implicitHeight or Layout.*,
    //: which is also why it never collides with a derived card that sets
    //: its own full-size dimensions (TimeRangeCard's `implicitWidth: 300`).
    readonly property int compactSize: 56

    color: Theme.bgCard
    border.color: Theme.border
    border.width: 1
    radius: Theme.radiusMd

    //: Override in a derived card if it needs to visually react to being
    //: marked active/selected. No visual effect by default.
    function setActive(active) {}

    //: Override in a derived card if it needs to visually react to being
    //: disabled as a whole unit. No visual effect by default — today every
    //: card in this app disables its individual controls instead; a card
    //: only needs this if it actually wants whole-card behavior (dimming,
    //: blocking interaction, pausing a live update, etc.).
    function setDisabled(disabled) {}

    //: Assigned to `data` explicitly rather than declared as plain children.
    //: `default property alias contentData` above captures *every* child
    //: declared in this root's body — including these internal ones —
    //: redirecting them into `contentContainer.data`, i.e. into the very
    //: object being declared. An explicit `data:` assignment bypasses the
    //: default property, which is the documented way to have both a
    //: default-property alias and internal children in one component.
    data: [
    Item {
        id: contentContainer
        anchors.fill: parent
        visible: !root.compact
    },

    Item {
        id: compactBadge
        anchors.fill: parent
        visible: root.compact

        //: Both bind to root properties a ViewModel can drive (see their
        //: declarations above) — the badge itself makes no decision.
        Image {
            id: compactIcon
            visible: root.showIcon
            anchors.centerIn: parent
            source: root.showIcon
                    ? "image://icons/" + root.icon + "/accent"
                    : ""
            sourceSize.width: 24
            sourceSize.height: 24
        }

        Text {
            visible: !root.showIcon
            anchors.centerIn: parent
            text: root.badgeText
            color: Theme.accent
            font.pixelSize: Theme.fontSizeLg
            font.bold: true
            textFormat: Text.PlainText
        }
    }
    ]
}
