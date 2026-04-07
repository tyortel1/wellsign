"""Email Templates page — global library of message templates."""

from __future__ import annotations

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

from wellsign.db.templates import get_email_template, list_email_templates
from wellsign.ui.dialogs import NewEmailTemplateDialog
from wellsign.ui.dialogs.help_dialog import HelpButton


class EmailTemplatesPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()
        self.refresh()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Email Templates")
        f = title.font()
        f.setPointSize(18)
        f.setBold(True)
        title.setFont(f)
        header.addWidget(title)
        header.addStretch(1)

        self.new_btn = QPushButton("+ New Email Template")
        self.new_btn.clicked.connect(self._on_new)
        header.addWidget(self.new_btn)
        header.addWidget(HelpButton("email_templates"))

        subtitle = QLabel(
            "Reusable email subject + body templates with merge variables. "
            "Used when sending packets to investors via Outlook."
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Purpose", "Subject", "Created"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        outer.addLayout(header)
        outer.addWidget(subtitle)
        outer.addWidget(self.table, 1)

    def refresh(self) -> None:
        templates = list_email_templates()
        self._row_ids: list[str] = [t.id for t in templates]
        self.table.setRowCount(len(templates))
        for row, t in enumerate(templates):
            cells = [t.name, t.purpose.title(), t.subject, (t.created_at or "")[:10]]
            for col, text in enumerate(cells):
                self.table.setItem(row, col, QTableWidgetItem(text))

    def _on_new(self) -> None:
        dlg = NewEmailTemplateDialog(self)
        if dlg.exec():
            self.refresh()

    def _on_double_click(self, row: int, _col: int) -> None:
        if row < 0 or row >= len(self._row_ids):
            return
        existing = get_email_template(self._row_ids[row])
        if existing is None:
            return
        dlg = NewEmailTemplateDialog(self, existing=existing)
        if dlg.exec():
            self.refresh()
