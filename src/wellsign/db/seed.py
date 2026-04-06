"""One-time demo data seeding so a fresh launch shows something interesting.

Only runs when each table is empty. Idempotent — safe to call on every startup.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from wellsign.db.investors import insert_investor
from wellsign.db.migrate import connect
from wellsign.db.projects import count_projects, insert_project
from wellsign.db.templates import (
    insert_doc_template,
    insert_email_template,
    list_doc_templates,
    list_email_templates,
)
from wellsign.db.workflows import (
    ExitCondition,
    attach_doc_to_stage,
    attach_email_to_stage,
    insert_stage,
    insert_stage_run,
    insert_workflow,
    list_stages,
    list_workflows,
)

_DEMO_LICENSE_HASH = hashlib.sha256(b"wellsign-demo-license").hexdigest()


def _has_any(table: str) -> bool:
    with connect() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] > 0


def seed_if_empty() -> None:
    """Top-level entry point — call from main.py after migrate."""
    if not _has_any("document_templates"):
        _seed_doc_templates()
    if not _has_any("email_templates"):
        _seed_email_templates()
    if not _has_any("workflows"):
        _seed_default_workflow()
    if count_projects() == 0:
        _seed_demo_project_with_runs()


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
def _seed_doc_templates() -> None:
    insert_doc_template(
        name="Joint Operating Agreement (A.A.P.L. 610-1989)",
        doc_type="joa",
        storage_path="(none — drop a PDF to wire this)",
        page_size="legal",
        notary_required=True,
    )
    insert_doc_template(
        name="Participation Agreement",
        doc_type="pa",
        storage_path="(none — drop a PDF to wire this)",
        page_size="letter",
    )
    insert_doc_template(
        name="Cash Call C-1 (LLG → Decker)",
        doc_type="cash_call_c1",
        storage_path="(none — drop a PDF to wire this)",
        page_size="letter",
    )
    insert_doc_template(
        name="Cash Call C-2 (DHC → Paloma)",
        doc_type="cash_call_c2",
        storage_path="(none — drop a PDF to wire this)",
        page_size="letter",
    )
    insert_doc_template(
        name="Investor Info Sheet",
        doc_type="info_sheet",
        storage_path="(none — drop a PDF to wire this)",
        page_size="letter",
    )
    insert_doc_template(
        name="Subscription Agreement",
        doc_type="other",
        storage_path="(none — drop a PDF to wire this)",
        page_size="letter",
    )


def _seed_email_templates() -> None:
    insert_email_template(
        name="Solicitation — Initial Pitch",
        purpose="invitation",
        subject="Investment opportunity: {{prospect_name}} ({{well_name}})",
        body_html=(
            "<p>Hi {{investor_first_name}},</p>"
            "<p>I wanted to put a new opportunity in front of you — "
            "{{prospect_name}}, a {{well_name}} well in {{county_state}}.</p>"
            "<p>Total raise: ${{total_raise}}. AFE attached. Subscription "
            "agreement on the way if you'd like to participate.</p>"
            "<p>— {{operator_name}}</p>"
        ),
    )
    insert_email_template(
        name="Solicitation — Follow-up",
        purpose="invitation",
        subject="Following up — {{prospect_name}}",
        body_html=(
            "<p>Hi {{investor_first_name}},</p>"
            "<p>Quick follow-up on {{prospect_name}} — wanted to make sure you "
            "saw my note. Happy to jump on a call if you have any questions.</p>"
            "<p>— {{operator_name}}</p>"
        ),
    )
    insert_email_template(
        name="Solicitation — Final Ask",
        purpose="invitation",
        subject="Last call — {{prospect_name}} closes soon",
        body_html=(
            "<p>Hi {{investor_first_name}},</p>"
            "<p>Just a heads up — we're wrapping subscriptions on "
            "{{prospect_name}} this week. If you're in, let me know by Friday "
            "and I'll send paperwork.</p>"
            "<p>— {{operator_name}}</p>"
        ),
    )
    insert_email_template(
        name="Documentation — Send Packet",
        purpose="invitation",
        subject="{{prospect_name}} — Investor Documents for {{investor_name}}",
        body_html=(
            "<p>Hi {{investor_first_name}},</p>"
            "<p>Attached are your documents for the {{prospect_name}} "
            "({{well_name}}) project. Your working interest is "
            "{{investor_wi_percent_display}}.</p>"
            "<p><b>Cash call breakdown:</b><br>"
            "LLG to Decker Exploration: {{llg_amount}}<br>"
            "DHC to Paloma Operating: {{dhc_amount}}</p>"
            "<p>Please return signed documents and wire / mail payment by "
            "{{close_deadline}}.</p>"
            "<p>— {{operator_name}}</p>"
        ),
    )
    insert_email_template(
        name="Documentation — Reminder",
        purpose="reminder",
        subject="REMINDER: {{prospect_name}} signatures still outstanding",
        body_html=(
            "<p>Hi {{investor_first_name}},</p>"
            "<p>This is a friendly reminder that we still need your signed "
            "documents for {{prospect_name}}. Outstanding items:</p>"
            "<p>{{outstanding_items}}</p>"
            "<p>Reach out if you need anything.</p>"
            "<p>— {{operator_name}}</p>"
        ),
    )
    insert_email_template(
        name="Documentation — Final Reminder",
        purpose="reminder",
        subject="URGENT: {{prospect_name}} — please return signatures",
        body_html=(
            "<p>Hi {{investor_first_name}},</p>"
            "<p>We're approaching the close deadline for {{prospect_name}} on "
            "{{close_deadline}} and still need your signed paperwork. Please "
            "let me know today if there's anything blocking you.</p>"
            "<p>— {{operator_name}}</p>"
        ),
    )
    insert_email_template(
        name="Funding — Wire Instructions",
        purpose="invitation",
        subject="{{prospect_name}} — Wire instructions for cash call",
        body_html=(
            "<p>Hi {{investor_first_name}},</p>"
            "<p>Thanks for signing. Wire instructions for your cash call:</p>"
            "<p><b>LLG (${{llg_amount}}) → Decker Exploration, Inc.</b><br>"
            "Routing / account on the attached PDF.</p>"
            "<p><b>DHC (${{dhc_amount}}) → Paloma Operating LLC</b><br>"
            "Routing / account on the attached PDF.</p>"
            "<p>Funds due by {{close_deadline}}.</p>"
            "<p>— {{operator_name}}</p>"
        ),
    )
    insert_email_template(
        name="Funding — Reminder",
        purpose="reminder",
        subject="REMINDER: {{prospect_name}} cash call outstanding",
        body_html=(
            "<p>Hi {{investor_first_name}},</p>"
            "<p>Friendly reminder that we haven't seen your wire / check yet "
            "for {{prospect_name}}. Total owed: ${{total_owed}}.</p>"
            "<p>— {{operator_name}}</p>"
        ),
    )
    insert_email_template(
        name="Funding — Thank You",
        purpose="thank_you",
        subject="Received — thank you ({{prospect_name}})",
        body_html=(
            "<p>Hi {{investor_first_name}},</p>"
            "<p>Confirming we received your cash call payment for "
            "{{prospect_name}}. We'll reach out with operational updates as "
            "we approach spud.</p>"
            "<p>— {{operator_name}}</p>"
        ),
    )


# ---------------------------------------------------------------------------
# Default workflow
# ---------------------------------------------------------------------------
def _seed_default_workflow() -> None:
    workflow = insert_workflow(
        name="Standard Paloma Closing",
        description="Default 4-stage workflow used for typical Paloma well prospects.",
    )

    docs_by_type = {t.doc_type: t.id for t in list_doc_templates()}
    emails_by_name = {t.name: t.id for t in list_email_templates()}

    # Stage 1: Solicitation
    s1 = insert_stage(
        workflow_id=workflow.id,
        name="Solicitation",
        duration_days=21,
        exit_condition=ExitCondition.INVESTOR_COMMITTED.value,
        description="Pitch the deal and collect verbal commitments.",
    )
    if "other" in docs_by_type:
        attach_doc_to_stage(s1.id, docs_by_type["other"])  # Subscription Agreement
    for name, wait in [
        ("Solicitation — Initial Pitch", 0),
        ("Solicitation — Follow-up", 7),
        ("Solicitation — Final Ask", 14),
    ]:
        if name in emails_by_name:
            attach_email_to_stage(s1.id, emails_by_name[name], wait_days=wait)

    # Stage 2: Documentation
    s2 = insert_stage(
        workflow_id=workflow.id,
        name="Documentation",
        duration_days=14,
        exit_condition=ExitCondition.ALL_DOCS_SIGNED.value,
        description="Send packets, collect signatures.",
    )
    for code in ("joa", "pa", "cash_call_c1", "cash_call_c2", "info_sheet"):
        if code in docs_by_type:
            attach_doc_to_stage(s2.id, docs_by_type[code])
    for name, wait in [
        ("Documentation — Send Packet", 0),
        ("Documentation — Reminder", 7),
        ("Documentation — Final Reminder", 12),
    ]:
        if name in emails_by_name:
            attach_email_to_stage(s2.id, emails_by_name[name], wait_days=wait)

    # Stage 3: Funding
    s3 = insert_stage(
        workflow_id=workflow.id,
        name="Funding",
        duration_days=10,
        exit_condition=ExitCondition.LLG_AND_DHC_PAID.value,
        description="Cash call collection from each investor.",
    )
    for name, wait in [
        ("Funding — Wire Instructions", 0),
        ("Funding — Reminder", 5),
        ("Funding — Thank You", 0),
    ]:
        if name in emails_by_name:
            attach_email_to_stage(s3.id, emails_by_name[name], wait_days=wait)

    # Stage 4: Drilling (manual exit — operator marks complete after spud / completion)
    insert_stage(
        workflow_id=workflow.id,
        name="Drilling",
        duration_days=90,
        exit_condition=ExitCondition.MANUAL.value,
        description="Well is being drilled. Track AFE actuals and reconcile.",
    )


# ---------------------------------------------------------------------------
# Demo project
# ---------------------------------------------------------------------------
def _seed_demo_project_with_runs() -> None:
    now = datetime.now(timezone.utc)
    issued = now.isoformat().replace("+00:00", "Z")
    expires = (now + timedelta(days=365)).isoformat().replace("+00:00", "Z")

    project = insert_project(
        name="Highlander Prospect (Demo)",
        region="Karnes County, TX",
        well_name="Pargmann-Gisler #1",
        license_key_hash=_DEMO_LICENSE_HASH,
        license_customer="Paloma Operating LLC (Demo)",
        license_issued_at=issued,
        license_expires_at=expires,
        license_key_id="demo-key-0001",
        is_test=True,
    )

    workflows = list_workflows()
    workflow = workflows[0] if workflows else None
    stages = list_stages(workflow.id) if workflow else []

    with connect() as conn:
        conn.execute(
            """
            UPDATE projects
               SET total_llg_cost = 1500000.00,
                   total_dhc_cost = 2750000.00,
                   operator_llc = 'Paloma Operating LLC',
                   prospect_name = 'Highlander Prospect',
                   county = 'Karnes',
                   state = 'TX',
                   agreement_date = ?,
                   close_deadline = ?,
                   workflow_id = ?
             WHERE id = ?
            """,
            (
                (now - timedelta(days=14)).date().isoformat(),
                (now + timedelta(days=21)).date().isoformat(),
                workflow.id if workflow else None,
                project.id,
            ),
        )
        conn.commit()

    demo_investors = [
        # (last, first, entity, email, city, state, wi%, days_in_doc_stage)
        ("Almanza",  "Roberto",  None,                          "ralmanza@example.com",  "San Antonio", "TX", 0.05000000,  2),  # green
        ("Brennan",  "Margaret", "Brennan Family Trust",        "mbrennan@example.com",  "Houston",     "TX", 0.10000000,  7),  # green
        ("Castillo", None,       "Castillo Royalty Partners LP","ops@castillo-rp.com",   "Midland",     "TX", 0.15000000, 12),  # yellow (14d SLA, 12 in)
        ("Doyle",    "Patrick",  None,                          "pdoyle@example.com",    "Dallas",      "TX", 0.02500000, 16),  # red (overdue)
        ("Eichmann", None,       "Eichmann IRA Holdings",       "eichmann@example.com",  "Austin",      "TX", 0.07500000,  0),  # green (just entered)
    ]

    LLG = 1500000.00
    DHC = 2750000.00

    # Stage to put investors into for the demo: Stage 2 (Documentation)
    doc_stage = stages[1] if len(stages) >= 2 else None

    for last, first, entity, email, city, state, wi, days_offset in demo_investors:
        inv = insert_investor(
            project_id=project.id,
            first_name=first,
            last_name=last,
            entity_name=entity,
            email=email,
            city=city,
            state=state,
            wi_percent=wi,
            llg_amount=round(wi * LLG, 2),
            dhc_amount=round(wi * DHC, 2),
            payment_preference="wire" if entity else "check",
        )
        if doc_stage is not None:
            insert_stage_run(
                investor_id=inv.id,
                project_id=project.id,
                stage_id=doc_stage.id,
                entered_at=datetime.utcnow() - timedelta(days=days_offset),
            )
