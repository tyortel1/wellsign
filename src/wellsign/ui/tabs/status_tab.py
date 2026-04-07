"""Status tab — per-investor dashboard for the active project.

One row per investor showing a quick-read of where they sit in the workflow:
  * colored traffic-light dot
  * name + entity
  * current stage name
  * days in stage
  * SLA / days remaining (or overdue)
  * next email that's due to go out
  * overall status pill

This is the operator's morning dashboard: "who do I need to chase today".
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.investors import list_investors
from wellsign.db.projects import ProjectRow
from wellsign.db.workflows import (
    TrafficLight,
    compute_pending_sends,
    compute_traffic_light,
)

_HEADERS = [
    "", "Investor", "Entity", "Stage", "Days In", "SLA", "Remaining", "Next Email", "Status",
]

_LIGHT_COLOR = {
    TrafficLight.GREEN:  QColor("#1a7f37"),
    TrafficLight.YELLOW: QColor("#d97706"),
    TrafficLight.RED:    QColor("#d1242f"),
    TrafficLight.GREY:   QColor("#aab1bd"),
}


class StatusTab(QWidget):
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
        title = QLabel("Status")
        f = title.font()
        f.setPointSize(18)
        f.setBold(True)
        title.setFont(f)
        header.addWidget(title)
        header.addStretch(1)

        subtitle = QLabel(
            "Per-investor dashboard: current stage, days in stage, SLA remaining, "
            "and the next email due to go out. Sort the table by any column to find "
            "the investors that need your attention first."
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)

        # Light summary bar
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #5b6473;")

        # Table
        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)

        outer.addLayout(header)
        outer.addWidget(subtitle)
        outer.addWidget(self.summary_label)
        outer.addWidget(self.table, 1)

    # ---- public api ------------------------------------------------------
    def set_project(self, project: ProjectRow | None) -> None:
        self._project = project
        self.refresh()

    def refresh(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        if self._project is None:
            self.summary_label.setText("No project selected.")
            return

        investors = list_investors(self._project.id)
        pending_by_investor = self._pending_map()

        counts = {"green": 0, "yellow": 0, "red": 0, "grey": 0}
        self.table.setRowCount(len(investors))
        for r, inv in enumerate(investors):
            traffic = compute_traffic_light(inv.id)
            counts[traffic.light.value] += 1

            dot = QTableWidgetItem("●")
            dot.setForeground(QBrush(_LIGHT_COLOR[traffic.light]))
            dot.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            f = QFont(dot.font())
            f.setPointSize(16)
            f.setBold(True)
            dot.setFont(f)
            dot.setToolTip(traffic.label)
            self.table.setItem(r, 0, dot)

            self.table.setItem(r, 1, QTableWidgetItem(inv.display_name))
            self.table.setItem(r, 2, QTableWidgetItem(inv.entity_name or "—"))
            stage_name = traffic.stage.name if traffic.stage else "—"
            self.table.setItem(r, 3, QTableWidgetItem(stage_name))

            days_in_item = QTableWidgetItem()
            days_in_item.setData(Qt.ItemDataRole.DisplayRole, traffic.days_in_stage)
            days_in_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 4, days_in_item)

            sla_txt = ""
            if traffic.stage and traffic.stage.duration_days is not None:
                sla_txt = f"{traffic.stage.duration_days}d"
            self.table.setItem(r, 5, QTableWidgetItem(sla_txt))

            remaining_item = QTableWidgetItem()
            if traffic.days_remaining is not None:
                remaining_item.setData(Qt.ItemDataRole.DisplayRole, traffic.days_remaining)
                if traffic.days_remaining < 0:
                    remaining_item.setForeground(QBrush(QColor("#d1242f")))
                elif traffic.days_remaining <= 3:
                    remaining_item.setForeground(QBrush(QColor("#d97706")))
                else:
                    remaining_item.setForeground(QBrush(QColor("#1a7f37")))
            remaining_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, 6, remaining_item)

            # Next email
            next_email = pending_by_investor.get(inv.id)
            if next_email:
                txt = f"{next_email[0]}  ({next_email[1]})"
            else:
                txt = "—"
            self.table.setItem(r, 7, QTableWidgetItem(txt))

            status_item = QTableWidgetItem(traffic.label)
            status_item.setForeground(QBrush(_LIGHT_COLOR[traffic.light]))
            self.table.setItem(r, 8, status_item)

        self.table.setSortingEnabled(True)

        self.summary_label.setText(
            f"<span style='color:#1a7f37;'><b>{counts['green']}</b> on track</span>"
            f"  ·  "
            f"<span style='color:#d97706;'><b>{counts['yellow']}</b> warning</span>"
            f"  ·  "
            f"<span style='color:#d1242f;'><b>{counts['red']}</b> overdue</span>"
            f"  ·  "
            f"<span style='color:#aab1bd;'><b>{counts['grey']}</b> not started</span>"
            f"  ·  <b>{len(investors)}</b> total"
        )

    # ---- helpers ---------------------------------------------------------
    def _pending_map(self) -> dict[str, tuple[str, str]]:
        """Return the next-due email per investor: {investor_id: (name, due_label)}."""
        if self._project is None:
            return {}
        result: dict[str, tuple[str, str]] = {}
        for ps in compute_pending_sends(self._project.id):
            if ps.investor_id in result:
                continue  # first one (most overdue / most due) wins
            if ps.days_overdue > 0:
                label = f"overdue {ps.days_overdue}d"
            elif ps.days_overdue == 0:
                label = "due today"
            else:
                label = f"in {-ps.days_overdue}d"
            result[ps.investor_id] = (ps.email_template_name, label)
        return result
