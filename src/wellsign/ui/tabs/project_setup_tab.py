"""Project Setup tab — read-only summary of the active project (POC)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from wellsign.db.investors import list_investors
from wellsign.db.projects import ProjectRow
from wellsign.db.workflows import (
    TrafficLight,
    compute_traffic_light,
    get_workflow,
    list_stages,
)


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

        # Workflow / stage banner
        self.stage_banner = QFrame()
        self.stage_banner.setObjectName("StageBanner")
        self.stage_banner.setStyleSheet(
            "QFrame#StageBanner { background: #e2ecff; border: 1px solid #1f6feb; "
            "border-radius: 8px; }"
        )
        banner_layout = QHBoxLayout(self.stage_banner)
        banner_layout.setContentsMargins(18, 14, 18, 14)
        banner_layout.setSpacing(12)
        self.stage_label = QLabel("")
        f2 = self.stage_label.font()
        f2.setPointSize(11)
        f2.setBold(True)
        self.stage_label.setFont(f2)
        self.stage_label.setStyleSheet("color: #14489f;")
        self.stage_summary_label = QLabel("")
        self.stage_summary_label.setStyleSheet("color: #1f2430;")
        banner_layout.addWidget(self.stage_label)
        banner_layout.addStretch(1)
        banner_layout.addWidget(self.stage_summary_label)
        outer.addWidget(self.stage_banner)

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
            self.stage_label.setText("No project selected")
            self.stage_summary_label.setText("")
            self.stage_banner.setVisible(False)
            return

        self._refresh_stage_banner(project)

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

    def _refresh_stage_banner(self, project: ProjectRow) -> None:
        if not project.workflow_id:
            self.stage_label.setText("No workflow assigned")
            self.stage_summary_label.setText("Pick a workflow at project creation.")
            self.stage_banner.setVisible(True)
            return

        wf = get_workflow(project.workflow_id)
        stages = list_stages(project.workflow_id) if wf else []
        if not wf or not stages:
            self.stage_label.setText("Workflow missing")
            self.stage_summary_label.setText("")
            self.stage_banner.setVisible(True)
            return

        # Compute the most-common active stage across this project's investors
        # so the banner reflects "where the deal is at" overall.
        investors = list_investors(project.id)
        if not investors:
            self.stage_label.setText(f"{wf.name} — Stage 1 of {len(stages)}: {stages[0].name}")
            self.stage_summary_label.setText("No investors yet.")
            self.stage_banner.setVisible(True)
            return

        stage_counts: dict[str, int] = {}
        light_counts = {"green": 0, "yellow": 0, "red": 0, "grey": 0}
        for inv in investors:
            t = compute_traffic_light(inv.id)
            light_counts[t.light.value] += 1
            if t.stage:
                stage_counts[t.stage.id] = stage_counts.get(t.stage.id, 0) + 1

        if stage_counts:
            top_stage_id = max(stage_counts, key=lambda k: stage_counts[k])
            top_stage = next((s for s in stages if s.id == top_stage_id), stages[0])
        else:
            top_stage = stages[0]

        self.stage_label.setText(
            f"{wf.name}  ·  Stage {top_stage.stage_order + 1} of {len(stages)}: {top_stage.name}"
        )
        sla_text = f"  ·  {top_stage.duration_days}d SLA" if top_stage.duration_days else ""
        self.stage_summary_label.setText(
            f"🟢 {light_counts['green']}  🟡 {light_counts['yellow']}  "
            f"🔴 {light_counts['red']}  ⚪ {light_counts['grey']}{sla_text}"
        )
        self.stage_banner.setVisible(True)
