"""Investor Detail dialog — tabs-on-the-left: Edit | Activity.

**Edit tab**: inline editable form for the basic investor fields (identity,
address, WI%, payment preference, notes). Saves via ``update_investor``.
For sensitive PII fields (SSN / EIN / banking), clicking the "Advanced /
PII & Banking…" button opens the full ``InvestorDialog``.

**Activity tab**: scrolling timeline of everything that's happened for this
investor on this project:
  * header card (name / stage / traffic light / contributed)
  * documents (sent / received / attachments)
  * sent emails
  * stage history
  * payments
  * notes
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.investors import InvestorRow, get_investor, update_investor
from wellsign.db.migrate import connect
from wellsign.db.projects import ProjectRow
from wellsign.db.workflows import TrafficLight, compute_traffic_light, get_stage

_LIGHT_COLOR = {
    TrafficLight.GREEN:  "#1a7f37",
    TrafficLight.YELLOW: "#d97706",
    TrafficLight.RED:    "#d1242f",
    TrafficLight.GREY:   "#aab1bd",
}


class InvestorDetailDialog(QDialog):
    def __init__(
        self,
        project: ProjectRow,
        investor: InvestorRow,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._project = project
        self._investor = investor
        self._dirty = False  # any save happened → caller should refresh the list

        self.setWindowTitle(f"{investor.display_name} — Investor")
        self.setModal(True)
        self.setMinimumSize(980, 760)

        self._build()
        self._populate_edit_fields()
        self._populate_activity_sections()

    # ---- top-level layout -----------------------------------------------
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.West)
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet(
            # Give the vertical tabs a bit more breathing room
            "QTabBar::tab { min-width: 90px; padding: 12px 18px; }"
            "QTabBar::tab:selected { background: #ffffff; color: #1f6feb; "
            "border-right: 2px solid #1f6feb; }"
        )

        self.edit_tab = self._build_edit_tab()
        self.activity_tab = self._build_activity_tab()

        self.tabs.addTab(self.edit_tab, "Edit")
        self.tabs.addTab(self.activity_tab, "Activity")
        # Default to Activity since that's usually what you come here to see
        self.tabs.setCurrentIndex(1)

        outer.addWidget(self.tabs, 1)

        # Bottom close row
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(24, 12, 24, 18)
        btn_row.setSpacing(10)
        btn_row.addStretch(1)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.close_btn)
        outer.addLayout(btn_row)

    # =====================================================================
    # EDIT TAB
    # =====================================================================
    def _build_edit_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)

        # Header
        title = QLabel("Edit investor")
        f = title.font()
        f.setPointSize(16)
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)

        subtitle = QLabel(
            "Basic investor details. For SSN / EIN / banking, click "
            "<b>Advanced — PII &amp; Banking…</b> below."
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # ---- Identity card ----
        ident_card = _section_card("Identity")
        ident_form = QFormLayout()
        ident_form.setHorizontalSpacing(14)
        ident_form.setVerticalSpacing(8)

        self.first_edit = QLineEdit()
        self.last_edit = QLineEdit()
        self.entity_edit = QLineEdit()
        self.title_edit = QLineEdit()
        self.email_edit = QLineEdit()
        self.phone_edit = QLineEdit()

        ident_form.addRow("First name:", self.first_edit)
        ident_form.addRow("Last name:", self.last_edit)
        ident_form.addRow("Entity:", self.entity_edit)
        ident_form.addRow("Title:", self.title_edit)
        ident_form.addRow("Email:", self.email_edit)
        ident_form.addRow("Phone:", self.phone_edit)
        ident_card.layout().addLayout(ident_form)
        layout.addWidget(ident_card)

        # ---- Address card ----
        addr_card = _section_card("Address")
        addr_form = QFormLayout()
        addr_form.setHorizontalSpacing(14)
        addr_form.setVerticalSpacing(8)

        self.addr1_edit = QLineEdit()
        self.addr2_edit = QLineEdit()
        self.city_edit = QLineEdit()
        self.state_edit = QLineEdit()
        self.zip_edit = QLineEdit()

        city_row = QHBoxLayout()
        city_row.setSpacing(8)
        city_row.addWidget(self.city_edit, 2)
        city_row.addWidget(self.state_edit, 1)
        city_row.addWidget(self.zip_edit, 1)

        addr_form.addRow("Address 1:", self.addr1_edit)
        addr_form.addRow("Address 2:", self.addr2_edit)
        addr_form.addRow("City / State / Zip:", city_row)
        addr_card.layout().addLayout(addr_form)
        layout.addWidget(addr_card)

        # ---- Investment card ----
        inv_card = _section_card("Investment")
        inv_form = QFormLayout()
        inv_form.setHorizontalSpacing(14)
        inv_form.setVerticalSpacing(8)

        self.wi_spin = QDoubleSpinBox()
        self.wi_spin.setDecimals(6)
        self.wi_spin.setRange(0, 100)
        self.wi_spin.setSuffix(" %")
        self.wi_spin.setSingleStep(0.1)

        self.payment_combo = QComboBox()
        self.payment_combo.addItem("(none)",    userData=None)
        self.payment_combo.addItem("Wire",      userData="wire")
        self.payment_combo.addItem("Check",     userData="check")

        inv_form.addRow("Working interest:", self.wi_spin)
        inv_form.addRow("Payment preference:", self.payment_combo)
        inv_card.layout().addLayout(inv_form)
        layout.addWidget(inv_card)

        # ---- Notes ----
        notes_card = _section_card("Notes")
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setMaximumHeight(90)
        notes_card.layout().addWidget(self.notes_edit)
        layout.addWidget(notes_card)

        layout.addStretch(1)

        # Actions row
        actions = QHBoxLayout()
        actions.setSpacing(10)

        self.advanced_btn = QPushButton("Advanced — PII && Banking…")
        self.advanced_btn.setProperty("secondary", True)
        self.advanced_btn.setToolTip("Edit SSN / EIN / bank info in the full investor dialog")
        self.advanced_btn.clicked.connect(self._on_advanced)
        actions.addWidget(self.advanced_btn)
        actions.addStretch(1)

        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self._on_save_edit)
        actions.addWidget(self.save_btn)

        layout.addLayout(actions)
        return container

    def _populate_edit_fields(self) -> None:
        inv = self._investor
        self.first_edit.setText(inv.first_name or "")
        self.last_edit.setText(inv.last_name or "")
        self.entity_edit.setText(inv.entity_name or "")
        self.title_edit.setText(inv.title or "")
        self.email_edit.setText(inv.email or "")
        self.phone_edit.setText(inv.phone or "")
        self.addr1_edit.setText(inv.address_line1 or "")
        self.addr2_edit.setText(inv.address_line2 or "")
        self.city_edit.setText(inv.city or "")
        self.state_edit.setText(inv.state or "")
        self.zip_edit.setText(inv.zip or "")
        self.wi_spin.setValue(inv.wi_percent * 100)

        idx = self.payment_combo.findData(inv.payment_preference)
        self.payment_combo.setCurrentIndex(idx if idx >= 0 else 0)

        self.notes_edit.setPlainText(inv.notes or "")

    def _on_save_edit(self) -> None:
        wi_val = self.wi_spin.value() / 100.0
        # Recompute LLG/DHC from the project totals
        from wellsign.db.projects import get_project_totals

        total_llg, total_dhc = get_project_totals(self._project.id)
        llg_amount = round(wi_val * total_llg, 2) if total_llg else None
        dhc_amount = round(wi_val * total_dhc, 2) if total_dhc else None

        try:
            update_investor(
                self._investor.id,
                first_name=self.first_edit.text().strip() or None,
                last_name=self.last_edit.text().strip() or None,
                entity_name=self.entity_edit.text().strip() or None,
                title=self.title_edit.text().strip() or None,
                email=self.email_edit.text().strip() or None,
                phone=self.phone_edit.text().strip() or None,
                address_line1=self.addr1_edit.text().strip() or None,
                address_line2=self.addr2_edit.text().strip() or None,
                city=self.city_edit.text().strip() or None,
                state=self.state_edit.text().strip() or None,
                zip_code=self.zip_edit.text().strip() or None,
                wi_percent=wi_val,
                llg_amount=llg_amount,
                dhc_amount=dhc_amount,
                payment_preference=self.payment_combo.currentData(),
                notes=self.notes_edit.toPlainText().strip() or None,
            )
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Save failed", f"Could not save investor: {e}")
            return

        self._dirty = True
        fresh = get_investor(self._investor.id)
        if fresh is not None:
            self._investor = fresh
            self._populate_edit_fields()
            self._populate_activity_sections()
        self.close_btn.setText("Close")  # visual nudge
        QMessageBox.information(self, "Saved", "Investor details saved.")

    def _on_advanced(self) -> None:
        from wellsign.ui.dialogs.investor_dialog import InvestorDialog

        dlg = InvestorDialog(self._project, parent=self, existing=self._investor)
        if dlg.exec() and dlg.saved_investor is not None:
            self._dirty = True
            fresh = get_investor(self._investor.id)
            if fresh is not None:
                self._investor = fresh
                self._populate_edit_fields()
                self._populate_activity_sections()

    # =====================================================================
    # ACTIVITY TAB
    # =====================================================================
    def _build_activity_tab(self) -> QWidget:
        outer = QWidget()
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: #ffffff; }")
        self._activity_container = QWidget()
        self._activity_container.setStyleSheet("background: #ffffff;")
        self._activity_layout = QVBoxLayout(self._activity_container)
        self._activity_layout.setContentsMargins(24, 22, 24, 22)
        self._activity_layout.setSpacing(14)
        scroll.setWidget(self._activity_container)
        layout.addWidget(scroll, 1)
        return outer

    def _populate_activity_sections(self) -> None:
        # Clear existing
        while self._activity_layout.count():
            item = self._activity_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        inv = self._investor
        self._activity_layout.addWidget(self._build_header_card(inv))
        self._activity_layout.addWidget(self._build_documents_section(inv))
        self._activity_layout.addWidget(self._build_emails_section(inv))
        self._activity_layout.addWidget(self._build_stage_history_section(inv))
        self._activity_layout.addWidget(self._build_payments_section(inv))
        if inv.notes:
            self._activity_layout.addWidget(self._build_notes_section(inv))
        self._activity_layout.addStretch(1)

    # ---- header card ----------------------------------------------------
    def _build_header_card(self, inv: InvestorRow) -> QFrame:
        card = _section_card_plain()
        layout = card.layout()

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        traffic = compute_traffic_light(inv.id)
        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {_LIGHT_COLOR[traffic.light]}; font-size: 22pt; border: none;"
        )
        top_row.addWidget(dot)

        name = QLabel(inv.display_name)
        nf = name.font()
        nf.setPointSize(18)
        nf.setBold(True)
        name.setFont(nf)
        name.setStyleSheet("border: none;")
        top_row.addWidget(name)
        top_row.addStretch(1)

        wi_label = QLabel(f"{inv.wi_percent * 100:.6f}% WI")
        wi_label.setStyleSheet(
            "color: #1f6feb; font-weight: 600; font-size: 13pt; border: none;"
        )
        top_row.addWidget(wi_label)
        layout.addLayout(top_row)

        subtitle_bits: list[str] = []
        if inv.entity_name and inv.entity_name != inv.display_name:
            subtitle_bits.append(inv.entity_name)
        if inv.title:
            subtitle_bits.append(inv.title)
        if inv.email:
            subtitle_bits.append(inv.email)
        if inv.phone:
            subtitle_bits.append(inv.phone)
        if subtitle_bits:
            subtitle = QLabel("  ·  ".join(subtitle_bits))
            subtitle.setStyleSheet("color: #5b6473; font-size: 10pt; border: none;")
            layout.addWidget(subtitle)

        address_parts = [
            p
            for p in (
                inv.address_line1,
                inv.address_line2,
                ", ".join(p for p in (inv.city, inv.state, inv.zip) if p),
            )
            if p
        ]
        if address_parts:
            addr = QLabel("  ·  ".join(address_parts))
            addr.setStyleSheet("color: #5b6473; font-size: 10pt; border: none;")
            layout.addWidget(addr)

        layout.addSpacing(8)

        info_row = QHBoxLayout()
        info_row.setSpacing(24)
        stage_name = traffic.stage.name if traffic.stage else "—"
        stage_label = QLabel(
            f"<b>Stage:</b> {stage_name}  "
            f"<span style='color:{_LIGHT_COLOR[traffic.light]};'>· {traffic.label}</span>"
        )
        stage_label.setStyleSheet("border: none;")
        info_row.addWidget(stage_label)

        contributed = (inv.llg_amount or 0) + (inv.dhc_amount or 0)
        contrib_label = QLabel(
            f"<b>Contributed:</b> ${contributed:,.2f} "
            f"<span style='color:#5b6473;'>"
            f"(LLG ${inv.llg_amount or 0:,.2f} + DHC ${inv.dhc_amount or 0:,.2f})</span>"
        )
        contrib_label.setStyleSheet("border: none;")
        info_row.addWidget(contrib_label)
        info_row.addStretch(1)
        layout.addLayout(info_row)

        return card

    # ---- documents section ----------------------------------------------
    def _build_documents_section(self, inv: InvestorRow) -> QFrame:
        with connect() as conn:
            rows = conn.execute(
                "SELECT id, doc_type, direction, source, storage_path, external_url, "
                "       status, sent_at, received_at, signed_at, created_at "
                "  FROM investor_documents "
                " WHERE investor_id = ? "
                " ORDER BY datetime(created_at) DESC",
                (inv.id,),
            ).fetchall()

        section = _section_card_with_header(
            "📄  Documents",
            f"{len(rows)} item{'s' if len(rows) != 1 else ''}",
        )
        layout = section.layout()

        if not rows:
            layout.addWidget(_empty_row("No documents generated or attached for this investor yet."))
            return section

        table = QTableWidget(len(rows), 5)
        table.setHorizontalHeaderLabels(["Type", "Direction", "Status", "Created", "File"])
        _style_mini_table(table, len(rows))
        h = table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        paths: list[str] = []
        for r, row in enumerate(rows):
            storage_path = row["storage_path"] or ""
            paths.append(storage_path)

            table.setItem(r, 0, QTableWidgetItem((row["doc_type"] or "").replace("_", " ").title()))

            dir_item = QTableWidgetItem((row["direction"] or "").title())
            dir_item.setForeground(QBrush(QColor(_direction_color(row["direction"] or ""))))
            table.setItem(r, 1, dir_item)

            table.setItem(r, 2, QTableWidgetItem((row["status"] or "").title()))
            table.setItem(r, 3, QTableWidgetItem((row["created_at"] or "")[:16].replace("T", " ")))
            table.setItem(r, 4, QTableWidgetItem(Path(storage_path).name if storage_path else "—"))

        def _open_row(row: int, _col: int = 0) -> None:
            if 0 <= row < len(paths) and paths[row]:
                _open_file(Path(paths[row]), parent=self)

        table.cellDoubleClicked.connect(_open_row)
        layout.addWidget(table)

        hint = QLabel("Double-click a row to open the file.")
        hint.setStyleSheet("color: #aab1bd; font-size: 9pt; font-style: italic; border: none;")
        layout.addWidget(hint)

        return section

    # ---- emails section -------------------------------------------------
    def _build_emails_section(self, inv: InvestorRow) -> QFrame:
        with connect() as conn:
            rows = conn.execute(
                "SELECT id, subject, sent_at, success, error_message, attached_doc_ids "
                "  FROM send_events "
                " WHERE investor_id = ? "
                " ORDER BY datetime(sent_at) DESC",
                (inv.id,),
            ).fetchall()

        section = _section_card_with_header(
            "✉  Sent Emails",
            f"{len(rows)} item{'s' if len(rows) != 1 else ''}",
        )
        layout = section.layout()

        if not rows:
            layout.addWidget(_empty_row("No emails have been sent to this investor yet."))
            return section

        table = QTableWidget(len(rows), 4)
        table.setHorizontalHeaderLabels(["Sent At", "Subject", "Attached", "Status"])
        _style_mini_table(table, len(rows))
        h = table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        for r, row in enumerate(rows):
            sent_at = (row["sent_at"] or "")[:16].replace("T", " ")
            table.setItem(r, 0, QTableWidgetItem(sent_at))
            table.setItem(r, 1, QTableWidgetItem(row["subject"] or "(no subject)"))

            attached_raw = row["attached_doc_ids"] or ""
            attached_count = attached_raw.count(",") + 1 if "[" in attached_raw and attached_raw.strip() != "[]" else 0
            table.setItem(r, 2, QTableWidgetItem(str(attached_count) if attached_count else "—"))

            status_txt = "Sent" if row["success"] else (row["error_message"] or "Failed")
            status_item = QTableWidgetItem(status_txt)
            status_item.setForeground(
                QBrush(QColor("#1a7f37" if row["success"] else "#d1242f"))
            )
            table.setItem(r, 3, status_item)

        layout.addWidget(table)
        return section

    # ---- stage history section ------------------------------------------
    def _build_stage_history_section(self, inv: InvestorRow) -> QFrame:
        with connect() as conn:
            rows = conn.execute(
                "SELECT id, stage_id, entered_at, completed_at, status, notes "
                "  FROM investor_stage_runs "
                " WHERE investor_id = ? "
                " ORDER BY datetime(entered_at) DESC",
                (inv.id,),
            ).fetchall()

        section = _section_card_with_header(
            "📜  Stage History",
            f"{len(rows)} run{'s' if len(rows) != 1 else ''}",
        )
        layout = section.layout()

        if not rows:
            layout.addWidget(_empty_row("No stage runs recorded for this investor yet."))
            return section

        table = QTableWidget(len(rows), 5)
        table.setHorizontalHeaderLabels(["Stage", "Entered", "Completed", "Duration", "Status"])
        _style_mini_table(table, len(rows))
        h = table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        for r, row in enumerate(rows):
            stage = get_stage(row["stage_id"])
            stage_name = stage.name if stage else "(deleted)"
            table.setItem(r, 0, QTableWidgetItem(stage_name))
            table.setItem(r, 1, QTableWidgetItem((row["entered_at"] or "")[:16].replace("T", " ")))
            table.setItem(r, 2, QTableWidgetItem((row["completed_at"] or "")[:16].replace("T", " ") or "—"))

            duration = _duration_text(row["entered_at"], row["completed_at"])
            table.setItem(r, 3, QTableWidgetItem(duration))

            status = (row["status"] or "").replace("_", " ").title()
            status_item = QTableWidgetItem(status)
            status_color = {
                "In Progress": "#1f6feb",
                "Completed":   "#1a7f37",
                "Skipped":     "#aab1bd",
                "Blocked":     "#d1242f",
            }.get(status, "#5b6473")
            status_item.setForeground(QBrush(QColor(status_color)))
            table.setItem(r, 4, status_item)

        layout.addWidget(table)
        return section

    # ---- payments section -----------------------------------------------
    def _build_payments_section(self, inv: InvestorRow) -> QFrame:
        with connect() as conn:
            rows = conn.execute(
                "SELECT payment_type, payee, expected_amount, received_amount, "
                "       method, received_at, reference_number, status "
                "  FROM payments "
                " WHERE investor_id = ? "
                " ORDER BY payment_type",
                (inv.id,),
            ).fetchall()

        total_expected = sum(float(r["expected_amount"] or 0) for r in rows)
        total_received = sum(float(r["received_amount"] or 0) for r in rows)
        subtitle = (
            f"${total_received:,.2f} received of ${total_expected:,.2f} expected"
            if rows
            else "none yet"
        )
        section = _section_card_with_header("💰  Payments", subtitle)
        layout = section.layout()

        if not rows:
            layout.addWidget(
                _empty_row(
                    "No payments recorded for this investor yet. Use the Payments tab "
                    "to log wires / checks as they land."
                )
            )
            return section

        table = QTableWidget(len(rows), 6)
        table.setHorizontalHeaderLabels(
            ["Type", "Payee", "Expected", "Received", "Method", "Status"]
        )
        _style_mini_table(table, len(rows))
        h = table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        for r, row in enumerate(rows):
            table.setItem(r, 0, QTableWidgetItem((row["payment_type"] or "").upper()))
            table.setItem(r, 1, QTableWidgetItem(row["payee"] or ""))
            table.setItem(r, 2, QTableWidgetItem(f"${float(row['expected_amount'] or 0):,.2f}"))
            table.setItem(
                r,
                3,
                QTableWidgetItem(
                    f"${float(row['received_amount'] or 0):,.2f}"
                    if row["received_amount"] is not None
                    else "—"
                ),
            )
            table.setItem(r, 4, QTableWidgetItem((row["method"] or "").title()))
            table.setItem(r, 5, QTableWidgetItem((row["status"] or "").title()))

        layout.addWidget(table)
        return section

    # ---- notes section --------------------------------------------------
    def _build_notes_section(self, inv: InvestorRow) -> QFrame:
        section = _section_card_with_header("📝  Notes", None)
        layout = section.layout()
        text = QLabel(inv.notes or "")
        text.setWordWrap(True)
        text.setStyleSheet("color: #1f2430; padding: 4px 0; border: none;")
        layout.addWidget(text)
        return section

    # ---- public --------------------------------------------------------
    @property
    def refreshed(self) -> bool:
        """Caller can check this to decide whether to reload the investor list."""
        return self._dirty


# ===========================================================================
# Module-level helpers
# ===========================================================================
def _section_card(title: str) -> QFrame:
    card = QFrame()
    card.setStyleSheet(
        "QFrame { background: #ffffff; border: 1px solid #d8dce3; border-radius: 8px; }"
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 14, 18, 14)
    layout.setSpacing(8)

    title_label = QLabel(title)
    f = title_label.font()
    f.setPointSize(11)
    f.setBold(True)
    title_label.setFont(f)
    title_label.setStyleSheet("color: #1f2430; border: none;")
    layout.addWidget(title_label)
    return card


def _section_card_plain() -> QFrame:
    card = QFrame()
    card.setStyleSheet(
        "QFrame { background: #ffffff; border: 1px solid #d8dce3; border-radius: 8px; }"
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(22, 18, 22, 18)
    layout.setSpacing(6)
    return card


def _section_card_with_header(title: str, right_text: str | None) -> QFrame:
    card = QFrame()
    card.setStyleSheet(
        "QFrame { background: #ffffff; border: 1px solid #d8dce3; border-radius: 8px; }"
    )
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 14, 18, 14)
    layout.setSpacing(8)

    header = QHBoxLayout()
    header.setSpacing(8)
    title_label = QLabel(title)
    f = title_label.font()
    f.setPointSize(12)
    f.setBold(True)
    title_label.setFont(f)
    title_label.setStyleSheet("color: #1f2430; border: none;")
    header.addWidget(title_label)
    header.addStretch(1)
    if right_text:
        right = QLabel(right_text)
        right.setStyleSheet("color: #5b6473; border: none;")
        header.addWidget(right)
    layout.addLayout(header)
    return card


def _empty_row(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "color: #aab1bd; font-style: italic; padding: 6px 0; border: none;"
    )
    lbl.setWordWrap(True)
    return lbl


def _style_mini_table(table: QTableWidget, row_count: int) -> None:
    table.verticalHeader().setVisible(False)
    table.setAlternatingRowColors(False)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setMaximumHeight(min(260, 40 + 26 * row_count))


def _direction_color(direction: str) -> str:
    return {
        "sent":       "#1f6feb",
        "received":   "#1a7f37",
        "attachment": "#7c3aed",
    }.get(direction, "#5b6473")


def _duration_text(entered_at: str | None, completed_at: str | None) -> str:
    if not entered_at:
        return "—"
    try:
        start = datetime.fromisoformat(entered_at)
    except ValueError:
        return "—"
    end = datetime.utcnow()
    if completed_at:
        try:
            end = datetime.fromisoformat(completed_at)
        except ValueError:
            pass
    delta = end - start
    days = delta.days
    if days == 0:
        hours = delta.seconds // 3600
        return f"{hours}h"
    if days == 1:
        return "1 day"
    return f"{days} days"


def _open_file(path: Path, parent: QWidget | None = None) -> None:
    if not path.exists():
        QMessageBox.warning(
            parent,
            "File not found",
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
        QMessageBox.warning(
            parent,
            "Could not open file",
            f"OS error opening {path.name}: {e}",
        )
