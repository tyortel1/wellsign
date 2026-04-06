# WellSign — Roadmap

> Everything the document review and competitor research surfaced as missing or wrong, but **deliberately not in v1**. This is the v2/v3 wishlist. Items here are NOT designed yet — they're problems to solve, not specs.

## v1 scope — current status

### Done
- ✅ Local PySide6 desktop, SQLite, per-project license keys
- ✅ Schema (`schema.sql`), migrate runner, demo seed
- ✅ AES-256-GCM PII column encryption with keyring master key
- ✅ RSA-3072 PSS license verification, bundled public key
- ✅ NavigatorTree + DashboardPage + ProjectWorkspace + WorkflowsPage
- ✅ DocTemplatesPage + NewDocTemplateDialog (PDF browse + form-field detection)
- ✅ EmailTemplatesPage + NewEmailTemplateDialog
- ✅ NewProjectDialog with license-file verify + workflow picker
- ✅ Workflow engine: workflows / stages / stage_doc_templates / stage_email_templates / investor_stage_runs tables and CRUD
- ✅ WorkflowsPage with drag-drop reorderable stage cards
- ✅ Multi-select TemplatePickerDialog for batch attaching docs/emails to stages
- ✅ **Phases subsystem** (`db/phases.py`) — 7-state operator lifecycle with phase banner, Advance/Set Phase buttons, color-coded navigator dots
- ✅ **AFE Costs subsystem** (`db/costs.py` + `CostsTab` + `CostLineDialog`) — line items with vendor/status, receipt attachments, variance coloring, totals row
- ✅ Default "Standard Paloma Closing" workflow seeded with 4 stages and all the right docs/emails attached
- ✅ Real ProjectSetupTab (read-only summary) with traffic-light counts in the phase banner
- ✅ Real InvestorsTab (table view) with traffic lights + WI sum validation
- ✅ Demo data with 5 investors at varying stage timing for traffic light demo + 10 realistic AFE cost lines

### Still placeholder / not built
- ⏳ Editable Project Setup form (currently read-only summary)
- ⏳ NewInvestorDialog + Excel import wiring on InvestorsTab
- ⏳ pypdf form-field MERGE (only field READ exists today via `pdf_/fields.py`)
- ⏳ Real DocumentsTab — generate filled per-investor packets
- ⏳ Outlook COM wrapper in `email_/`
- ⏳ Real SendTab — pick investors, preview, fire
- ⏳ Real StatusTab — per-investor doc grid + reminder one-click
- ⏳ Real BurndownTab — completion-over-time chart vs close deadline
- ⏳ Real `insert_investor()` creates `investor_stage_runs` (currently only the seed does)
- ⏳ Exit-condition enforcement on workflow stages (auto-advance when all_docs_signed / llg_and_dhc_paid)
- ⏳ Reminder scheduler that honors `wait_days`
- ⏳ Audit log writes (table + triggers exist, no callers)
- ⏳ Surplus / supplemental cash call calculator (the Costs tab subtitle promises this)
- ⏳ Migration runner upgrade (current dumb idempotent script breaks on returning installs after schema additions)

## v2 — research-driven additions

These came out of the document review and competitor research on 2026-04-06.

### 1. E-signature integration (high value, low effort)

The schema is already forward-compatible (`investor_documents.source` includes `'docusign' | 'pandadoc'`, `external_url` field exists). What's missing is just an API client.

- **PandaDoc API** is the recommended pick — single API for doc-gen + e-sign + payment, cheaper than DocuSign for the volume
- DocuSign as fallback if PandaDoc has gaps in oil & gas use cases
- **Note:** the JOA still needs notarization — wet-ink for now, RON integration in v3
- Ship as configurable per-investor: Outlook COM (current path) OR PandaDoc API
- Webhook ingest for `sent → viewed → signed` state transitions
- **Why now:** removes the biggest pain point (investors print, sign, scan, mail back). Without this, WellSign is only marginally better than Word mail merge.

### 2. Reg D / Securities compliance module (biggest moat)

Selling working interests = selling securities. Paloma relies on Reg D 506(b) + Texas 7 TAC §109.14. None of the existing oil & gas software handles this.

See [regd-compliance.md](regd-compliance.md) for the full breakdown. Short version:

- Capture **accreditation status** + basis per investor (5 SEC tests as checkboxes)
- Capture **"how did this investor come to the deal"** provenance (the #1 Reg D failure point)
- Track `first_sale_date` per project to drive a "Form D due in 15 days" alarm
- **v2:** Form D PDF generator + Texas SSB notice generator
- **v3:** 50-state blue sky filing automation
- Bad-actor Rule 506(d) self-check for the operator

**Schema impact:** new tables `accreditation_records`, `regd_filings`. The `investor_info_form` should become an `accredited_investor_questionnaire`.

### 3. Multi-well investor history

Same human investor will be in 5+ Paloma wells over 3 years. Current schema treats them as a per-project row, which means re-entering name/address/SSN/W-9/accreditation every drill — and stale accreditation status is a Reg D risk.

**Schema impact (significant):**
- Promote `investors` to a top-level entity (no `project_id`)
- New join table `project_participations(project_id, investor_id, wi_percent_bcp, wi_percent_acp, nri_percent, llg_amount, dhc_amount, status, ...)`
- Migration: ALTER + backfill the existing `investors` rows

This is the biggest schema refactor on the list. Worth it because the workflow assumes repeat investors.

### 4. BCP / ACP / NRI working interest split

Real PA documents show three percentages per investor:

- **BCP (Before Completion Point)** — what the investor pays cash on (drives Cash Call)
- **ACP (After Completion Point)** — what the investor owns post-completion (operator keeps a back-in / promote)
- **NRI (Net Revenue Interest)** — what the investor gets paid on production

v1 collapses these into a single `wi_percent`. v2 should split.

**Schema impact:** add `wi_percent_bcp`, `wi_percent_acp`, `nri_percent` to investors (or to `project_participations` once that lands). Drop `wi_percent` after migration.

### 5. ~~Cash call line items~~ — DONE as the AFE Costs subsystem

**Status: shipped.** The `cost_line_items` and `cost_attachments` tables, `db/costs.py`, `CostsTab`, and `CostLineDialog` together provide per-project line-item budget tracking with vendor, status (planned/committed/invoiced/paid), and receipt attachments.

The original idea was to model the C-2 cash call breakdown specifically. What landed is broader — full AFE budget vs actuals tracking through the entire well lifecycle, not just the cash call. Variance is colored red/green and totaled at the bottom of the Costs tab.

**What's still missing related to this:** the **surplus / supplemental cash call calculator** that the Costs tab subtitle promises. When the well finishes drilling and actuals are in, the operator should see "you collected $X DHC, spent $Y, surplus to refund = $Z" or "supplemental needed = $Z". The data is there; the math + UI isn't.

### 6. Supplemental AFE versioning

PA Section 3.2 explicitly contemplates supplemental AFEs when costs overrun. Current schema is one-shot. Add:

- New table `cash_call_rounds(project_id, round_number, total_llg, total_dhc, issued_at, status)`
- Each round generates a fresh packet subset for existing investors
- Reconciliation tracks "round 1 paid" vs "round 2 outstanding" per investor

### 7. Wire reconciliation

Operator's day-to-day pain is matching incoming wires (BoA statement) to expected cash calls. Add:

- CSV import of bank statements (BoA exports CSV directly)
- Fuzzy matcher: amount + date window + memo contains investor last name → suggest match
- Manual override for the rest
- Optional v3: Plaid bank-feed for live reconciliation

**Schema impact:** new table `bank_statement_lines(imported_at, amount, posted_at, memo, matched_payment_id)`.

### 8. K-1 / CPA year-end export

WellSign never generates K-1s (CPA's job), but it stores the data the CPA needs. Add a per-investor CSV export with: leasehold contribution, DHC contribution, dates, wire confirmations, K-1 recipient entity (LLC vs personal vs IRA).

### 9. Lightweight investor status page (NOT a portal)

Generate a per-investor static HTML status page with a tokenized URL. Push to S3 / Cloudflare Pages from the desktop app via a simple upload script. Investors get a link in their email; clicking it shows "You have 3 docs signed, 4 pending, wire not yet received".

**Why:** kills 80% of "where's my packet?" emails without building a real portal. ~1 day of work.

### 10. Word `.docx` template support

Real Paloma templates are `.docx` files in SharePoint, not PDFs with AcroForm fields. v1's `pdf_/fields.py` only reads PDF form fields.

- Add `docxtpl` dependency (LGPL v2.1+, same compliance pattern as PySide6)
- Add `docx2pdf` (uses Word COM via existing `pywin32`) for filled `.docx` → PDF conversion
- New `docx_/` module mirroring `pdf_/`
- Templates table needs a `template_format` column (`pdf` / `docx`)

See [licenses.md](licenses.md) for the dep license rundown.

### 11. Notaries table

Paloma has a go-to notary they use for every packet. Each party gets their own notary in their own state. Need a reusable notary identity:

**Schema impact:** new table `notaries(name, state, county, commission_id, commission_expires_at)`.

### 12. Pre-signed packet workflow

The "return packet" Paloma sends out is already partially executed: Paloma has signed and gotten their own notary acknowledgment on the JOA, Decker has counter-signed. The investor signs their blank blocks and gets their own notary.

**Schema impact:** new concept `signing_parties(document_id, party_role, party_name, signed_at, notary_id, notarized_at)`. Tracks order: Paloma → Decker → Investor → Bowersox.

### 13. JOA signature page reassembly

Each party gets the JOA notarized in their own state — only the signature page goes back. Operator collects all signature/notary pages and stitches them with the master JOA body to produce a "fully executed JOA".

**Implementation:** `pdf_/` module gets a `reassemble_joa(master_pdf, signature_pages)` helper. Status tab shows progress per party.

### 14. Annual seat license (alternative to per-project keys)

Per-project keys add friction every time the operator starts a new well. For an operator drilling 10+ wells/year, this becomes hostile UX.

**Alternative model:**
- Annual subscription per operator install (still RSA-signed offline file, just bound to operator + year, not project)
- Same crypto module (`license_/verify.py`), just different payload schema (`{key_id, customer, issued_at, expires_at, max_projects?, max_investors?}`)
- Schema impact: drop the per-project license columns, add a separate `installation_licenses` table
- **Big refactor** — touches verify.py, issue.py, mint_license.py, schema, project insert flow, and every bit of UI that mentions license keys

Defer until per-project model proves to be a real friction point with a real customer.

## v3 — bigger ideas

- **Online notarization (RON)** for the JOA — Texas allows it. APIs from BlueNotary, OneNotary, Proof.com.
- **JIB handoff export** — clean CSV in PakEnergy / Petrofly import format for when the well goes to production
- **Plaid bank-feed** for live wire reconciliation
- **SMS reminders** via Twilio
- **Multi-user / network share mode** for operator + CPA + landman collaboration
- **Hosted Postgres option** for operators who outgrow SQLite
- **About / Licenses dialog** in the app showing all dep licenses (mandatory once we ship under LGPL — see [licenses.md](licenses.md))

## Things explicitly NOT on the roadmap

- Investor web portal — not now, not ever. The lightweight status page (#9) is the substitute.
- Multi-tenant SaaS — single-operator install only. If demand emerges, we ship a separate hosted product, we don't bolt it on.
- DocuSign as primary e-sign — PandaDoc covers it cheaper.
- PyQt6 — GPL, would taint the whole app. **Never import.**
- Custom in-house notarization — RON via API only.
