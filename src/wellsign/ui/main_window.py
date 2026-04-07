"""WellSign main window — splitter with left navigator and right page stack.

Layout::

    +-------------------------------------------------------+
    | Toolbar:  WellSign    [active project label]    [+ New Project] |
    +----------+--------------------------------------------+
    | Navigator| Right pane                                 |
    | (tree)   |  - DashboardPage      (Projects root)      |
    |          |  - ProjectWorkspace   (a specific project) |
    |          |  - DocTemplatesPage   (Templates > Docs)   |
    |          |  - EmailTemplatesPage (Templates > Emails) |
    +----------+--------------------------------------------+
    | DB: ...                                                |
    +-------------------------------------------------------+
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QToolBar,
    QWidget,
)

from wellsign import __version__
from wellsign.app_paths import database_path
from wellsign.ui.dialogs import AboutDialog, HelpDialog, NewProjectDialog
from wellsign.ui.navigator import NavigatorTree, NavKind, NavSelection
from wellsign.ui.pages import (
    DashboardPage,
    DocTemplatesPage,
    EmailTemplatesPage,
    ProjectWorkspace,
    WorkflowsPage,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"WellSign  ·  v{__version__}")
        self.resize(1380, 860)
        self.setMinimumSize(1100, 700)

        self._build_actions()
        self._build_menubar()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._wire()

        # Trigger initial selection so the right pane shows something useful.
        self.navigator.refresh_projects()

    # ---- actions (shared by toolbar + menu bar) ------------------------
    def _build_actions(self) -> None:
        from PySide6.QtGui import QAction

        self.new_project_action = QAction("+ New Project", self)
        self.new_project_action.setShortcut("Ctrl+N")
        self.new_project_action.setToolTip("Create a new well project (Ctrl+N)")
        self.new_project_action.triggered.connect(self._open_new_project_dialog)

        self.help_action = QAction("Help", self)
        self.help_action.setShortcut("F1")
        self.help_action.setToolTip("Open the WellSign help browser (F1)")
        self.help_action.triggered.connect(self._open_help_dialog)

        self.about_action = QAction("About WellSign…", self)
        self.about_action.triggered.connect(self._open_about_dialog)

        self.licenses_action = QAction("Licenses…", self)
        self.licenses_action.triggered.connect(self._open_about_dialog)

        self.quit_action = QAction("E&xit", self)
        self.quit_action.setShortcut("Ctrl+Q")
        self.quit_action.triggered.connect(self.close)

    # ---- menu bar -------------------------------------------------------
    def _build_menubar(self) -> None:
        bar = self.menuBar()

        file_menu = bar.addMenu("&File")
        file_menu.addAction(self.new_project_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)

        help_menu = bar.addMenu("&Help")
        help_menu.addAction(self.help_action)
        help_menu.addSeparator()
        help_menu.addAction(self.about_action)
        help_menu.addAction(self.licenses_action)

    def _open_about_dialog(self) -> None:
        AboutDialog(self).exec()

    def _open_help_dialog(self) -> None:
        HelpDialog(parent=self).exec()

    # ---- toolbar --------------------------------------------------------
    def _build_toolbar(self) -> None:
        bar = QToolBar("TopBar", self)
        bar.setObjectName("TopBar")
        bar.setMovable(False)
        bar.setFloatable(False)
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)

        bar.addAction(self.new_project_action)
        bar.addSeparator()
        bar.addAction(self.help_action)

    # ---- central --------------------------------------------------------
    def _build_central(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)

        self.navigator = NavigatorTree()

        self.stack = QStackedWidget()
        self.dashboard_page = DashboardPage()
        self.project_workspace = ProjectWorkspace()
        self.doc_templates_page = DocTemplatesPage()
        self.email_templates_page = EmailTemplatesPage()
        self.workflows_page = WorkflowsPage()

        self.stack.addWidget(self.dashboard_page)        # index 0
        self.stack.addWidget(self.project_workspace)     # index 1
        self.stack.addWidget(self.doc_templates_page)    # index 2
        self.stack.addWidget(self.email_templates_page)  # index 3
        self.stack.addWidget(self.workflows_page)        # index 4

        splitter.addWidget(self.navigator)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 1100])

        self.setCentralWidget(splitter)

    # ---- status bar -----------------------------------------------------
    def _build_statusbar(self) -> None:
        sb = self.statusBar()
        self.db_path_label = QLabel(f"DB: {database_path()}")
        font = QFont(self.db_path_label.font())
        font.setPointSize(8)
        self.db_path_label.setFont(font)
        sb.addPermanentWidget(self.db_path_label)
        sb.showMessage("Ready.", 3000)

    # ---- signals --------------------------------------------------------
    def _wire(self) -> None:
        self.navigator.selectionChangedTo.connect(self._on_nav_selection)
        self.dashboard_page.newProjectRequested.connect(self._open_new_project_dialog)
        self.project_workspace.phaseChanged.connect(self._on_phase_changed)
        self.project_workspace.projectEdited.connect(self._on_project_edited)
        self.workflows_page.workflowCreated.connect(self._on_workflow_created)
        self.workflows_page.workflowDeleted.connect(self._on_workflow_deleted)

    def _on_workflow_created(self, workflow_id: str) -> None:
        self.navigator.refresh_workflows(select_id=workflow_id)
        self.statusBar().showMessage("Workflow created.", 2500)

    def _on_workflow_deleted(self) -> None:
        self.navigator.refresh_workflows()
        self.statusBar().showMessage("Workflow deleted.", 2500)

    def _on_phase_changed(self, project_id: str) -> None:
        # Phase color drives the navigator dot — refresh it.
        self.navigator.refresh_projects(select_id=project_id)
        self.dashboard_page.refresh()
        self.statusBar().showMessage("Phase updated.", 2500)

    def _on_project_edited(self, project_id: str) -> None:
        # Project name / well / region / customer / dates may have changed —
        # refresh navigator labels and the dashboard table.
        self.navigator.refresh_projects(select_id=project_id)
        self.dashboard_page.refresh()
        self.statusBar().showMessage("Project updated.", 2500)

    # ---- handlers -------------------------------------------------------
    def _on_nav_selection(self, sel: NavSelection) -> None:
        if sel.kind == NavKind.PROJECTS_ROOT:
            self.dashboard_page.refresh()
            self.stack.setCurrentWidget(self.dashboard_page)
        elif sel.kind == NavKind.PROJECT and sel.project is not None:
            self.project_workspace.set_project(sel.project)
            self.stack.setCurrentWidget(self.project_workspace)
        elif sel.kind == NavKind.TEMPLATES_ROOT:
            self.doc_templates_page.refresh()
            self.stack.setCurrentWidget(self.doc_templates_page)
        elif sel.kind == NavKind.DOC_TEMPLATES:
            self.doc_templates_page.refresh()
            self.stack.setCurrentWidget(self.doc_templates_page)
        elif sel.kind == NavKind.EMAIL_TEMPLATES:
            self.email_templates_page.refresh()
            self.stack.setCurrentWidget(self.email_templates_page)
        elif sel.kind == NavKind.WORKFLOWS_ROOT:
            self.workflows_page._load_first_workflow()
            self.stack.setCurrentWidget(self.workflows_page)
        elif sel.kind == NavKind.WORKFLOW and sel.workflow_id:
            self.workflows_page.show_workflow(sel.workflow_id)
            self.stack.setCurrentWidget(self.workflows_page)

    def _open_new_project_dialog(self) -> None:
        dlg = NewProjectDialog(self)
        if dlg.exec() and dlg.created_project is not None:
            new_proj = dlg.created_project
            self.navigator.refresh_projects(select_id=new_proj.id)
            self.dashboard_page.refresh()
            self.statusBar().showMessage(f"Created project: {new_proj.name}", 4000)
