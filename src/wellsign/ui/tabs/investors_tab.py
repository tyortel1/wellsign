"""Investors tab — table view of every investor on the active project."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QBrush, QColor, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wellsign.app_paths import investor_dir
from wellsign.db.investors import delete_investor, get_investor, list_investors
from wellsign.db.projects import ProjectRow
from wellsign.db.workflows import TrafficLight, compute_traffic_light
from wellsign.ui.dialogs.help_dialog import HelpButton
from wellsign.ui.dialogs.import_investors_dialog import ImportInvestorsDialog
from wellsign.ui.dialogs.investor_detail_dialog import InvestorDetailDialog
from wellsign.ui.dialogs.investor_dialog import InvestorDialog

_INVESTOR_ID_ROLE = Qt.ItemDataRole.UserRole + 1

_HEADERS = [
    "", "Name", "Entity", "Email", "City, State", "WI %",
    "LLG (Decker)", "DHC (Paloma)", "Stage",
]

_LIGHT_COLORS = {
    TrafficLight.GREEN:  QColor("#1a7f37"),
    TrafficLight.YELLOW: QColor("#d97706"),
    TrafficLight.RED:    QColor("#d1242f"),
    TrafficLight.GREY:   QColor("#aab1bd"),
}


class InvestorsTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: ProjectRow | None = None
        self._all_investors: list = []
        self._build()
        # Accept drops of .xlsx files onto the tab itself
        self.setAcceptDrops(True)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Investors")
        f = title.font()
        f.setPointSize(18)
        f.setBold(True)
        title.setFont(f)
        header.addWidget(title)
        header.addStretch(1)

        self.import_btn = QPushButton("Import from Excel…")
        self.import_btn.setProperty("secondary", True)
        self.import_btn.setToolTip("Pick an .xlsx file — or drag one onto this tab")
        self.import_btn.clicked.connect(self._on_import)
        self.add_btn = QPushButton("+ Add Investor")
        self.add_btn.clicked.connect(self._on_add)
        header.addWidget(self.import_btn)
        header.addWidget(self.add_btn)
        header.addWidget(HelpButton("investors"))

        self.summary_label = QLabel("No project selected.")
        self.summary_label.setStyleSheet("color: #5b6473;")

        # Filter bar: free-text search + state filter + status filter
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search name, entity, email, city…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filters)
        filter_row.addWidget(self.search_edit, 1)

        state_lbl = QLabel("State:")
        state_lbl.setStyleSheet("color: #5b6473;")
        filter_row.addWidget(state_lbl)
        self.state_filter = QComboBox()
        self.state_filter.addItem("All", userData=None)
        self.state_filter.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self.state_filter)

        status_lbl = QLabel("Status:")
        status_lbl.setStyleSheet("color: #5b6473;")
        filter_row.addWidget(status_lbl)
        self.status_filter = QComboBox()
        self.status_filter.addItem("All", userData=None)
        for code, label in (
            ("not_sent", "Not sent"),
            ("sent",     "Sent"),
            ("partial",  "Partial"),
            ("complete", "Complete"),
        ):
            self.status_filter.addItem(label, userData=code)
        self.status_filter.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self.status_filter)

        self.clear_filters_btn = QPushButton("Clear")
        self.clear_filters_btn.setProperty("secondary", True)
        self.clear_filters_btn.clicked.connect(self._clear_filters)
        filter_row.addWidget(self.clear_filters_btn)

        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self._on_double_clicked)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)

        outer.addLayout(header)
        outer.addWidget(self.summary_label)
        outer.addLayout(filter_row)
        outer.addWidget(self.table, 1)

    def set_project(self, project: ProjectRow | None) -> None:
        self._project = project
        self.refresh()

    def refresh(self) -> None:
        if self._project is None:
            self.table.setRowCount(0)
            self.summary_label.setText("No project selected.")
            self._all_investors = []
            return

        self._all_investors = list_investors(self._project.id)

        # Populate the state filter from the current investor set
        current_state = self.state_filter.currentData()
        self.state_filter.blockSignals(True)
        self.state_filter.clear()
        self.state_filter.addItem("All", userData=None)
        for s in sorted({(i.state or "").upper() for i in self._all_investors if i.state}):
            self.state_filter.addItem(s, userData=s)
        # Restore the previous selection if it's still present
        idx = self.state_filter.findData(current_state)
        if idx >= 0:
            self.state_filter.setCurrentIndex(idx)
        self.state_filter.blockSignals(False)

        self._apply_filters()

    def _apply_filters(self) -> None:
        if self._project is None:
            return
        needle = self.search_edit.text().strip().lower()
        state_code = self.state_filter.currentData()
        status_code = self.status_filter.currentData()

        def match(inv) -> bool:
            if state_code and (inv.state or "").upper() != state_code:
                return False
            if status_code and (inv.portal_status or "") != status_code:
                return False
            if needle:
                haystack = " ".join(
                    str(x or "")
                    for x in (inv.first_name, inv.last_name, inv.entity_name,
                              inv.email, inv.city, inv.state)
                ).lower()
                if needle not in haystack:
                    return False
            return True

        rows = [i for i in self._all_investors if match(i)]

        wi_total = sum(r.wi_percent for r in rows)
        llg_total = sum((r.llg_amount or 0) for r in rows)
        dhc_total = sum((r.dhc_amount or 0) for r in rows)
        ok = abs(wi_total - 1.0) < 0.0001 if rows else False
        status_color = "#1a7f37" if ok else ("#5b6473" if wi_total == 0 else "#d97706")
        total_count = len(self._all_investors)
        filter_note = ""
        if len(rows) != total_count:
            filter_note = f"  ·  showing <b>{len(rows)}</b> of <b>{total_count}</b> (filtered)"
        self.summary_label.setText(
            f"<span style='color:{status_color};'><b>{len(rows)}</b> investors  ·  "
            f"WI sum: <b>{wi_total * 100:.6f}%</b>  ·  "
            f"LLG total: <b>${llg_total:,.2f}</b>  ·  "
            f"DHC total: <b>${dhc_total:,.2f}</b>{filter_note}</span>"
        )

        self.table.setRowCount(len(rows))
        for r, inv in enumerate(rows):
            traffic = compute_traffic_light(inv.id)
            light_color = _LIGHT_COLORS[traffic.light]

            light_item = QTableWidgetItem("●")
            light_item.setForeground(QBrush(light_color))
            light_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            light_item.setToolTip(traffic.label)
            font = light_item.font()
            font.setPointSize(16)
            font.setBold(True)
            light_item.setFont(font)
            light_item.setData(_INVESTOR_ID_ROLE, inv.id)
            self.table.setItem(r, 0, light_item)

            cells = [
                inv.display_name,
                inv.entity_name or "—",
                inv.email or "—",
                ", ".join([x for x in (inv.city, inv.state) if x]) or "—",
                f"{inv.wi_percent * 100:.6f}%",
                f"${(inv.llg_amount or 0):,.2f}",
                f"${(inv.dhc_amount or 0):,.2f}",
                traffic.label,
            ]
            for offset, text in enumerate(cells):
                col = offset + 1
                item = QTableWidgetItem(text)
                if col in (5, 6, 7):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(r, col, item)

    # ---- handlers --------------------------------------------------------
    def _on_add(self) -> None:
        if self._project is None:
            return
        dlg = InvestorDialog(self._project, parent=self)
        if dlg.exec() and dlg.saved_investor is not None:
            self.refresh()

    def _on_import(self, initial: Path | None = None) -> None:
        if self._project is None:
            QMessageBox.information(
                self, "No project", "Select a project from the navigator first."
            )
            return
        dlg = ImportInvestorsDialog(
            self._project,
            parent=self,
            initial_file=initial,
        )
        if dlg.exec():
            msg_lines = [f"Imported {dlg.imported_count} investor(s)."]
            if dlg.skipped_count:
                msg_lines.append(f"Skipped {dlg.skipped_count} row(s).")
            if dlg.errors:
                msg_lines.append("")
                msg_lines.append("Details:")
                msg_lines.extend(dlg.errors[:10])
                if len(dlg.errors) > 10:
                    msg_lines.append(f"… and {len(dlg.errors) - 10} more")
            QMessageBox.information(self, "Import complete", "\n".join(msg_lines))
            self.refresh()

    # ---- drag-drop -------------------------------------------------------
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 — Qt override
        if self._extract_xlsx_path(event) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 — Qt override
        if self._extract_xlsx_path(event) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 — Qt override
        path = self._extract_xlsx_path(event)
        if path is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self._on_import(initial=path)

    @staticmethod
    def _extract_xlsx_path(event) -> Path | None:
        md = event.mimeData() if hasattr(event, "mimeData") else None
        if md is None or not md.hasUrls():
            return None
        for url in md.urls():
            if not url.isLocalFile():
                continue
            p = Path(url.toLocalFile())
            if p.suffix.lower() in (".xlsx", ".xlsm"):
                return p
        return None

    def _on_double_clicked(self, index) -> None:
        if self._project is None or not index.isValid():
            return
        row = index.row()
        light_item = self.table.item(row, 0)
        if light_item is None:
            return
        investor_id = light_item.data(_INVESTOR_ID_ROLE)
        if not investor_id:
            return
        existing = get_investor(investor_id)
        if existing is None:
            return
        dlg = InvestorDetailDialog(self._project, existing, parent=self)
        dlg.exec()
        if dlg.refreshed:
            self.refresh()

    # ---- filter + context menu ------------------------------------------
    def _clear_filters(self) -> None:
        self.search_edit.clear()
        self.state_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)

    def _selected_investor_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        light_item = self.table.item(row, 0)
        if light_item is None:
            return None
        return light_item.data(_INVESTOR_ID_ROLE)

    def _on_context_menu(self, pos: QPoint) -> None:
        if self._project is None:
            return
        row = self.table.indexAt(pos).row()
        if row < 0:
            return
        self.table.selectRow(row)
        investor_id = self._selected_investor_id()
        if not investor_id:
            return
        inv = get_investor(investor_id)
        if inv is None:
            return

        menu = QMenu(self)
        edit_action = QAction("Edit investor…", self)
        edit_action.triggered.connect(lambda: self._on_double_clicked(self.table.currentIndex()))
        menu.addAction(edit_action)

        menu.addSeparator()

        if inv.email:
            copy_email_action = QAction("Copy email", self)
            copy_email_action.triggered.connect(lambda: self._copy_to_clipboard(inv.email))
            menu.addAction(copy_email_action)

        address_parts = [p for p in (inv.address_line1, inv.city, inv.state, inv.zip) if p]
        if address_parts:
            copy_addr_action = QAction("Copy address", self)
            copy_addr_action.triggered.connect(
                lambda: self._copy_to_clipboard(", ".join(address_parts))
            )
            menu.addAction(copy_addr_action)

        menu.addSeparator()

        open_folder_action = QAction("Open investor folder", self)
        open_folder_action.triggered.connect(
            lambda: self._open_investor_folder(inv.id)
        )
        menu.addAction(open_folder_action)

        menu.addSeparator()

        delete_action = QAction("Delete investor…", self)
        delete_action.triggered.connect(lambda: self._on_delete(inv))
        menu.addAction(delete_action)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _copy_to_clipboard(self, text: str) -> None:
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(text)

    def _open_investor_folder(self, investor_id: str) -> None:
        if self._project is None:
            return
        folder = investor_dir(self._project.id, investor_id)
        try:
            if sys.platform == "win32":
                os.startfile(str(folder))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(folder)], check=False)
            else:
                subprocess.run(["xdg-open", str(folder)], check=False)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Open folder failed", str(e))

    def _on_delete(self, inv) -> None:
        name = inv.display_name
        ans = QMessageBox.question(
            self,
            "Delete investor",
            f"Delete investor <b>{name}</b>?<br><br>"
            "This removes the database row and any generated document rows "
            "that reference this investor (via ON DELETE CASCADE). Files on "
            "disk in this investor's folder are NOT deleted.",
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        delete_investor(inv.id)
        self.refresh()
