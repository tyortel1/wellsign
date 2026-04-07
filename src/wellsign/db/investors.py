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
from wellsign.util.crypto import encrypt_pii


@dataclass
class InvestorRow:
    id: str
    project_id: str
    first_name: str | None
    last_name: str | None
    entity_name: str | None
    title: str | None
    email: str | None
    phone: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    zip: str | None
    wi_percent: float
    llg_amount: float | None
    dhc_amount: float | None
    payment_preference: str | None
    portal_status: str
    notes: str | None
    created_at: str
    # encrypted blobs — never decrypted in this module
    ssn_enc: str | None
    ein_enc: str | None
    bank_name_enc: str | None
    bank_routing_enc: str | None
    bank_account_enc: str | None

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
        title=row["title"],
        email=row["email"],
        phone=row["phone"],
        address_line1=row["address_line1"],
        address_line2=row["address_line2"],
        city=row["city"],
        state=row["state"],
        zip=row["zip"],
        wi_percent=float(row["wi_percent"] or 0),
        llg_amount=row["llg_amount"],
        dhc_amount=row["dhc_amount"],
        payment_preference=row["payment_preference"],
        portal_status=row["portal_status"],
        notes=row["notes"],
        created_at=row["created_at"],
        ssn_enc=row["ssn_enc"],
        ein_enc=row["ein_enc"],
        bank_name_enc=row["bank_name_enc"],
        bank_routing_enc=row["bank_routing_enc"],
        bank_account_enc=row["bank_account_enc"],
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


def get_investor(investor_id: str) -> InvestorRow | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM investors WHERE id = ?", (investor_id,)
        ).fetchone()
        return _row_to_investor(row) if row else None


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
    title: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    address_line1: str | None = None,
    address_line2: str | None = None,
    city: str | None = None,
    state: str | None = None,
    zip_code: str | None = None,
    wi_percent: float = 0.0,
    llg_amount: float | None = None,
    dhc_amount: float | None = None,
    payment_preference: str | None = None,
    notes: str | None = None,
    # PII (plaintext on the way in — encrypted before storage)
    ssn: str | None = None,
    ein: str | None = None,
    bank_name: str | None = None,
    bank_routing: str | None = None,
    bank_account: str | None = None,
) -> InvestorRow:
    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO investors (
                id, project_id,
                first_name, last_name, entity_name, title,
                email, phone,
                address_line1, address_line2, city, state, zip,
                wi_percent, llg_amount, dhc_amount, payment_preference, notes,
                ssn_enc, ein_enc, bank_name_enc, bank_routing_enc, bank_account_enc,
                created_at, updated_at
            ) VALUES (
                :id, :project_id,
                :first_name, :last_name, :entity_name, :title,
                :email, :phone,
                :address_line1, :address_line2, :city, :state, :zip,
                :wi_percent, :llg_amount, :dhc_amount, :payment_preference, :notes,
                :ssn_enc, :ein_enc, :bank_name_enc, :bank_routing_enc, :bank_account_enc,
                :now, :now
            )
            """,
            {
                "id": new_id,
                "project_id": project_id,
                "first_name": first_name,
                "last_name": last_name,
                "entity_name": entity_name,
                "title": title,
                "email": email,
                "phone": phone,
                "address_line1": address_line1,
                "address_line2": address_line2,
                "city": city,
                "state": state,
                "zip": zip_code,
                "wi_percent": wi_percent,
                "llg_amount": llg_amount,
                "dhc_amount": dhc_amount,
                "payment_preference": payment_preference,
                "notes": notes,
                "ssn_enc": encrypt_pii(ssn),
                "ein_enc": encrypt_pii(ein),
                "bank_name_enc": encrypt_pii(bank_name),
                "bank_routing_enc": encrypt_pii(bank_routing),
                "bank_account_enc": encrypt_pii(bank_account),
                "now": now,
            },
        )
        conn.commit()

    investor_dir(project_id, new_id)

    result = get_investor(new_id)
    assert result is not None
    return result


def update_investor(
    investor_id: str,
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    entity_name: str | None = None,
    title: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    address_line1: str | None = None,
    address_line2: str | None = None,
    city: str | None = None,
    state: str | None = None,
    zip_code: str | None = None,
    wi_percent: float = 0.0,
    llg_amount: float | None = None,
    dhc_amount: float | None = None,
    payment_preference: str | None = None,
    notes: str | None = None,
    # PII — only updated if not None; pass empty string to clear a field
    ssn: str | None = None,
    ein: str | None = None,
    bank_name: str | None = None,
    bank_routing: str | None = None,
    bank_account: str | None = None,
) -> InvestorRow:
    """Update an investor row.

    Non-PII fields are written as-is. PII fields are written only if the
    caller passed something other than ``None`` — pass an empty string to
    clear a stored value.
    """
    now = datetime.utcnow().isoformat(timespec="seconds")
    sets: list[str] = [
        "first_name = :first_name",
        "last_name = :last_name",
        "entity_name = :entity_name",
        "title = :title",
        "email = :email",
        "phone = :phone",
        "address_line1 = :address_line1",
        "address_line2 = :address_line2",
        "city = :city",
        "state = :state",
        "zip = :zip",
        "wi_percent = :wi_percent",
        "llg_amount = :llg_amount",
        "dhc_amount = :dhc_amount",
        "payment_preference = :payment_preference",
        "notes = :notes",
        "updated_at = :now",
    ]
    params: dict[str, object] = {
        "id": investor_id,
        "first_name": first_name,
        "last_name": last_name,
        "entity_name": entity_name,
        "title": title,
        "email": email,
        "phone": phone,
        "address_line1": address_line1,
        "address_line2": address_line2,
        "city": city,
        "state": state,
        "zip": zip_code,
        "wi_percent": wi_percent,
        "llg_amount": llg_amount,
        "dhc_amount": dhc_amount,
        "payment_preference": payment_preference,
        "notes": notes,
        "now": now,
    }

    pii_pairs = [
        ("ssn_enc", ssn),
        ("ein_enc", ein),
        ("bank_name_enc", bank_name),
        ("bank_routing_enc", bank_routing),
        ("bank_account_enc", bank_account),
    ]
    for col, plain in pii_pairs:
        if plain is None:
            continue  # leave existing value alone
        sets.append(f"{col} = :{col}")
        params[col] = encrypt_pii(plain) if plain != "" else None

    sql = f"UPDATE investors SET {', '.join(sets)} WHERE id = :id"
    with connect() as conn:
        conn.execute(sql, params)
        conn.commit()

    result = get_investor(investor_id)
    assert result is not None
    return result


def delete_investor(investor_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM investors WHERE id = ?", (investor_id,))
        conn.commit()
