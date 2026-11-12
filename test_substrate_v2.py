"""
test_substrate_v2.py — P9 Substrate v2 (strict layer) test suite

Function:
    Executable expression of SPEC_V2.md §5. Written before
    substrate_v2.py and run red first. Proves two things: (1) v2 stays
    compatible with the frozen v1 primitive, so ids, stored text and
    databases are shared; (2) v2 rejects, returns the existing id, or
    verifies where SPEC_V2 requires and v1 did not (NOTES.md D1–D7).

Functions in this file:
    Fixtures and helpers:
    1.  key                                  — fresh Ed25519 private key
    2.  db                                   — initialised temp database
    3.  _rows                                — read claims table rows
    4.  _tamper                              — rewrite a stored capsule
    Tests (pytest-collected):
    5.  test_public_api                      — six names, all callable
    6.  test_ids_and_storage_match_v1        — same id and stored text
    7.  test_v1_database_read_by_v2          — v1 rows verify under v2
    8.  test_write_claim_idempotent          — D3
    9.  test_write_claim_keeps_superseded    — duplicate leaves state
    10. test_supersede_ok                    — SPEC §3.4 still holds
    11. test_supersede_missing_old           — D4: KeyError, no write
    12. test_supersede_twice_rejected        — D5: no fork
    13. test_supersede_identical_rejected    — ValueError, rolled back
    14. test_link_evidence_missing_claim     — D6: KeyError
    15. test_link_evidence_idempotent        — same claim, same id
    16. test_link_evidence_other_claim       — ValueError
    17. test_link_evidence_to_superseded     — allowed
    18. test_evidence_order_deterministic    — D7
    19. test_get_claim_verify_ok             — verify passes, None kept
    20. test_get_claim_verify_tamper         — every check raises
    21. test_list_evidence_verify            — ok and tamper
    22. test_storage_lf_free                 — no raw CR or LF
    23. test_import_from_any_cwd             — D1

Layer:    P9 — Substrate, v2 (strict)
Spec:     SPEC_V2.md 2.0.0 (over SPEC.md v1.0.0)
Licence:  MSL-1.0
Author:   James Gilbert (Giblets Forge)
"""

import json
import os
import sqlite3
import subprocess
import sys

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import envelope_v2
import substrate as v1
import substrate_v2 as v2

_HERE = os.path.dirname(os.path.abspath(__file__))
SKY = {"subject": "sky", "predicate": "is", "object": "blue"}


# ---------------------------------------------------------------------------
# 1. key
# ---------------------------------------------------------------------------
@pytest.fixture
def key():
    return Ed25519PrivateKey.generate()


# ---------------------------------------------------------------------------
# 2. db
# ---------------------------------------------------------------------------
@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "substrate.db")
    v2.init_db(path)
    return path


# ---------------------------------------------------------------------------
# 3. _rows
# ---------------------------------------------------------------------------
def _rows(db):
    conn = sqlite3.connect(db)
    try:
        return {
            r[0]: (r[1], r[2])
            for r in conn.execute(
                "SELECT claim_id, is_active, superseded_by FROM claims"
            )
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 4. _tamper
# ---------------------------------------------------------------------------
def _tamper(db, table, id_col, row_id, text):
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            f"UPDATE {table} SET capsule=? WHERE {id_col}=?", (text, row_id)
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 5. test_public_api
# ---------------------------------------------------------------------------
def test_public_api():
    for name in ("init_db", "write_claim", "get_claim", "supersede_claim",
                 "link_evidence", "list_evidence"):
        assert callable(getattr(v2, name))
    assert v2.init_db is v1.init_db


# ---------------------------------------------------------------------------
# 6. test_ids_and_storage_match_v1
# ---------------------------------------------------------------------------
def test_ids_and_storage_match_v1(tmp_path, key):
    a, b = str(tmp_path / "a.db"), str(tmp_path / "b.db")
    v1.init_db(a)
    v2.init_db(b)
    claim = {"subject": "café", "n": [1, 2, {"z": None}]}
    assert v1.write_claim(a, claim, key) == v2.write_claim(b, claim, key)
    ta = sqlite3.connect(a).execute("SELECT capsule FROM claims").fetchone()
    tb = sqlite3.connect(b).execute("SELECT capsule FROM claims").fetchone()
    assert ta == tb


# ---------------------------------------------------------------------------
# 7. test_v1_database_read_by_v2
# ---------------------------------------------------------------------------
def test_v1_database_read_by_v2(db, key):
    cid = v1.write_claim(db, SKY, key)
    eid = v1.link_evidence(db, cid, {"source": "eye"}, key)
    assert v2.get_claim(db, cid, verify=True)["object"] == "blue"
    evs = v2.list_evidence(db, cid, verify=True)
    assert len(evs) == 1 and evs[0]["source"] == "eye"
    assert envelope_v2.sha256_hex(envelope_v2.canonical_bytes(evs[0])) == eid


# ---------------------------------------------------------------------------
# 8. test_write_claim_idempotent
# ---------------------------------------------------------------------------
def test_write_claim_idempotent(db, key):
    a = v2.write_claim(db, SKY, key)
    b = v2.write_claim(db, SKY, key)
    assert a == b
    assert len(_rows(db)) == 1


# ---------------------------------------------------------------------------
# 9. test_write_claim_keeps_superseded
# ---------------------------------------------------------------------------
def test_write_claim_keeps_superseded(db, key):
    old = v2.write_claim(db, SKY, key)
    new = v2.supersede_claim(db, old, {"sky": "grey"}, key)
    assert v2.write_claim(db, SKY, key) == old
    assert _rows(db)[old] == (0, new)


# ---------------------------------------------------------------------------
# 10. test_supersede_ok
# ---------------------------------------------------------------------------
def test_supersede_ok(db, key):
    old = v2.write_claim(db, SKY, key)
    new = v2.supersede_claim(db, old, {"sky": "grey"}, key)
    rows = _rows(db)
    assert rows[old] == (0, new)
    assert rows[new] == (1, None)
    assert v2.get_claim(db, old) is not None  # history preserved


# ---------------------------------------------------------------------------
# 11. test_supersede_missing_old
# ---------------------------------------------------------------------------
def test_supersede_missing_old(db, key):
    with pytest.raises(KeyError):
        v2.supersede_claim(db, "f" * 64, SKY, key)
    assert _rows(db) == {}


# ---------------------------------------------------------------------------
# 12. test_supersede_twice_rejected
# ---------------------------------------------------------------------------
def test_supersede_twice_rejected(db, key):
    a = v2.write_claim(db, SKY, key)
    b = v2.supersede_claim(db, a, {"sky": "grey"}, key)
    with pytest.raises(ValueError):
        v2.supersede_claim(db, a, {"sky": "red"}, key)
    rows = _rows(db)
    assert len(rows) == 2
    assert rows[a] == (0, b)
    assert rows[b] == (1, None)


# ---------------------------------------------------------------------------
# 13. test_supersede_identical_rejected
# ---------------------------------------------------------------------------
def test_supersede_identical_rejected(db, key):
    a = v2.write_claim(db, SKY, key)
    with pytest.raises(ValueError):
        v2.supersede_claim(db, a, dict(SKY), key)
    b = v2.write_claim(db, {"other": 1}, key)
    with pytest.raises(ValueError):
        v2.supersede_claim(db, a, {"other": 1}, key)
    rows = _rows(db)
    assert rows[a] == (1, None)
    assert rows[b] == (1, None)


# ---------------------------------------------------------------------------
# 14. test_link_evidence_missing_claim
# ---------------------------------------------------------------------------
def test_link_evidence_missing_claim(db, key):
    with pytest.raises(KeyError):
        v2.link_evidence(db, "f" * 64, {"source": "eye"}, key)
    assert v2.list_evidence(db, "f" * 64) == []


# ---------------------------------------------------------------------------
# 15. test_link_evidence_idempotent
# ---------------------------------------------------------------------------
def test_link_evidence_idempotent(db, key):
    cid = v2.write_claim(db, SKY, key)
    a = v2.link_evidence(db, cid, {"source": "eye"}, key)
    b = v2.link_evidence(db, cid, {"source": "eye"}, key)
    assert a == b
    assert len(v2.list_evidence(db, cid)) == 1


# ---------------------------------------------------------------------------
# 16. test_link_evidence_other_claim
# ---------------------------------------------------------------------------
def test_link_evidence_other_claim(db, key):
    c1 = v2.write_claim(db, SKY, key)
    c2 = v2.write_claim(db, {"other": 1}, key)
    v2.link_evidence(db, c1, {"source": "eye"}, key)
    with pytest.raises(ValueError):
        v2.link_evidence(db, c2, {"source": "eye"}, key)
    assert v2.list_evidence(db, c2) == []


# ---------------------------------------------------------------------------
# 17. test_link_evidence_to_superseded
# ---------------------------------------------------------------------------
def test_link_evidence_to_superseded(db, key):
    old = v2.write_claim(db, SKY, key)
    v2.supersede_claim(db, old, {"sky": "grey"}, key)
    v2.link_evidence(db, old, {"source": "photo"}, key)
    assert len(v2.list_evidence(db, old)) == 1


# ---------------------------------------------------------------------------
# 18. test_evidence_order_deterministic
# ---------------------------------------------------------------------------
def test_evidence_order_deterministic(db, key):
    cid = v2.write_claim(db, SKY, key)
    ids = [v2.link_evidence(db, cid, {"n": i}, key) for i in range(5)]
    conn = sqlite3.connect(db)
    conn.execute("UPDATE evidence SET created_at='2026-01-01T00:00:00+00:00'")
    conn.commit()
    conn.close()
    assert [e["n"] for e in v2.list_evidence(db, cid)] == list(range(5))
    assert len(ids) == 5


# ---------------------------------------------------------------------------
# 19. test_get_claim_verify_ok
# ---------------------------------------------------------------------------
def test_get_claim_verify_ok(db, key):
    cid = v2.write_claim(db, SKY, key)
    assert v2.get_claim(db, cid, verify=True) == v2.get_claim(db, cid)
    assert v2.get_claim(db, "0" * 64, verify=True) is None


# ---------------------------------------------------------------------------
# 20. test_get_claim_verify_tamper
# ---------------------------------------------------------------------------
def test_get_claim_verify_tamper(db, key):
    cid = v2.write_claim(db, SKY, key)
    good = v2.get_claim(db, cid)
    other = Ed25519PrivateKey.generate()

    # 1. content changed (hash mismatch)
    bad = dict(good, object="grey")
    _tamper(db, "claims", "claim_id", cid, envelope_v2.canonicalise(bad))
    assert v2.get_claim(db, cid)["object"] == "grey"  # v1 behaviour
    with pytest.raises(ValueError):
        v2.get_claim(db, cid, verify=True)

    # 2. non-canonical text of the right content
    _tamper(db, "claims", "claim_id", cid, json.dumps(good, indent=1))
    with pytest.raises(ValueError):
        v2.get_claim(db, cid, verify=True)

    # 3. text not JSON
    _tamper(db, "claims", "claim_id", cid, "not json")
    with pytest.raises(ValueError):
        v2.get_claim(db, cid, verify=True)

    # 4. signer column does not match signature key_id
    _tamper(db, "claims", "claim_id", cid, envelope_v2.canonicalise(good))
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE claims SET signer=? WHERE claim_id=?",
        (envelope_v2.did_key_encode(other.public_key()), cid),
    )
    conn.commit()
    conn.close()
    with pytest.raises(ValueError):
        v2.get_claim(db, cid, verify=True)


# ---------------------------------------------------------------------------
# 21. test_list_evidence_verify
# ---------------------------------------------------------------------------
def test_list_evidence_verify(db, key):
    cid = v2.write_claim(db, SKY, key)
    eid = v2.link_evidence(db, cid, {"source": "eye"}, key)
    assert v2.list_evidence(db, cid, verify=True)[0]["source"] == "eye"
    good = v2.list_evidence(db, cid)[0]
    _tamper(db, "evidence", "evidence_id", eid,
            envelope_v2.canonicalise(dict(good, source="rumour")))
    with pytest.raises(ValueError):
        v2.list_evidence(db, cid, verify=True)


# ---------------------------------------------------------------------------
# 22. test_storage_lf_free
# ---------------------------------------------------------------------------
def test_storage_lf_free(db, key):
    cid = v2.write_claim(db, {"text": "line1\r\nline2\n"}, key)
    v2.link_evidence(db, cid, {"text": "a\rb\nc"}, key)
    conn = sqlite3.connect(db)
    texts = [r[0] for r in conn.execute(
        "SELECT capsule FROM claims UNION ALL SELECT capsule FROM evidence")]
    conn.close()
    for t in texts:
        assert "\r" not in t and "\n" not in t
    assert v2.get_claim(db, cid, verify=True)["text"] == "line1\r\nline2\n"


# ---------------------------------------------------------------------------
# 23. test_import_from_any_cwd
# ---------------------------------------------------------------------------
def test_import_from_any_cwd(tmp_path):
    code = (
        "import sys; sys.path.insert(0, %r); import substrate_v2; "
        "print('ok')" % _HERE
    )
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=str(tmp_path),
        capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "ok"
