"""Read/write access for the ``projects`` table.

Kept intentionally narrow: small functions, parameterised SQL, no ORM.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime

from wellsign.app_paths import project_dir
from wellsign.db.migrate import connect
from wellsign.util.audit import log_action


@dataclass
class ProjectRow:
    id: str
    name: str
    prospect_name: str | None
    well_name: str | None
    region: str | None  # stored in projects.state
    operator_llc: str | None
    license_customer: str | None
    license_expires_at: str | None
    status: str
    is_test: bool
    created_at: str
    workflow_id: str | None = None
    phase: str = "investigating"
    phase_entered_at: str | None = None
    wire_fee: float = 15.00  # bank wire fee passthrough on DHC, see Tanner's email

    @property
    def display_label(self) -> str:
        bits = [self.name]
        if self.well_name:
            bits.append(self.well_name)
        return "  ·  ".join(bits)


def _row_to_project(row: sqlite3.Row) -> ProjectRow:
    # workflow_id / phase may be missing on legacy rows; tolerate it.
    def _safe(key: str, default=None):
        try:
            return row[key]
        except (KeyError, IndexError):
            return default

    return ProjectRow(
        id=row["id"],
        name=row["name"],
        prospect_name=row["prospect_name"],
        well_name=row["well_name"],
        region=row["state"],
        operator_llc=row["operator_llc"],
        license_customer=row["license_customer"],
        license_expires_at=row["license_expires_at"],
        status=row["status"],
        is_test=bool(row["is_test"]),
        created_at=row["created_at"],
        workflow_id=_safe("workflow_id"),
        phase=_safe("phase", "investigating") or "investigating",
        phase_entered_at=_safe("phase_entered_at"),
        wire_fee=float(_safe("wire_fee", 15.00) or 15.00),
    )


def count_projects() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]


def list_projects() -> list[ProjectRow]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM projects ORDER BY datetime(created_at) DESC"
        ).fetchall()
        return [_row_to_project(r) for r in rows]


def get_project(project_id: str) -> ProjectRow | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return _row_to_project(row) if row else None


def insert_project(
    *,
    name: str,
    region: str,
    well_name: str,
    license_key_hash: str,
    license_customer: str,
    license_issued_at: str,
    license_expires_at: str,
    license_key_id: str,
    workflow_id: str | None = None,
    is_test: bool = False,
) -> ProjectRow:
    """Create a project row and ensure its on-disk folder exists."""
    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat(timespec="seconds")
    storage_relpath = new_id

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO projects (
                id, name, prospect_name, well_name, state,
                license_key_hash, license_customer, license_issued_at,
                license_expires_at, license_key_id,
                storage_path, workflow_id, status, is_test, created_at, updated_at
            ) VALUES (
                :id, :name, :name, :well_name, :region,
                :license_key_hash, :license_customer, :license_issued_at,
                :license_expires_at, :license_key_id,
                :storage_path, :workflow_id, 'active', :is_test, :now, :now
            )
            """,
            {
                "id": new_id,
                "name": name,
                "well_name": well_name,
                "region": region,
                "license_key_hash": license_key_hash,
                "license_customer": license_customer,
                "license_issued_at": license_issued_at,
                "license_expires_at": license_expires_at,
                "license_key_id": license_key_id,
                "storage_path": storage_relpath,
                "workflow_id": workflow_id,
                "is_test": 1 if is_test else 0,
                "now": now,
            },
        )
        conn.commit()

    # Ensure the on-disk folder structure exists for this project.
    project_dir(new_id)

    project = get_project(new_id)
    assert project is not None
    log_action(
        "project_created",
        project_id=project.id,
        target_type="project",
        target_id=project.id,
        metadata={
            "name": project.name,
            "well_name": project.well_name,
            "region": project.region,
            "license_customer": project.license_customer,
            "license_key_id": license_key_id,
            "is_test": bool(is_test),
        },
    )
    log_action(
        "license_verified",
        project_id=project.id,
        target_type="license",
        target_id=license_key_id,
        metadata={"customer": license_customer, "expires_at": license_expires_at},
    )
    return project


def get_project_totals(project_id: str) -> tuple[float, float]:
    """Return ``(total_llg_cost, total_dhc_cost)`` for a project, defaulting to 0."""
    with connect() as conn:
        row = conn.execute(
            "SELECT total_llg_cost, total_dhc_cost FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
    if row is None:
        return 0.0, 0.0
    return float(row["total_llg_cost"] or 0), float(row["total_dhc_cost"] or 0)


def set_phase(project_id: str, new_phase: str) -> None:
    """Move a project to a new phase, stamping phase_entered_at."""
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            "UPDATE projects SET phase = ?, phase_entered_at = ?, updated_at = ? "
            " WHERE id = ?",
            (new_phase, now, now, project_id),
        )
        conn.commit()
    log_action(
        "phase_advanced",
        project_id=project_id,
        target_type="project",
        target_id=project_id,
        metadata={"new_phase": new_phase},
    )


def update_project(
    project_id: str,
    *,
    name: str,
    prospect_name: str | None,
    well_name: str | None,
    operator_llc: str | None,
    county: str | None,
    state: str | None,
    agreement_date: str | None,
    close_deadline: str | None,
    total_llg_cost: float | None,
    total_dhc_cost: float | None,
    wire_fee: float = 15.00,
) -> "ProjectRow":
    """Update editable project fields. License + workflow + phase are NOT touched.

    Used by EditProjectDialog. License binding is immutable after creation;
    phase has its own setter (``set_phase``); workflow swap is intentionally
    not supported (would orphan investor_stage_runs).
    """
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            UPDATE projects
               SET name             = :name,
                   prospect_name    = :prospect_name,
                   well_name        = :well_name,
                   operator_llc     = :operator_llc,
                   county           = :county,
                   state            = :state,
                   agreement_date   = :agreement_date,
                   close_deadline   = :close_deadline,
                   total_llg_cost   = :total_llg_cost,
                   total_dhc_cost   = :total_dhc_cost,
                   wire_fee         = :wire_fee,
                   updated_at       = :now
             WHERE id = :id
            """,
            {
                "id": project_id,
                "name": name,
                "prospect_name": prospect_name,
                "well_name": well_name,
                "operator_llc": operator_llc,
                "county": county,
                "state": state,
                "agreement_date": agreement_date,
                "close_deadline": close_deadline,
                "total_llg_cost": total_llg_cost,
                "total_dhc_cost": total_dhc_cost,
                "wire_fee": wire_fee,
                "now": now,
            },
        )
        conn.commit()
    result = get_project(project_id)
    assert result is not None
    log_action(
        "project_updated",
        project_id=project_id,
        target_type="project",
        target_id=project_id,
        metadata={
            "name": name,
            "well_name": well_name,
            "total_llg_cost": total_llg_cost,
            "total_dhc_cost": total_dhc_cost,
            "wire_fee": wire_fee,
        },
    )
    return result
