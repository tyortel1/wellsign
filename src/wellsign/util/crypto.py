"""AES-256-GCM encryption for investor PII columns.

Master key is stored in the OS keyring (Windows Credential Manager on Windows)
under service ``wellsign.pii``. The key never touches disk and never appears in
source code or logs.

The key is auto-generated on first launch (when no encrypted data exists yet).
On returning launches, ``healthcheck_master_key()`` enforces that if the
database holds any encrypted PII, the key must be present in the keyring —
otherwise the app refuses to start with a clear "key was wiped, restore from
backup" error. This prevents silent data loss.

Storage format for an encrypted value: ``<iv_hex>:<tag_hex>:<ct_hex>``.
"""

from __future__ import annotations

import os
import secrets
import sqlite3

import keyring
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_KEYRING_SERVICE = "wellsign.pii"
_KEYRING_USER = "master_key"
_ENV_OVERRIDE = "WELLSIGN_PII_KEY_HEX"  # for tests / CI only


class MasterKeyMissingError(RuntimeError):
    """Raised by ``healthcheck_master_key`` when encrypted data exists but the
    keyring entry is gone — likely a wiped credential vault. The app should
    refuse to start instead of silently regenerating the key (which would
    leave existing ciphertext unreadable forever)."""


def _has_encrypted_pii_in_db() -> bool:
    """Check whether the local database holds any encrypted PII rows.

    Used by ``healthcheck_master_key``. Tolerates a missing or empty database
    file (returns False), and tolerates the investors table not existing yet.
    """
    from wellsign.app_paths import database_path

    db = database_path()
    if not db.exists() or db.stat().st_size == 0:
        return False
    try:
        with sqlite3.connect(str(db)) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM investors WHERE "
                " ssn_enc IS NOT NULL OR ein_enc IS NOT NULL "
                " OR bank_routing_enc IS NOT NULL OR bank_account_enc IS NOT NULL "
                " OR bank_name_enc IS NOT NULL"
            ).fetchone()
            return bool(row and row[0])
    except sqlite3.Error:
        return False


def healthcheck_master_key() -> None:
    """Refuse to boot if the encryption master key is gone but data exists.

    Called once from ``main.py`` after migrations and before the main window
    shows. Three outcomes:

    * **Env override set** (tests / CI) → no-op, the override key wins
    * **Keyring entry present** → no-op, business as usual
    * **Keyring entry missing AND no encrypted data in DB** → fresh install
      or test mode; auto-generate the key in keyring and continue
    * **Keyring entry missing AND encrypted data exists** → raise
      ``MasterKeyMissingError`` — operator must restore from backup or
      wipe the database. Existing ciphertext cannot be decrypted.
    """
    if os.environ.get(_ENV_OVERRIDE):
        return

    stored = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
    if stored:
        # Validate length while we're at it
        try:
            key = bytes.fromhex(stored)
        except ValueError as e:
            raise MasterKeyMissingError(
                f"Stored PII master key is corrupt (not valid hex): {e}"
            ) from e
        if len(key) != 32:
            raise MasterKeyMissingError(
                "Stored PII master key is corrupt — wrong length "
                f"({len(key)} bytes, expected 32)"
            )
        return

    if _has_encrypted_pii_in_db():
        from wellsign.app_paths import database_path

        raise MasterKeyMissingError(
            "WellSign cannot find its encryption master key in the Windows "
            "Credential Manager (service 'wellsign.pii', user 'master_key'), "
            "but the local database contains encrypted investor PII.\n\n"
            f"Database: {database_path()}\n\n"
            "The key may have been wiped from your credential vault. Without "
            "the original key, the existing encrypted data CANNOT be "
            "decrypted — there is no recovery path inside WellSign.\n\n"
            "Options:\n"
            " 1. Restore the keyring entry from a backup\n"
            " 2. Delete the database file to start fresh (loses all "
            "encrypted data)\n"
            " 3. Contact WellSign support"
        )

    # Fresh install with no encrypted data — safe to auto-generate
    key = secrets.token_bytes(32)
    keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, key.hex())


def _load_or_create_master_key() -> bytes:
    """Lazy loader called by encrypt/decrypt at runtime.

    By the time this runs, ``healthcheck_master_key()`` has already verified
    that the keyring entry exists (or auto-generated it on a fresh install).
    The lazy path is the env override → keyring entry. If neither exists at
    encrypt-time we still raise rather than silently regenerating, since a
    silent regeneration mid-session would mean any value encrypted earlier in
    the session becomes unreadable.
    """
    override = os.environ.get(_ENV_OVERRIDE)
    if override:
        key = bytes.fromhex(override)
        if len(key) != 32:
            raise ValueError("WELLSIGN_PII_KEY_HEX must be 64 hex chars (32 bytes)")
        return key

    stored = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
    if stored:
        key = bytes.fromhex(stored)
        if len(key) != 32:
            raise ValueError("Stored PII master key is corrupt — wrong length")
        return key

    raise MasterKeyMissingError(
        "WellSign encryption master key is missing from the keyring. "
        "Restart the app — healthcheck_master_key() should auto-generate it "
        "on a fresh install or refuse to start cleanly otherwise."
    )


_master_key: bytes | None = None


def _key() -> bytes:
    global _master_key
    if _master_key is None:
        _master_key = _load_or_create_master_key()
    return _master_key


def encrypt_pii(plaintext: str | None) -> str | None:
    """Encrypt a PII string. Returns None if input is None or empty."""
    if plaintext is None or plaintext == "":
        return None
    iv = secrets.token_bytes(12)
    aesgcm = AESGCM(_key())
    ct_with_tag = aesgcm.encrypt(iv, plaintext.encode("utf-8"), associated_data=None)
    # AESGCM returns ciphertext || tag (16-byte tag at the end)
    ct, tag = ct_with_tag[:-16], ct_with_tag[-16:]
    return f"{iv.hex()}:{tag.hex()}:{ct.hex()}"


def decrypt_pii(stored: str | None) -> str | None:
    """Decrypt a stored PII value. Returns None if input is None or empty."""
    if stored is None or stored == "":
        return None
    try:
        iv_hex, tag_hex, ct_hex = stored.split(":")
    except ValueError as e:
        raise ValueError("Encrypted PII value is malformed") from e
    iv = bytes.fromhex(iv_hex)
    tag = bytes.fromhex(tag_hex)
    ct = bytes.fromhex(ct_hex)
    aesgcm = AESGCM(_key())
    pt = aesgcm.decrypt(iv, ct + tag, associated_data=None)
    return pt.decode("utf-8")


def mask_pii(value: str | None, visible_tail: int = 4) -> str:
    """Display helper. Always returns a string. ``None`` -> empty string."""
    if not value:
        return ""
    if len(value) <= visible_tail:
        return "•" * len(value)
    return "••••" + value[-visible_tail:]
