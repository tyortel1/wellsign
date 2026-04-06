# WellSign — Security

> WellSign handles SSNs, EINs, bank routing numbers, and signed legal documents. The rules below are about not leaking that data — encrypt it at rest, mask it in the UI, keep it out of logs. Don't overthink it.

## PII inventory

| Field | At rest | In UI |
|---|---|---|
| SSN / EIN | AES-256-GCM (`ssn_enc`, `ein_enc`) | Masked `••••1234` after entry, never re-shown in full |
| Bank routing # | AES-256-GCM (`bank_routing_enc`) | Masked `••••1234` |
| Bank account # | AES-256-GCM (`bank_account_enc`) | Masked `••••1234` |
| Bank name | AES-256-GCM (`bank_name_enc`) | Full display OK, but never in logs |
| Investor name, address, email, phone | Plaintext | OK |
| Signed PDFs | Filesystem (NTFS perms) | Filenames never contain PII values |

## Encryption design (`util/crypto.py`)

- **Algorithm:** AES-256-GCM via the `cryptography.hazmat.primitives.ciphers.aead.AESGCM` class. Each encrypted value stores `iv_hex:tag_hex:ct_hex` (12-byte IV, 16-byte tag, ciphertext).
- **Master key:** 32 random bytes generated on first use via `secrets.token_bytes(32)`. Stored in Windows Credential Manager via `keyring` under service `wellsign.pii`, user `master_key`.
- **Test/CI override:** `WELLSIGN_PII_KEY_HEX` environment variable. **Never used in production.**
- **Key never touches disk in plaintext.** Never logged. Never sent in error messages.
- **Decryption is opt-in.** `db/investors.py` deliberately does NOT auto-decrypt PII. Callers must explicitly invoke `decrypt_pii()` for a single field at the moment of display, then re-mask immediately.
- **If the keyring entry is missing**, the app refuses to start (TODO: enforce this in `main.py`) and asks the user to restore from backup or wipe and re-enter.

## License keys (`license_/verify.py`, `license_/issue.py`)

- **Algorithm:** RSA-3072 with PSS padding (MGF1 + SHA-256, MAX salt length).
- **Format:** JSON envelope `{"payload": {...}, "signature": "<base64>"}`.
- **Payload fields:** `key_id`, `customer`, `project_name`, `issued_at`, `expires_at` — all required.
- **Canonical encoding:** `json.dumps(payload, sort_keys=True, separators=(",", ":"))`. Both signer and verifier use the same canonical form.
- **Public key** lives at `src/wellsign/resources/license_public_key.pem` and is loaded via `importlib.resources`. Bundled with the app.
- **Private key** lives outside the repo, supplied to `scripts/mint_license.py mint` via `--private-key`. The `secrets/` folder is gitignored entirely. **Never commit a private key.**
- **One key = one project.** Project creation hashes the canonical payload to produce `license_key_hash`, stored on the project row. Re-using a license envelope for a second project would produce the same hash and could be detected.
- **Expiry** is enforced — `verify_license_file()` raises `LicenseError` if `expires_at < now`.

## Audit log

- **Append-only enforced at the SQL level.** `audit_log_no_update` and `audit_log_no_delete` triggers raise `RAISE(FAIL, 'audit_log is append-only')` on any UPDATE or DELETE. The application doesn't have to remember to be careful — the database refuses.
- **Records:** `project_created`, `investor_added`, `template_uploaded`, `packet_generated`, `email_sent`, `document_received`, `payment_received`, `status_changed`, `license_verified`, `app_started`.
- **Never contains PII values.** UUIDs and metadata only. The `metadata` JSON column must be sanitized at the call site.

## Logging rules — non-negotiable

- Never log decrypted PII. Period.
- Never include PII in exception messages, breadcrumbs, or stack traces.
- All log statements that touch an investor record use the investor's UUID, not name/email.
- The user-visible error dialog never echoes back the value the user typed.
- The PII encryption module raises bare exceptions with no operand context.

## Test-mode safeguards

- Projects created with `is_test = 1` should get a visible banner everywhere (TODO).
- Test investors should use clearly fake data — system should warn if a test project's email looks like a real domain (TODO).
- Test mode never auto-sends via Outlook — drafts are left in the Outbox for inspection (TODO).

## File handling

- Generated PDFs live under `%APPDATA%\WellSign\projects\{project_id}\investors\{investor_id}\`. NTFS permissions restrict to the operator's user account.
- Filenames include doc type and timestamp but **never** PII values (`util/storage.py:_safe()` strips anything not in `[A-Za-z0-9._-]`).
- The `received/` subfolder is the auto-detect dropzone — any new PDF appearing is offered for assignment to a document slot (TODO).

## What is NOT in `.gitignore` and why it matters

- `src/wellsign/resources/license_public_key.pem` — the bundled public key MUST be committed for the app to verify licenses. The `*.pem` rule in `.gitignore` has an explicit exception for this file.
- `secrets/` and any `*.pem` outside that exception — gitignored. **Never commit private keys.**
- `docs/reference/` — gitignored. Real Paloma reference PDFs (with PII) live here for development and never get pushed.
- `*.wslicense` — gitignored. Issued license files contain customer + project info; not catastrophic if leaked but no reason to commit them.

## Open security questions

- **Whole-DB encryption (SQLCipher)** as defense-in-depth on top of column-level? Trade-off is added install/distribution complexity. Defer until first real-data deployment.
- **Backup model:** the operator should be able to back up `%APPDATA%\WellSign\` to a USB drive — but the master key lives in Credential Manager, not in that folder. Need a documented backup-and-restore flow before any real data goes in.
- **Outlook send authorization:** does sending need a per-batch confirmation dialog showing the recipient list? (Probably yes, especially in test mode.)
