"""Costs tab — AFE budget vs actuals + receipts, grouped by phase.

Per-project line items showing expected (AFE budget) vs actual cost, grouped
into 5 phases (Pre-drilling / Drilling / Completion / Facilities / Soft costs)
with collapsible parent rows that show per-phase subtotals.

The grand totals strip at the bottom shows overall expected/actual/variance
plus the IDC vs TDC tax-class breakdown that drives investor tax deductions.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.costs import (
    PHASE_GROUPS,
    PHASE_LABEL,
    attach_receipt,
    delete_cost_line,
    list_cost_lines,
    totals_by_phase,
    totals_for,
)
from wellsign.db.projects import ProjectRow
from wellsign.ui.dialogs import CostLineDialog
from wellsign.ui.dialogs.help_dialog import HelpButton

_HEADERS = [
    "Category", "Description", "Vendor", "Expected (AFE)",
    "Actual", "Variance", "Tax", "Status", "Receipts",
]

_STATUS_COLOR = {
    "planned":   "#5b6473",
    "committed": "#1f6feb",
    "invoiced":  "#d97706",
    "paid":      "#1a7f37",
}

_TAX_LABEL_SHORT = {
    "intangible": "IDC",
    "tangible":   "TDC",
    "mixed":      "MIX",
}

_TAX_COLOR = {
    "intangible": "#1f6feb",
    "tangible":   "#7c3aed",
    "mixed":      "#5b6473",
}

_LINE_ID_ROLE = Qt.ItemDataRole.UserRole + 1


class CostsTab(QWidget):
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
        title = QLabel("Costs")
        f = title.font()
        f.setPointSize(18)
        f.setBold(True)
        title.setFont(f)
        header.addWidget(title)
        header.addStretch(1)

        self.add_btn = QPushButton("+ Add Line")
        self.add_btn.clicked.connect(self._on_add)
        header.addWidget(self.add_btn)

        self.attach_btn = QPushButton("📎 Attach Receipts…")
        self.attach_btn.setProperty("secondary", True)
        self.attach_btn.setEnabled(False)
        self.attach_btn.clicked.connect(self._on_attach_receipts)
        header.addWidget(self.attach_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setProperty("secondary", True)
        self.edit_btn.setEnabled(False)
        self.edit_btn.clicked.connect(self._on_edit_selected)
        header.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setProperty("danger", True)
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete_selected)
        header.addWidget(self.delete_btn)
        header.addWidget(HelpButton("costs"))

        subtitle = QLabel(
            "AFE budget vs. actual costs with receipt attachments. Lines are grouped by "
            "phase (Pre-drilling → Drilling → Completion → Facilities → Soft costs). "
            "Tax class (IDC / TDC) drives investor deductions at year end."
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)

        # Tree (one parent per phase, child rows = line items)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(_HEADERS))
        self.tree.setHeaderLabels(_HEADERS)
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(18)
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(False)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.itemDoubleClicked.connect(lambda *_: self._on_edit_selected())
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)

        h = self.tree.header()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)

        # Totals strip
        self.totals_label = QLabel("")
        self.totals_label.setStyleSheet(
            "background: #f7f9ff; border: 1px solid #d8dce3; border-radius: 6px; "
            "padding: 12px 16px; color: #1f2430;"
        )
        f2 = self.totals_label.font()
        f2.setPointSize(11)
        self.totals_label.setFont(f2)
        self.totals_label.setTextFormat(Qt.TextFormat.RichText)

        outer.addLayout(header)
        outer.addWidget(subtitle)
        outer.addWidget(self.tree, 1)
        outer.addWidget(self.totals_label)

    # ---- public api -----------------------------------------------------
    def set_project(self, project: ProjectRow | None) -> None:
        self._project = project
        self.refresh()

    def refresh(self) -> None:
        self.tree.clear()
        if self._project is None:
            self.totals_label.setText("No project selected.")
            self.add_btn.setEnabled(False)
            return

        self.add_btn.setEnabled(True)
        lines = list_cost_lines(self._project.id)
        phase_subtotals = totals_by_phase(self._project.id)

        # Build a parent row for every phase that exists in PHASE_GROUPS so the
        # tree always has the same five sections in the same order.
        for phase_code, phase_label in PHASE_GROUPS:
            phase_lines = [l for l in lines if l.phase_group == phase_code]
            sub = phase_subtotals.get(phase_code, {"expected": 0.0, "actual": 0.0, "variance": 0.0})

            parent = QTreeWidgetItem(self.tree)
            parent.setText(0, f"  {phase_label}")
            count_text = f"{len(phase_lines)} line{'s' if len(phase_lines) != 1 else ''}"
            parent.setText(1, count_text)
            parent.setText(3, _money(sub["expected"]))
            parent.setText(4, _money(sub["actual"]) if sub["actual"] else "—")
            parent.setText(5, _variance_text(sub["variance"]) if sub["actual"] else "—")
            v_color = _variance_color(sub["variance"]) if sub["actual"] else None

            for col in (3, 4, 5):
                parent.setTextAlignment(
                    col,
                    int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                )
            for col in range(self.tree.columnCount()):
                f = parent.font(col)
                f.setBold(True)
                parent.setFont(col, f)
                parent.setBackground(col, QBrush(QColor("#f3f5fa")))
            if v_color is not None:
                parent.setForeground(5, QBrush(v_color))

            for line in phase_lines:
                child = QTreeWidgetItem(parent)
                child.setData(0, _LINE_ID_ROLE, line.id)

                actual_text = "—" if line.actual_amount is None else _money(line.actual_amount)
                if line.variance is None:
                    variance_text = "—"
                    variance_color: QColor | None = None
                else:
                    variance_text = _variance_text(line.variance)
                    variance_color = _variance_color(line.variance)

                receipt_text = str(len(line.attachments)) if line.attachments else "—"
                tax_short = _TAX_LABEL_SHORT.get(line.tax_class, "—")

                child.setText(0, line.category)
                child.setText(1, line.description)
                child.setText(2, line.vendor or "—")
                child.setText(3, _money(line.expected_amount))
                child.setText(4, actual_text)
                child.setText(5, variance_text)
                child.setText(6, tax_short)
                child.setText(7, line.status.title())
                child.setText(8, receipt_text)

                child.setTextAlignment(3, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                child.setTextAlignment(4, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                child.setTextAlignment(5, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                child.setTextAlignment(6, int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter))
                child.setTextAlignment(7, int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter))
                child.setTextAlignment(8, int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter))

                if variance_color is not None:
                    child.setForeground(5, QBrush(variance_color))
                child.setForeground(6, QBrush(QColor(_TAX_COLOR.get(line.tax_class, "#5b6473"))))
                child.setForeground(7, QBrush(QColor(_STATUS_COLOR.get(line.status, "#5b6473"))))

                if line.attachments:
                    child.setToolTip(8, "\n".join(a.file_name for a in line.attachments))

            parent.setExpanded(True)

        # Grand totals
        t = totals_for(self._project.id)
        v_color = _variance_color(t.variance).name() if t.variance else "#5b6473"
        v_sign = "+" if t.variance > 0.005 else ("−" if t.variance < -0.005 else "")
        idc_pct = (t.intangible_expected / t.expected * 100) if t.expected else 0
        tdc_pct = (t.tangible_expected / t.expected * 100) if t.expected else 0
        self.totals_label.setText(
            f"<b>Expected:</b> {_money(t.expected)}"
            f" &nbsp;·&nbsp; <b>Actual:</b> {_money(t.actual)}"
            f" &nbsp;·&nbsp; <b>Variance:</b> "
            f"<span style='color:{v_color};'><b>{v_sign}{_money(abs(t.variance))}</b></span>"
            f" &nbsp;·&nbsp; <b>Receipts:</b> {t.receipts}<br>"
            f"<span style='color:#5b6473;'>"
            f"<b style='color:#1f6feb;'>IDC</b> (deductible): {_money(t.intangible_expected)} ({idc_pct:.0f}%)"
            f" &nbsp;·&nbsp; "
            f"<b style='color:#7c3aed;'>TDC</b> (depreciable): {_money(t.tangible_expected)} ({tdc_pct:.0f}%)"
            f"</span>"
        )

        self._on_selection_changed()

    # ---- handlers -------------------------------------------------------
    def _selected_id(self) -> str | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        sid = items[0].data(0, _LINE_ID_ROLE)
        return sid if sid else None

    def _on_selection_changed(self) -> None:
        has = self._selected_id() is not None
        self.attach_btn.setEnabled(has)
        self.edit_btn.setEnabled(has)
        self.delete_btn.setEnabled(has)

    def _on_add(self) -> None:
        if self._project is None:
            return
        dlg = CostLineDialog(self, project_id=self._project.id)
        if dlg.exec():
            self.refresh()

    def _on_edit_selected(self) -> None:
        sid = self._selected_id()
        if not sid or self._project is None:
            return
        from wellsign.db.costs import get_cost_line

        existing = get_cost_line(sid)
        if existing is None:
            return
        dlg = CostLineDialog(self, project_id=self._project.id, existing=existing)
        if dlg.exec():
            self.refresh()

    def _on_delete_selected(self) -> None:
        sid = self._selected_id()
        if not sid:
            return
        ans = QMessageBox.question(
            self,
            "Delete cost line",
            "Delete this line item and all its receipt attachments? This cannot be undone.",
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        delete_cost_line(sid)
        self.refresh()

    def _on_attach_receipts(self) -> None:
        sid = self._selected_id()
        if not sid or self._project is None:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Attach Receipts (multi-select)",
            str(Path.home()),
            "All files (*);;PDF (*.pdf);;Images (*.png *.jpg *.jpeg)",
        )
        if not paths:
            return
        for p in paths:
            attach_receipt(sid, self._project.id, Path(p))
        self.refresh()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _money(n: float) -> str:
    return f"${n:,.2f}"


def _variance_text(v: float) -> str:
    sign = "+" if v >= 0 else "−"
    return f"{sign}${abs(v):,.2f}"


def _variance_color(v: float) -> QColor:
    if v > 0.005:
        return QColor("#d1242f")
    if v < -0.005:
        return QColor("#1a7f37")
    return QColor("#5b6473")
