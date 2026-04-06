# WellSign — Architecture

> **Status:** v0.0.1 scaffold. The skeleton runs (`wellsign` entry point), the schema is live, the license verifier is wired up, the demo data seeds, and most tabs are placeholders pending feature work. See [roadmap.md](roadmap.md) for what's still ahead.

## Doc index

- **architecture.md** — this file: tech stack, module map, UI shape, key flows
- [data-model.md](data-model.md) — SQLite schema as it exists in `src/wellsign/db/schema.sql`
- [paloma-packet.md](paloma-packet.md) — the 7-document Paloma investor packet (business reference)
- [security.md](security.md) — PII encryption, license model, audit log
- [licenses.md](licenses.md) — runtime + dev dependency license audit
- [regd-compliance.md](regd-compliance.md) — securities / Reg D considerations
- [roadmap.md](roadmap.md) — v2 / future items the v1 scope deliberately defers

## What we are building

WellSign is a Windows desktop app that automates the investor document workflow for small oil & gas operators. For each well project, the operator must produce ~7 personalized legal documents per investor, email packets, track returns, and reconcile payments to two payees (Decker for LLG, Paloma for DHC). WellSign collapses that into one PySide6 application with a local SQLite database — single-operator install, no cloud, no portal.

## Tech stack (actual `pyproject.toml`)

| Layer | Choice | Notes |
|---|---|---|
| UI | PySide6 (Qt 6) | Single QMainWindow, splitter, navigator + page stack |
| Database | SQLite via stdlib `sqlite3` | `%APPDATA%\WellSign\wellsign.db`, WAL journal mode, foreign keys ON |
| Path management | `platformdirs` | `WELLSIGN_DATA_DIR` env override for tests |
| Encryption | `cryptography` (AES-256-GCM) | Column-level PII via `util/crypto.py` |
| Master key storage | `keyring` | Windows Credential Manager — service `wellsign.pii`, user `master_key` |
| License verify | `cryptography` (RSA-3072 PSS over canonical JSON) | Bundled public key in `wellsign/resources/license_public_key.pem` |
| Excel import | `openpyxl` | Investor list import |
| PDF read | `pypdf` | Form-field discovery for template mapping |
| PDF write/sign | `pdfrw`, `reportlab` | Stamping + page layout (TODO) |
| Email | `pywin32` Outlook COM | Sends from operator's own Outlook profile (TODO) |
| Distribution | PyInstaller (`wellsign.spec`) | One-folder mode for LGPL compliance |

**Clean-room note:** PySide6 desktop apps for oil & gas IS Jeremy's day job at SeisWare. **No** patterns, helpers, styling, or layout copied from `D:\Repos\sw-*` or `seisware-*`. Public Qt tutorials only.

## Module layout (actual on disk)

```
src/wellsign/
├── __init__.py
├── main.py                 # Entry point — QApplication, run_migrations, seed_if_empty, MainWindow
├── app_paths.py            # platformdirs paths: %APPDATA%/WellSign/{wellsign.db, projects/, templates/}
├── db/
│   ├── schema.sql          # SOURCE OF TRUTH for the data model
│   ├── migrate.py          # Idempotent schema apply on every startup, schema_version stamping
│   ├── seed.py             # Demo data — 1 project, 5 investors, 5 doc templates, 2 email templates
│   ├── projects.py         # ProjectRow + list/get/insert
│   ├── investors.py        # InvestorRow + list/insert (NEVER auto-decrypts PII)
│   ├── templates.py        # DocTemplateRow + EmailTemplateRow
│   └── stages.py           # Per-project workflow stage computation (drives navigator color dot)
├── license_/
│   ├── verify.py           # RSA-PSS verify against bundled public key, returns LicensePayload
│   └── issue.py            # Keypair gen + license minting (out-of-band; NEVER imported by the app)
├── util/
│   ├── crypto.py           # encrypt_pii / decrypt_pii / mask_pii — AES-256-GCM
│   └── storage.py          # Per-investor file management (sent/received/attachments)
├── pdf_/
│   └── fields.py           # pypdf-based form-field reader for template mapping
├── email_/                 # Outlook COM wrapper (TODO)
├── models/                 # Reserved for cross-cutting dataclasses
├── resources/
│   ├── license_public_key.pem    # Bundled — must be in git (gitignore exception added)
│   └── style.qss                  # Qt stylesheet
└── ui/
    ├── main_window.py             # Toolbar + splitter + status bar
    ├── navigator.py               # Left-side tree
    ├── pages/
    │   ├── dashboard_page.py      # All-projects table
    │   ├── project_workspace.py   # Per-project tab container
    │   ├── doc_templates_page.py
    │   └── email_templates_page.py
    ├── tabs/                      # Tabs inside ProjectWorkspace
    │   ├── _base.py               # PlaceholderTab — most tabs subclass this for now
    │   ├── project_setup_tab.py
    │   ├── investors_tab.py
    │   ├── documents_tab.py
    │   ├── send_tab.py
    │   ├── status_tab.py
    │   └── burndown_tab.py
    └── dialogs/
        ├── new_project_dialog.py
        ├── new_doc_template_dialog.py
        └── new_email_template_dialog.py

scripts/mint_license.py             # CLI for issuing license keys (Jeremy/Parker only)
secrets/                            # Private key + issued licenses (gitignored entirely)
tests/test_crypto.py                # Round-trip encrypt/decrypt
tests/test_smoke_boot.py            # App boots without crashing
wellsign.spec                       # PyInstaller config
```

## UI shape (actual)

The main window is **NOT** a top-level QTabWidget. It's a left navigator + right page stack:

```
+----------------------------------------------------------------+
| TopBar:  [active project name]              [+ New Project]    |
+--------------+-------------------------------------------------+
|              |                                                 |
| ▼ Projects   |   Right pane shows ONE of:                      |
|     ● Proj A |     - DashboardPage    (Projects root selected) |
|     ● Proj B |     - ProjectWorkspace (a project selected)     |
|              |     - DocTemplatesPage (Templates > Documents)  |
| ▼ Templates  |     - EmailTemplatesPage (Templates > Emails)   |
|     Document |                                                 |
|     Email    |                                                 |
|              |                                                 |
+--------------+-------------------------------------------------+
| DB: %APPDATA%/WellSign/wellsign.db                              |
+----------------------------------------------------------------+
```

`MainWindow._on_nav_selection()` swaps the right pane based on `NavSelection.kind`. `NavigatorTree.refresh_projects()` rebuilds the project list with stage-colored dots.

### ProjectWorkspace tabs

The right pane when a project is selected is a `QTabWidget` with 6 tabs:

| Tab | State | Purpose |
|---|---|---|
| Project Setup | Stub | Edit prospect / well / county / dates / total LLG / total DHC |
| Investors | Stub | Excel import + manual add/edit, WI% sum validation |
| Documents | Placeholder | Generate filled packets, preview, regenerate |
| Send | Placeholder | Pick investors, preview Outlook draft, fire |
| Status | Placeholder | Per-investor doc grid + colored statuses |
| Burndown | Placeholder | Completion-over-time chart vs. close deadline |

Most tab classes currently inherit from `tabs/_base.py:PlaceholderTab` so the chrome works while feature work is in flight.

### DashboardPage

7-column table: **Project · Well · Region · Customer · Status · Investors · Created**. Has a `+ New Project` button that bubbles `newProjectRequested` up to `MainWindow`. `refresh()` re-queries `list_projects()` + `count_investors()`.

### Stages

`db/stages.py:compute_stage(project_id)` returns the current workflow stage for a project (referenced from `ui/navigator.py`). The navigator paints each project's dot in the stage color and shows the stage label in the tooltip. **Document the stage definitions here when feature work locks them down.**

## Key flows

### App start
1. `main.py` → `QApplication.setStyle("Fusion")`, loads `style.qss` from `wellsign.resources`
2. `run_migrations()` — applies `schema.sql` idempotently, stamps `schema_version`
3. `seed_if_empty()` — only seeds demo data if `projects` table is empty
4. Shows `MainWindow` (1380×860, min 1100×700)

### Create project
1. Operator clicks `+ New Project` (Ctrl+N) → `NewProjectDialog`
2. Operator pastes a `.wslicense` file path
3. `license_/verify.py:verify_license_file()` parses the envelope, verifies RSA-PSS signature against the bundled public key, parses `issued_at`/`expires_at`, returns a `LicensePayload`
4. SHA-256 of canonical payload becomes `license_key_hash` stored on the new project row
5. `db/projects.py:insert_project()` writes the row + `app_paths.project_dir(uuid)` creates the on-disk folder
6. Navigator refreshes, dashboard refreshes

### License model
- One license = one project, baked into the signed payload: `{key_id, customer, project_name, issued_at, expires_at}`
- RSA-3072 with PSS padding (MGF1+SHA-256, MAX salt length), canonical JSON (`sort_keys=True, separators=(",", ":")`)
- Public key shipped at `wellsign/resources/license_public_key.pem`, loaded via `importlib.resources`
- Private key generated by `scripts/mint_license.py generate-keypair --out secrets/`, **NEVER in git**
- License files (`.wslicense`) issued by `scripts/mint_license.py mint --customer ... --project ...`
- See [security.md](security.md) for the threat model and key handling rules
- See [roadmap.md](roadmap.md) for the annual-seat license alternative if the per-project model proves to be hostile UX

### PII encryption
- `util/crypto.py:encrypt_pii(plaintext)` → `iv_hex:tag_hex:ct_hex` string, stored in `_enc` columns
- Master key generated on first call via `secrets.token_bytes(32)`, stashed in keyring service `wellsign.pii` user `master_key`
- `WELLSIGN_PII_KEY_HEX` env override for tests/CI ONLY — never a production code path
- `decrypt_pii` is opt-in: callers must explicitly request a single field at the moment of display
- `mask_pii(value)` returns `••••<last4>` for UI rendering

### File storage
`util/storage.py` is the single point of contact. Helpers:
- `store_sent_document(project, investor, doc_type, src)` → `investors/<uuid>/sent/<doc_type>_<timestamp>.pdf`
- `store_received_document(project, investor, doc_type, src)` → `investors/<uuid>/received/signed_<doc_type>_<timestamp>.pdf`
- `store_attachment(project, investor, src)` → `investors/<uuid>/attachments/<safe_filename>`
- `store_project_template(project, template_id, src)` → `templates/<safe_id>.pdf`
- `store_export(project, filename, src)` → `exports/<safe_filename>`

The DB only ever stores **relative** paths under `projects/<uuid>/`. Filenames are run through `_safe()` to strip anything not in `[A-Za-z0-9._-]`. SHA-256 helpers exist for integrity checks.

## Out of scope for v1

These are explicitly NOT in v1. See [roadmap.md](roadmap.md) for what we'd add later:

- E-signature integration (DocuSign / PandaDoc) — schema fields exist but no API client
- Investor web portal — not now, not later
- Multi-tenant SaaS — single-operator install only
- Reg D / Form D / blue sky filing automation
- Multi-well investor history (investor as a top-level entity instead of per-project)
- BCP / ACP / NRI working interest split
- Cash call line items, supplemental AFE versioning
- Wire reconciliation / bank statement import
- K-1 / CPA year-end export
- Word template support (`docxtpl`) — currently we read PDF AcroForm fields only
- Online notarization (RON) integration
- SMS reminders, anything Twilio
- Server-side anything

## Open architectural questions

- **License model:** per-project keys are hostile UX for operators who run 10+ wells/year. See [roadmap.md](roadmap.md).
- **Templates:** real Paloma templates are .docx (Word), not PDF AcroForms. See [paloma-packet.md](paloma-packet.md) and [roadmap.md](roadmap.md) for the docxtpl plan.
- **Stages:** what are the canonical stages? `db/stages.py` is the source of truth — when feature work happens, document them here.
