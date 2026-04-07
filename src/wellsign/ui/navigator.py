"""Left-side navigator tree.

Two top-level roots:
  ▼ Projects
       <project A>
       <project B>
       ...
  ▼ Templates
       Document templates
       Email templates

Emits ``selectionChanged`` with a ``NavSelection`` describing what the user
clicked. The MainWindow uses that to swap the right-pane stack.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush
from PySide6.QtWidgets import QHeaderView, QTreeWidget, QTreeWidgetItem, QWidget

from wellsign.db.phases import info_for as phase_info_for
from wellsign.db.projects import ProjectRow, list_projects


class NavKind(str, Enum):
    PROJECTS_ROOT = "projects_root"
    PROJECT       = "project"
    TEMPLATES_ROOT = "templates_root"
    DOC_TEMPLATES = "doc_templates"
    EMAIL_TEMPLATES = "email_templates"
    WORKFLOWS_ROOT = "workflows_root"
    WORKFLOW       = "workflow"


@dataclass
class NavSelection:
    kind: NavKind
    project: ProjectRow | None = None
    workflow_id: str | None = None


_ROLE_KIND = Qt.ItemDataRole.UserRole + 1
_ROLE_PROJECT_ID = Qt.ItemDataRole.UserRole + 2
_ROLE_WORKFLOW_ID = Qt.ItemDataRole.UserRole + 3


class NavigatorTree(QTreeWidget):
    selectionChangedTo = Signal(object)  # NavSelection

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(14)
        self.setRootIsDecorated(True)
        self.setUniformRowHeights(True)
        self.setColumnCount(1)
        self.setMinimumWidth(220)
        self.setMaximumWidth(360)
        self.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self._projects_root: QTreeWidgetItem | None = None
        self._templates_root: QTreeWidgetItem | None = None
        self._doc_templates_item: QTreeWidgetItem | None = None
        self._email_templates_item: QTreeWidgetItem | None = None
        self._workflows_root: QTreeWidgetItem | None = None

        self._build_static_nodes()
        self.refresh_projects()
        self.refresh_workflows()

        self.itemSelectionChanged.connect(self._on_selection)

    # ---- public api -----------------------------------------------------
    def refresh_projects(self, select_id: str | None = None) -> None:
        if self._projects_root is None:
            return
        self._projects_root.takeChildren()
        for proj in list_projects():
            phase = phase_info_for(proj.phase)
            label = f"●  {proj.name}"
            item = QTreeWidgetItem([label])
            item.setData(0, _ROLE_KIND, NavKind.PROJECT.value)
            item.setData(0, _ROLE_PROJECT_ID, proj.id)
            item.setForeground(0, QBrush(phase.color))
            item.setToolTip(0, f"{proj.name}\nPhase: {phase.label}")
            self._projects_root.addChild(item)
            if select_id and proj.id == select_id:
                self.setCurrentItem(item)
        self._projects_root.setExpanded(True)
        if select_id is None and self.currentItem() is None:
            # Default selection: first project, otherwise the projects root.
            if self._projects_root.childCount() > 0:
                self.setCurrentItem(self._projects_root.child(0))
            else:
                self.setCurrentItem(self._projects_root)

    def select_doc_templates(self) -> None:
        if self._doc_templates_item:
            self.setCurrentItem(self._doc_templates_item)

    def refresh_workflows(self, select_id: str | None = None) -> None:
        if self._workflows_root is None:
            return
        from wellsign.db.workflows import list_workflows

        self._workflows_root.takeChildren()
        for wf in list_workflows():
            item = QTreeWidgetItem([f"⚡  {wf.name}"])
            item.setData(0, _ROLE_KIND, NavKind.WORKFLOW.value)
            item.setData(0, _ROLE_WORKFLOW_ID, wf.id)
            item.setToolTip(0, wf.description or wf.name)
            self._workflows_root.addChild(item)
            if select_id and wf.id == select_id:
                self.setCurrentItem(item)
        self._workflows_root.setExpanded(True)

    # ---- internals ------------------------------------------------------
    def _build_static_nodes(self) -> None:
        self._projects_root = QTreeWidgetItem(["Projects"])
        self._projects_root.setData(0, _ROLE_KIND, NavKind.PROJECTS_ROOT.value)
        font = self._projects_root.font(0)
        font.setBold(True)
        self._projects_root.setFont(0, font)
        self.addTopLevelItem(self._projects_root)
        self._projects_root.setExpanded(True)

        self._templates_root = QTreeWidgetItem(["Templates"])
        self._templates_root.setData(0, _ROLE_KIND, NavKind.TEMPLATES_ROOT.value)
        self._templates_root.setFont(0, font)
        self.addTopLevelItem(self._templates_root)

        self._doc_templates_item = QTreeWidgetItem(["Document templates"])
        self._doc_templates_item.setData(0, _ROLE_KIND, NavKind.DOC_TEMPLATES.value)
        self._templates_root.addChild(self._doc_templates_item)

        self._email_templates_item = QTreeWidgetItem(["Email templates"])
        self._email_templates_item.setData(0, _ROLE_KIND, NavKind.EMAIL_TEMPLATES.value)
        self._templates_root.addChild(self._email_templates_item)

        self._templates_root.setExpanded(True)

        self._workflows_root = QTreeWidgetItem(["Workflows"])
        self._workflows_root.setData(0, _ROLE_KIND, NavKind.WORKFLOWS_ROOT.value)
        self._workflows_root.setFont(0, font)
        self.addTopLevelItem(self._workflows_root)
        self._workflows_root.setExpanded(True)

    def _on_selection(self) -> None:
        item = self.currentItem()
        if item is None:
            return
        kind_str = item.data(0, _ROLE_KIND)
        if kind_str is None:
            return
        kind = NavKind(kind_str)
        project: ProjectRow | None = None
        workflow_id: str | None = None
        if kind == NavKind.PROJECT:
            from wellsign.db.projects import get_project
            project = get_project(item.data(0, _ROLE_PROJECT_ID))
        elif kind == NavKind.WORKFLOW:
            workflow_id = item.data(0, _ROLE_WORKFLOW_ID)
        self.selectionChangedTo.emit(
            NavSelection(kind=kind, project=project, workflow_id=workflow_id)
        )
