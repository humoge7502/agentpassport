"""Cryptographic primitives for AgentPassport.

Ed25519 (PyNaCl/libsodium) signing with canonical JSON serialization.
Canonical form: sorted keys, tight separators, UTF-8 — applied to an
explicit field whitelist chosen by the caller (never `**obj`).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

B64 = base64.b64encode
B64D = base64.b64decode


def canonical_json(payload: dict) -> bytes:
    """Deterministic serialization used for hashing and signing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_hash(payload: dict) -> str:
    return sha256_hex(canonical_json(payload))


@dataclass(frozen=True)
class KeyPair:
    """Ed25519 key pair; `private_b64`/`public_b64` are base64-encoded raw keys."""

    public_b64: str
    private_b64: str

    @staticmethod
    def generate() -> "KeyPair":
        sk = SigningKey.generate()
        return KeyPair(
            public_b64=base64.b64encode(bytes(sk.verify_key)).decode(),
            private_b64=base64.b64encode(bytes(sk)).decode(),
        )


def sign_bytes(private_b64: str, message: bytes) -> str:
    sk = SigningKey(base64.b64decode(private_b64))
    return base64.b64encode(sk.sign(message).signature).decode()


def verify_bytes(public_b64: str, message: bytes, signature_b64: str) -> bool:
    try:
        vk = VerifyKey(base64.b64decode(public_b64))
        vk.verify(message, base64.b64decode(signature_b64))
        return True
    except (BadSignatureError, ValueError, TypeError):
        return False


def sign_payload(private_b64: str, payload: dict) -> str:
    """Sign the canonical JSON of a whitelist-built payload dict."""
    return sign_bytes(private_b64, canonical_json(payload))


def verify_payload(public_b64: str, payload: dict, signature_b64: str) -> bool:
    return verify_bytes(public_b64, canonical_json(payload), signature_b64)


def fingerprint(public_b64: str) -> str:
    """Stable short fingerprint of a public key (first 16 hex chars of SHA-256)."""
    return sha256_hex(base64.b64decode(public_b64))[:16]


class KeyFileStore:
    """File-based private-key storage for server-managed keys (dev/demo).

    Production deployments must inject keys from a secret manager instead;
    see SECURITY.md ("Key custody"). Files are written with restrictive
    permissions; the directory is created on first use.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key_id: str) -> Path:
        safe = key_id.replace("/", "_").replace("\\", "_")
        return self.root / f"{safe}.key"

    def put(self, key_id: str, private_b64: str) -> None:
        p = self._path(key_id)
        p.write_text(private_b64, encoding="utf-8")
        if os.name == "posix":
            p.chmod(0o600)

    def get(self, key_id: str) -> str | None:
        p = self._path(key_id)
        if not p.exists():
            return None
        return p.read_text(encoding="utf-8").strip()

    def delete(self, key_id: str) -> None:
        p = self._path(key_id)
        if p.exists():
            p.unlink()
