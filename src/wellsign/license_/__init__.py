"""Per-project license keys.

Verification is offline: every project requires a signed key file (RSA-PSS,
SHA-256). The public key is bundled with the app; the private key is held by
Parker/Jeremy out of band and used by ``scripts/mint_license.py``.

A key file is JSON with two top-level fields::

    {
      "payload": {
        "key_id": "uuid",
        "customer": "Paloma Operating LLC",
        "project_name": "Highlander Prospect",
        "issued_at": "2026-04-06T12:00:00Z",
        "expires_at": "2027-04-06T12:00:00Z"
      },
      "signature": "<base64 RSA-PSS signature over canonical JSON of payload>"
    }
"""
