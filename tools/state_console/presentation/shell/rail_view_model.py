"""`RailViewModel` — `EPIC-008B` §2.

Data only, no application logic: `sections`/`activeSectionId` are pushed in
by `ShellPresenter`, and `AppRail.sectionSelected` is forwarded as
`navigateRequested` for the Presenter to act on (it, not this class, decides
what "navigate" means — `ConsoleShellView.navigate_to()`).
"""

from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot

from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel


class RailViewModel(BaseQmlViewModel):
    sectionsChanged = Signal()
    activeSectionIdChanged = Signal()

    navigateRequested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._sections: list[dict] = []
        self._active_section_id = ""

    def _get_sections(self) -> list:
        return self._sections

    # "QVariantList" -- same idiom OverviewViewModel.threadPools already uses.
    sections = Property("QVariantList", _get_sections, notify=sectionsChanged)  # type: ignore[arg-type]

    def set_sections(self, sections: list[dict]) -> None:
        self._sections = sections
        self.sectionsChanged.emit()

    def _get_active_section_id(self) -> str:
        return self._active_section_id

    def set_active_section_id(self, value: str) -> None:
        if value != self._active_section_id:
            self._active_section_id = value
            self.activeSectionIdChanged.emit()

    activeSectionId = Property(
        str, _get_active_section_id, notify=activeSectionIdChanged
    )

    @Slot(str)
    def requestNavigate(self, section_id: str) -> None:
        self.navigateRequested.emit(section_id)
