# WellSign — Data Model

> **Source of truth:** `src/wellsign/db/schema.sql`. This file is a human-readable description; if it ever drifts from `schema.sql`, the SQL wins.
>
> Schema is applied idempotently on every startup by `db/migrate.py:run_migrations()`. Demo data is seeded by `db/seed.py:seed_if_empty()` on first run only.

## Conventions

- All IDs are UUID v4 strings stored as `TEXT` (`str(uuid.uuid4())`)
- Timestamps are ISO-8601 `TEXT` (`datetime('now')` default in SQL, `datetime.utcnow().isoformat(timespec='seconds')` in Python)
- Booleans are `INTEGER 0/1` (SQLite has no native bool)
- All PII columns end in `_enc` and store AES-256-GCM ciphertext as `iv_hex:tag_hex:ct_hex` (see `util/crypto.py`)
- Foreign key cascades: `ON DELETE CASCADE` on every project-owned child, so dropping a project drops everything beneath it
- `PRAGMA foreign_keys = ON` set in `db/migrate.py:connect()`
- `PRAGMA journal_mode = WAL` set in `schema.sql`

## Entity overview

```
projects ──< investors ──< investor_documents
    │             │              │
    │             │              └── (also references external_url for hosted-signing services)
    │             │
    │             └──< payments       (one row per LLG/DHC expectation)
    │
    └──< project_templates ── document_templates  (per-project snapshots of the global library)

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
| created_at, updated_at | TEXT | |

**Index:** `idx_projects_status` on `(status)`

> **License model:** one license = one project, signed offline by `scripts/mint_license.py`. The hash is stored on the row to detect tampering or reuse. The per-project license model is locked into the schema; see [roadmap.md](roadmap.md) for the annual-seat alternative.

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
| llg_amount | REAL | `wi_percent * project.total_llg_cost`, computed at insert/update |
| dhc_amount | REAL | `wi_percent * project.total_dhc_cost` |
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

> **Investors are per-project.** Same human investor in 5 wells = 5 rows. See [roadmap.md](roadmap.md) for the multi-well investor refactor proposal.

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

Demo seed creates two templates: "Initial Investor Invitation" and "Reminder — 7 Days Before Close". See `db/seed.py` for the merge variable conventions: `{{prospect_name}}`, `{{well_name}}`, `{{investor_first_name}}`, `{{investor_wi_percent_display}}`, `{{llg_amount}}`, `{{dhc_amount}}`, `{{close_deadline}}`, `{{operator_name}}`, `{{outstanding_items}}`.

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

## On-disk file layout

`app_paths.app_data_root()` = `%APPDATA%\WellSign\` (override with `WELLSIGN_DATA_DIR` env var).

```
%APPDATA%\WellSign\
├── wellsign.db                       # SQLite — encrypted PII columns
├── templates/
│   └── documents/
│       └── <template_id>.pdf         # Global template library
├── projects/
│   └── <project_uuid>/
│       ├── templates/                # Per-project template snapshots
│       │   └── <template_id>.pdf
│       ├── exports/                  # Operator exports (CSV, etc.)
│       └── investors/
│           └── <investor_uuid>/
│               ├── sent/             # Generated PDFs sent to the investor
│               │   └── <doc_type>_<timestamp>.pdf
│               ├── received/         # Signed/notarized PDFs the operator drops in
│               │   └── signed_<doc_type>_<timestamp>.pdf
│               └── attachments/      # Arbitrary uploads (W-9, ID, etc.)
│                   └── <safe_filename>
```

The DB only ever stores **relative** paths under `projects/<uuid>/`. `util/storage.py` is the single point of contact for writing files; it produces the relative paths and SHA-256 hashes.

## Precision rules

- WI% stored as `REAL` fraction. SQLite `REAL` is IEEE 754 double precision (~15–16 significant digits), enough for 8 decimal places.
- Per-investor amount calculation: `llg_amount = round(wi_percent * total_llg_cost, 2)`, same for DHC.
- Sum-of-amounts validation: ± $0.10 against the project totals; flag larger discrepancies.

## Schema evolution

When the schema needs to change:

1. Update `db/schema.sql` with the new tables/columns
2. Bump `db/migrate.py:CURRENT_VERSION`
3. Add an `ALTER TABLE` block (the current migrate.py is intentionally dumb — schema is applied as a single idempotent script. When the first non-idempotent change happens, swap it for a versioned migrations folder)
4. Update this doc and `paloma-packet.md` if the change is user-visible

For the v2 schema additions surfaced by the document review (BCP/ACP/NRI split, line items, supplemental AFEs, Reg D, multi-well investors, etc.) see [roadmap.md](roadmap.md).
