"""Dev-only license-key minting helper.

Used by ``scripts/mint_license.py`` to issue keys for projects. The private
key file lives outside the repo and is supplied via ``--private-key`` or the
``WELLSIGN_LICENSE_PRIVATE_KEY`` env var.

This module is intentionally not imported by the running app — operators
should never have access to the minting code path.
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def generate_keypair(out_dir: Path, name: str = "license") -> tuple[Path, Path]:
    """Create a fresh RSA-3072 keypair for license signing.

    Writes ``<name>_private_key.pem`` and ``<name>_public_key.pem`` to ``out_dir``.
    Run this exactly once at project setup; commit ONLY the public key.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    priv_path = out_dir / f"{name}_private_key.pem"
    pub_path = out_dir / f"{name}_public_key.pem"

    priv_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    pub_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return priv_path, pub_path


def mint_license(
    private_key_path: Path,
    customer: str,
    project_name: str,
    valid_for_days: int = 365,
) -> dict:
    """Build and sign a license envelope. Returns the dict ready to be written."""
    private_key = serialization.load_pem_private_key(
        private_key_path.read_bytes(), password=None
    )
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise TypeError("Private key file is not RSA")

    now = datetime.now(timezone.utc)
    payload = {
        "key_id": str(uuid.uuid4()),
        "customer": customer,
        "project_name": project_name,
        "issued_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(days=valid_for_days)).isoformat().replace("+00:00", "Z"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = private_key.sign(
        canonical,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    return {"payload": payload, "signature": base64.b64encode(signature).decode("ascii")}
