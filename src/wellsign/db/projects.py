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

    @property
    def display_label(self) -> str:
        bits = [self.name]
        if self.well_name:
            bits.append(self.well_name)
        return "  ·  ".join(bits)


def _row_to_project(row: sqlite3.Row) -> ProjectRow:
    # workflow_id may be missing on legacy rows; tolerate it.
    try:
        wf = row["workflow_id"]
    except (KeyError, IndexError):
        wf = None
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
        workflow_id=wf,
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
    return project
