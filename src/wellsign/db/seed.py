"""One-time demo data seeding so a fresh launch shows something interesting.

Only runs when each table is empty. Idempotent — safe to call on every startup.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from wellsign.db.costs import insert_cost_line
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
        name="Outreach — Initial Pitch",
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
        name="Outreach — Follow-up",
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
        name="Outreach — Final Ask",
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
        name="Subscription — Send Packet",
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
        name="Subscription — Reminder",
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
        name="Subscription — Final Reminder",
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
        name="Cash Call — Wire Instructions",
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
        name="Cash Call — Reminder",
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
        name="Cash Call — Thank You",
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
        name="Standard Capital Raise",
        description="Default 3-stage capital raise pipeline: Outreach → Subscription → Cash Call.",
    )

    docs_by_type = {t.doc_type: t.id for t in list_doc_templates()}
    emails_by_name = {t.name: t.id for t in list_email_templates()}

    # Stage 1: Outreach (pre-subscription marketing to existing relationships)
    s1 = insert_stage(
        workflow_id=workflow.id,
        name="Outreach",
        duration_days=21,
        exit_condition=ExitCondition.INVESTOR_COMMITTED.value,
        description="Pitch the deal to existing relationships and collect verbal commitments.",
    )
    if "other" in docs_by_type:
        attach_doc_to_stage(s1.id, docs_by_type["other"])  # Subscription Agreement
    for name, wait in [
        ("Outreach — Initial Pitch", 0),
        ("Outreach — Follow-up", 7),
        ("Outreach — Final Ask", 14),
    ]:
        if name in emails_by_name:
            attach_email_to_stage(s1.id, emails_by_name[name], wait_days=wait)

    # Stage 2: Subscription (full investor packet — PA, JOA, C-1, C-2, W-9, Info Form)
    s2 = insert_stage(
        workflow_id=workflow.id,
        name="Subscription",
        duration_days=14,
        exit_condition=ExitCondition.ALL_DOCS_SIGNED.value,
        description="Send the full subscription packet and collect signed returns.",
    )
    for code in ("joa", "pa", "cash_call_c1", "cash_call_c2", "info_sheet"):
        if code in docs_by_type:
            attach_doc_to_stage(s2.id, docs_by_type[code])
    for name, wait in [
        ("Subscription — Send Packet", 0),
        ("Subscription — Reminder", 7),
        ("Subscription — Final Reminder", 12),
    ]:
        if name in emails_by_name:
            attach_email_to_stage(s2.id, emails_by_name[name], wait_days=wait)

    # Stage 3: Cash Call (LLG to Decker, DHC to operator)
    s3 = insert_stage(
        workflow_id=workflow.id,
        name="Cash Call",
        duration_days=10,
        exit_condition=ExitCondition.LLG_AND_DHC_PAID.value,
        description="Cash call collection: LLG wires to Decker, DHC wires/checks to the operator.",
    )
    for name, wait in [
        ("Cash Call — Wire Instructions", 0),
        ("Cash Call — Reminder", 5),
        ("Cash Call — Thank You", 0),
    ]:
        if name in emails_by_name:
            attach_email_to_stage(s3.id, emails_by_name[name], wait_days=wait)

    # NOTE: Drilling is a project PHASE, not a per-investor workflow stage.
    # Once all investors complete the Cash Call stage, the project's `phase`
    # advances to 'drilling' — operator-side activity, no per-investor signaling.


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
                   workflow_id = ?,
                   phase = 'documenting',
                   phase_entered_at = ?
             WHERE id = ?
            """,
            (
                (now - timedelta(days=14)).date().isoformat(),
                (now + timedelta(days=21)).date().isoformat(),
                workflow.id if workflow else None,
                (now - timedelta(days=10)).isoformat(timespec="seconds"),
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

    # Stage to put investors into for the demo: Stage 2 (Subscription)
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

    # Realistic ~$8M Eagle Ford horizontal AFE — 32 line items grouped by phase
    # (phase, tax, category, description, expected, actual, vendor, status)
    demo_costs = [
        # ---- Pre-drilling ----
        ("pre_drilling", "intangible", "Lease Bonus",          "Lease bonus payments — 320 acres @ ~$625/ac", 200000.00,  200000.00, "Various mineral owners",   "paid"),
        ("pre_drilling", "intangible", "Title Work",           "Title opinions and curative",                  25000.00,   24750.00, "Brennan Title Co.",        "paid"),
        ("pre_drilling", "intangible", "Permits / Regulatory", "RRC application + bonding + APD",              40000.00,   42000.00, "Texas RRC",                "paid"),
        ("pre_drilling", "intangible", "Surveying",            "Pre-spud + post-spud surveys",                 25000.00,   23500.00, "Twin Lakes Surveying",     "paid"),
        ("pre_drilling", "intangible", "Site Prep",            "Pad construction + grading",                  200000.00,  192300.00, "Karnes Earthworks LLC",    "paid"),
        ("pre_drilling", "intangible", "Roads / Location",     "Access road build + culverts",                 80000.00,   84600.00, "Karnes Earthworks LLC",    "paid"),
        # ---- Drilling ----
        ("drilling",     "intangible", "Drilling",             "Rig day rate × ~21 days — Pargmann-Gisler #1", 1500000.00, 1488750.00, "Patterson-UTI Rig 174",    "paid"),
        ("drilling",     "intangible", "Drill Bits / BHA",     "PDC bits + bottomhole assembly",              150000.00,  142800.00, "NOV ReedHycalog",          "paid"),
        ("drilling",     "intangible", "Directional Drilling", "Geosteering + MWD/LWD services",              400000.00,  411500.00, "Halliburton Sperry",       "paid"),
        ("drilling",     "intangible", "Mud / Fluids",         "Drilling fluids program (3 sections)",        250000.00,  248900.00, "M-I SWACO",                "invoiced"),
        ("drilling",     "intangible", "Logging",              "Open-hole + mud logging suite",               150000.00,  148200.00, "Schlumberger",             "paid"),
        ("drilling",     "tangible",   "Surface Casing",       "13-3/8 in surface string",                     80000.00,   79400.00, "Tenaris USA",              "paid"),
        ("drilling",     "tangible",   "Intermediate Casing",  "9-5/8 in intermediate string",                200000.00,  198650.00, "Tenaris USA",              "paid"),
        ("drilling",     "tangible",   "Production Casing",    "5-1/2 in production string",                  300000.00,  295100.00, "Tenaris USA",              "paid"),
        ("drilling",     "intangible", "Cement",               "Cementing services — all 3 strings",          180000.00,  174800.00, "Halliburton",              "paid"),
        ("drilling",     "intangible", "Mob / Demob",          "Rig mobilization + demobilization",            80000.00,   82500.00, "Patterson-UTI",            "paid"),
        ("drilling",     "intangible", "Trucking",             "Equipment + materials hauling",                70000.00,   71200.00, "South Texas Hot Shot",     "invoiced"),
        # ---- Completion ----
        ("completion",   "intangible", "Frac Services",        "22-stage hydraulic fracturing — labor",      1500000.00,       None, "Liberty Energy",           "committed"),
        ("completion",   "tangible",   "Proppant / Sand",      "Northern white + 100 mesh sand",              800000.00,       None, "US Silica",                "committed"),
        ("completion",   "intangible", "Frac Fluids",          "Slickwater + chemical additives",             400000.00,       None, "ChampionX",                "committed"),
        ("completion",   "intangible", "Perforating",          "22-stage perforation guns",                   120000.00,       None, "GR Energy Services",       "planned"),
        ("completion",   "intangible", "Wireline",             "Plug + perf + dipole sonic",                  100000.00,       None, "Halliburton",              "planned"),
        ("completion",   "intangible", "Coiled Tubing",        "Cleanout + flowback prep",                     60000.00,       None, "STEP Energy Services",     "planned"),
        # ---- Facilities ----
        ("facilities",   "tangible",   "Wellhead",             "Wellhead + christmas tree",                    80000.00,       None, "Cactus Wellhead",          "planned"),
        ("facilities",   "tangible",   "Tank Battery",         "3 × 400 bbl tanks + manifold",                120000.00,       None, "Permian Tank",             "planned"),
        ("facilities",   "tangible",   "Separator",            "3-phase separator + heater treater",           60000.00,       None, "Sivalls Inc.",             "planned"),
        ("facilities",   "tangible",   "Flowlines",            "Wellhead → battery flowlines",                 80000.00,       None, "Stallion Oilfield",        "planned"),
        ("facilities",   "tangible",   "Pipeline / Gathering", "Gathering line + tap fee",                    200000.00,       None, "Enterprise Crude",         "planned"),
        ("facilities",   "tangible",   "Meter / SCADA",        "Custody-transfer meter + SCADA",               30000.00,       None, "Quorum Software",          "planned"),
        # ---- Soft costs ----
        ("soft",         "intangible", "Operator Overhead",    "Operator overhead @ 5% of project",           400000.00,       None, "Paloma Operating LLC",     "planned"),
        ("soft",         "mixed",      "Contingency",          "10% contingency reserve",                     720000.00,       None, "—",                        "planned"),
        ("soft",         "intangible", "Insurance",            "Well control + general liability",             40000.00,   40000.00, "Marsh McLennan",           "paid"),
    ]
    for phase, tax, category, description, expected, actual, vendor, status in demo_costs:
        insert_cost_line(
            project_id=project.id,
            phase_group=phase,
            tax_class=tax,
            category=category,
            description=description,
            expected_amount=expected,
            actual_amount=actual,
            vendor=vendor,
            status=status,
        )

    # ------------------------------------------------------------------
    # Second demo project — different phase, smaller raise, fewer
    # investors. Lets the navigator show 2 colored dots and demos the
    # cross-project comparison view on the Projects dashboard.
    # ------------------------------------------------------------------
    project2 = insert_project(
        name="Frio Wildcat #2 (Demo)",
        region="Atascosa County, TX",
        well_name="Buchanan-Vela #1H",
        license_key_hash=_DEMO_LICENSE_HASH,
        license_customer="Paloma Operating LLC (Demo)",
        license_issued_at=issued,
        license_expires_at=expires,
        license_key_id="demo-key-0002",
        is_test=True,
    )

    with connect() as conn:
        conn.execute(
            """
            UPDATE projects
               SET total_llg_cost = 800000.00,
                   total_dhc_cost = 1500000.00,
                   operator_llc = 'Paloma Operating LLC',
                   prospect_name = 'Frio Wildcat',
                   county = 'Atascosa',
                   state = 'TX',
                   agreement_date = ?,
                   close_deadline = ?,
                   workflow_id = ?,
                   phase = 'soliciting',
                   phase_entered_at = ?
             WHERE id = ?
            """,
            (
                (now - timedelta(days=4)).date().isoformat(),
                (now + timedelta(days=45)).date().isoformat(),
                workflow.id if workflow else None,
                (now - timedelta(days=4)).isoformat(timespec="seconds"),
                project2.id,
            ),
        )
        conn.commit()

    # 3 investors, all in the Outreach (stage 1) phase at varying ages.
    LLG2 = 800000.00
    DHC2 = 1500000.00
    sol_stage = stages[0] if stages else None
    project2_investors = [
        # (last, first, entity, email, city, state, wi%, days_in_stage)
        ("Hartwell",  "Joel",      None,                          "joel.hartwell@example.com",  "Pleasanton", "TX", 0.20000000,  1),
        ("Ortega",    None,        "Ortega Holdings LLC",         "kim@ortega-holdings.com",    "Jourdanton", "TX", 0.15000000,  3),
        ("Quinn",     "Lila",      None,                          "lila.quinn@example.com",     "Three Rivers","TX", 0.10000000,  6),
    ]
    for last, first, entity, email, city, state, wi, days_offset in project2_investors:
        inv = insert_investor(
            project_id=project2.id,
            first_name=first,
            last_name=last,
            entity_name=entity,
            email=email,
            city=city,
            state=state,
            wi_percent=wi,
            llg_amount=round(wi * LLG2, 2),
            dhc_amount=round(wi * DHC2, 2),
            payment_preference="wire" if entity else "check",
        )
        if sol_stage is not None:
            insert_stage_run(
                investor_id=inv.id,
                project_id=project2.id,
                stage_id=sol_stage.id,
                entered_at=datetime.utcnow() - timedelta(days=days_offset),
            )

    # Sparse cost setup — only the pre-drilling planning lines have entries.
    project2_costs = [
        ("pre_drilling", "intangible", "Lease Bonus",          "Lease bonus — 160 acres @ $500/ac",            80000.00,  80000.00, "Various mineral owners",   "paid"),
        ("pre_drilling", "intangible", "Title Work",           "Title opinions",                              15000.00,      None, "Brennan Title Co.",        "committed"),
        ("pre_drilling", "intangible", "Permits / Regulatory", "RRC application",                             20000.00,      None, "Texas RRC",                "planned"),
        ("pre_drilling", "intangible", "Surveying",            "Pre-spud survey",                             12000.00,      None, "Twin Lakes Surveying",     "planned"),
        ("pre_drilling", "intangible", "Site Prep",            "Pad construction (estimate)",                120000.00,      None, "Karnes Earthworks LLC",    "planned"),
    ]
    for phase, tax, category, description, expected, actual, vendor, status in project2_costs:
        insert_cost_line(
            project_id=project2.id,
            phase_group=phase,
            tax_class=tax,
            category=category,
            description=description,
            expected_amount=expected,
            actual_amount=actual,
            vendor=vendor,
            status=status,
        )
