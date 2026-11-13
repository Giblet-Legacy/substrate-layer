"""
test_substrate_v4.py — P9 Substrate v4 (entities and subjects) test suite

Function:
    Executable expression of SPEC_V4.md. Written before
    substrate_v4.py and run red first.

Functions in this file (pytest-collected):
    1. test_v3_reexports
    2. test_init_db_upgrades_v3_database
    3. test_add_entity_and_subject
    4. test_names_are_checked
    5. test_add_member
    6. test_members_subjects_of_find
    7. test_claims_about
    8. test_unregistered
    9. test_reads_are_read_only_and_verify

Helpers:
    10. db    — fixture: a v4 database with four claims
    11. _claim — write one affirmed FACT claim

Layer:    P9 — Substrate, v4
Spec:     SPEC_V4.md 4.0.0
Licence:  MSL-1.0
Author:   James Gilbert (Giblets Forge)
"""

import sqlite3

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import substrate_v3
import substrate_v4 as s4

KEY = Ed25519PrivateKey.generate()


# 11. _claim
def _claim(path, subject, obj, text):
    return s4.write_claim(path, {"subject": subject, "object": obj, "FACT": text,
                                 "face": "FACT", "polarity": "affirm"}, KEY)


# 10. db
@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "forge.db")
    s4.init_db(path)
    ids = {
        "ledger": _claim(path, "ledger-layer", "P4", "The hash-chained ledger"),
        "ledger2": _claim(path, "Ledger-Layer ", "status", "Frozen 2.0.0"),
        "m5": _claim(path, "M5StickC Plus2", "ESP32", "An ESP32 device"),
        "pi": _claim(path, "Raspberry Pi", "SoC", "A single-board computer"),
    }
    return path, ids


# 1. test_v3_reexports
def test_v3_reexports():
    for name in ("write_claim", "get_claim", "supersede_claim", "link_evidence", "list_evidence",
                 "list_claims", "read_claim", "read_evidence", "link_attestation", "latest_attestation"):
        assert getattr(s4, name) is getattr(substrate_v3, name)


# 2. test_init_db_upgrades_v3_database
def test_init_db_upgrades_v3_database(tmp_path):
    path = str(tmp_path / "old.db")
    substrate_v3.init_db(path)
    cid = _claim(path, "sky", "blue", "The sky is blue")
    assert s4.list_entities(path) == [] and s4.list_subjects(path) == []
    assert s4.find(path, "sky") is None and s4.unregistered(path) == ["sky"]
    s4.init_db(path)
    s4.init_db(path)  # idempotent
    assert [r["claim_id"] for r in s4.list_claims(path)] == [cid]
    tables = {r[0] for r in sqlite3.connect(path).execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"claims", "evidence", "entities", "subjects", "memberships"} <= tables


# 3. test_add_entity_and_subject
def test_add_entity_and_subject(db):
    path, _ = db
    eid = s4.add_entity(path, "  M5StickC Plus2 ", KEY, kind="device")
    sid = s4.add_subject(path, "hardware", KEY)
    assert s4.add_entity(path, "m5stickc plus2", KEY, kind="other") == eid  # exists once
    assert s4.add_subject(path, "HARDWARE", KEY) == sid
    [e] = s4.list_entities(path, verify=True)
    assert e == {**e, "id": eid, "type": "entity", "name": "M5StickC Plus2", "kind": "device", "verified": True}
    assert e["signer"].startswith("did:key:") and e["capsule"]["type"] == "entity"
    [s] = s4.list_subjects(path, verify=True)
    assert (s["id"], s["type"], s["name"], s["kind"], s["verified"]) == (sid, "subject", "hardware", None, True)


# 4. test_names_are_checked
def test_names_are_checked(db):
    path, _ = db
    s4.add_subject(path, "hardware", KEY)
    s4.add_entity(path, "Raspberry Pi", KEY)
    with pytest.raises(ValueError):
        s4.add_entity(path, "Hardware", KEY)  # taken by a subject
    with pytest.raises(ValueError):
        s4.add_subject(path, "raspberry pi", KEY)  # taken by an entity
    for bad in ("", "   ", "x" * 201, None, 7):
        with pytest.raises(ValueError):
            s4.add_entity(path, bad, KEY)
    for bad in ("", "k" * 61, 3):
        with pytest.raises(ValueError):
            s4.add_subject(path, "software", KEY, kind=bad)
    assert len(s4.list_entities(path)) == 1 and len(s4.list_subjects(path)) == 1


# 5. test_add_member
def test_add_member(db):
    path, _ = db
    sid = s4.add_subject(path, "hardware", KEY)
    eid = s4.add_entity(path, "M5StickC Plus2", KEY)
    mid = s4.add_member(path, sid, eid, KEY)
    assert s4.add_member(path, sid, eid, KEY) == mid
    with pytest.raises(KeyError):
        s4.add_member(path, "nope", eid, KEY)
    with pytest.raises(KeyError):
        s4.add_member(path, sid, "nope", KEY)
    with pytest.raises(KeyError):
        s4.add_member(path, eid, sid, KEY)  # swapped: an entity is not a subject
    assert sqlite3.connect(path).execute("SELECT COUNT(*) FROM memberships").fetchone()[0] == 1


# 6. test_members_subjects_of_find
def test_members_subjects_of_find(db):
    path, _ = db
    hw = s4.add_subject(path, "hardware", KEY)
    boards = s4.add_subject(path, "boards", KEY)
    m5 = s4.add_entity(path, "M5StickC Plus2", KEY)
    pi = s4.add_entity(path, "Raspberry Pi", KEY)
    for sid, eid in ((hw, m5), (hw, pi), (boards, pi)):
        s4.add_member(path, sid, eid, KEY)
    assert [r["id"] for r in s4.members(path, hw)] == [m5, pi]
    assert [r["id"] for r in s4.subjects_of(path, pi)] == [hw, boards]
    assert s4.members(path, "nope") == [] and s4.subjects_of(path, "nope") == []
    assert s4.find(path, " RASPBERRY PI ")["id"] == pi and s4.find(path, "Hardware")["type"] == "subject"
    assert s4.find(path, "nothing") is None


# 7. test_claims_about
def test_claims_about(db):
    path, ids = db
    assert [r["claim_id"] for r in s4.claims_about(path, "LEDGER-LAYER")] == [ids["ledger"], ids["ledger2"]]
    assert s4.claims_about(path, "unheard of") == []
    hw = s4.add_subject(path, "hardware", KEY)
    hw_claim = _claim(path, "hardware", "bench", "Everything on the bench")
    for name in ("M5StickC Plus2", "Raspberry Pi"):
        s4.add_member(path, hw, s4.add_entity(path, name, KEY), KEY)
    got = [r["claim_id"] for r in s4.claims_about(path, "hardware")]
    assert got == [hw_claim, ids["m5"], ids["pi"]]
    new = s4.supersede_claim(path, ids["pi"], {"subject": "Raspberry Pi", "object": "SoC", "FACT": "A Pi 5",
                                               "face": "FACT", "polarity": "affirm"}, KEY)
    assert [r["claim_id"] for r in s4.claims_about(path, "hardware")] == [hw_claim, ids["m5"], new]


# 8. test_unregistered
def test_unregistered(db):
    path, _ = db
    assert s4.unregistered(path) == ["ledger-layer", "M5StickC Plus2", "Raspberry Pi"]
    s4.add_subject(path, "ledger-layer", KEY, kind="repo")
    s4.add_entity(path, "raspberry pi", KEY)
    assert s4.unregistered(path) == ["M5StickC Plus2"]


# 9. test_reads_are_read_only_and_verify
def test_reads_are_read_only_and_verify(db):
    path, _ = db
    sid = s4.add_subject(path, "hardware", KEY)
    eid = s4.add_entity(path, "M5StickC Plus2", KEY)
    s4.add_member(path, sid, eid, KEY)
    before = open(path, "rb").read()
    for read in (lambda: s4.list_entities(path, verify=True), lambda: s4.list_subjects(path, verify=True),
                 lambda: s4.members(path, sid), lambda: s4.subjects_of(path, eid), lambda: s4.find(path, "x"),
                 lambda: s4.claims_about(path, "hardware"), lambda: s4.unregistered(path)):
        read()
    assert open(path, "rb").read() == before
    with pytest.raises(FileNotFoundError):
        s4.list_entities(path + ".missing")
    conn = sqlite3.connect(path)
    conn.execute("UPDATE entities SET capsule = replace(capsule, 'M5StickC', 'M6StickC')")
    conn.commit()
    conn.close()
    [row] = s4.list_entities(path, verify=True)
    assert row["verified"] is False and row["verify_error"]
