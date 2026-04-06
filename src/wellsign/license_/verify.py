"""Offline license-key verification (RSA-PSS over canonical JSON)."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


class LicenseError(Exception):
    """Raised when a license file is missing, malformed, expired, or unsigned."""


@dataclass(frozen=True)
class LicensePayload:
    key_id: str
    customer: str
    project_name: str
    issued_at: datetime
    expires_at: datetime
    raw_bytes: bytes  # the canonical JSON we verified — used for hashing/binding

    @property
    def key_hash(self) -> str:
        return hashlib.sha256(self.raw_bytes).hexdigest()


def _canonical_payload_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _load_public_key() -> rsa.RSAPublicKey:
    """Load the bundled public key from package resources.

    For the POC the public key file is shipped at
    ``src/wellsign/resources/license_public_key.pem``. ``scripts/mint_license.py``
    is responsible for generating the matching private key (kept out of git).
    """
    pem = resources.files("wellsign.resources").joinpath("license_public_key.pem").read_bytes()
    key = serialization.load_pem_public_key(pem)
    if not isinstance(key, rsa.RSAPublicKey):
        raise LicenseError("Bundled license public key is not RSA")
    return key


def verify_license_file(path: Path) -> LicensePayload:
    """Read, verify, and return a license payload. Raises ``LicenseError``."""
    if not path.exists():
        raise LicenseError(f"License file not found: {path}")
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        payload = envelope["payload"]
        signature_b64 = envelope["signature"]
    except (KeyError, json.JSONDecodeError) as e:
        raise LicenseError("License file is malformed") from e

    canonical = _canonical_payload_bytes(payload)
    signature = base64.b64decode(signature_b64)

    public_key = _load_public_key()
    try:
        public_key.verify(
            signature,
            canonical,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
    except InvalidSignature as e:
        raise LicenseError("License signature is invalid") from e

    try:
        issued_at = _parse_iso(payload["issued_at"])
        expires_at = _parse_iso(payload["expires_at"])
    except KeyError as e:
        raise LicenseError("License payload is missing required fields") from e

    if expires_at < datetime.now(timezone.utc):
        raise LicenseError(f"License expired on {expires_at.date().isoformat()}")

    return LicensePayload(
        key_id=str(payload.get("key_id", "")),
        customer=str(payload.get("customer", "")),
        project_name=str(payload.get("project_name", "")),
        issued_at=issued_at,
        expires_at=expires_at,
        raw_bytes=canonical,
    )


def _parse_iso(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
