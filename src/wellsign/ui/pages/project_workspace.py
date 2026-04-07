"""ProjectWorkspace — the right pane shown when a project is selected.

Holds a QTabWidget with one tab per workflow stage of a project: Setup,
Investors, Documents, Send, Status, Burndown. Tabs that consume the active
project receive ``set_project()`` calls.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.phases import PHASES, info_for as phase_info_for, next_phase_options
from wellsign.db.projects import ProjectRow, get_project, set_phase
from wellsign.ui.tabs import (
    BurndownTab,
    CostsTab,
    DocumentsTab,
    InvestorsTab,
    ProjectSetupTab,
    SendTab,
    StatusTab,
)


class ProjectWorkspace(QWidget):
    phaseChanged = Signal(str)  # emits project_id when phase advances

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: ProjectRow | None = None
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(10)

        # Title row
        title_row = QHBoxLayout()
        self.title_label = QLabel("No project selected")
        f = self.title_label.font()
        f.setPointSize(18)
        f.setBold(True)
        self.title_label.setFont(f)
        title_row.addWidget(self.title_label)
        title_row.addStretch(1)
        outer.addLayout(title_row)

        self.subtitle_label = QLabel("")
        self.subtitle_label.setStyleSheet("color: #5b6473;")
        outer.addWidget(self.subtitle_label)

        # Phase banner
        self.phase_banner = QFrame()
        self.phase_banner.setObjectName("PhaseBanner")
        banner_layout = QHBoxLayout(self.phase_banner)
        banner_layout.setContentsMargins(18, 12, 14, 12)
        banner_layout.setSpacing(14)

        self.phase_dot = QLabel("●")
        self.phase_dot.setStyleSheet("font-size: 22pt;")
        banner_layout.addWidget(self.phase_dot)

        phase_text_box = QVBoxLayout()
        phase_text_box.setSpacing(2)
        self.phase_label = QLabel("")
        f2 = self.phase_label.font()
        f2.setPointSize(12)
        f2.setBold(True)
        self.phase_label.setFont(f2)
        self.phase_sub = QLabel("")
        self.phase_sub.setStyleSheet("color: #5b6473;")
        phase_text_box.addWidget(self.phase_label)
        phase_text_box.addWidget(self.phase_sub)
        banner_layout.addLayout(phase_text_box)

        banner_layout.addStretch(1)

        self.advance_btn = QPushButton("Advance →")
        self.advance_btn.setToolTip("Move this project to the next phase")
        self.advance_btn.clicked.connect(self._on_advance)
        banner_layout.addWidget(self.advance_btn)

        self.set_phase_btn = QPushButton("Set Phase…")
        self.set_phase_btn.setProperty("secondary", True)
        self.set_phase_btn.setToolTip("Manually pick any phase")
        self.set_phase_btn.clicked.connect(self._on_set_phase)
        banner_layout.addWidget(self.set_phase_btn)

        outer.addWidget(self.phase_banner)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.setup_tab = ProjectSetupTab()
        self.investors_tab = InvestorsTab()
        self.documents_tab = DocumentsTab()
        self.send_tab = SendTab()
        self.status_tab = StatusTab()
        self.costs_tab = CostsTab()
        self.burndown_tab = BurndownTab()

        self.tabs.addTab(self.setup_tab,     "Project Setup")
        self.tabs.addTab(self.investors_tab, "Investors")
        self.tabs.addTab(self.documents_tab, "Documents")
        self.tabs.addTab(self.send_tab,      "Send")
        self.tabs.addTab(self.status_tab,    "Status")
        self.tabs.addTab(self.costs_tab,     "Costs")
        self.tabs.addTab(self.burndown_tab,  "Burndown")

        outer.addWidget(self.tabs, 1)

    def set_project(self, project: ProjectRow | None) -> None:
        self._project = project
        if project is None:
            self.title_label.setText("No project selected")
            self.subtitle_label.setText("")
            self.phase_banner.setVisible(False)
        else:
            self.title_label.setText(project.name)
            bits = [b for b in (project.well_name, project.region, project.license_customer) if b]
            self.subtitle_label.setText("  ·  ".join(bits))
            self._refresh_phase_banner()

        # Tabs that need the project explicitly:
        self.setup_tab.set_project(project)
        self.investors_tab.set_project(project)
        self.documents_tab.set_project(project)
        self.send_tab.set_project(project)
        self.status_tab.set_project(project)
        self.costs_tab.set_project(project)
        self.burndown_tab.set_project(project)

    # ---- phase banner ---------------------------------------------------
    def _refresh_phase_banner(self) -> None:
        if self._project is None:
            self.phase_banner.setVisible(False)
            return
        info = phase_info_for(self._project.phase)
        bg = info.color_hex + "22"  # ~13% alpha when sent through #RRGGBBAA
        self.phase_banner.setStyleSheet(
            f"QFrame#PhaseBanner {{ background: {bg}; "
            f"border: 1px solid {info.color_hex}; border-radius: 8px; }}"
        )
        self.phase_dot.setStyleSheet(f"color: {info.color_hex}; font-size: 22pt;")
        self.phase_label.setText(info.label)
        self.phase_sub.setText(info.description)

        next_options = next_phase_options(self._project.phase)
        if not next_options:
            self.advance_btn.setText("Advance →")
            self.advance_btn.setEnabled(False)
        elif len(next_options) == 1:
            self.advance_btn.setText(f"Advance → {next_options[0].short}")
            self.advance_btn.setEnabled(True)
        else:
            self.advance_btn.setText("Advance →")
            self.advance_btn.setEnabled(True)
        self.phase_banner.setVisible(True)

    def _on_advance(self) -> None:
        if self._project is None:
            return
        next_options = next_phase_options(self._project.phase)
        if not next_options:
            return

        if len(next_options) == 1:
            chosen = next_options[0]
        else:
            labels = [p.label for p in next_options]
            choice, ok = QInputDialog.getItem(
                self,
                "Advance phase",
                "Pick the next phase:",
                labels,
                0,
                False,
            )
            if not ok:
                return
            chosen = next(p for p in next_options if p.label == choice)

        set_phase(self._project.id, chosen.code)
        # Refresh local state
        self._project = get_project(self._project.id)
        self._refresh_phase_banner()
        self.phaseChanged.emit(self._project.id if self._project else "")

    def _on_set_phase(self) -> None:
        if self._project is None:
            return
        labels = [p.label for p in PHASES]
        current_label = phase_info_for(self._project.phase).label
        idx = labels.index(current_label) if current_label in labels else 0
        choice, ok = QInputDialog.getItem(
            self,
            "Set phase",
            "Pick any phase for this project:",
            labels,
            idx,
            False,
        )
        if not ok:
            return
        chosen = next(p for p in PHASES if p.label == choice)
        set_phase(self._project.id, chosen.code)
        self._project = get_project(self._project.id)
        self._refresh_phase_banner()
        self.phaseChanged.emit(self._project.id if self._project else "")
