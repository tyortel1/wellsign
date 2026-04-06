"""Read/write access for the ``investors`` table.

PII columns (ssn_enc, ein_enc, bank_*_enc) are stored encrypted at the app
layer. The list/get helpers do NOT decrypt — callers that need plaintext
must explicitly invoke ``util.crypto.decrypt_pii`` on a single field at the
moment of display.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime

from wellsign.app_paths import investor_dir
from wellsign.db.migrate import connect


@dataclass
class InvestorRow:
    id: str
    project_id: str
    first_name: str | None
    last_name: str | None
    entity_name: str | None
    email: str | None
    phone: str | None
    city: str | None
    state: str | None
    wi_percent: float
    llg_amount: float | None
    dhc_amount: float | None
    payment_preference: str | None
    portal_status: str
    created_at: str

    @property
    def display_name(self) -> str:
        if self.entity_name:
            return self.entity_name
        parts = [p for p in (self.first_name, self.last_name) if p]
        return " ".join(parts) or "(unnamed)"


def _row_to_investor(row: sqlite3.Row) -> InvestorRow:
    return InvestorRow(
        id=row["id"],
        project_id=row["project_id"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        entity_name=row["entity_name"],
        email=row["email"],
        phone=row["phone"],
        city=row["city"],
        state=row["state"],
        wi_percent=float(row["wi_percent"] or 0),
        llg_amount=row["llg_amount"],
        dhc_amount=row["dhc_amount"],
        payment_preference=row["payment_preference"],
        portal_status=row["portal_status"],
        created_at=row["created_at"],
    )


def list_investors(project_id: str) -> list[InvestorRow]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM investors
             WHERE project_id = ?
             ORDER BY last_name, first_name, entity_name
            """,
            (project_id,),
        ).fetchall()
        return [_row_to_investor(r) for r in rows]


def count_investors(project_id: str) -> int:
    with connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM investors WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]


def insert_investor(
    *,
    project_id: str,
    first_name: str | None = None,
    last_name: str | None = None,
    entity_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    address_line1: str | None = None,
    city: str | None = None,
    state: str | None = None,
    zip_code: str | None = None,
    wi_percent: float = 0.0,
    llg_amount: float | None = None,
    dhc_amount: float | None = None,
    payment_preference: str | None = None,
) -> InvestorRow:
    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO investors (
                id, project_id,
                first_name, last_name, entity_name,
                email, phone,
                address_line1, city, state, zip,
                wi_percent, llg_amount, dhc_amount, payment_preference,
                created_at, updated_at
            ) VALUES (
                :id, :project_id,
                :first_name, :last_name, :entity_name,
                :email, :phone,
                :address_line1, :city, :state, :zip,
                :wi_percent, :llg_amount, :dhc_amount, :payment_preference,
                :now, :now
            )
            """,
            {
                "id": new_id,
                "project_id": project_id,
                "first_name": first_name,
                "last_name": last_name,
                "entity_name": entity_name,
                "email": email,
                "phone": phone,
                "address_line1": address_line1,
                "city": city,
                "state": state,
                "zip": zip_code,
                "wi_percent": wi_percent,
                "llg_amount": llg_amount,
                "dhc_amount": dhc_amount,
                "payment_preference": payment_preference,
                "now": now,
            },
        )
        conn.commit()

    investor_dir(project_id, new_id)

    with connect() as conn:
        row = conn.execute("SELECT * FROM investors WHERE id = ?", (new_id,)).fetchone()
    return _row_to_investor(row)
