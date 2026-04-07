"""Reconcile tab — end-of-drilling surplus / shortfall calculator.

Top of tab: bold summary card with the three totals (raised / actual / variance)
and the verdict (surplus · shortfall · on-target · incomplete).

Below: per-investor breakdown table showing each investor's contributed amount,
their share of the variance, and the specific refund or supplemental-call
amount owed.

This is a pure computation view for now. Generating actual refund rows or
supplemental cash-call rows (that become investor-facing dollars) is a
follow-up — see the roadmap.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.projects import ProjectRow
from wellsign.db.reconcile import compute_reconciliation

_HEADERS = ["Investor", "Entity", "WI %", "Contributed", "Share", "Action", "Amount"]

_STATUS_COLOR = {
    "surplus":    ("#1a7f37", "#def7e6"),
    "shortfall":  ("#d1242f", "#fde2e4"),
    "on_target":  ("#1f6feb", "#e2ecff"),
    "incomplete": ("#5b6473", "#eef0f4"),
}


class ReconcileTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: ProjectRow | None = None
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(14)

        # Header
        header = QHBoxLayout()
        title = QLabel("Reconciliation")
        f = title.font()
        f.setPointSize(18)
        f.setBold(True)
        title.setFont(f)
        header.addWidget(title)
        header.addStretch(1)

        subtitle = QLabel(
            "End-of-drilling surplus / shortfall calculator. Compares total raised "
            "from investors against total actual well costs, then splits the "
            "variance pro-rata by working interest. Shows each investor's refund "
            "(surplus) or supplemental cash-call amount (shortfall)."
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)

        # Summary card
        self.summary_card = QFrame()
        self.summary_card.setObjectName("ReconcileSummary")
        card_layout = QVBoxLayout(self.summary_card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(8)

        self.raised_label = QLabel("")
        self.actual_label = QLabel("")
        self.variance_label = QLabel("")
        self.verdict_label = QLabel("")
        for lbl in (self.raised_label, self.actual_label, self.variance_label):
            lbl.setStyleSheet("color: #1f2430; font-size: 11pt;")
        verdict_font = QFont()
        verdict_font.setPointSize(14)
        verdict_font.setBold(True)
        self.verdict_label.setFont(verdict_font)
        card_layout.addWidget(self.raised_label)
        card_layout.addWidget(self.actual_label)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #d8dce3;")
        card_layout.addWidget(divider)

        card_layout.addWidget(self.variance_label)
        card_layout.addSpacing(4)
        card_layout.addWidget(self.verdict_label)

        # Per-investor table
        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

        outer.addLayout(header)
        outer.addWidget(subtitle)
        outer.addWidget(self.summary_card)
        outer.addWidget(self.table, 1)

    # ---- public api ------------------------------------------------------
    def set_project(self, project: ProjectRow | None) -> None:
        self._project = project
        self.refresh()

    def refresh(self) -> None:
        self.table.setRowCount(0)
        if self._project is None:
            self._paint_card("incomplete", "No project selected", "—", "—", "—")
            self.verdict_label.setText("No project selected.")
            return

        recon = compute_reconciliation(self._project.id)
        if recon is None:
            self._paint_card("incomplete", "—", "—", "—", "—")
            self.verdict_label.setText("Could not compute reconciliation.")
            return

        # Paint summary card
        self._paint_card(
            recon.status,
            _money(recon.total_raised),
            _money(recon.total_actual_costs),
            _variance_text(recon.variance),
            recon.summary_label,
        )

        # Populate per-investor table
        self.table.setRowCount(len(recon.per_investor))
        for r, ir in enumerate(recon.per_investor):
            cells: list[tuple[str, Qt.AlignmentFlag, QColor | None]] = [
                (ir.name,                            Qt.AlignmentFlag.AlignLeft,   None),
                (ir.entity_name or "—",              Qt.AlignmentFlag.AlignLeft,   None),
                (f"{ir.wi_percent * 100:.6f}%",      Qt.AlignmentFlag.AlignRight,  None),
                (_money(ir.contributed),             Qt.AlignmentFlag.AlignRight,  None),
                (_variance_text(ir.share_of_variance), Qt.AlignmentFlag.AlignRight,
                                                      _variance_color(ir.share_of_variance)),
                (ir.action.title() if ir.action != "none" else "—",
                                                      Qt.AlignmentFlag.AlignCenter, _action_color(ir.action)),
                (_money(ir.amount) if ir.action != "none" else "—",
                                                      Qt.AlignmentFlag.AlignRight,  _action_color(ir.action)),
            ]
            for col, (text, align, color) in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(int(align | Qt.AlignmentFlag.AlignVCenter))
                if color is not None:
                    item.setForeground(QBrush(color))
                    if col in (5, 6):
                        font = QFont(item.font())
                        font.setBold(True)
                        item.setFont(font)
                self.table.setItem(r, col, item)

    # ---- helpers ---------------------------------------------------------
    def _paint_card(
        self,
        status: str,
        raised: str,
        actual: str,
        variance_text: str,
        verdict: str,
    ) -> None:
        fg, bg = _STATUS_COLOR.get(status, _STATUS_COLOR["incomplete"])
        self.summary_card.setStyleSheet(
            f"QFrame#ReconcileSummary {{ background: {bg}; "
            f"border: 1px solid {fg}; border-radius: 8px; }}"
        )
        self.raised_label.setText(
            f"<b>Total raised from investors:</b> &nbsp; {raised}"
        )
        self.actual_label.setText(
            f"<b>Total actual well costs:</b> &nbsp; &nbsp; &nbsp; &nbsp; {actual}"
        )
        self.variance_label.setText(
            f"<b>Variance:</b> &nbsp; <span style='color:{fg};'><b>{variance_text}</b></span>"
        )
        self.verdict_label.setText(verdict)
        self.verdict_label.setStyleSheet(f"color: {fg};")


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def _money(n: float) -> str:
    return f"${n:,.2f}"


def _variance_text(v: float) -> str:
    sign = "+" if v >= 0 else "−"
    return f"{sign}${abs(v):,.2f}"


def _variance_color(v: float) -> QColor:
    if v > 0.005:
        return QColor("#1a7f37")  # green — money back to investor
    if v < -0.005:
        return QColor("#d1242f")  # red — money owed by investor
    return QColor("#5b6473")


def _action_color(action: str) -> QColor | None:
    if action == "refund":
        return QColor("#1a7f37")
    if action == "owe":
        return QColor("#d1242f")
    return None
