"""
test_substrate_v3.py — P9 Substrate v3 (read and attestation layer) test suite

Function:
    Executable expression of SPEC_V3.md. Written before
    substrate_v3.py and run red first.

Functions in this file (pytest-collected):
    1. test_v2_reexports
    2. test_list_claims
    3. test_reads_are_read_only
    4. test_verify_marks_tampered_rows
    5. test_read_claim
    6. test_link_attestation_approve_and_refuse
    7. test_link_attestation_rejects_bad_seals
    8. test_latest_attestation

Helpers:
    9.  _seal — a P2-signed seal-shaped capsule
    10. db    — fixture: initialised database with three claims, one superseded

Layer:    P9 — Substrate, v3
Spec:     SPEC_V3.md 3.0.0
Licence:  MSL-1.0
Author:   James Gilbert (Giblets Forge)
"""

import sqlite3

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import sign_v2
import substrate_v2
import substrate_v3 as s3

KEY = Ed25519PrivateKey.generate()


# 9. _seal
def _seal(decision="approve", key=KEY):
    return sign_v2.sign_capsule({
        "decision": decision, "action_type": "claim", "subject_id": "x",
        "rationale": "checked by hand", "timestamp": 1_700_000_000.0,
        "signature": None,
    }, key)


# 10. db
@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "forge.db")
    s3.init_db(path)
    a = s3.write_claim(path, {"subject": "sky", "object": "blue"}, KEY)
    b = s3.supersede_claim(path, a, {"subject": "sky", "object": "grey"}, KEY)
    c = s3.write_claim(path, {"subject": "sea", "object": "deep"}, KEY)
    return path, a, b, c


# 1. test_v2_reexports
def test_v2_reexports():
    for name in ("init_db", "write_claim", "get_claim", "supersede_claim",
                 "link_evidence", "list_evidence"):
        assert getattr(s3, name) is getattr(substrate_v2, name)


# 2. test_list_claims
def test_list_claims(db):
    path, a, b, c = db
    active = s3.list_claims(path)
    assert [r["claim_id"] for r in active] == [b, c]
    every = s3.list_claims(path, active_only=False)
    assert [r["claim_id"] for r in every] == [a, b, c]
    row = every[0]
    assert set(row) == {"claim_id", "signer", "capsule", "is_active", "superseded_by", "created_at"}
    assert row["is_active"] is False and row["superseded_by"] == b
    assert row["capsule"]["object"] == "blue"


# 3. test_reads_are_read_only
def test_reads_are_read_only(db, tmp_path):
    path, a, _, _ = db
    before = open(path, "rb").read()
    s3.list_claims(path, verify=True)
    s3.read_claim(path, a)
    s3.read_evidence(path, a)
    s3.latest_attestation(path, a)
    assert open(path, "rb").read() == before
    missing = tmp_path / "absent.db"
    with pytest.raises(FileNotFoundError):
        s3.list_claims(str(missing))
    assert not missing.exists()


# 4. test_verify_marks_tampered_rows
def test_verify_marks_tampered_rows(db):
    path, _, b, c = db
    conn = sqlite3.connect(path)
    with conn:
        text = conn.execute("SELECT capsule FROM claims WHERE claim_id=?", (c,)).fetchone()[0]
        conn.execute("UPDATE claims SET capsule=? WHERE claim_id=?", (text.replace("deep", "shallow"), c))
    conn.close()
    rows = {r["claim_id"]: r for r in s3.list_claims(path, verify=True)}
    assert rows[b]["verified"] is True and rows[b]["verify_error"] is None
    assert rows[c]["verified"] is False and rows[c]["verify_error"]


# 5. test_read_claim
def test_read_claim(db):
    path, a, b, _ = db
    assert s3.read_claim(path, a)["superseded_by"] == b
    assert s3.read_claim(path, b, verify=True)["verified"] is True
    assert s3.read_claim(path, "0" * 64) is None


# 6. test_link_attestation_approve_and_refuse
def test_link_attestation_approve_and_refuse(db):
    path, _, b, c = db
    s3.link_attestation(path, b, _seal("approve"), KEY)
    s3.link_attestation(path, c, _seal("refuse"), KEY)
    ev_b = s3.read_evidence(path, b, verify=True)[0]
    assert ev_b["verified"] is True
    cap = ev_b["capsule"]
    assert cap["kind"] == "attestation" and cap["decision"] == "approve"
    assert cap["by"] == _seal()["signature"]["key_id"]
    assert cap["note"] == "checked by hand" and cap["at"] == 1_700_000_000.0
    assert cap["seal"] == _seal("approve")
    assert s3.read_evidence(path, c)[0]["capsule"]["kind"] == "refusal"


# 7. test_link_attestation_rejects_bad_seals
def test_link_attestation_rejects_bad_seals(db):
    path, _, b, _ = db
    unsigned = dict(_seal(), signature=None)
    tampered = dict(_seal(), rationale="changed")
    wrong_decision = sign_v2.sign_capsule(dict(_seal(), decision="maybe", signature=None), KEY)
    for bad in (unsigned, tampered, wrong_decision, "not a dict"):
        with pytest.raises(ValueError):
            s3.link_attestation(path, b, bad, KEY)
    assert s3.read_evidence(path, b) == []
    with pytest.raises(KeyError):
        s3.link_attestation(path, "0" * 64, _seal(), KEY)


# 8. test_latest_attestation
def test_latest_attestation(db):
    path, _, b, c = db
    assert s3.latest_attestation(path, b) is None
    s3.link_evidence(path, b, {"kind": "note", "text": "unrelated"}, KEY)
    s3.link_attestation(path, b, _seal("approve"), KEY)
    other = Ed25519PrivateKey.generate()
    s3.link_attestation(path, b, _seal("refuse", other), KEY)
    assert s3.latest_attestation(path, b)["kind"] == "refusal"
    assert s3.latest_attestation(path, c) is None
