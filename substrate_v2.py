"""
substrate_v2.py — P9 Substrate v2, strict layer over the frozen v1 primitive

Function:
    The layer new code imports instead of substrate.py. It keeps the
    v1 schema, ids and stored text byte-for-byte, and adds the guards
    the semantic memory graph needs: evidence cannot be orphaned,
    supersession cannot be phantom or fork the history, duplicates
    return the existing id instead of crashing, every connection is
    closed and every write is one atomic transaction. Reads can
    optionally verify the content hash and the P2 signature
    (SPEC_V2.md §2). Signing goes through P2 (sign_v2) and hashing
    through P1 (envelope_v2); no primitive is reimplemented.

    substrate.py is not edited (Immutable Rule). This file is the
    "add a layer" half of that rule.

Public API (same names and numbering as P9 v1.0.0):
    1. init_db          — re-exported from v1 unchanged
    2. write_claim      — sign, insert active; idempotent on duplicate
    3. get_claim        — fetch by id; optional verify
    4. supersede_claim  — guarded, atomic supersession
    5. link_evidence    — claim must exist; idempotent on duplicate
    6. list_evidence    — deterministic order; optional verify

Internal helpers (not exported):
    7. _connect         — connection with foreign keys on
    8. _seal            — sign via P2, return (id, canonical text)
    9. _verify_text     — hash, canonical form and signature checks

Layer:    P9 — Substrate, v2 (strict)
Depends:  substrate.py (P9 v1.0.0), envelope_v2.py (P1 v2.0.0),
          sign_v2.py (P2 v2.0.0)
Consumed: P12 Rules, P13 DataCube, SC-OS
Spec:     SPEC_V2.md 2.0.0 (over SPEC.md v1.0.0)
Version:  2.0.0
Licence:  MSL-1.0
Author:   James Gilbert (Giblets Forge)
"""

import json
import os
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone

# Locate P1 and P2 from this file, not the working directory
# (SPEC_V2 §2.1). Must run before importing substrate.py, whose own
# path insert is cwd-relative.
_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
for _p in (os.path.join(_PARENT, "envelope-layer"),
           os.path.join(_PARENT, "sign-layer"),
           _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import envelope_v2 as envelope
import sign_v2 as sign
import substrate as _v1

# ---------------------------------------------------------------------------
# 1. init_db
#    v1's function, re-exported. Schema is SPEC.md §2, unchanged.
# ---------------------------------------------------------------------------
init_db = _v1.init_db


# ---------------------------------------------------------------------------
# 7. _connect
#    sqlite3 connection with foreign keys enforced (SPEC_V2 §2.2).
#    Callers wrap it in closing() and in "with conn" for one
#    transaction that commits on success and rolls back on error.
# ---------------------------------------------------------------------------
def _connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# 8. _seal
#    Signs a capsule via P2 and returns (id, canonical text, signed).
#    id is sha256_hex of the canonical bytes, exactly as in v1.
# ---------------------------------------------------------------------------
def _seal(capsule, private_key):
    signed = sign.sign_capsule(capsule, private_key)
    text = envelope.canonicalise(signed)
    return envelope.sha256_hex(text.encode("utf-8")), text, signed


# ---------------------------------------------------------------------------
# 9. _verify_text
#    SPEC_V2 §2.7: returns the parsed capsule if the stored text
#    hashes to row_id, is canonical, (for claims) is signed by the
#    stored signer, and the P2 signature verifies. Else ValueError.
# ---------------------------------------------------------------------------
def _verify_text(row_id, text, signer=None):
    if envelope.sha256_hex(text.encode("utf-8")) != row_id:
        raise ValueError(f"hash mismatch for {row_id}")
    try:
        capsule = json.loads(text)
    except ValueError:
        raise ValueError(f"stored capsule is not JSON: {row_id}") from None
    if not isinstance(capsule, dict) or envelope.canonicalise(capsule) != text:
        raise ValueError(f"stored capsule is not canonical: {row_id}")
    sig = capsule.get("signature")
    key_id = sig.get("key_id") if isinstance(sig, dict) else None
    if signer is not None and key_id != signer:
        raise ValueError(f"signer does not match signature key: {row_id}")
    try:
        public_key = envelope.did_key_decode(key_id)
    except (ValueError, TypeError):
        raise ValueError(f"invalid signature key_id: {row_id}") from None
    if not sign.verify_capsule(capsule, public_key):
        raise ValueError(f"signature does not verify: {row_id}")
    return capsule


# ---------------------------------------------------------------------------
# 2. write_claim
#    Signs via P2, inserts as active. If the claim_id already exists,
#    returns it unchanged (SPEC_V2 §2.3).
# ---------------------------------------------------------------------------
def write_claim(db_path, claim, private_key):
    claim_id, text, signed = _seal(claim, private_key)
    signer = signed["signature"]["key_id"]
    now = datetime.now(timezone.utc).isoformat()
    with closing(_connect(db_path)) as conn, conn:
        conn.execute(
            "INSERT OR IGNORE INTO claims "
            "(claim_id, signer, capsule, is_active, created_at) "
            "VALUES (?, ?, ?, 1, ?)",
            (claim_id, signer, text, now),
        )
    return claim_id


# ---------------------------------------------------------------------------
# 3. get_claim
#    Returns the signed capsule, or None if not found. verify=True
#    applies SPEC_V2 §2.7 and raises ValueError on any failure.
# ---------------------------------------------------------------------------
def get_claim(db_path, claim_id, verify=False):
    with closing(_connect(db_path)) as conn:
        row = conn.execute(
            "SELECT capsule, signer FROM claims WHERE claim_id=?", (claim_id,)
        ).fetchone()
    if row is None:
        return None
    if verify:
        return _verify_text(claim_id, row[0], signer=row[1])
    return json.loads(row[0])


# ---------------------------------------------------------------------------
# 4. supersede_claim
#    One transaction (SPEC_V2 §2.4): old must exist (KeyError) and be
#    active (ValueError); new id must be new (ValueError). Then old is
#    marked inactive/superseded_by and new is inserted active.
# ---------------------------------------------------------------------------
def supersede_claim(db_path, old_claim_id, new_claim, private_key):
    new_id, text, signed = _seal(new_claim, private_key)
    signer = signed["signature"]["key_id"]
    now = datetime.now(timezone.utc).isoformat()
    with closing(_connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT is_active FROM claims WHERE claim_id=?", (old_claim_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"claim not found: {old_claim_id}")
        if row[0] != 1:
            raise ValueError(f"claim already superseded: {old_claim_id}")
        if conn.execute(
            "SELECT 1 FROM claims WHERE claim_id=?", (new_id,)
        ).fetchone():
            raise ValueError(f"new claim already exists: {new_id}")
        conn.execute(
            "UPDATE claims SET is_active=0, superseded_by=? WHERE claim_id=?",
            (new_id, old_claim_id),
        )
        conn.execute(
            "INSERT INTO claims "
            "(claim_id, signer, capsule, is_active, created_at) "
            "VALUES (?, ?, ?, 1, ?)",
            (new_id, signer, text, now),
        )
    return new_id


# ---------------------------------------------------------------------------
# 5. link_evidence
#    Signs evidence via P2 and links it (SPEC_V2 §2.5). KeyError if
#    the claim is missing; existing id returned if already linked to
#    this claim; ValueError if linked to another claim.
# ---------------------------------------------------------------------------
def link_evidence(db_path, claim_id, evidence, private_key):
    evidence_id, text, _ = _seal(evidence, private_key)
    now = datetime.now(timezone.utc).isoformat()
    with closing(_connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute(
            "SELECT 1 FROM claims WHERE claim_id=?", (claim_id,)
        ).fetchone() is None:
            raise KeyError(f"claim not found: {claim_id}")
        row = conn.execute(
            "SELECT claim_id FROM evidence WHERE evidence_id=?", (evidence_id,)
        ).fetchone()
        if row is not None:
            if row[0] != claim_id:
                raise ValueError(
                    f"evidence {evidence_id} already linked to {row[0]}"
                )
            return evidence_id
        conn.execute(
            "INSERT INTO evidence (evidence_id, claim_id, capsule, created_at) "
            "VALUES (?, ?, ?, ?)",
            (evidence_id, claim_id, text, now),
        )
    return evidence_id


# ---------------------------------------------------------------------------
# 6. list_evidence
#    All evidence for a claim, ordered by created_at then insertion
#    order (SPEC_V2 §2.6). verify=True applies §2.7 to each capsule.
# ---------------------------------------------------------------------------
def list_evidence(db_path, claim_id, verify=False):
    with closing(_connect(db_path)) as conn:
        rows = conn.execute(
            "SELECT evidence_id, capsule FROM evidence WHERE claim_id=? "
            "ORDER BY created_at ASC, rowid ASC",
            (claim_id,),
        ).fetchall()
    if verify:
        return [_verify_text(eid, text) for eid, text in rows]
    return [json.loads(text) for _, text in rows]
