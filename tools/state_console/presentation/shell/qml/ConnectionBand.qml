import QtQuick
import Sagittarius.UI 1.0

// `EPIC-008B` §2 -- the shell-wide status band, thinly wrapping the kit's
// `LiveConnectionBand` around `viewModel` (a `ConnectionBandViewModel`).
// Every value shown is pushed in by `ShellPresenter`; this file owns no
// state of its own.
LiveConnectionBand {
    anchors.fill: parent
    state: viewModel.state
    stateLabel: viewModel.stateLabel
    stateNote: viewModel.stateNote
    ageLabel: viewModel.ageLabel
    ageValue: viewModel.ageValue
    targetText: viewModel.targetText
    actionLabel: viewModel.actionLabel
    heartbeatTicks: viewModel.heartbeatTicks
    onActionRequested: viewModel.requestAction()
    onChangeTargetRequested: viewModel.requestChangeTarget()
}
