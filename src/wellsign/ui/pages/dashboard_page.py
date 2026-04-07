"""Dashboard page — cross-project overview shown when 'Projects' root is selected."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.investors import count_investors
from wellsign.db.projects import list_projects
from wellsign.ui.dialogs.help_dialog import HelpButton


class DashboardPage(QWidget):
    """Cross-project dashboard. Header + table + 'New Project' button."""

    newProjectRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
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
            "Side-by-side view of every project. Click a project in the navigator "
            "on the left to drill into its workspace."
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)

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
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

        outer.addLayout(header)
        outer.addWidget(subtitle)
        outer.addWidget(self.table, 1)

    def refresh(self) -> None:
        projects = list_projects()
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
                if col in (5,):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)
