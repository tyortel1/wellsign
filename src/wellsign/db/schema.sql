-- WellSign SQLite schema
-- Hierarchy: projects -> investors -> investor_documents
-- All on-disk file storage is referenced by relative paths under
-- %APPDATA%/WellSign/projects/<project_uuid>/...
-- PII columns ending in _enc store AES-256-GCM ciphertext (see util/crypto.py).

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ---------------------------------------------------------------------------
-- Schema version table — updated by db/migrate.py
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- Projects (one row = one well prospect = one license)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    id                  TEXT PRIMARY KEY,                  -- UUID
    name                TEXT NOT NULL,                     -- display name e.g. "Highlander Prospect"
    prospect_name       TEXT,
    well_name           TEXT,
    operator_llc        TEXT,
    county              TEXT,
    state               TEXT,
    agreement_date      TEXT,                              -- ISO date
    close_deadline      TEXT,                              -- ISO date
    total_llg_cost      REAL,                              -- total cost for C-1 (Decker)
    total_dhc_cost      REAL,                              -- total cost for C-2 (Paloma)
    status              TEXT NOT NULL DEFAULT 'draft',     -- draft | active | closed | archived
    is_test             INTEGER NOT NULL DEFAULT 0,

    -- License binding (see license_/verify.py)
    license_key_hash    TEXT NOT NULL,                     -- SHA-256 of the issued key file contents
    license_customer    TEXT,
    license_issued_at   TEXT,
    license_expires_at  TEXT,
    license_key_id      TEXT,

    -- Storage
    storage_path        TEXT NOT NULL,                     -- relative to projects_root, usually = id

    -- Workflow assignment (which workflow this project runs against)
    workflow_id         TEXT,                              -- nullable for legacy / unassigned

    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

-- ---------------------------------------------------------------------------
-- Investors (the "users" inside a project)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS investors (
    id                  TEXT PRIMARY KEY,                  -- UUID
    project_id          TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    first_name          TEXT,
    last_name           TEXT,
    entity_name         TEXT,                              -- LLC / trust / IRA name if applicable
    title               TEXT,                              -- signing title
    email               TEXT,
    phone               TEXT,

    address_line1       TEXT,
    address_line2       TEXT,
    city                TEXT,
    state               TEXT,
    zip                 TEXT,

    wi_percent          REAL NOT NULL DEFAULT 0,           -- store as fraction e.g. 0.01000000 = 1%
    llg_amount          REAL,                              -- calculated: wi_percent * project.total_llg_cost
    dhc_amount          REAL,                              -- calculated: wi_percent * project.total_dhc_cost

    payment_preference  TEXT,                              -- 'wire' | 'check'

    -- Encrypted PII (AES-256-GCM, hex iv:tag:ct)
    ssn_enc             TEXT,
    ein_enc             TEXT,
    bank_name_enc       TEXT,
    bank_routing_enc    TEXT,
    bank_account_enc    TEXT,

    portal_status       TEXT NOT NULL DEFAULT 'not_sent',  -- not_sent | sent | partial | complete
    info_form_complete  INTEGER NOT NULL DEFAULT 0,
    consent_given       INTEGER NOT NULL DEFAULT 0,
    consent_given_at    TEXT,

    notes               TEXT,

    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_investors_project ON investors(project_id);
CREATE INDEX IF NOT EXISTS idx_investors_status ON investors(portal_status);

-- ---------------------------------------------------------------------------
-- Document templates (PDFs the operator builds once and reuses across projects)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_templates (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,                     -- "Paloma JOA", "Decker C-1", etc.
    doc_type            TEXT NOT NULL,                     -- 'joa' | 'pa' | 'cash_call_c1' | 'cash_call_c2'
                                                           --  | 'info_sheet' | 'w9' | 'wiring' | 'other'
    storage_path        TEXT NOT NULL,                     -- path to the blank PDF (under app_data_root/templates/)
    field_mapping       TEXT,                              -- JSON: { "pdf_field_name": "merge_variable_name" }
    page_size           TEXT,                              -- 'letter' | 'legal'
    notary_required     INTEGER NOT NULL DEFAULT 0,
    is_global           INTEGER NOT NULL DEFAULT 1,        -- 1 = available to all projects
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Per-project copy / picked templates
CREATE TABLE IF NOT EXISTS project_templates (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    template_id         TEXT NOT NULL REFERENCES document_templates(id),
    storage_path        TEXT NOT NULL,                     -- snapshot copy under projects/<uuid>/templates/
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_project_templates_project ON project_templates(project_id);

-- ---------------------------------------------------------------------------
-- Email templates (the message body / subject lines the operator reuses)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_templates (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    purpose             TEXT NOT NULL,                     -- 'invitation' | 'reminder' | 'thank_you' | 'custom'
    subject             TEXT NOT NULL,                     -- supports {{merge_variables}}
    body_html           TEXT NOT NULL,                     -- supports {{merge_variables}}
    is_global           INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- Investor documents — every PDF that exists for a given investor on a project
-- (sent packets, signed returns, attachments, anything)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS investor_documents (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    investor_id         TEXT NOT NULL REFERENCES investors(id) ON DELETE CASCADE,

    doc_type            TEXT NOT NULL,                     -- mirrors document_templates.doc_type or 'attachment'
    direction           TEXT NOT NULL,                     -- 'sent' | 'received' | 'attachment'
    source              TEXT NOT NULL DEFAULT 'app',       -- 'app' | 'manual_upload' | 'email_import' | 'docusign' | 'pandadoc'

    storage_path        TEXT,                              -- relative to project root; null if external_url is set
    external_url        TEXT,                              -- set if the signed doc lives in a 3rd-party signing service
    file_sha256         TEXT,                              -- integrity check
    byte_size           INTEGER,
    mime_type           TEXT,

    status              TEXT NOT NULL DEFAULT 'pending',   -- pending | generated | sent | viewed | signed | notarized | rejected
    sent_at             TEXT,
    received_at         TEXT,
    signed_at           TEXT,

    metadata            TEXT,                              -- JSON for anything extra; never PII
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_invdocs_project ON investor_documents(project_id);
CREATE INDEX IF NOT EXISTS idx_invdocs_investor ON investor_documents(investor_id);
CREATE INDEX IF NOT EXISTS idx_invdocs_status ON investor_documents(status);

-- ---------------------------------------------------------------------------
-- Payments — track LLG (to Decker) and DHC (to Paloma) per investor
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payments (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    investor_id         TEXT NOT NULL REFERENCES investors(id) ON DELETE CASCADE,

    payment_type        TEXT NOT NULL,                     -- 'llg' | 'dhc'
    payee               TEXT NOT NULL,                     -- 'decker' | 'paloma'
    expected_amount     REAL NOT NULL,
    received_amount     REAL,
    method              TEXT,                              -- 'wire' | 'check'
    received_at         TEXT,
    reference_number    TEXT,                              -- check #, wire confirmation, etc.
    notes               TEXT,

    status              TEXT NOT NULL DEFAULT 'expected',  -- expected | partial | received | overdue
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_payments_project ON payments(project_id);
CREATE INDEX IF NOT EXISTS idx_payments_investor ON payments(investor_id);

-- ---------------------------------------------------------------------------
-- Send events — one row per Outlook send so we can show a timeline
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS send_events (
    id                  TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    investor_id         TEXT NOT NULL REFERENCES investors(id) ON DELETE CASCADE,
    email_template_id   TEXT REFERENCES email_templates(id),
    subject             TEXT,
    sent_at             TEXT NOT NULL DEFAULT (datetime('now')),
    attached_doc_ids    TEXT,                              -- JSON array of investor_documents.id
    success             INTEGER NOT NULL DEFAULT 1,
    error_message       TEXT
);

CREATE INDEX IF NOT EXISTS idx_send_events_investor ON send_events(investor_id);

-- ---------------------------------------------------------------------------
-- Append-only audit log
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at         TEXT NOT NULL DEFAULT (datetime('now')),
    actor               TEXT,                              -- OS username
    project_id          TEXT,
    investor_id         TEXT,
    action              TEXT NOT NULL,                     -- 'project_created', 'doc_sent', 'doc_received', etc.
    target_type         TEXT,
    target_id           TEXT,
    metadata            TEXT                               -- JSON; never PII
);

CREATE INDEX IF NOT EXISTS idx_audit_project ON audit_log(project_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);

-- Block updates and deletes on audit_log via triggers (append-only).
CREATE TRIGGER IF NOT EXISTS audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(FAIL, 'audit_log is append-only');
END;

CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(FAIL, 'audit_log is append-only');
END;

-- ---------------------------------------------------------------------------
-- Workflows — reusable pipeline definitions built from templates
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflows (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT,
    is_global       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workflow_stages (
    id              TEXT PRIMARY KEY,
    workflow_id     TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    stage_order     INTEGER NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    duration_days   INTEGER,                  -- relative SLA from entered_at
    exit_condition  TEXT NOT NULL DEFAULT 'manual',
                                              -- 'manual' | 'investor_committed'
                                              -- | 'all_docs_signed' | 'llg_paid'
                                              -- | 'dhc_paid' | 'llg_and_dhc_paid'
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_workflow_stages_workflow ON workflow_stages(workflow_id);

CREATE TABLE IF NOT EXISTS stage_doc_templates (
    id                TEXT PRIMARY KEY,
    stage_id          TEXT NOT NULL REFERENCES workflow_stages(id) ON DELETE CASCADE,
    doc_template_id   TEXT NOT NULL REFERENCES document_templates(id) ON DELETE CASCADE,
    item_order        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_stage_doc_templates_stage ON stage_doc_templates(stage_id);

CREATE TABLE IF NOT EXISTS stage_email_templates (
    id                TEXT PRIMARY KEY,
    stage_id          TEXT NOT NULL REFERENCES workflow_stages(id) ON DELETE CASCADE,
    email_template_id TEXT NOT NULL REFERENCES email_templates(id) ON DELETE CASCADE,
    item_order        INTEGER NOT NULL DEFAULT 0,
    wait_days         INTEGER NOT NULL DEFAULT 0    -- delay from stage entry before this email is due
);
CREATE INDEX IF NOT EXISTS idx_stage_email_templates_stage ON stage_email_templates(stage_id);

-- Per-investor stage runtime — tracks who is in which stage right now and when they entered
CREATE TABLE IF NOT EXISTS investor_stage_runs (
    id              TEXT PRIMARY KEY,
    investor_id     TEXT NOT NULL REFERENCES investors(id) ON DELETE CASCADE,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    stage_id        TEXT NOT NULL REFERENCES workflow_stages(id) ON DELETE CASCADE,
    entered_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT,
    status          TEXT NOT NULL DEFAULT 'in_progress',  -- in_progress | completed | skipped | blocked
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_isr_investor ON investor_stage_runs(investor_id);
CREATE INDEX IF NOT EXISTS idx_isr_project  ON investor_stage_runs(project_id);
CREATE INDEX IF NOT EXISTS idx_isr_status   ON investor_stage_runs(status);
