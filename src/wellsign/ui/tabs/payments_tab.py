"""Payments tab — operator's view of incoming investor money.

This is the OTHER side of the Costs tab. Costs tracks what the operator
SPENDS on a well (drilling, casing, frac, etc). Payments tracks what the
operator COLLECTS from investors (LLG to Decker, DHC to Paloma).

One row per investor per payment type, so for a 5-investor project there
are 10 rows: Almanza LLG, Almanza DHC, Brennan LLG, Brennan DHC, ...

The operator's daily workflow on this tab:
  * Open the tab in the morning
  * See "$X outstanding" at the top
  * Filter to "Outstanding only" or "Overdue"
  * For every wire/check that came in: double-click the row, enter the
    amount + date + method + reference number, hit Save
  * Watch the totals row update
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.investors import list_investors
from wellsign.db.migrate import connect
from wellsign.db.payments import (
    PaymentRow,
    list_for_project,
    mark_overdue_if_past,
    totals_for_project,
)
from wellsign.db.projects import ProjectRow
from wellsign.ui.dialogs.payment_dialog import PaymentDialog

_HEADERS = [
    "", "Investor", "Type", "Payee", "Expected",
    "Received", "Variance", "Method", "Date", "Reference", "Status",
]
_PAYMENT_ID_ROLE = Qt.ItemDataRole.UserRole + 1

_STATUS_COLOR = {
    "expected": QColor("#5b6473"),
    "partial":  QColor("#d97706"),
    "received": QColor("#1a7f37"),
    "overdue":  QColor("#d1242f"),
}

_STATUS_LABEL = {
    "expected": "Expected",
    "partial":  "Partial",
    "received": "Received",
    "overdue":  "Overdue",
}


class PaymentsTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: ProjectRow | None = None
        self._all_payments: list[PaymentRow] = []
        self._build()

    # ---- layout ---------------------------------------------------------
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(14)

        # Header row
        header = QHBoxLayout()
        title = QLabel("Payments")
        f = title.font()
        f.setPointSize(18)
        f.setBold(True)
        title.setFont(f)
        header.addWidget(title)
        header.addStretch(1)

        self.filter_combo = QComboBox()
        self.filter_combo.addItem("All payments",     "all")
        self.filter_combo.addItem("Outstanding only", "outstanding")
        self.filter_combo.addItem("Received only",    "received")
        self.filter_combo.addItem("Overdue only",     "overdue")
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        header.addWidget(self.filter_combo)

        self.mark_btn = QPushButton("Mark Received…")
        self.mark_btn.setEnabled(False)
        self.mark_btn.clicked.connect(self._on_mark_received)
        header.addWidget(self.mark_btn)

        subtitle = QLabel(
            "Per-investor incoming payment tracker. <b>LLG</b> wires/checks "
            "go to <b>Decker Exploration</b>; <b>DHC</b> wires/checks go to "
            "<b>Paloma Operating</b>. Double-click a row (or select + Mark "
            "Received) to log a wire/check. Status auto-derives from amount "
            "received vs expected."
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)

        # Table
        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._on_row_changed)
        self.table.doubleClicked.connect(lambda *_: self._on_mark_received())
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(10, QHeaderView.ResizeMode.ResizeToContents)

        # Totals strip
        self.totals_label = QLabel("")
        self.totals_label.setStyleSheet(
            "background: #f7f9ff; border: 1px solid #d8dce3; border-radius: 6px; "
            "padding: 12px 16px; color: #1f2430;"
        )
        f2 = self.totals_label.font()
        f2.setPointSize(11)
        f2.setBold(True)
        self.totals_label.setFont(f2)

        outer.addLayout(header)
        outer.addWidget(subtitle)
        outer.addWidget(self.table, 1)
        outer.addWidget(self.totals_label)

    # ---- public api -----------------------------------------------------
    def set_project(self, project: ProjectRow | None) -> None:
        self._project = project
        self.refresh()

    def refresh(self) -> None:
        if self._project is None:
            self.table.setRowCount(0)
            self.totals_label.setText("No project selected.")
            self.mark_btn.setEnabled(False)
            return

        # Auto-flip past-deadline expected rows to overdue
        deadline = self._close_deadline()
        if deadline:
            mark_overdue_if_past(self._project.id, deadline)

        self._all_payments = list_for_project(self._project.id)
        self._render_table()
        self._render_totals()

    # ---- table rendering ------------------------------------------------
    def _render_table(self) -> None:
        # Investor lookup for display name
        inv_names = {i.id: i.display_name for i in list_investors(self._project.id)}

        filtered = self._filtered_payments()

        # Disable sorting while we mutate, re-enable after
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(filtered))

        for r, p in enumerate(filtered):
            received_text = (
                "—" if p.received_amount is None else f"${p.received_amount:,.2f}"
            )
            variance = p.variance
            if variance is None:
                variance_text = "—"
                variance_color: QColor | None = None
            else:
                sign = "+" if variance >= 0 else "−"
                variance_text = f"{sign}${abs(variance):,.2f}"
                if variance > 0.005:
                    variance_color = QColor("#1a7f37")  # got more = green
                elif variance < -0.005:
                    variance_color = QColor("#d1242f")  # short = red
                else:
                    variance_color = QColor("#5b6473")

            cells: list[tuple[str, Qt.AlignmentFlag, QColor | None, bool]] = [
                ("●", Qt.AlignmentFlag.AlignCenter, _STATUS_COLOR[p.status], True),
                (inv_names.get(p.investor_id, "(unknown)"),
                                                       Qt.AlignmentFlag.AlignLeft, None, False),
                (p.payment_type.upper(),               Qt.AlignmentFlag.AlignCenter, None, False),
                (p.payee.title(),                      Qt.AlignmentFlag.AlignLeft, None, False),
                (f"${p.expected_amount:,.2f}",         Qt.AlignmentFlag.AlignRight, None, False),
                (received_text,                        Qt.AlignmentFlag.AlignRight, None, False),
                (variance_text,                        Qt.AlignmentFlag.AlignRight, variance_color, False),
                ((p.method or "—").title(),            Qt.AlignmentFlag.AlignCenter, None, False),
                ((p.received_at or "")[:10] or "—",    Qt.AlignmentFlag.AlignCenter, None, False),
                (p.reference_number or "—",            Qt.AlignmentFlag.AlignLeft, None, False),
                (_STATUS_LABEL[p.status],              Qt.AlignmentFlag.AlignCenter,
                                                          _STATUS_COLOR[p.status], False),
            ]
            for col, (text, align, color, big_dot) in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(int(align | Qt.AlignmentFlag.AlignVCenter))
                if color is not None:
                    item.setForeground(QBrush(color))
                if big_dot:
                    f = QFont(item.font())
                    f.setPointSize(16)
                    f.setBold(True)
                    item.setFont(f)
                if col == 0:
                    item.setData(_PAYMENT_ID_ROLE, p.id)
                self.table.setItem(r, col, item)

        self.table.setSortingEnabled(True)

    def _render_totals(self) -> None:
        if self._project is None:
            return
        t = totals_for_project(self._project.id)

        def _delta_color(outstanding: float) -> str:
            if outstanding > 0.005:
                return "#d97706"  # money still owed = amber
            return "#1a7f37"      # all in = green

        llg_color = _delta_color(t.llg_outstanding)
        dhc_color = _delta_color(t.dhc_outstanding)
        total_color = _delta_color(t.total_outstanding)

        self.totals_label.setText(
            f"<b>LLG (→ Decker)</b>: ${t.llg_received:,.2f} of ${t.llg_expected:,.2f}  "
            f"<span style='color:{llg_color};'>(${t.llg_outstanding:,.2f} outstanding)</span>"
            f"     ·     "
            f"<b>DHC (→ Paloma)</b>: ${t.dhc_received:,.2f} of ${t.dhc_expected:,.2f}  "
            f"<span style='color:{dhc_color};'>(${t.dhc_outstanding:,.2f} outstanding)</span>"
            f"     ·     "
            f"<b>Total collected</b>: ${t.total_received:,.2f} of ${t.total_expected:,.2f}  "
            f"<span style='color:{total_color};'>(${t.total_outstanding:,.2f} outstanding)</span>"
        )

    # ---- filtering ------------------------------------------------------
    def _filtered_payments(self) -> list[PaymentRow]:
        mode = self.filter_combo.currentData() or "all"
        if mode == "all":
            return self._all_payments
        if mode == "outstanding":
            return [p for p in self._all_payments if p.status in ("expected", "partial", "overdue")]
        if mode == "received":
            return [p for p in self._all_payments if p.status == "received"]
        if mode == "overdue":
            return [p for p in self._all_payments if p.status == "overdue"]
        return self._all_payments

    def _apply_filter(self) -> None:
        self._render_table()

    # ---- handlers -------------------------------------------------------
    def _selected_payment_id(self) -> str | None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        row = rows[0].row()
        item = self.table.item(row, 0)
        if item is None:
            return None
        return item.data(_PAYMENT_ID_ROLE)

    def _on_row_changed(self) -> None:
        self.mark_btn.setEnabled(self._selected_payment_id() is not None)

    def _on_mark_received(self) -> None:
        pid = self._selected_payment_id()
        if pid is None or self._project is None:
            return
        # Find the row to get the matching investor name
        target = next((p for p in self._all_payments if p.id == pid), None)
        if target is None:
            return
        inv_names = {i.id: i.display_name for i in list_investors(self._project.id)}
        investor_name = inv_names.get(target.investor_id, "(unknown)")
        dlg = PaymentDialog(target, investor_name=investor_name, parent=self)
        if dlg.exec() and dlg.saved_payment is not None:
            self.refresh()

    # ---- helpers --------------------------------------------------------
    def _close_deadline(self) -> str | None:
        if self._project is None:
            return None
        with connect() as conn:
            row = conn.execute(
                "SELECT close_deadline FROM projects WHERE id = ?",
                (self._project.id,),
            ).fetchone()
        return row["close_deadline"] if row else None
