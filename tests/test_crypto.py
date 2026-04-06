"""Smoke tests for the PII crypto helpers (uses an env-var key, no keyring)."""

from __future__ import annotations

import os

import pytest

os.environ["WELLSIGN_PII_KEY_HEX"] = "00" * 32

from wellsign.util import crypto  # noqa: E402


def test_roundtrip():
    pt = "123-45-6789"
    ct = crypto.encrypt_pii(pt)
    assert ct is not None and ct != pt
    assert crypto.decrypt_pii(ct) == pt


def test_none_and_empty():
    assert crypto.encrypt_pii(None) is None
    assert crypto.encrypt_pii("") is None
    assert crypto.decrypt_pii(None) is None
    assert crypto.decrypt_pii("") is None


def test_mask():
    assert crypto.mask_pii("123456789") == "••••6789"
    assert crypto.mask_pii(None) == ""
    assert crypto.mask_pii("12") == "••"


def test_tampered_ciphertext_raises():
    ct = crypto.encrypt_pii("hello")
    iv, tag, body = ct.split(":")
    tampered = f"{iv}:{tag}:{body[:-2]}ff"
    with pytest.raises(Exception):
        crypto.decrypt_pii(tampered)
