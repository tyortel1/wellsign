"""AES-256-GCM encryption for investor PII columns.

Master key is stored in the OS keyring (Windows Credential Manager on Windows)
under service ``wellsign.pii``. The key never touches disk and never appears in
source code or logs. On first use, a fresh 32-byte key is generated.

Storage format for an encrypted value: ``<iv_hex>:<tag_hex>:<ct_hex>``.
"""

from __future__ import annotations

import os
import secrets

import keyring
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_KEYRING_SERVICE = "wellsign.pii"
_KEYRING_USER = "master_key"
_ENV_OVERRIDE = "WELLSIGN_PII_KEY_HEX"  # for tests / CI only


def _load_or_create_master_key() -> bytes:
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

    key = secrets.token_bytes(32)
    keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, key.hex())
    return key


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
