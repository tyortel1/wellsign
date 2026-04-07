"""Workflow + stage CRUD and per-investor runtime helpers.

Three layers:
  workflows                      → reusable pipeline definitions
  workflow_stages                → ordered children of a workflow
  stage_doc_templates            → docs attached to each stage
  stage_email_templates          → emails attached to each stage (with wait_days)
  investor_stage_runs            → per-investor in-flight state
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from wellsign.db.migrate import connect


# ---------------------------------------------------------------------------
# Exit conditions
# ---------------------------------------------------------------------------
class ExitCondition(str, Enum):
    MANUAL              = "manual"
    INVESTOR_COMMITTED  = "investor_committed"
    ALL_DOCS_SIGNED     = "all_docs_signed"
    LLG_PAID            = "llg_paid"
    DHC_PAID            = "dhc_paid"
    LLG_AND_DHC_PAID    = "llg_and_dhc_paid"


EXIT_LABELS: dict[str, str] = {
    ExitCondition.MANUAL.value:             "Manual (operator marks complete)",
    ExitCondition.INVESTOR_COMMITTED.value: "Investor committed",
    ExitCondition.ALL_DOCS_SIGNED.value:    "All documents signed",
    ExitCondition.LLG_PAID.value:           "LLG payment received",
    ExitCondition.DHC_PAID.value:           "DHC payment received",
    ExitCondition.LLG_AND_DHC_PAID.value:   "Both LLG and DHC paid",
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class WorkflowRow:
    id: str
    name: str
    description: str | None
    is_global: bool
    created_at: str


@dataclass
class StageEmailItem:
    id: str
    email_template_id: str
    email_template_name: str
    item_order: int
    wait_days: int


@dataclass
class StageDocItem:
    id: str
    doc_template_id: str
    doc_template_name: str
    item_order: int


@dataclass
class StageRow:
    id: str
    workflow_id: str
    stage_order: int
    name: str
    description: str | None
    duration_days: int | None
    exit_condition: str
    docs:   list[StageDocItem]   = field(default_factory=list)
    emails: list[StageEmailItem] = field(default_factory=list)


@dataclass
class StageRunRow:
    id: str
    investor_id: str
    project_id: str
    stage_id: str
    entered_at: str
    completed_at: str | None
    status: str
    notes: str | None


# ---------------------------------------------------------------------------
# Workflow CRUD
# ---------------------------------------------------------------------------
def list_workflows() -> list[WorkflowRow]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM workflows ORDER BY name").fetchall()
        return [_to_workflow(r) for r in rows]


def get_workflow(workflow_id: str) -> WorkflowRow | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        return _to_workflow(row) if row else None


def insert_workflow(*, name: str, description: str = "") -> WorkflowRow:
    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            "INSERT INTO workflows (id, name, description, is_global, created_at, updated_at) "
            "VALUES (?, ?, ?, 1, ?, ?)",
            (new_id, name, description, now, now),
        )
        conn.commit()
    result = get_workflow(new_id)
    assert result is not None
    return result


def update_workflow(workflow_id: str, *, name: str, description: str) -> None:
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            "UPDATE workflows SET name = ?, description = ?, updated_at = ? WHERE id = ?",
            (name, description, now, workflow_id),
        )
        conn.commit()


def delete_workflow(workflow_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
        conn.commit()


def _to_workflow(row: sqlite3.Row) -> WorkflowRow:
    return WorkflowRow(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        is_global=bool(row["is_global"]),
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# Stage CRUD
# ---------------------------------------------------------------------------
def list_stages(workflow_id: str) -> list[StageRow]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM workflow_stages WHERE workflow_id = ? ORDER BY stage_order",
            (workflow_id,),
        ).fetchall()
        stages: list[StageRow] = []
        for r in rows:
            sid = r["id"]
            doc_rows = conn.execute(
                "SELECT sdt.id, sdt.doc_template_id, sdt.item_order, dt.name "
                "  FROM stage_doc_templates sdt "
                "  JOIN document_templates dt ON dt.id = sdt.doc_template_id "
                " WHERE sdt.stage_id = ? "
                " ORDER BY sdt.item_order",
                (sid,),
            ).fetchall()
            email_rows = conn.execute(
                "SELECT s.id, s.email_template_id, s.item_order, s.wait_days, et.name "
                "  FROM stage_email_templates s "
                "  JOIN email_templates et ON et.id = s.email_template_id "
                " WHERE s.stage_id = ? "
                " ORDER BY s.item_order",
                (sid,),
            ).fetchall()
            stages.append(
                StageRow(
                    id=sid,
                    workflow_id=r["workflow_id"],
                    stage_order=r["stage_order"],
                    name=r["name"],
                    description=r["description"],
                    duration_days=r["duration_days"],
                    exit_condition=r["exit_condition"],
                    docs=[
                        StageDocItem(
                            id=d["id"],
                            doc_template_id=d["doc_template_id"],
                            doc_template_name=d["name"],
                            item_order=d["item_order"],
                        )
                        for d in doc_rows
                    ],
                    emails=[
                        StageEmailItem(
                            id=e["id"],
                            email_template_id=e["email_template_id"],
                            email_template_name=e["name"],
                            item_order=e["item_order"],
                            wait_days=e["wait_days"],
                        )
                        for e in email_rows
                    ],
                )
            )
        return stages


def get_stage(stage_id: str) -> StageRow | None:
    with connect() as conn:
        row = conn.execute("SELECT workflow_id FROM workflow_stages WHERE id = ?", (stage_id,)).fetchone()
        if not row:
            return None
    for s in list_stages(row["workflow_id"]):
        if s.id == stage_id:
            return s
    return None


def insert_stage(
    *,
    workflow_id: str,
    name: str,
    duration_days: int | None = None,
    exit_condition: str = ExitCondition.MANUAL.value,
    description: str = "",
) -> StageRow:
    new_id = str(uuid.uuid4())
    with connect() as conn:
        next_order = conn.execute(
            "SELECT COALESCE(MAX(stage_order), -1) + 1 FROM workflow_stages WHERE workflow_id = ?",
            (workflow_id,),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO workflow_stages (id, workflow_id, stage_order, name, description, "
            "                             duration_days, exit_condition) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (new_id, workflow_id, next_order, name, description, duration_days, exit_condition),
        )
        conn.commit()
    result = get_stage(new_id)
    assert result is not None
    return result


def update_stage(
    stage_id: str,
    *,
    name: str,
    duration_days: int | None,
    exit_condition: str,
    description: str = "",
) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE workflow_stages "
            "   SET name = ?, description = ?, duration_days = ?, exit_condition = ? "
            " WHERE id = ?",
            (name, description, duration_days, exit_condition, stage_id),
        )
        conn.commit()


def delete_stage(stage_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM workflow_stages WHERE id = ?", (stage_id,))
        conn.commit()


def reorder_stages(workflow_id: str, ordered_stage_ids: list[str]) -> None:
    with connect() as conn:
        for idx, sid in enumerate(ordered_stage_ids):
            conn.execute(
                "UPDATE workflow_stages SET stage_order = ? WHERE id = ? AND workflow_id = ?",
                (idx, sid, workflow_id),
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Stage attachments (docs / emails)
# ---------------------------------------------------------------------------
def attach_doc_to_stage(stage_id: str, doc_template_id: str) -> None:
    new_id = str(uuid.uuid4())
    with connect() as conn:
        next_order = conn.execute(
            "SELECT COALESCE(MAX(item_order), -1) + 1 FROM stage_doc_templates WHERE stage_id = ?",
            (stage_id,),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO stage_doc_templates (id, stage_id, doc_template_id, item_order) "
            "VALUES (?, ?, ?, ?)",
            (new_id, stage_id, doc_template_id, next_order),
        )
        conn.commit()


def detach_doc_from_stage(item_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM stage_doc_templates WHERE id = ?", (item_id,))
        conn.commit()


def attach_email_to_stage(stage_id: str, email_template_id: str, wait_days: int = 0) -> None:
    new_id = str(uuid.uuid4())
    with connect() as conn:
        next_order = conn.execute(
            "SELECT COALESCE(MAX(item_order), -1) + 1 FROM stage_email_templates WHERE stage_id = ?",
            (stage_id,),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO stage_email_templates (id, stage_id, email_template_id, item_order, wait_days) "
            "VALUES (?, ?, ?, ?, ?)",
            (new_id, stage_id, email_template_id, next_order, wait_days),
        )
        conn.commit()


def detach_email_from_stage(item_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM stage_email_templates WHERE id = ?", (item_id,))
        conn.commit()


# ---------------------------------------------------------------------------
# Investor stage runs (per-investor runtime)
# ---------------------------------------------------------------------------
def get_active_run(investor_id: str) -> StageRunRow | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM investor_stage_runs "
            " WHERE investor_id = ? AND status = 'in_progress' "
            " ORDER BY datetime(entered_at) DESC LIMIT 1",
            (investor_id,),
        ).fetchone()
        return _to_run(row) if row else None


def list_runs_for_investor(investor_id: str) -> list[StageRunRow]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM investor_stage_runs WHERE investor_id = ? "
            " ORDER BY datetime(entered_at)",
            (investor_id,),
        ).fetchall()
        return [_to_run(r) for r in rows]


def insert_stage_run(
    *,
    investor_id: str,
    project_id: str,
    stage_id: str,
    entered_at: datetime | None = None,
    status: str = "in_progress",
) -> StageRunRow:
    new_id = str(uuid.uuid4())
    ts = (entered_at or datetime.utcnow()).isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            "INSERT INTO investor_stage_runs "
            "(id, investor_id, project_id, stage_id, entered_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (new_id, investor_id, project_id, stage_id, ts, status),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM investor_stage_runs WHERE id = ?", (new_id,)).fetchone()
    return _to_run(row)


def start_workflow_for_investor(investor_id: str, project_id: str) -> StageRunRow | None:
    """Kick off the project's default workflow for a brand-new investor.

    Looks up the project's ``workflow_id``, finds the first stage of that
    workflow, and inserts a stage run putting the investor at stage 1 with
    ``entered_at = now``. Returns ``None`` if the project has no workflow,
    if the workflow has no stages, or if the investor is already in an
    active stage run.

    Used by InvestorDialog after a successful insert and by any future
    bulk-import code.
    """
    # Deferred imports to avoid circular dependencies with db/projects.py
    from wellsign.db.projects import get_project

    if get_active_run(investor_id) is not None:
        return None  # already running — don't double-start

    project = get_project(project_id)
    if project is None or not project.workflow_id:
        return None

    stages = list_stages(project.workflow_id)
    if not stages:
        return None

    return insert_stage_run(
        investor_id=investor_id,
        project_id=project_id,
        stage_id=stages[0].id,
    )


def complete_run(run_id: str) -> None:
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            "UPDATE investor_stage_runs "
            "   SET status = 'completed', completed_at = ? "
            " WHERE id = ?",
            (now, run_id),
        )
        conn.commit()


def set_run_status(run_id: str, status: str, notes: str | None = None) -> None:
    """Force-set a run's status — used by Mark Blocked / Skip actions."""
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        if status == "completed":
            conn.execute(
                "UPDATE investor_stage_runs SET status = ?, completed_at = ?, notes = ? "
                " WHERE id = ?",
                (status, now, notes, run_id),
            )
        else:
            conn.execute(
                "UPDATE investor_stage_runs SET status = ?, notes = ? WHERE id = ?",
                (status, notes, run_id),
            )
        conn.commit()


def advance_investor_stage(investor_id: str) -> StageRunRow | None:
    """Complete the investor's current stage run and start the next stage.

    Returns the new stage run, or ``None`` if the investor was already on the
    final stage of the workflow (in which case we only complete the current run).
    """
    current = get_active_run(investor_id)
    if current is None:
        return None

    current_stage = get_stage(current.stage_id)
    if current_stage is None:
        complete_run(current.id)
        return None

    stages = list_stages(current_stage.workflow_id)
    next_stage: StageRow | None = None
    for i, s in enumerate(stages):
        if s.id == current.stage_id and i + 1 < len(stages):
            next_stage = stages[i + 1]
            break

    complete_run(current.id)

    if next_stage is None:
        return None

    return insert_stage_run(
        investor_id=investor_id,
        project_id=current.project_id,
        stage_id=next_stage.id,
    )


def revert_investor_stage(investor_id: str) -> StageRunRow | None:
    """Move the investor back one stage. Opposite of advance_investor_stage."""
    current = get_active_run(investor_id)
    if current is None:
        return None
    current_stage = get_stage(current.stage_id)
    if current_stage is None:
        return None
    stages = list_stages(current_stage.workflow_id)
    prev_stage: StageRow | None = None
    for i, s in enumerate(stages):
        if s.id == current.stage_id and i > 0:
            prev_stage = stages[i - 1]
            break
    if prev_stage is None:
        return None
    set_run_status(current.id, "skipped")
    return insert_stage_run(
        investor_id=investor_id,
        project_id=current.project_id,
        stage_id=prev_stage.id,
    )


def _to_run(row: sqlite3.Row) -> StageRunRow:
    return StageRunRow(
        id=row["id"],
        investor_id=row["investor_id"],
        project_id=row["project_id"],
        stage_id=row["stage_id"],
        entered_at=row["entered_at"],
        completed_at=row["completed_at"],
        status=row["status"],
        notes=row["notes"],
    )


# ---------------------------------------------------------------------------
# Traffic light + active stage helpers
# ---------------------------------------------------------------------------
class TrafficLight(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    GREY = "grey"


@dataclass
class TrafficStatus:
    light: TrafficLight
    label: str
    stage: StageRow | None
    days_in_stage: int
    days_remaining: int | None  # negative if overdue


@dataclass
class PendingSend:
    investor_id: str
    investor_name: str
    investor_email: str       # rendered "To:" address for Outlook
    stage_id: str
    stage_name: str
    email_template_id: str
    email_template_name: str
    subject: str              # already rendered, no {{merge_variables}}
    body_html: str            # already rendered, no {{merge_variables}}
    wait_days: int
    entered_at: str
    due_at: str               # ISO datetime when this email becomes due
    days_overdue: int         # negative if not yet due
    status: str               # 'due' | 'upcoming' | 'overdue'


def compute_pending_sends(project_id: str) -> list[PendingSend]:
    """Compute which emails are due to go out for each investor in this project.

    Walks every investor's active stage run, expands the stage's attached
    emails into PendingSend rows with rendered subject + body, filters out
    pairs that already have a successful send_events row, and sorts by
    status (overdue → due → upcoming).
    """
    # Deferred imports to avoid circular dependencies
    from wellsign.db.investors import list_investors
    from wellsign.db.projects import get_project
    from wellsign.db.send_events import already_sent_pairs
    from wellsign.db.templates import get_email_template
    from wellsign.pdf_.fill import build_merge_context
    from wellsign.pdf_.merge_vars import render_template

    project = get_project(project_id)
    if project is None:
        return []

    investors = list_investors(project_id)
    sent_pairs = already_sent_pairs(project_id)
    out: list[PendingSend] = []
    today = datetime.utcnow()

    for inv in investors:
        run = get_active_run(inv.id)
        if run is None:
            continue
        stage = get_stage(run.stage_id)
        if stage is None or not stage.emails:
            continue

        try:
            entered = datetime.fromisoformat(run.entered_at)
        except ValueError:
            entered = today

        # Build the merge context once per investor — used for every attached email
        ctx = build_merge_context(project, inv)

        for email in stage.emails:
            # Skip pairs we've already sent
            if (inv.id, email.email_template_id) in sent_pairs:
                continue

            due_at = entered + timedelta(days=email.wait_days)
            delta_days = (today - due_at).days  # positive = overdue

            if delta_days < -2:
                status = "upcoming"
            elif delta_days < 0:
                status = "due"  # about to be due
            elif delta_days == 0:
                status = "due"
            else:
                status = "overdue"

            template = get_email_template(email.email_template_id)
            if template is None:
                continue

            # Render merge variables in subject + body
            rendered_subject = render_template(template.subject, ctx)
            rendered_body    = render_template(template.body_html, ctx)

            out.append(
                PendingSend(
                    investor_id=inv.id,
                    investor_name=inv.display_name,
                    investor_email=inv.email or "",
                    stage_id=stage.id,
                    stage_name=stage.name,
                    email_template_id=email.email_template_id,
                    email_template_name=email.email_template_name,
                    subject=rendered_subject,
                    body_html=rendered_body,
                    wait_days=email.wait_days,
                    entered_at=run.entered_at,
                    due_at=due_at.isoformat(timespec="seconds"),
                    days_overdue=delta_days,
                    status=status,
                )
            )

    # Order: overdue first (most overdue), then due, then upcoming
    _status_rank = {"overdue": 0, "due": 1, "upcoming": 2}
    out.sort(key=lambda p: (_status_rank[p.status], -p.days_overdue))
    return out


def compute_traffic_light(investor_id: str, warning_days: int = 3) -> TrafficStatus:
    run = get_active_run(investor_id)
    if run is None:
        return TrafficStatus(
            light=TrafficLight.GREY,
            label="Not started",
            stage=None,
            days_in_stage=0,
            days_remaining=None,
        )

    stage = get_stage(run.stage_id)
    if stage is None:
        return TrafficStatus(
            light=TrafficLight.GREY,
            label="Stage missing",
            stage=None,
            days_in_stage=0,
            days_remaining=None,
        )

    try:
        entered = datetime.fromisoformat(run.entered_at)
    except ValueError:
        entered = datetime.utcnow()
    days_in = (datetime.utcnow() - entered).days

    if stage.duration_days is None:
        return TrafficStatus(
            light=TrafficLight.GREEN,
            label=f"In {stage.name} (no SLA)",
            stage=stage,
            days_in_stage=days_in,
            days_remaining=None,
        )

    days_remaining = stage.duration_days - days_in
    if days_remaining < 0:
        light = TrafficLight.RED
        label = f"{stage.name} — {-days_remaining}d overdue"
    elif days_remaining <= warning_days:
        light = TrafficLight.YELLOW
        label = f"{stage.name} — {days_remaining}d left"
    else:
        light = TrafficLight.GREEN
        label = f"{stage.name} — {days_remaining}d left"

    return TrafficStatus(
        light=light,
        label=label,
        stage=stage,
        days_in_stage=days_in,
        days_remaining=days_remaining,
    )
