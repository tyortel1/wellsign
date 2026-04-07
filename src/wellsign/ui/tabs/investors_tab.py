"""Investors tab — table view of every investor on the active project."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
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

from wellsign.db.investors import get_investor, list_investors
from wellsign.db.projects import ProjectRow
from wellsign.db.workflows import TrafficLight, compute_traffic_light
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
        self._build()

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
        self.add_btn = QPushButton("+ Add Investor")
        self.add_btn.clicked.connect(self._on_add)
        header.addWidget(self.import_btn)
        header.addWidget(self.add_btn)

        self.summary_label = QLabel("No project selected.")
        self.summary_label.setStyleSheet("color: #5b6473;")

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

        outer.addLayout(header)
        outer.addWidget(self.summary_label)
        outer.addWidget(self.table, 1)

    def set_project(self, project: ProjectRow | None) -> None:
        self._project = project
        self.refresh()

    def refresh(self) -> None:
        if self._project is None:
            self.table.setRowCount(0)
            self.summary_label.setText("No project selected.")
            return

        rows = list_investors(self._project.id)
        wi_total = sum(r.wi_percent for r in rows)
        llg_total = sum((r.llg_amount or 0) for r in rows)
        dhc_total = sum((r.dhc_amount or 0) for r in rows)
        ok = abs(wi_total - 1.0) < 0.0001 if rows else False
        status_color = "#1a7f37" if ok else ("#5b6473" if wi_total == 0 else "#d97706")
        self.summary_label.setText(
            f"<span style='color:{status_color};'><b>{len(rows)}</b> investors  ·  "
            f"WI sum: <b>{wi_total * 100:.6f}%</b>  ·  "
            f"LLG total: <b>${llg_total:,.2f}</b>  ·  "
            f"DHC total: <b>${dhc_total:,.2f}</b></span>"
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
        dlg = InvestorDialog(self._project, parent=self, existing=existing)
        if dlg.exec() and dlg.saved_investor is not None:
            self.refresh()
