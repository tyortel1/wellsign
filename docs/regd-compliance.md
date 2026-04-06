# WellSign — Reg D / Securities Compliance

> **This is not legal advice.** Operators must consult securities counsel before relying on any of this. WellSign's job is to capture the right data and generate the right paperwork — the legal interpretation belongs to a lawyer.
>
> **None of this is in v1.** This doc captures what we'll need to add. See [roadmap.md](roadmap.md).

## Why this matters

When a small oil & gas operator (Paloma) sells working interests to small investors (Adrian Almanza, etc.) for cash, they are **selling securities**. The fact that the security is a "fractional interest in oil and gas leases" doesn't change that — federal securities law applies, and so does Texas state law.

A Reg D 506(b) compliance failure can result in:

- SEC enforcement action against the operator
- Investor recission rights (the investor can demand their money back, with interest, for years)
- Personal liability for the operator's officers under "control person" rules
- Loss of the safe-harbor exemption for future raises

Mostly the risk is that an unhappy investor calls a securities attorney after a well goes dry. **Compliance paperwork is the operator's defense.**

## Exemption stack

Paloma almost certainly relies on:

1. **Federal: Reg D 506(b)** — unlimited accredited investors + up to 35 non-accredited "sophisticated" investors. No general solicitation. Self-certification of accreditation is acceptable.
2. **Texas: 7 TAC §109.14** — oil, gas & mineral interest exemption. Up to 35 sales in any rolling 12-month period. No advertising. Stacks with the federal 506(b) exemption for in-state deals.

The PA we read includes the standard private-placement language: *"this Agreement is a result of a private offering, without any public solicitation."* That's the 506(b) safe harbor invocation.

## Mandatory filings

These have to happen, the operator probably already knows that, and WellSign should automate them.

### SEC Form D

- **Filed via:** EDGAR e-filing (https://www.sec.gov/edgar)
- **Deadline:** within **15 calendar days** of the first sale in the offering
- **Fields:** issuer info, offering total, type of securities, exemption claimed, executive officers, total amount sold, number of investors
- **Amendment:** required annually for ongoing offerings or whenever material info changes

### Texas SSB notice filing

- **Filed via:** Texas State Securities Board
- **Deadline:** within **15 days** of the first sale in Texas
- **Fee:** 0.1% of the offering amount, capped at $500
- **Form:** copy of the Form D + a Texas-specific cover

### Multi-state blue sky notices

- **46 states** require a notice filing (Rule 506 is federally preempted under NSMIA, but states can still require notice)
- Each investor's home state where the sale occurred = one filing
- Fees range $100 – $500 per state
- Deadlines vary (most are 15 days from first sale in that state)

## Accredited investor verification

Under Reg D 506(b), self-certification is sufficient — the investor signs a statement attesting they meet one of the SEC's accreditation tests:

1. **Income:** $200K+/yr individual, $300K+/yr joint, in each of the last 2 years, with reasonable expectation of same this year
2. **Net worth:** $1M+ individual or joint, EXCLUDING primary residence
3. **Professional certification:** Series 7, 65, or 82 license in good standing
4. **Knowledgeable employee** of a private fund (rare for our use case)
5. **Entity tests:** $5M+ in assets, OR all equity owners are accredited individuals, OR specific entity types (banks, RIAs, etc.)

For non-accredited "sophisticated" investors under 506(b), the operator must reasonably believe the investor has the knowledge and experience to evaluate the investment — and must deliver a **Private Placement Memorandum (PPM)** with prescribed disclosures.

## "No general solicitation" provenance

The single most common Reg D 506(b) compliance failure is sloppy investor sourcing. The operator must be able to demonstrate that every investor came to the deal through a **pre-existing substantive relationship** — not advertising, not a website, not a cold email blast.

WellSign should capture, per investor:

- **How did they hear about this offering?** (referral / existing relationship / prior deal / other)
- **When did the relationship begin?** (date)
- **Who introduced them?** (free text — the existing investor or advisor)

This metadata sits on every investor record and is the operator's defense if the SEC ever asks.

## Bad actor Rule 506(d)

Reg D exemption is unavailable if any "covered person" (the operator's officers, directors, 20%+ owners, promoters, placement agents) has a "disqualifying event" — felony conviction, SEC bar, court injunction, etc., generally within the last 10 years.

WellSign should prompt the operator to complete a **bad actor self-questionnaire** at the time of license activation, store the result, and refuse to issue new packets if any answer changes.

## WellSign feature roadmap

### v1 (current)
- Nothing. The Participant Information Form collects SSN/Tax ID and contact info but does not capture accreditation status, provenance, or anything compliance-relevant.

### v2 — capture the data
- Reframe the "Investor Info Sheet" as an **Accredited Investor Questionnaire** with the 5 SEC tests as checkboxes + signature
- Add `accreditation_status` + `accreditation_basis` + `acquired_via` columns to investors
- Add `first_sale_date` to projects
- Add a "Form D due in N days" alert in the dashboard
- Add a "Bad actor self-check" in the operator settings, with a date stamp
- Capture provenance ("how did this investor come to the deal") at investor add time

### v3 — generate the filings
- Form D PDF generator (the SEC fields are stable; we fill the form, the operator reviews, manual EDGAR upload)
- Texas SSB notice generator (PDF + fee calculation)
- Per-investor home-state lookup → list of required blue sky notices for each project
- One-click "filing package" export: a zip with Form D, Texas notice, and every state notice ready for the operator to file

### v4 — automation
- Direct EDGAR API submission (SEC supports it)
- State filing portals where they exist
- Renewal alerts for annual amendments
- Investor-side accreditation verification via a third-party service (e.g., VerifyInvestor.com) for 506(c) deals if the operator ever wants to advertise

## Open questions

- Does Paloma already have a securities attorney who handles their Form D filings? If so, WellSign's job is to feed that attorney clean data, not replace them.
- Is Paloma running a single offering per well (which means a fresh Form D per project) or one continuous offering (one Form D, periodic amendments)? Affects how we model `first_sale_date`.
- Bowersox Exploration LLC's role — they appear in the PA notices block but aren't a participant. Are they a placement agent? If so, that triggers additional 506(b) requirements.

## References

- [SEC Rule 506(b)](https://www.sec.gov/resources-small-businesses/exempt-offerings/private-placements-rule-506b)
- [SEC Form D FAQ](https://www.sec.gov/about/divisions-offices/division-corporation-finance/frequently-asked-questions-answers-form-d)
- [Texas SSB Filing Requirements](https://www.ssb.texas.gov/securities-professionals/regulation-securities/filing-requirements-regulation-d-offerings-texas)
- [7 TAC §109.14](http://txrules.elaws.us/rule/title7_chapter109_sec.109.14)
- [DLA Piper 2025 506(c) verification guidance](https://www.dlapiper.com/en/insights/publications/2025/03/sec-permits-rule-506-c-verification-compliance-with-self-certification)
