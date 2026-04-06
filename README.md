# WellSign

Local Windows desktop app that automates the investor document workflow for small oil & gas operators. Built in PySide6, stores everything locally in SQLite + a per-project file folder. Sends packets through the operator's existing Outlook install. No web portal, no cloud — the operator's machine is the system of record.

## What it does

- Manage multiple **projects** (one per well prospect), switch between them, and compare status across all of them at once
- Track **investors** under each project (Excel import or manual add) with working interest %, contact info, payment preference
- Build reusable **PDF document templates** and **email message templates** in-app — set them up once, reuse across projects
- **Auto-fill** every legal document per investor (name, address, WI%, cash call dollars to the right payee)
- **Send** packets through Outlook with one click — auto-attaches the right PDFs and prefills the message
- **Auto-assign** sent and received documents to the right investor on the right project
- **Per-project file storage** — every PDF, attachment, and signed return doc lives in the project's folder, indexed by the database
- **Status dashboard** per project + cross-project view, with **burndown charts** vs. close deadlines
- **Payment tracking** for both LLG (to Decker Exploration) and DHC (to Paloma Operating)
- **License-gated project creation** — every new project requires a license key issued by us

## Quick start (developers)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -e .
wellsign
```

## Project layout

```
wellsign/
├── src/wellsign/
│   ├── main.py                # entry point
│   ├── app_paths.py           # %APPDATA%/WellSign locations
│   ├── db/                    # SQLite schema, migrations, queries
│   ├── models/                # dataclasses for Project, Investor, Document
│   ├── license_/              # offline RSA license key verify + issue
│   ├── pdf_/                  # PDF form-field fill, template field mapping
│   ├── email_/                # Outlook COM send
│   ├── util/                  # crypto (PII AES), storage (project file layout), helpers
│   ├── ui/
│   │   ├── main_window.py     # QMainWindow + tabs
│   │   ├── tabs/              # one widget per tab
│   │   └── widgets/           # shared custom widgets
│   └── resources/             # QSS stylesheet, icons
├── tests/
└── scripts/                   # license-mint CLI etc.
```

## Security notes

- All investor PII (SSN, EIN, bank routing/account) is encrypted at the application layer with AES-256-GCM before being written to SQLite
- Master encryption key is stored in Windows Credential Manager via `keyring` — never on disk, never in source
- File paths are stored in the DB; file contents live on disk under `%APPDATA%/WellSign/projects/<uuid>/`
- Sample/test investor data files (`*_REAL.*`, `sample_data/real/`) are gitignored — never commit real data
