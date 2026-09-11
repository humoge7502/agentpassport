"""Crypto primitives: canonical JSON, sign/verify, tamper detection."""

from __future__ import annotations

import json

from app.domain import crypto


def test_canonical_json_is_deterministic():
    a = crypto.canonical_json({"b": 1, "a": {"y": 2, "x": 1}})
    b = crypto.canonical_json({"a": {"x": 1, "y": 2}, "b": 1})
    assert a == b
    assert b == b'{"a":{"x":1,"y":2},"b":1}'


def test_sign_verify_roundtrip():
    kp = crypto.KeyPair.generate()
    payload = {"event_id": "e1", "seq": 1}
    sig = crypto.sign_payload(kp.private_b64, payload)
    assert crypto.verify_payload(kp.public_b64, payload, sig)


def test_tampered_payload_fails():
    kp = crypto.KeyPair.generate()
    payload = {"event_id": "e1", "seq": 1}
    sig = crypto.sign_payload(kp.private_b64, payload)
    tampered = {"event_id": "e1", "seq": 2}
    assert not crypto.verify_payload(kp.public_b64, tampered, sig)


def test_wrong_key_fails():
    kp1 = crypto.KeyPair.generate()
    kp2 = crypto.KeyPair.generate()
    payload = {"x": 1}
    sig = crypto.sign_payload(kp1.private_b64, payload)
    assert not crypto.verify_payload(kp2.public_b64, payload, sig)


def test_garbage_signature_fails_cleanly():
    kp = crypto.KeyPair.generate()
    assert not crypto.verify_payload(kp.public_b64, {"x": 1}, "not-base64!!")
    assert not crypto.verify_payload(kp.public_b64, {"x": 1}, "AAAA")


def test_key_file_store_roundtrip(tmp_path):
    store = crypto.KeyFileStore(tmp_path)
    kp = crypto.KeyPair.generate()
    store.put("k1", kp.private_b64)
    assert store.get("k1") == kp.private_b64
    assert store.get("missing") is None
    store.delete("k1")
    assert store.get("k1") is None


def test_fingerprint_stable():
    kp = crypto.KeyPair.generate()
    assert crypto.fingerprint(kp.public_b64) == crypto.fingerprint(kp.public_b64)
    assert len(crypto.fingerprint(kp.public_b64)) == 16
