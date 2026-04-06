# WellSign — Data Model

> **Source of truth:** `src/wellsign/db/schema.sql`. This file is a human-readable description; if it ever drifts from `schema.sql`, the SQL wins.
>
> Schema is applied idempotently on every startup by `db/migrate.py:run_migrations()`. Demo data is seeded by `db/seed.py:seed_if_empty()` on first run only.

## Conventions

- All IDs are UUID v4 strings stored as `TEXT` (`str(uuid.uuid4())`)
- Timestamps are ISO-8601 `TEXT` (`datetime('now')` default in SQL, `datetime.utcnow().isoformat(timespec='seconds')` in Python)
- Booleans are `INTEGER 0/1` (SQLite has no native bool)
- All PII columns end in `_enc` and store AES-256-GCM ciphertext as `iv_hex:tag_hex:ct_hex` (see `util/crypto.py`)
- Foreign key cascades: `ON DELETE CASCADE` everywhere a project owns its children, so dropping a project drops everything beneath it
- `PRAGMA foreign_keys = ON` set in `db/migrate.py:connect()`
- `PRAGMA journal_mode = WAL` set in `schema.sql`

## Entity overview

```
projects ─< investors ─< investor_documents
    │           │            │
    │           │            └── (also references external_url for hosted-signing services)
    │           │
    │           ├──< investor_stage_runs ──> workflow_stages
    │           │
    │           └──< payments       (one row per LLG/DHC expectation)
    │
    ├──< project_templates ──> document_templates  (per-project snapshots)
    │
    ├──< cost_line_items ──< cost_attachments     (AFE budget + receipts)
    │
    └── workflow_id (FK) ──> workflows ──< workflow_stages
                                              ├──< stage_doc_templates ──> document_templates
                                              └──< stage_email_templates ──> email_templates

document_templates  (global library)
email_templates     (global library)
send_events         (timeline of every Outlook send)
audit_log           (append-only via SQL triggers)
schema_version      (versioning for db/migrate.py)
```

## Tables

### `schema_version`

| Column | Type | Notes |
|---|---|---|
| version | INTEGER PK | |
| applied_at | TEXT | `datetime('now')` default |

`db/migrate.py:CURRENT_VERSION` is the integer the app stamps on startup. Bump when the schema changes meaningfully.

### `projects`

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| name | TEXT NOT NULL | Display name |
| prospect_name | TEXT | |
| well_name | TEXT | |
| operator_llc | TEXT | |
| county | TEXT | |
| state | TEXT | |
| agreement_date | TEXT | ISO date |
| close_deadline | TEXT | ISO date |
| total_llg_cost | REAL | Drives Cash Call C-1 (Decker) |
| total_dhc_cost | REAL | Drives Cash Call C-2 (Paloma) |
| status | TEXT | `draft` / `active` / `closed` / `archived`, default `draft` |
| is_test | INTEGER | 1 = test mode |
| **license_key_hash** | TEXT NOT NULL | SHA-256 of canonical license payload — binds project to license |
| license_customer | TEXT | From license payload |
| license_issued_at | TEXT | ISO-8601 |
| license_expires_at | TEXT | ISO-8601 |
| license_key_id | TEXT | UUID from license payload |
| storage_path | TEXT NOT NULL | Relative to `projects_root`, usually = `id` |
| **workflow_id** | TEXT | nullable — FK to `workflows`, picked at project creation |
| **phase** | TEXT NOT NULL | default `'investigating'` — current lifecycle phase (see `db/phases.py`) |
| **phase_entered_at** | TEXT | nullable — timestamp set by `set_phase()` |
| created_at, updated_at | TEXT | |

**Index:** `idx_projects_status` on `(status)`

> **License model:** one license = one project, signed offline by `scripts/mint_license.py`. The hash is stored on the row to detect tampering or reuse. See [roadmap.md](roadmap.md) for the annual-seat alternative.
>
> **`db/projects.py:_row_to_project()` defensively handles missing columns** via a `_safe()` helper, so legacy rows without `workflow_id` / `phase` / `phase_entered_at` still load. **However, `insert_project()` writes `workflow_id` directly** — returning installs whose `projects` table predates these columns will fail on insert. See "Migration gap" below.

### `investors`

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| project_id | TEXT FK | `→ projects(id) ON DELETE CASCADE` |
| first_name, last_name, entity_name | TEXT | |
| title | TEXT | Signing title (e.g. "Trustee") |
| email, phone | TEXT | |
| address_line1, address_line2, city, state, zip | TEXT | |
| **wi_percent** | REAL NOT NULL | Stored as fraction. `0.01000000` = 1%. Single value (no BCP/ACP split — see [roadmap.md](roadmap.md)) |
| llg_amount | REAL | `wi_percent × project.total_llg_cost`, computed at insert/update |
| dhc_amount | REAL | `wi_percent × project.total_dhc_cost` |
| payment_preference | TEXT | `wire` / `check` |
| **ssn_enc** | TEXT | AES-256-GCM ciphertext |
| **ein_enc** | TEXT | AES-256-GCM ciphertext |
| **bank_name_enc** | TEXT | AES-256-GCM ciphertext |
| **bank_routing_enc** | TEXT | AES-256-GCM ciphertext |
| **bank_account_enc** | TEXT | AES-256-GCM ciphertext |
| portal_status | TEXT | `not_sent` / `sent` / `partial` / `complete`, default `not_sent` |
| info_form_complete | INTEGER | |
| consent_given | INTEGER | |
| consent_given_at | TEXT | |
| notes | TEXT | |
| created_at, updated_at | TEXT | |

**Indexes:** `idx_investors_project`, `idx_investors_status`

> **Investors are per-project.** Same human investor in 5 wells = 5 rows. See [roadmap.md](roadmap.md) for the multi-well investor refactor.

### `document_templates` (global library)

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | |
| name | TEXT NOT NULL | "Joint Operating Agreement (A.A.P.L. 610-1989)" |
| doc_type | TEXT NOT NULL | `joa` / `pa` / `cash_call_c1` / `cash_call_c2` / `info_sheet` / `w9` / `wiring` / `other` |
| storage_path | TEXT NOT NULL | Path under `app_data_root/templates/documents/` |
| field_mapping | TEXT | JSON: `{ "pdf_field_name": "merge_variable_name" }` |
| page_size | TEXT | `letter` / `legal` |
| notary_required | INTEGER | 0/1 — JOA = 1 |
| is_global | INTEGER | 1 = available to all projects |
| created_at, updated_at | TEXT | |

### `project_templates` (per-project snapshot)

Snapshot of which templates are wired into a specific project, with a per-project storage path so the operator can pin a frozen copy of the template at the moment of project creation.

### `email_templates` (global library)

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | |
| name | TEXT NOT NULL | |
| purpose | TEXT NOT NULL | `invitation` / `reminder` / `thank_you` / `custom` |
| subject | TEXT NOT NULL | Supports `{{merge_variables}}` |
| body_html | TEXT NOT NULL | Supports `{{merge_variables}}` |
| is_global | INTEGER | |
| created_at, updated_at | TEXT | |

The seed creates **9 templates** spread across the 3 active phases — Solicitation × 3 (Initial Pitch / Follow-up / Final Ask), Documentation × 3 (Send Packet / Reminder / Final Reminder), Funding × 3 (Wire Instructions / Reminder / Thank You). See `db/seed.py:_seed_email_templates()`.

Merge variables used by the seeded templates:
`{{prospect_name}}`, `{{well_name}}`, `{{county_state}}`, `{{investor_first_name}}`, `{{investor_name}}`, `{{investor_wi_percent_display}}`, `{{llg_amount}}`, `{{dhc_amount}}`, `{{total_raise}}`, `{{total_owed}}`, `{{close_deadline}}`, `{{operator_name}}`, `{{outstanding_items}}`.

### `investor_documents`

Every PDF that exists for an investor on a project — sent packets, signed returns, attachments, anything.

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | |
| project_id | TEXT FK | `→ projects(id) ON DELETE CASCADE` |
| investor_id | TEXT FK | `→ investors(id) ON DELETE CASCADE` |
| doc_type | TEXT NOT NULL | Mirrors `document_templates.doc_type` or `attachment` |
| **direction** | TEXT NOT NULL | `sent` / `received` / `attachment` |
| **source** | TEXT NOT NULL | `app` / `manual_upload` / `email_import` / `docusign` / `pandadoc` |
| storage_path | TEXT | Relative to project root; null if `external_url` is set |
| external_url | TEXT | Set when the signed doc lives in a third-party signing service |
| file_sha256 | TEXT | Integrity check |
| byte_size | INTEGER | |
| mime_type | TEXT | |
| status | TEXT | `pending` / `generated` / `sent` / `viewed` / `signed` / `notarized` / `rejected` |
| sent_at, received_at, signed_at | TEXT | |
| metadata | TEXT | JSON; **never PII** |
| created_at, updated_at | TEXT | |

**Indexes:** `idx_invdocs_project`, `idx_invdocs_investor`, `idx_invdocs_status`

> **Forward-compatible for e-sign.** `source` already includes `docusign` and `pandadoc`, and `external_url` is provisioned. Adding e-sign integration in a later milestone does NOT require a schema migration — just an API client.

### `payments`

One row per expected payment per investor.

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | |
| project_id, investor_id | TEXT FK | |
| payment_type | TEXT NOT NULL | `llg` / `dhc` |
| payee | TEXT NOT NULL | `decker` / `paloma` |
| expected_amount | REAL NOT NULL | |
| received_amount | REAL | Nullable until received |
| method | TEXT | `wire` / `check` |
| received_at | TEXT | |
| reference_number | TEXT | Wire confirmation # / check # |
| notes | TEXT | |
| status | TEXT | `expected` / `partial` / `received` / `overdue` |
| created_at, updated_at | TEXT | |

### `send_events`

One row per Outlook send so we can render a timeline.

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | |
| project_id, investor_id | TEXT FK | |
| email_template_id | TEXT FK | Nullable |
| subject | TEXT | |
| sent_at | TEXT | |
| attached_doc_ids | TEXT | JSON array of `investor_documents.id` |
| success | INTEGER | 0/1 |
| error_message | TEXT | |

### `audit_log` (append-only)

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| occurred_at | TEXT | |
| actor | TEXT | OS username |
| project_id, investor_id | TEXT | Nullable |
| action | TEXT NOT NULL | `project_created` / `doc_sent` / `doc_received` / etc. |
| target_type, target_id | TEXT | |
| metadata | TEXT | JSON; **never PII** |

> **Append-only enforced at the SQL level.** Triggers `audit_log_no_update` and `audit_log_no_delete` raise `RAISE(FAIL, 'audit_log is append-only')` on any UPDATE or DELETE attempt. The application doesn't have to remember to be careful — the database refuses.

## Workflow engine tables

These five tables make up the per-investor workflow automation. See `db/workflows.py` for the CRUD layer and `WorkflowsPage` for the UI.

### `workflows`

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | |
| name | TEXT NOT NULL | "Standard Paloma Closing" |
| description | TEXT | |
| is_global | INTEGER | 1 = available to all projects |
| created_at, updated_at | TEXT | |

### `workflow_stages`

Ordered children of a workflow. Each stage has an SLA and an exit condition.

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | |
| workflow_id | TEXT FK | `→ workflows(id) ON DELETE CASCADE` |
| stage_order | INTEGER NOT NULL | 0-indexed; reorderable via drag-drop in `WorkflowsPage` |
| name | TEXT NOT NULL | "Solicitation" / "Documentation" / "Funding" / "Drilling" |
| description | TEXT | |
| duration_days | INTEGER | SLA — drives traffic-light yellow/red |
| exit_condition | TEXT NOT NULL | default `'manual'`. Other values: `investor_committed` / `all_docs_signed` / `llg_paid` / `dhc_paid` / `llg_and_dhc_paid` |
| created_at | TEXT | |

**Index:** `idx_workflow_stages_workflow`

> **Exit conditions are captured but not enforced yet.** No code currently auto-advances an investor when the condition is met. See "Open gaps" below.

### `stage_doc_templates`

Join table — which doc templates are attached to which stage, in what order.

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | |
| stage_id | TEXT FK | `→ workflow_stages(id) ON DELETE CASCADE` |
| doc_template_id | TEXT FK | `→ document_templates(id) ON DELETE CASCADE` |
| item_order | INTEGER NOT NULL | default 0 |

**Index:** `idx_stage_doc_templates_stage`

### `stage_email_templates`

Join table — which email templates are attached to which stage, with a per-attachment `wait_days` for delayed reminders.

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | |
| stage_id | TEXT FK | `→ workflow_stages(id) ON DELETE CASCADE` |
| email_template_id | TEXT FK | `→ email_templates(id) ON DELETE CASCADE` |
| item_order | INTEGER NOT NULL | default 0 |
| wait_days | INTEGER NOT NULL | default 0 — delay from `entered_at` before this email is due |

**Index:** `idx_stage_email_templates_stage`

> **`wait_days` is captured but no scheduler reads it.** A reminder loop that fires emails when `entered_at + wait_days < now()` is the next obvious feature. See "Open gaps".

### `investor_stage_runs`

Per-investor runtime — which stage an investor is in right now, when they entered, when they completed.

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | |
| investor_id | TEXT FK | `→ investors(id) ON DELETE CASCADE` |
| project_id | TEXT FK | `→ projects(id) ON DELETE CASCADE` (denormalized for fast queries) |
| stage_id | TEXT FK | `→ workflow_stages(id) ON DELETE CASCADE` |
| entered_at | TEXT | default `datetime('now')` |
| completed_at | TEXT | |
| status | TEXT NOT NULL | default `in_progress`. Other values: `completed` / `skipped` / `blocked` |
| notes | TEXT | |

**Indexes:** `idx_isr_investor`, `idx_isr_project`, `idx_isr_status`

> **Created at seed time only.** The demo project's investors get stage runs at varying day-offsets (2, 7, 12, 16, 0) so the traffic lights render across green/yellow/red on first launch. **Real `insert_investor()` does NOT create a stage run.** This needs wiring before traffic lights work outside the demo. See "Open gaps".

## AFE Costs tables

Per-project budget vs actuals tracker. See `db/costs.py` for CRUD and `CostsTab` for the UI.

### `cost_line_items`

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | |
| project_id | TEXT FK | `→ projects(id) ON DELETE CASCADE` |
| category | TEXT NOT NULL | Free text but populated from 14 O&G suggestions in `CostLineDialog` (Drilling / Casing / Mud / Cement / Logging / Completion / Permits / etc.) |
| description | TEXT NOT NULL | |
| expected_amount | REAL NOT NULL | AFE budget for this line, default 0 |
| actual_amount | REAL | Nullable until something is paid |
| vendor | TEXT | |
| invoice_number | TEXT | |
| paid_at | TEXT | Set when status flips to `paid` |
| notes | TEXT | |
| status | TEXT NOT NULL | default `planned`. Other values: `committed` / `invoiced` / `paid` |
| item_order | INTEGER NOT NULL | default 0 |
| created_at, updated_at | TEXT | |

**Index:** `idx_cost_lines_project`

### `cost_attachments`

Receipt files (PDF / image / anything) attached to cost lines.

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | |
| cost_line_item_id | TEXT FK | `→ cost_line_items(id) ON DELETE CASCADE` |
| file_name | TEXT NOT NULL | |
| storage_path | TEXT NOT NULL | Absolute path under `projects/<uuid>/costs/<line_id>/` |
| file_sha256 | TEXT | |
| byte_size | INTEGER | |
| mime_type | TEXT | Guessed via `mimetypes.guess_type` |
| uploaded_at | TEXT | |

**Index:** `idx_cost_attachments_line`

## On-disk file layout

`app_paths.app_data_root()` = `%APPDATA%\WellSign\` (override with `WELLSIGN_DATA_DIR` env var).

```
%APPDATA%\WellSign\
├── wellsign.db                       # SQLite — encrypted PII columns
├── templates/
│   └── documents/
│       └── <template_id>.pdf         # Global template library
└── projects/
    └── <project_uuid>/
        ├── templates/                # Per-project template snapshots
        │   └── <template_id>.pdf
        ├── exports/                  # Operator exports (CSV, etc.)
        ├── investors/
        │   └── <investor_uuid>/
        │       ├── sent/             # Generated PDFs sent to the investor
        │       ├── received/         # Signed/notarized PDFs the operator drops in
        │       └── attachments/      # Arbitrary uploads (W-9, ID, etc.)
        └── costs/
            └── <cost_line_id>/       # AFE receipt attachments
                └── <receipt_filename>
```

The DB only ever stores **relative** paths under `projects/<uuid>/` for investor docs. `cost_attachments.storage_path` is currently absolute (set by `attach_receipt()` which uses `cost_attachments_dir()`).

## Precision rules

- WI% stored as `REAL` fraction. SQLite `REAL` is IEEE 754 double precision (~15–16 significant digits), enough for 8 decimal places.
- Per-investor amount calculation: `llg_amount = round(wi_percent × total_llg_cost, 2)`, same for DHC.
- Sum-of-amounts validation: ± $0.10 against the project totals; flag larger discrepancies. Investors tab does this check live and colors the summary line accordingly.

## Open gaps

Listed here so they're discoverable from the data-model doc — also tracked in [roadmap.md](roadmap.md).

1. **Migration runner is dumb.** `schema.sql` uses `CREATE TABLE IF NOT EXISTS` so new columns added to existing tables (`projects.workflow_id`, `phase`, `phase_entered_at`) are NOT applied to returning installs. `insert_project()` writes `workflow_id` directly and would crash on a stale DB. Fix: add `ALTER TABLE` blocks inside try/except, or move to a versioned migrations folder. Bump `db/migrate.py:CURRENT_VERSION` when this changes.
2. **Real `insert_investor()` doesn't create an `investor_stage_runs` row.** Only the demo seed does. Until this is wired, traffic lights only work for the demo project.
3. **Exit conditions aren't enforced.** No code checks `exit_condition` and advances an investor's stage run when the condition is met (e.g., when all docs are signed, the Documentation stage should auto-complete).
4. **Reminder scheduler missing.** `stage_email_templates.wait_days` is captured but no background loop fires reminders when `entered_at + wait_days < now()`.
5. **Audit log writes missing.** Schema + triggers exist but no code calls into the table.
6. **Send events not written.** `send_events` table exists but Outlook send isn't built yet.
7. **Phase ↔ workflow stage are not coupled.** When a stage exits, the project's phase doesn't auto-advance. Operator manually clicks Advance even when conditions are met.
8. **Surplus / supplemental cash call calculator** referenced from `costs_tab.py`'s subtitle but not implemented. When Drilling phase closes and actuals are in, the operator should see "you collected $X, spent $Y, surplus = $Z" or "supplemental needed = $Z".

## Schema evolution

When the schema needs to change:

1. Update `db/schema.sql` with the new tables/columns
2. Bump `db/migrate.py:CURRENT_VERSION`
3. Add an `ALTER TABLE` block (the current migrate.py is intentionally dumb — single idempotent script. The first non-idempotent change will force the switch to a versioned migrations folder)
4. Update this doc and `paloma-packet.md` if the change is user-visible

For the v2 schema additions surfaced by the document review (BCP/ACP/NRI split, multi-well investors, supplemental cash call rounds, Reg D / accreditation tables, notaries, etc.) see [roadmap.md](roadmap.md).
