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
                "SELECT set.id, set.email_template_id, set.item_order, set.wait_days, et.name "
                "  FROM stage_email_templates set "
                "  JOIN email_templates et ON et.id = set.email_template_id "
                " WHERE set.stage_id = ? "
                " ORDER BY set.item_order",
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
