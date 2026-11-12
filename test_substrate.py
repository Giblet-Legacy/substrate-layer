"""
test_substrate.py — P9 Substrate test suite

Function:
    Executable expression of SPEC.md. Written before substrate.py per
    build discipline.

Layer:    P9 — Substrate
Spec:     SPEC.md v1.0.0
Licence:  MSL-1.0
"""

import os
import sys
import sqlite3
import tempfile
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, os.path.abspath('../envelope-layer'))
sys.path.insert(0, os.path.abspath('../sign-layer'))

import substrate

@pytest.fixture
def key():
    return Ed25519PrivateKey.generate()

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    yield path
    if os.path.exists(path):
        os.remove(path)

def test_init_db(temp_db):
    substrate.init_db(temp_db)
    conn = sqlite3.connect(temp_db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "claims" in tables
    assert "evidence" in tables
    conn.close()

def test_write_and_get_claim(temp_db, key):
    substrate.init_db(temp_db)
    claim = {"subject": "sky", "predicate": "is", "object": "blue"}
    cid = substrate.write_claim(temp_db, claim, key)
    assert isinstance(cid, str)
    assert len(cid) == 64

    got = substrate.get_claim(temp_db, cid)
    assert got is not None
    assert got["subject"] == "sky"
    assert "signature" in got

def test_get_claim_not_found(temp_db, key):
    substrate.init_db(temp_db)
    assert substrate.get_claim(temp_db, "0" * 64) is None

def test_supersede_claim(temp_db, key):
    substrate.init_db(temp_db)
    old = {"subject": "sky", "predicate": "is", "object": "blue"}
    new = {"subject": "sky", "predicate": "is", "object": "grey"}
    old_id = substrate.write_claim(temp_db, old, key)
    new_id = substrate.supersede_claim(temp_db, old_id, new, key)

    conn = sqlite3.connect(temp_db)
    old_row = conn.execute(
        "SELECT is_active, superseded_by FROM claims WHERE claim_id=?", (old_id,)
    ).fetchone()
    assert old_row[0] == 0
    assert old_row[1] == new_id

    new_row = conn.execute(
        "SELECT is_active FROM claims WHERE claim_id=?", (new_id,)
    ).fetchone()
    assert new_row[0] == 1
    conn.close()

def test_link_and_list_evidence(temp_db, key):
    substrate.init_db(temp_db)
    claim = {"subject": "sky", "predicate": "is", "object": "blue"}
    cid = substrate.write_claim(temp_db, claim, key)

    ev = {"source": "observation", "content": "looked up"}
    eid = substrate.link_evidence(temp_db, cid, ev, key)
    assert isinstance(eid, str)
    assert len(eid) == 64

    evs = substrate.list_evidence(temp_db, cid)
    assert len(evs) == 1
    assert evs[0]["source"] == "observation"

def test_list_evidence_empty(temp_db, key):
    substrate.init_db(temp_db)
    claim = {"subject": "sky", "predicate": "is", "object": "blue"}
    cid = substrate.write_claim(temp_db, claim, key)
    assert substrate.list_evidence(temp_db, cid) == []
