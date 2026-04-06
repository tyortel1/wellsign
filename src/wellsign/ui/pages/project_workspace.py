"""ProjectWorkspace — the right pane shown when a project is selected.

Holds a QTabWidget with one tab per workflow stage of a project: Setup,
Investors, Documents, Send, Status, Burndown. Tabs that consume the active
project receive ``set_project()`` calls.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from wellsign.db.projects import ProjectRow
from wellsign.ui.tabs import (
    BurndownTab,
    DocumentsTab,
    InvestorsTab,
    ProjectSetupTab,
    SendTab,
    StatusTab,
)


class ProjectWorkspace(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: ProjectRow | None = None
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(10)

        self.title_label = QLabel("No project selected")
        f = self.title_label.font()
        f.setPointSize(18)
        f.setBold(True)
        self.title_label.setFont(f)
        outer.addWidget(self.title_label)

        self.subtitle_label = QLabel("")
        self.subtitle_label.setStyleSheet("color: #5b6473;")
        outer.addWidget(self.subtitle_label)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.setup_tab = ProjectSetupTab()
        self.investors_tab = InvestorsTab()
        self.documents_tab = DocumentsTab()
        self.send_tab = SendTab()
        self.status_tab = StatusTab()
        self.burndown_tab = BurndownTab()

        self.tabs.addTab(self.setup_tab,     "Project Setup")
        self.tabs.addTab(self.investors_tab, "Investors")
        self.tabs.addTab(self.documents_tab, "Documents")
        self.tabs.addTab(self.send_tab,      "Send")
        self.tabs.addTab(self.status_tab,    "Status")
        self.tabs.addTab(self.burndown_tab,  "Burndown")

        outer.addWidget(self.tabs, 1)

    def set_project(self, project: ProjectRow | None) -> None:
        self._project = project
        if project is None:
            self.title_label.setText("No project selected")
            self.subtitle_label.setText("")
        else:
            self.title_label.setText(project.name)
            bits = [b for b in (project.well_name, project.region, project.license_customer) if b]
            self.subtitle_label.setText("  ·  ".join(bits))

        # Tabs that need the project explicitly:
        self.setup_tab.set_project(project)
        self.investors_tab.set_project(project)
