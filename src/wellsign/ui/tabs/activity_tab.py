"""Activity tab — project-wide chronological event timeline.

Unified timeline pulling from every persistence point we already have:

  * send_events                  → ✉  Email sent to X
  * investor_documents           → 📄 Document generated / received for X
  * investor_stage_runs          → 📜 X entered stage / completed stage
  * payments (received_at)       → 💰 Payment received from X
  * projects.phase_entered_at    → 🚩 Project entered phase
  * cost_line_items (updated_at with actual)  → 💵 Actual cost logged

Sorted most-recent-first. Filter dropdown lets you show all events or
restrict to a single type. Click a row to see details (for docs, opens the
file; for emails, shows the rendered body in a dialog).
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.investors import list_investors
from wellsign.db.migrate import connect
from wellsign.db.projects import ProjectRow
from wellsign.db.workflows import get_stage


@dataclass
class ActivityEvent:
    timestamp: str           # ISO
    event_type: str          # 'email' | 'doc' | 'stage' | 'payment' | 'phase' | 'cost'
    icon: str
    investor_name: str
    description: str
    detail: str              # extra one-line info (status, amounts, etc.)
    click_action: tuple | None = None  # ('open_file', path) | ('show_email', subject, body) | None


_TYPE_LABEL = {
    "email":   "Email",
    "doc":     "Document",
    "stage":   "Stage",
    "payment": "Payment",
    "phase":   "Phase",
    "cost":    "Cost",
}

_TYPE_COLOR = {
    "email":   "#1f6feb",
    "doc":     "#7c3aed",
    "stage":   "#0a958e",
    "payment": "#1a7f37",
    "phase":   "#d97706",
    "cost":    "#5b6473",
}


class ActivityTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: ProjectRow | None = None
        self._events: list[ActivityEvent] = []
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(14)

        # Header
        header = QHBoxLayout()
        title = QLabel("Activity")
        f = title.font()
        f.setPointSize(18)
        f.setBold(True)
        title.setFont(f)
        header.addWidget(title)
        header.addStretch(1)

        header.addWidget(QLabel("Show:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("All events",   userData=None)
        self.filter_combo.addItem("Emails",       userData="email")
        self.filter_combo.addItem("Documents",    userData="doc")
        self.filter_combo.addItem("Stage moves",  userData="stage")
        self.filter_combo.addItem("Payments",     userData="payment")
        self.filter_combo.addItem("Phase moves",  userData="phase")
        self.filter_combo.addItem("Costs",        userData="cost")
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        header.addWidget(self.filter_combo)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setProperty("secondary", True)
        self.refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self.refresh_btn)

        subtitle = QLabel(
            "Every event on this project in chronological order — emails sent, "
            "documents generated or received, stage transitions, payments, phase "
            "changes, and logged cost actuals. Filter by type to zoom in."
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #5b6473;")

        # Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["When", "Type", "Investor", "What Happened", "Detail"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        outer.addLayout(header)
        outer.addWidget(subtitle)
        outer.addWidget(self.summary_label)
        outer.addWidget(self.table, 1)

    # ---- public api ------------------------------------------------------
    def set_project(self, project: ProjectRow | None) -> None:
        self._project = project
        self.refresh()

    def refresh(self) -> None:
        self.table.setRowCount(0)
        if self._project is None:
            self.summary_label.setText("No project selected.")
            self._events = []
            return

        self._events = self._collect_events(self._project.id)
        self._render_filtered()

    # ---- event collection -----------------------------------------------
    def _collect_events(self, project_id: str) -> list[ActivityEvent]:
        investor_names = {i.id: i.display_name for i in list_investors(project_id)}
        events: list[ActivityEvent] = []

        with connect() as conn:
            # -- Emails --
            for row in conn.execute(
                "SELECT investor_id, subject, sent_at, success, error_message "
                "  FROM send_events WHERE project_id = ?",
                (project_id,),
            ):
                name = investor_names.get(row["investor_id"], "(unknown investor)")
                ok = bool(row["success"])
                events.append(
                    ActivityEvent(
                        timestamp=row["sent_at"] or "",
                        event_type="email",
                        icon="✉",
                        investor_name=name,
                        description=f"Sent email: {row['subject'] or '(no subject)'}",
                        detail="Sent" if ok else (row["error_message"] or "Failed"),
                        click_action=("show_email", row["subject"] or "(no subject)", ""),
                    )
                )

            # -- Documents --
            for row in conn.execute(
                "SELECT investor_id, doc_type, direction, status, storage_path, created_at "
                "  FROM investor_documents WHERE project_id = ?",
                (project_id,),
            ):
                name = investor_names.get(row["investor_id"], "(unknown investor)")
                direction = (row["direction"] or "").title()
                doc_type = (row["doc_type"] or "").replace("_", " ").title()
                verb = {
                    "sent":       "Generated",
                    "received":   "Received",
                    "attachment": "Attached",
                }.get(row["direction"] or "", "Created")
                path = row["storage_path"] or ""
                events.append(
                    ActivityEvent(
                        timestamp=row["created_at"] or "",
                        event_type="doc",
                        icon="📄",
                        investor_name=name,
                        description=f"{verb} {doc_type}",
                        detail=f"{direction}  ·  {(row['status'] or '').title()}",
                        click_action=("open_file", path) if path else None,
                    )
                )

            # -- Stage runs (completed and in-progress starts) --
            for row in conn.execute(
                "SELECT investor_id, stage_id, entered_at, completed_at, status "
                "  FROM investor_stage_runs WHERE project_id = ?",
                (project_id,),
            ):
                name = investor_names.get(row["investor_id"], "(unknown investor)")
                stage = get_stage(row["stage_id"])
                stage_name = stage.name if stage else "(deleted stage)"

                # Entry event
                events.append(
                    ActivityEvent(
                        timestamp=row["entered_at"] or "",
                        event_type="stage",
                        icon="📜",
                        investor_name=name,
                        description=f"Entered stage '{stage_name}'",
                        detail=(row["status"] or "").replace("_", " ").title(),
                    )
                )
                # Completion event (if completed)
                if row["completed_at"]:
                    events.append(
                        ActivityEvent(
                            timestamp=row["completed_at"],
                            event_type="stage",
                            icon="✓",
                            investor_name=name,
                            description=f"Completed stage '{stage_name}'",
                            detail=(row["status"] or "").replace("_", " ").title(),
                        )
                    )

            # -- Payments --
            for row in conn.execute(
                "SELECT investor_id, payment_type, payee, received_amount, "
                "       received_at, method, status "
                "  FROM payments "
                " WHERE project_id = ? AND received_at IS NOT NULL",
                (project_id,),
            ):
                name = investor_names.get(row["investor_id"], "(unknown investor)")
                amount = float(row["received_amount"] or 0)
                ptype = (row["payment_type"] or "").upper()
                payee = (row["payee"] or "").title()
                events.append(
                    ActivityEvent(
                        timestamp=row["received_at"] or "",
                        event_type="payment",
                        icon="💰",
                        investor_name=name,
                        description=f"Received {ptype} payment ${amount:,.2f}",
                        detail=f"→ {payee}  ·  {(row['method'] or '').title()}",
                    )
                )

            # -- Phase change --
            phase_row = conn.execute(
                "SELECT phase, phase_entered_at FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if phase_row and phase_row["phase_entered_at"]:
                from wellsign.db.phases import info_for as phase_info_for

                info = phase_info_for(phase_row["phase"])
                events.append(
                    ActivityEvent(
                        timestamp=phase_row["phase_entered_at"],
                        event_type="phase",
                        icon="🚩",
                        investor_name="(project)",
                        description=f"Entered phase '{info.label}'",
                        detail=info.description,
                    )
                )

            # -- Cost actuals logged (lines that have an actual_amount set) --
            for row in conn.execute(
                "SELECT category, description, actual_amount, vendor, updated_at "
                "  FROM cost_line_items "
                " WHERE project_id = ? AND actual_amount IS NOT NULL",
                (project_id,),
            ):
                amount = float(row["actual_amount"] or 0)
                events.append(
                    ActivityEvent(
                        timestamp=row["updated_at"] or "",
                        event_type="cost",
                        icon="💵",
                        investor_name="(project)",
                        description=f"Logged ${amount:,.2f} — {row['category']}: {row['description']}",
                        detail=(row["vendor"] or "").strip() or "—",
                    )
                )

        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events

    # ---- render ----------------------------------------------------------
    def _render_filtered(self) -> None:
        filter_kind = self.filter_combo.currentData()
        filtered = [e for e in self._events if filter_kind is None or e.event_type == filter_kind]

        self.table.setRowCount(len(filtered))
        for r, ev in enumerate(filtered):
            ts = (ev.timestamp or "")[:16].replace("T", " ")
            self.table.setItem(r, 0, QTableWidgetItem(ts))

            type_item = QTableWidgetItem(f"{ev.icon}  {_TYPE_LABEL.get(ev.event_type, '?')}")
            type_item.setForeground(QBrush(QColor(_TYPE_COLOR.get(ev.event_type, "#5b6473"))))
            fnt = QFont(type_item.font())
            fnt.setBold(True)
            type_item.setFont(fnt)
            type_item.setData(Qt.ItemDataRole.UserRole, r)  # stash index for double-click
            self.table.setItem(r, 1, type_item)

            self.table.setItem(r, 2, QTableWidgetItem(ev.investor_name))
            self.table.setItem(r, 3, QTableWidgetItem(ev.description))
            self.table.setItem(r, 4, QTableWidgetItem(ev.detail))

        self.summary_label.setText(
            f"<b>{len(filtered)}</b> of {len(self._events)} events"
        )

    def _on_filter_changed(self) -> None:
        self._render_filtered()

    def _on_double_click(self, row: int, _col: int) -> None:
        # Need to map the visible row back to the filtered event — the Type
        # column stores the index into the filtered list.
        type_item = self.table.item(row, 1)
        if type_item is None:
            return
        filter_kind = self.filter_combo.currentData()
        filtered = [e for e in self._events if filter_kind is None or e.event_type == filter_kind]
        if row < 0 or row >= len(filtered):
            return
        ev = filtered[row]
        if ev.click_action is None:
            return
        action = ev.click_action[0]
        if action == "open_file":
            path = Path(ev.click_action[1])
            if not path.exists():
                QMessageBox.warning(
                    self, "File not found",
                    f"Could not find {path.name} — the file may have been moved or deleted.",
                )
                return
            try:
                if sys.platform.startswith("win"):
                    os.startfile(str(path))  # type: ignore[attr-defined]
                elif sys.platform == "darwin":
                    subprocess.run(["open", str(path)], check=False)
                else:
                    subprocess.run(["xdg-open", str(path)], check=False)
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(self, "Could not open file", str(e))
