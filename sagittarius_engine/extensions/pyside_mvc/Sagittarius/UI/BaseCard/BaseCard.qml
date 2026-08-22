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
// Usage:
//     MyCard.qml:
//         BaseCard {
//             function setDisabled(disabled) {
//                 opacity = disabled ? Theme.stateDisabledOpacity : 1.0
//             }
//         }
Rectangle {
    id: root

    //: Override in a derived card if it needs to visually react to being
    //: marked active/selected. No visual effect by default.
    function setActive(active) {}

    //: Override in a derived card if it needs to visually react to being
    //: disabled as a whole unit. No visual effect by default — today every
    //: card in this app disables its individual controls instead; a card
    //: only needs this if it actually wants whole-card behavior (dimming,
    //: blocking interaction, pausing a live update, etc.).
    function setDisabled(disabled) {}
}
