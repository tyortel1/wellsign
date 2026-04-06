# Paloma Investor Packet — Reference

> Business reference for the document set every investor receives. **Architecture-independent** — the rules below are about the legal/financial workflow, not WellSign internals.
>
> Verified against real Paloma reference packets in `docs/reference/` (gitignored). When in doubt, the actual packet wins.

## The 7 documents

| # | Document | Form | Payee / Notes | Page Size | Notary |
|---|---|---|---|---|---|
| 1 | Joint Operating Agreement (JOA) | A.A.P.L. Form 610-1989 (with operator HST revisions) | Paloma Operating LLC (Operator) | **Legal** | **Yes** — signature + notary block at end |
| 2 | Participation Agreement (PA) | Decker custom letter | Binding agreement, no payee | Letter | No |
| 3 | Cash Call Exhibit C-1 (LLG) | Decker custom | Pay to **Decker Exploration, Inc.** | Letter | No |
| 4 | Cash Call Exhibit C-2 (DHC) | Paloma custom | Pay to **Paloma Operating LLC** | Letter | No |
| 5 | W-9 | IRS Form W-9 (Rev. 3-2024) | Retained by operator for tax records — Paloma is the W-9 requester | Letter | No |
| 6 | Participant Information Form | Paloma custom | Operator's investor intake — name, entity, address, phone, email, **SSN/Tax ID** | Letter | No |
| 7 | Wiring Instructions (Decker) | Decker static PDF | Reference — LLG wires go to Decker (BoA, ACH 111000025 / Wire 026009593) | Letter | No |

## Critical business rules

- **C-1 always pays Decker. C-2 always pays Paloma.** This routing is enforced by the system, not chosen by the operator each time.
- **The JOA is legal-size.** The packet mixes letter- and legal-size pages — generated PDFs must preserve this.
- **WI% prints with 8 decimal places** on cash-call documents (e.g. `0.01000000` for 1%). Matches Paloma's existing format. Do not truncate.
- **Dollar amounts print with `$` sign and 2 decimal places** (e.g. `$10,000.00`).
- **JOA notary block is at the end** of the document. Wet-sign workflow: each party gets THEIR OWN notary in their own state.

## Real workflow notes (verified against the reference packet)

### Templates are .docx, NOT PDF

Paloma maintains the JOA as a Microsoft Word `.docx` file in SharePoint and prints to PDF on demand. The customization is named like `JOA 2024-11-07 HST Revisions Operating Agreement Form - Election Times for Rework and Recompletion.docx`. The PA letter and Participant Info Form are the same — Word documents printed to PDF.

The Cash Call C-1 / C-2 exhibits look auto-generated from the operator's accounting system (structured tables, "Cash Call#", "Property#", "Summary by Owner" rows) — not Word.

**Implication for WellSign:** v1 reads PDF AcroForm fields via `pypdf` (`pdf_/fields.py`). To support `.docx` templates with Word merge fields, we'd need to add `docxtpl` + `docx2pdf` (or LibreOffice headless conversion). See [roadmap.md](roadmap.md).

### The "return packet" is actually outbound, partially pre-signed

The Paloma "return packet" is what Paloma sends OUT to the investor — already partially executed. Specifically:

- The PA signature page already has Decker (President) and Paloma (CEO) signatures, leaving the investor's block blank
- The JOA signature page already has Paloma's signature (CEO), Decker's signature (President), and **Paloma's own notary acknowledgment is already filled in** (Paloma's go-to notary, in their county)
- Cash Call C-1 and C-2 have all the math filled in, blank approval blocks
- Participant Information Form is blank (investor fills in SSN/Tax ID, contact info)
- W-9 is blank (Paloma is named as the requester at the top right)

So the workflow is:
1. Paloma signs everything internally and gets their own notary acknowledgment on the JOA
2. Decker counter-signs as deal originator
3. The packet goes out to the investor pre-signed
4. The investor fills in their info form, signs the cash calls and PA, gets their own notary to acknowledge their JOA signature, and mails or scans back the signed pages

**Implication for the data model:** to model this properly we'd need a `signing_parties` concept with order (Paloma → Decker → Investor → Bowersox), per-party status, and a `notaries` table for reusable notary identities. None of this is in v1 — see [roadmap.md](roadmap.md).

### JOA signature page reassembly

Each party gets their JOA notarized in their own state. The operator collects all the signature/notary pages from all parties and stitches them into a "fully executed JOA" by combining the master document body + all per-party signature pages. WellSign should track each party's signature page separately (not one monolithic JOA file) and produce a final assembled PDF on demand. v2 work — see [roadmap.md](roadmap.md).

### Cash Call C-2 has 21 line items

The C-2 (DHC) breaks the total into structured line items:

**Intangible Drill/Compl** — Roads/location/damages, Drilling contractor turnkey, Drilling contractor daywork, Electric logging open hole, Coring/wireline/formation test, Mud logging, Directional drilling, Equipment rental, Trucking/hauling/disposal, Overhead drlg/compltn/recompl, Other intangible costs, Insurance, Labor, Permits/RRC filings, Survey/stake location, Engineering/professional fees, Water well drilling, Recording fees/title work

**Well Equipment** — Christmas tree wellhead eqpt, Other misc tangible costs, P&A services

The operator enters these once per project; they appear on every investor's C-2. Currently no `cash_call_line_items` table exists — the operator manages this outside the system in v1. See [roadmap.md](roadmap.md).

### Working interest is actually three numbers, not one

The PA shows three percentages per investor that v1 collapses into a single `wi_percent`:

| | Meaning | Used for |
|---|---|---|
| **BCP** Before Completion Point | What the investor pays cash on | Cash call calculation |
| **ACP** After Completion Point | What the investor owns post-completion | Decker keeps a back-in / promote |
| **NRI** Net Revenue Interest | What the investor actually gets paid on production | Revenue distributions |

v1 stores the BCP value in `wi_percent`. v2 should split — see [roadmap.md](roadmap.md).

## Merge variables (system → template fields)

These are the canonical merge variable names. Email templates use them in `{{double_curly}}` Jinja-style syntax (see `db/seed.py`); document templates map PDF AcroForm field names to them via `document_templates.field_mapping` JSON.

| Variable | Source | Output format |
|---|---|---|
| `investor_first_name` | `investors.first_name` | as-is |
| `investor_name` | `first_name + last_name` | `First Last` |
| `investor_entity` | `investors.entity_name` | as-is |
| `investor_address` | `address_line1, city, state, zip` | one-line concat |
| `investor_wi_percent` | `investors.wi_percent` | `0.01000000` (8 decimal places) |
| `investor_wi_percent_display` | `wi_percent × 100` | `1.000000%` |
| `llg_amount` | `investors.llg_amount` | `$10,000.00` |
| `dhc_amount` | `investors.dhc_amount` | `$10,000.00` |
| `well_name` | `projects.well_name` | as-is |
| `prospect_name` | `projects.prospect_name` | as-is |
| `operator_name` | `projects.operator_llc` | as-is |
| `county_state` | `projects.county + state` | `Karnes County, TX` |
| `agreement_date` | `projects.agreement_date` | `Month D, YYYY` |
| `close_deadline` | `projects.close_deadline` | `Month D, YYYY` |
| `payee_c1` | constant | **always** `Decker Exploration, Inc.` |
| `payee_c2` | `projects.operator_llc` | **always** the operator (Paloma) |
| `outstanding_items` | computed at reminder send | bullet list of incomplete docs |

## Reference materials

- **A.A.P.L. Form 610-1989** is publicly available from oil & gas legal references — useful for layout and field-position testing.
- **Real Paloma reference packets** live in `docs/reference/` (gitignored — never committed). When testing template field mapping, use these as the structural reference but **never copy real PII into committed code, docs, fixtures, or logs.**
- **Public company information** (Paloma Operating LLC, Decker Exploration Inc) may appear in committed docs as company names. Real investor PII (SSNs, bank routing, account numbers, personal addresses) must NEVER appear in committed files.
