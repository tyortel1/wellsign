"""Document Templates page — global library of PDF templates."""

from __future__ import annotations

from PySide6.QtCore import Qt
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

from wellsign.db.templates import get_doc_template, list_doc_templates
from wellsign.ui.dialogs import FieldMappingDialog, NewDocTemplateDialog
from wellsign.ui.dialogs.help_dialog import HelpButton


class DocTemplatesPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()
        self.refresh()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Document Templates")
        f = title.font()
        f.setPointSize(18)
        f.setBold(True)
        title.setFont(f)
        header.addWidget(title)
        header.addStretch(1)

        self.map_btn = QPushButton("Map Fields…")
        self.map_btn.setProperty("secondary", True)
        self.map_btn.setToolTip("Bind PDF form fields on the selected template to merge variables")
        self.map_btn.clicked.connect(self._on_map_fields)
        header.addWidget(self.map_btn)

        self.new_btn = QPushButton("+ New Document Template")
        self.new_btn.clicked.connect(self._on_new)
        header.addWidget(self.new_btn)
        header.addWidget(HelpButton("doc_templates"))

        subtitle = QLabel(
            "Reusable PDF templates. Each template has form fields that get auto-filled "
            "with investor data when generating a project's packets."
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Page Size", "Notary", "Mapped fields", "Storage Path"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        outer.addLayout(header)
        outer.addWidget(subtitle)
        outer.addWidget(self.table, 1)

    def refresh(self) -> None:
        templates = list_doc_templates()
        self._row_ids: list[str] = [t.id for t in templates]
        self.table.setRowCount(len(templates))
        for row, t in enumerate(templates):
            mapped_count = len(t.field_mapping or {})
            cells = [
                t.name,
                t.doc_type,
                (t.page_size or "").title(),
                "Yes" if t.notary_required else "—",
                f"{mapped_count} mapped" if mapped_count else "— none —",
                t.storage_path,
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if col in (3, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

    def _on_new(self) -> None:
        dlg = NewDocTemplateDialog(self)
        if dlg.exec():
            self.refresh()

    def _on_double_click(self, row: int, _col: int) -> None:
        if row < 0 or row >= len(self._row_ids):
            return
        existing = get_doc_template(self._row_ids[row])
        if existing is None:
            return
        dlg = NewDocTemplateDialog(self, existing=existing)
        if dlg.exec():
            self.refresh()

    def _on_map_fields(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._row_ids):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "No template", "Select a template row first.")
            return
        existing = get_doc_template(self._row_ids[row])
        if existing is None:
            return
        dlg = FieldMappingDialog(existing, parent=self)
        if dlg.exec() and dlg.saved:
            self.refresh()
