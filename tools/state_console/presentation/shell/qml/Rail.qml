import QtQuick
import Sagittarius.UI 1.0

// `EPIC-008B` §2 -- the shell-wide section rail, thinly wrapping the kit's
// `AppRail` around `viewModel` (a `RailViewModel`). `footer` is left unset
// here deliberately: the target/process info + appearance toggle
// `reference/handoff.md` §6 describes for the rail footer depend on data
// the Overview restyle (`EPIC-008B` §4) hasn't wired up yet -- adding a
// half-built footer now would just be a placeholder to redo later.
AppRail {
    anchors.fill: parent
    sections: viewModel.sections
    activeSectionId: viewModel.activeSectionId
    onSectionSelected: (id) => viewModel.requestNavigate(id)
}
