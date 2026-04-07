# WellSign — Architecture

> **Status:** v0.0.1 scaffold. The skeleton runs (`wellsign` entry point), the schema is live, the license verifier and PII crypto are wired up, and the **Phases / Workflows / Costs** subsystems are functional. Demo data seeds with realistic state. 4 of 7 ProjectWorkspace tabs are still placeholders pending feature work. See [roadmap.md](roadmap.md) for what's still ahead.

## Doc index

- **architecture.md** — this file: tech stack, module map, UI shape, key flows
- [data-model.md](data-model.md) — every table in `src/wellsign/db/schema.sql`
- [paloma-packet.md](paloma-packet.md) — the 7-document Paloma investor packet (business reference)
- [security.md](security.md) — PII encryption, license model, audit log
- [licenses.md](licenses.md) — runtime + dev dependency license audit
- [regd-compliance.md](regd-compliance.md) — securities / Reg D considerations
- [roadmap.md](roadmap.md) — v2 / future items the v1 scope deliberately defers

## What we are building

WellSign is a Windows desktop app that automates the investor document workflow for small oil & gas operators. For each well project, the operator must produce ~7 personalized legal documents per investor, email packets, track returns, reconcile payments to two payees (Decker for LLG, Paloma for DHC), and track AFE costs through drilling. WellSign collapses that into one PySide6 application with a local SQLite database — single-operator install, no cloud, no portal.

## Tech stack (actual `pyproject.toml`)

| Layer | Choice | Notes |
|---|---|---|
| UI | PySide6 (Qt 6) | Single QMainWindow, splitter, navigator + page stack |
| Database | SQLite via stdlib `sqlite3` | `%APPDATA%\WellSign\wellsign.db`, WAL journal mode, foreign keys ON |
| Path management | `platformdirs` | `WELLSIGN_DATA_DIR` env override for tests |
| Encryption | `cryptography` (AES-256-GCM) | Column-level PII via `util/crypto.py` |
| Master key storage | `keyring` | Windows Credential Manager — service `wellsign.pii`, user `master_key` |
| License verify | `cryptography` (RSA-3072 PSS over canonical JSON) | Bundled public key in `wellsign/resources/license_public_key.pem` |
| Excel import | `openpyxl` | Investor list import (TODO — dep is in, code isn't) |
| PDF read | `pypdf` | Form-field discovery for template mapping |
| PDF write/sign | `pdfrw`, `reportlab` | Stamping + page layout (TODO) |
| Email | `pywin32` Outlook COM | Sends from operator's own Outlook profile (TODO) |
| Distribution | PyInstaller (`wellsign.spec`) | One-folder mode for LGPL compliance |

**Clean-room note:** PySide6 desktop apps for oil & gas IS Jeremy's day job at SeisWare. **No** patterns, helpers, styling, or layout copied from `D:\Repos\sw-*` or `seisware-*`. Public Qt tutorials only.

## Three concept layers

WellSign has three orthogonal concept layers the operator interacts with:

| Layer | Granularity | Driven by | Where it lives |
|---|---|---|---|
| **Phases** | Per project | Operator manually advances | `db/phases.py` enum + `projects.phase` column + phase banner in `ProjectWorkspace` |
| **Workflows + Stages** | Per investor inside a project | Time + exit conditions (auto-advance is TODO) | `db/workflows.py` + 5 workflow tables + `WorkflowsPage` + traffic-light system |
| **Costs (AFE)** | Per project | Operator entries during Drilling phase | `db/costs.py` + `cost_line_items` / `cost_attachments` tables + `CostsTab` + `CostLineDialog` |

**Phases** are the operator's mental model — "where is this deal at right now?" 7 preset states (Prospect Generation → Outreach → Subscription → Cash Call → Drilling → P&A / Completion). Manually advanced via an "Advance →" button on the project's phase banner.

**Workflows** sit one level down — they automate the per-investor side of the active phase. A workflow has ordered stages, each stage attaches docs and emails (with `wait_days` for follow-ups) and an exit condition. Investors are tracked individually through `investor_stage_runs` with SLA timing → traffic-light status (🟢🟡🔴⚪).

**Costs** are the AFE budget vs actuals tracker. Per-project line items with vendor, status (planned/committed/invoiced/paid), receipt attachments, variance coloring, totals row.

## Module layout (actual on disk)

```
src/wellsign/
├── __init__.py
├── main.py                 # Entry point — QApplication, run_migrations, seed_if_empty, MainWindow
├── app_paths.py            # platformdirs paths: wellsign.db, projects/, templates/, costs/
├── db/
│   ├── schema.sql          # SOURCE OF TRUTH for the data model
│   ├── migrate.py          # Idempotent schema apply on every startup, schema_version stamping
│   ├── seed.py             # Demo: 6 doc templates, 9 email templates, default workflow, 1 project, 5 investors with stage runs, 10 cost lines
│   ├── projects.py         # ProjectRow + list/get/insert + set_phase
│   ├── investors.py        # InvestorRow + list/insert (NEVER auto-decrypts PII)
│   ├── templates.py        # DocTemplateRow + EmailTemplateRow CRUD
│   ├── workflows.py        # Workflow / Stage / StageRun CRUD + traffic-light computation
│   ├── phases.py           # 7-state Phase enum + colors + next_phase_options (operator lifecycle)
│   └── costs.py            # CostLineRow / CostAttachment CRUD + totals_for + receipt attachment
├── license_/
│   ├── verify.py           # RSA-PSS verify against bundled public key, returns LicensePayload
│   └── issue.py            # Keypair gen + license minting (out-of-band; NEVER imported by the app)
├── util/
│   ├── crypto.py           # encrypt_pii / decrypt_pii / mask_pii — AES-256-GCM
│   └── storage.py          # Per-investor file management (sent/received/attachments)
├── pdf_/
│   └── fields.py           # pypdf-based form-field reader for template mapping
├── email_/                 # Outlook COM wrapper (TODO — currently empty docstring only)
├── models/                 # Reserved for cross-cutting dataclasses
├── resources/
│   ├── license_public_key.pem    # Bundled — gitignore exception, must ship with app
│   └── style.qss                  # Qt stylesheet
└── ui/
    ├── main_window.py             # Toolbar + splitter + status bar
    ├── navigator.py               # Left tree (Projects + Templates + Workflows roots)
    ├── pages/
    │   ├── dashboard_page.py      # All-projects table
    │   ├── project_workspace.py   # Phase banner + 7-tab QTabWidget
    │   ├── doc_templates_page.py
    │   ├── email_templates_page.py
    │   └── workflows_page.py      # Drag-drop reorderable stage cards
    ├── tabs/                      # Tabs inside ProjectWorkspace
    │   ├── _base.py               # PlaceholderTab — Documents/Send/Status/Burndown still subclass this
    │   ├── project_setup_tab.py   # Read-only summary + phase banner counts (editable form TODO)
    │   ├── investors_tab.py       # Real table with traffic lights + WI sum validation (+Add / Import wiring TODO)
    │   ├── documents_tab.py       # Placeholder
    │   ├── send_tab.py            # Placeholder
    │   ├── status_tab.py          # Placeholder
    │   ├── costs_tab.py           # Real AFE budget table with variance coloring + receipt attachments
    │   └── burndown_tab.py        # Placeholder
    └── dialogs/
        ├── new_project_dialog.py       # License-gated, picks workflow at create time
        ├── new_doc_template_dialog.py  # PDF browse + form-field detection + global library
        ├── new_email_template_dialog.py
        ├── template_picker_dialog.py   # Multi-select picker for the workflows builder
        └── cost_line_dialog.py         # Add/edit a single AFE cost line

scripts/mint_license.py             # CLI for issuing license keys (Jeremy/Parker only)
secrets/                            # Private key + issued licenses (gitignored entirely)
tests/test_crypto.py                # Round-trip encrypt/decrypt
tests/test_smoke_boot.py            # App boots without crashing, expects 5 pages in stack
wellsign.spec                       # PyInstaller config
```

## UI shape (actual)

```
+---------------------------------------------------------------------+
| TopBar:  [active project name]                  [+ New Project]    |
+--------------+------------------------------------------------------+
|              |                                                      |
| ▼ Projects   |   Highlander Prospect (Demo)                         |
|     ● Proj A |   Pargmann-Gisler #1  ·  Karnes County, TX           |
|     ● Proj B |                                                      |
|              |   ┌─ Phase banner ──────────────────────────────┐    |
| ▼ Templates  |   │ ●  Subscription                 [Advance →] │    |
|     Document |   │    Sending packets and collecting signed... │    |
|     Email    |   └─────────────────────────────────────────────┘    |
|              |                                                      |
| ▼ Workflows  |   ┌─ Tabs ───────────────────────────────────────┐   |
|     ⚡ Std P  |   │ Setup │ Investors │ Documents │ Send │ ...  │   |
|              |   └──────────────────────────────────────────────┘   |
|              |                                                      |
+--------------+------------------------------------------------------+
| DB: %APPDATA%/WellSign/wellsign.db                                   |
+---------------------------------------------------------------------+
```

`MainWindow._on_nav_selection()` swaps the right pane based on `NavSelection.kind`. The right-pane stack has **5 pages**: DashboardPage, ProjectWorkspace, DocTemplatesPage, EmailTemplatesPage, WorkflowsPage.

### Navigator tree — three top-level roots

```
▼ Projects                ← phase-colored ● dot per project
    ● Highlander Prospect
    ● Sample Well B
▼ Templates
    Document templates
    Email templates
▼ Workflows               ← workflows are top-level navigable
    ⚡ Standard Capital Raise
```

### ProjectWorkspace — phase banner + 7 tabs

| Tab | State | Purpose |
|---|---|---|
| Project Setup | Read-only | Summary view + phase banner with traffic-light counts (editable form TODO) |
| Investors | Real | Traffic-light table with WI sum validation (+Add / Import buttons not yet wired) |
| Documents | Placeholder | Generate filled packets (needs `pdf_/fill.py`) |
| Send | Placeholder | Outlook COM send (needs `email_/sender.py`) |
| Status | Placeholder | Per-investor doc grid |
| **Costs** | **Real** | AFE budget vs actuals with variance coloring + receipt attachments + totals row |
| Burndown | Placeholder | Completion-over-time chart |

### Phase banner

Above the tabs in every project. Color-coded by phase, shows label + description, plus:
- **Advance →** — moves to next legal phase. Smart label shows the next phase name. Pops a chooser if there are 2 options (the Drilling fork: abandoned vs completing).
- **Set Phase…** — manual override; pick any phase from the full list.

Phase changes emit `phaseChanged(project_id)` which `MainWindow` listens to and the navigator refreshes the project's color dot.

### Traffic lights

In the Investors tab and the Project Setup banner, each investor shows a traffic light from `db/workflows.py:compute_traffic_light()`:

- 🟢 **GREEN** — in a stage, within SLA
- 🟡 **YELLOW** — in a stage, ≤ 3 days remaining
- 🔴 **RED** — overdue past SLA
- ⚪ **GREY** — no active stage run yet

## Key flows

### App start
1. `main.py` → `QApplication.setStyle("Fusion")`, loads `style.qss`
2. `run_migrations()` — applies `schema.sql` idempotently, stamps `schema_version`
3. `seed_if_empty()` — seeds doc templates → email templates → default workflow → demo project (each only if its table is empty; idempotent)
4. Shows `MainWindow` (1380×860, min 1100×700)

### Create project
1. Operator clicks `+ New Project` (Ctrl+N) → `NewProjectDialog`
2. Operator pastes a `.wslicense` file path → `verify_license_file()` parses, verifies RSA-PSS, returns `LicensePayload`
3. SHA-256 of canonical payload → `license_key_hash`
4. Operator picks a workflow from the combo (default: "Standard Capital Raise")
5. `db/projects.py:insert_project()` writes the row with `workflow_id` set
6. `app_paths.project_dir(uuid)` creates the on-disk folder
7. Navigator + dashboard refresh

> **Gap:** real `insert_investor()` does NOT create an `investor_stage_runs` row to kick off the workflow. The demo seed does this. Real project creation needs the same wiring before traffic lights work outside the demo.

### Advance phase
1. Operator clicks **Advance →** on the phase banner
2. `next_phase_options(current)` returns the legal next phases
3. If 1 option → jump straight there. If 2 → pop a chooser (the Drilling fork)
4. `set_phase(project_id, new_phase)` updates the row + stamps `phase_entered_at`
5. `phaseChanged` signal fires → navigator refreshes the dot

### Build a workflow
1. Click **Workflows** in the navigator → `WorkflowsPage`
2. **+ New Workflow** to create one (or pick the seeded default)
3. Drag-drop reorderable stage cards. Each card has SLA spinbox, exit condition combo, attached doc chips, attached email chips
4. **+ Add doc** / **+ Add email** opens the multi-select `TemplatePickerDialog` — operator can attach 5 docs in one click (was 5 separate clicks before)
5. Auto-saves on every field change

### Track AFE costs
1. Costs tab → **+ Add Line** → `CostLineDialog`
2. Pick category (14 O&G presets), description, expected vs actual `$`, vendor, invoice, status
3. Once saved, line shows in the table with variance colored red (over) / green (under)
4. Select a line → **📎 Attach Receipt** → file dialog → `attach_receipt()` copies to `projects/<uuid>/costs/<line_id>/`, hashes, mime-types
5. Totals row at the bottom: Expected / Actual / Variance / Receipts

### License model
- One license = one project, baked into the signed payload: `{key_id, customer, project_name, issued_at, expires_at}`
- RSA-3072 PSS, canonical JSON
- Public key shipped at `wellsign/resources/license_public_key.pem`
- Private key generated by `scripts/mint_license.py generate-keypair`, **NEVER in git**
- See [security.md](security.md) for the threat model
- See [roadmap.md](roadmap.md) for the annual-seat alternative if per-project becomes hostile UX

### PII encryption
- `util/crypto.py:encrypt_pii(plaintext)` → `iv_hex:tag_hex:ct_hex` string, stored in `_enc` columns
- Master key generated on first call via `secrets.token_bytes(32)`, stashed in keyring service `wellsign.pii` user `master_key`
- `decrypt_pii` is opt-in: callers explicitly request a single field at the moment of display
- `mask_pii(value)` returns `••••<last4>`

### File storage layout

```
%APPDATA%\WellSign\
├── wellsign.db
├── templates/documents/<template_id>.pdf       # Global template library
└── projects/<project_uuid>/
    ├── templates/<template_id>.pdf             # Per-project template snapshots
    ├── exports/                                 # Operator CSV exports
    ├── investors/<investor_uuid>/
    │   ├── sent/                                # Generated PDFs sent out
    │   ├── received/                            # Signed/notarized returns
    │   └── attachments/                         # Arbitrary uploads (W-9, ID)
    └── costs/<cost_line_id>/                    # AFE receipt attachments
        └── <receipt_filename>
```

The DB only ever stores **relative** paths under `projects/<uuid>/`.

## Out of scope for v1

Per [roadmap.md](roadmap.md):

- E-signature integration (DocuSign / PandaDoc) — schema fields exist but no API client
- Investor web portal — not now, not later
- Multi-tenant SaaS — single-operator install only
- Reg D / Form D / blue sky filing automation
- Multi-well investor history (investor as a top-level entity)
- BCP / ACP / NRI working interest split
- Supplemental cash call versioning (separate from the Costs tab actuals tracker)
- Wire reconciliation / bank statement import
- K-1 / CPA year-end export
- Word `.docx` template support — currently only PDF AcroForm fields
- Online notarization (RON) integration
- SMS reminders, anything Twilio
- Server-side anything

## Open architectural questions

- **Phase ↔ workflow stage coupling:** `exit_condition` on a workflow stage doesn't auto-advance the project phase. Should it? (e.g., when the Subscription stage exits with `all_docs_signed`, auto-advance project phase from `documenting` → `funding`.) Probably yes — that's the whole point. Note that the phase enum **codes** stayed the same (`investigating` / `soliciting` / `documenting` / `funding` / `drilling` / `abandoned` / `completing`) when labels were renamed on 2026-04-07; only the user-facing strings changed.
- **Migration runner:** `db/migrate.py` is dumb — single idempotent script with `CREATE TABLE IF NOT EXISTS`. Adding new columns to existing tables doesn't apply on returning installs. **This will bite when an existing install upgrades.** Either add `ALTER TABLE` patterns inside try/except, or move to a versioned migrations folder.
- **Investor stage runs at real project creation:** the demo seed creates them, but real `insert_investor()` doesn't kick off a stage run. Needs wiring before traffic lights work outside the demo.
- **Reminder scheduler:** `wait_days` on `stage_email_templates` is captured but no background loop fires the reminders. Whole point of the workflow engine.
- **Surplus / supplemental cash call calculator:** Costs tab subtitle promises this ("the totals row drives the surplus / supplemental cash call calculation at end-of-drilling") but the calculator doesn't exist yet.
- **License model:** per-project keys are friction for high-volume operators. See [roadmap.md](roadmap.md).
- **Templates:** real Paloma templates are .docx (Word), not PDF AcroForms. See [paloma-packet.md](paloma-packet.md) and [roadmap.md](roadmap.md) for the docxtpl plan.
