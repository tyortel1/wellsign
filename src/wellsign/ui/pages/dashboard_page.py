"""Dashboard page — cross-project overview shown when 'Projects' root is selected."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.investors import count_investors
from wellsign.db.phases import PHASES
from wellsign.db.projects import list_projects
from wellsign.ui.dialogs.help_dialog import HelpButton

_PROJECT_ID_ROLE = Qt.ItemDataRole.UserRole + 1


class DashboardPage(QWidget):
    """Cross-project dashboard. Header + filter bar + table + 'New Project' button."""

    newProjectRequested = Signal()
    projectActivated = Signal(str)  # project_id — emitted when a row is double-clicked

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._all_projects: list = []  # cached ProjectRow list
        self._build()
        self.refresh()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(16)

        # Header row
        header = QHBoxLayout()
        title = QLabel("All Projects")
        title_font = title.font()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        header.addWidget(title)
        header.addStretch(1)

        self.new_btn = QPushButton("+ New Project")
        self.new_btn.clicked.connect(self.newProjectRequested.emit)
        header.addWidget(self.new_btn)
        header.addWidget(HelpButton("dashboard"))

        subtitle = QLabel(
            "Side-by-side view of every project. <b>Double-click a row</b> to jump "
            "into its workspace, or use the filters below to narrow the list."
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)

        # Filter bar
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search name, well, region, customer…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filters)
        filter_row.addWidget(self.search_edit, 1)

        phase_label = QLabel("Phase:")
        phase_label.setStyleSheet("color: #5b6473;")
        filter_row.addWidget(phase_label)

        self.phase_filter = QComboBox()
        self.phase_filter.addItem("All phases", userData=None)
        for p in PHASES:
            self.phase_filter.addItem(p.short, userData=p.code)
        self.phase_filter.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self.phase_filter)

        status_label = QLabel("Status:")
        status_label.setStyleSheet("color: #5b6473;")
        filter_row.addWidget(status_label)

        self.status_filter = QComboBox()
        self.status_filter.addItem("All", userData=None)
        for s in ("draft", "active", "closed", "archived"):
            self.status_filter.addItem(s.title(), userData=s)
        self.status_filter.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self.status_filter)

        self.clear_filters_btn = QPushButton("Clear")
        self.clear_filters_btn.setProperty("secondary", True)
        self.clear_filters_btn.clicked.connect(self._clear_filters)
        filter_row.addWidget(self.clear_filters_btn)

        # Table
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Project", "Well", "Region", "Customer", "Status", "Investors", "Created"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.doubleClicked.connect(self._on_double_clicked)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

        self.match_label = QLabel("")
        self.match_label.setStyleSheet("color: #5b6473; font-size: 9pt;")

        outer.addLayout(header)
        outer.addWidget(subtitle)
        outer.addLayout(filter_row)
        outer.addWidget(self.match_label)
        outer.addWidget(self.table, 1)

    def refresh(self) -> None:
        self._all_projects = list_projects()
        self._apply_filters()

    # -------------------------------------------------------------- filtering
    def _apply_filters(self) -> None:
        needle = self.search_edit.text().strip().lower()
        phase_code = self.phase_filter.currentData()
        status_code = self.status_filter.currentData()

        def match(p) -> bool:
            if phase_code and (p.phase or "") != phase_code:
                return False
            if status_code and (p.status or "") != status_code:
                return False
            if needle:
                haystack = " ".join(
                    str(x or "")
                    for x in (p.name, p.well_name, p.region, p.license_customer, p.operator_llc)
                ).lower()
                if needle not in haystack:
                    return False
            return True

        filtered = [p for p in self._all_projects if match(p)]
        self._render(filtered)
        total = len(self._all_projects)
        shown = len(filtered)
        if shown == total:
            self.match_label.setText(f"{total} projects")
        else:
            self.match_label.setText(f"{shown} of {total} projects (filtered)")

    def _clear_filters(self) -> None:
        self.search_edit.clear()
        self.phase_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)

    def _render(self, projects) -> None:
        self.table.setRowCount(len(projects))
        for row, p in enumerate(projects):
            inv_count = count_investors(p.id)
            cells = [
                p.name,
                p.well_name or "",
                p.region or "",
                p.license_customer or "",
                p.status.title(),
                str(inv_count),
                (p.created_at or "")[:10],
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setData(_PROJECT_ID_ROLE, p.id)
                if col == 5:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

    # ---------------------------------------------------------------- events
    def _on_double_clicked(self, index) -> None:
        if not index.isValid():
            return
        first = self.table.item(index.row(), 0)
        if first is None:
            return
        project_id = first.data(_PROJECT_ID_ROLE)
        if project_id:
            self.projectActivated.emit(project_id)
