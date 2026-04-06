"""Project Setup tab — read-only summary of the active project (POC)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.projects import ProjectRow


class ProjectSetupTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: ProjectRow | None = None
        self._fields: dict[str, QLabel] = {}
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(16)

        title = QLabel("Project Setup")
        f = title.font()
        f.setPointSize(18)
        f.setBold(True)
        title.setFont(f)
        outer.addWidget(title)

        subtitle = QLabel(
            "Prospect, well, county/state, key dates, and total cash-call costs for "
            "the active project. (Editable form coming next ticket — currently read-only.)"
        )
        subtitle.setStyleSheet("color: #5b6473;")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("ProjectCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(8)
        card.setStyleSheet(
            "QFrame#ProjectCard { background: #ffffff; border: 1px solid #d8dce3; border-radius: 8px; }"
        )

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(8)

        for key, label in [
            ("name",            "Project name:"),
            ("prospect_name",   "Prospect:"),
            ("well_name",       "Well:"),
            ("operator_llc",    "Operator:"),
            ("region",          "Region:"),
            ("agreement_date",  "Agreement date:"),
            ("close_deadline",  "Close deadline:"),
            ("total_llg_cost",  "Total LLG cost (→ Decker):"),
            ("total_dhc_cost",  "Total DHC cost (→ Paloma):"),
            ("license_customer","License customer:"),
            ("license_expires", "License expires:"),
            ("status",          "Status:"),
        ]:
            value = QLabel("—")
            value.setStyleSheet("color: #1f2430; font-weight: 500;")
            self._fields[key] = value
            form.addRow(label, value)

        card_layout.addLayout(form)
        outer.addWidget(card)
        outer.addStretch(1)

    def set_project(self, project: ProjectRow | None) -> None:
        self._project = project
        if project is None:
            for v in self._fields.values():
                v.setText("—")
            return

        # Pull a few extra columns directly from the DB for nicer display.
        from wellsign.db.migrate import connect

        with connect() as conn:
            row = conn.execute(
                "SELECT prospect_name, operator_llc, agreement_date, close_deadline, "
                "total_llg_cost, total_dhc_cost FROM projects WHERE id = ?",
                (project.id,),
            ).fetchone()

        def fmt_money(v) -> str:
            return f"${float(v):,.2f}" if v is not None else "—"

        self._fields["name"].setText(project.name or "—")
        self._fields["prospect_name"].setText((row["prospect_name"] if row else None) or "—")
        self._fields["well_name"].setText(project.well_name or "—")
        self._fields["operator_llc"].setText((row["operator_llc"] if row else None) or "—")
        self._fields["region"].setText(project.region or "—")
        self._fields["agreement_date"].setText((row["agreement_date"] if row else None) or "—")
        self._fields["close_deadline"].setText((row["close_deadline"] if row else None) or "—")
        self._fields["total_llg_cost"].setText(fmt_money(row["total_llg_cost"] if row else None))
        self._fields["total_dhc_cost"].setText(fmt_money(row["total_dhc_cost"] if row else None))
        self._fields["license_customer"].setText(project.license_customer or "—")
        self._fields["license_expires"].setText((project.license_expires_at or "—")[:10])
        self._fields["status"].setText((project.status or "").title())
