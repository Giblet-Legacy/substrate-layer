"""
substrate.py — P9 Substrate primitive layer

Function:
    Implements the semantic memory graph: claims and evidence.
    Manages supersession (history preservation). Consumes P1, P2, and
    delegates storage to standard sqlite3.

Public API:
    1. init_db          — Create claims and evidence tables.
    2. write_claim      — Sign and insert a claim.
    3. get_claim        — Fetch a signed claim by id.
    4. supersede_claim  — Mark an old claim inactive, insert new.
    5. link_evidence    — Attach signed evidence to a claim.
    6. list_evidence    — List all evidence for a claim.

Layer:    P9 — Substrate
Depends:  P1 Envelope v2, P2 Sign, P8 Store
Consumed: P12 Rules, P13 DataCube, SC-OS
Version:  1.0.0 (on freeze; 0.0.0-dev until then)
Licence:  MSL-1.0
Author:   James Gilbert (Giblets Forge)
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timezone

# Import P1 and P2
sys.path.insert(0, os.path.abspath('../envelope-layer'))
sys.path.insert(0, os.path.abspath('../sign-layer'))
import envelope_v2 as envelope
import sign

# ---------------------------------------------------------------------------
# 1. init_db
#    Creates claims and evidence tables.
# ---------------------------------------------------------------------------
def init_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            claim_id TEXT PRIMARY KEY,
            signer TEXT NOT NULL,
            capsule TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            superseded_by TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evidence (
            evidence_id TEXT PRIMARY KEY,
            claim_id TEXT NOT NULL,
            capsule TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_claims_signer ON claims(signer)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_claim ON evidence(claim_id)")
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# 2. write_claim
#    Signs via P2, computes claim_id, inserts as active.
# ---------------------------------------------------------------------------
def write_claim(db_path, claim, private_key):
    signed = sign.sign_capsule(claim, private_key)
    canonical_bytes = envelope.canonical_bytes(signed)
    claim_id = envelope.sha256_hex(canonical_bytes)
    did_key = envelope.did_key_encode(private_key.public_key())
    now = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO claims (claim_id, signer, capsule, is_active, created_at) "
        "VALUES (?, ?, ?, 1, ?)",
        (claim_id, did_key, json.dumps(signed, sort_keys=True, separators=(",", ":")), now),
    )
    conn.commit()
    conn.close()
    return claim_id

# ---------------------------------------------------------------------------
# 3. get_claim
#    Returns the signed capsule, or None if not found.
# ---------------------------------------------------------------------------
def get_claim(db_path, claim_id):
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT capsule FROM claims WHERE claim_id=?", (claim_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return json.loads(row[0])

# ---------------------------------------------------------------------------
# 4. supersede_claim
#    Marks old claim inactive, inserts new claim as active.
# ---------------------------------------------------------------------------
def supersede_claim(db_path, old_claim_id, new_claim, private_key):
    signed = sign.sign_capsule(new_claim, private_key)
    canonical_bytes = envelope.canonical_bytes(signed)
    new_id = envelope.sha256_hex(canonical_bytes)
    did_key = envelope.did_key_encode(private_key.public_key())
    now = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE claims SET is_active=0, superseded_by=? WHERE claim_id=?",
        (new_id, old_claim_id),
    )
    conn.execute(
        "INSERT INTO claims (claim_id, signer, capsule, is_active, created_at) "
        "VALUES (?, ?, ?, 1, ?)",
        (new_id, did_key, json.dumps(signed, sort_keys=True, separators=(",", ":")), now),
    )
    conn.commit()
    conn.close()
    return new_id

# ---------------------------------------------------------------------------
# 5. link_evidence
#    Signs evidence via P2, computes evidence_id, links to claim.
# ---------------------------------------------------------------------------
def link_evidence(db_path, claim_id, evidence, private_key):
    signed = sign.sign_capsule(evidence, private_key)
    canonical_bytes = envelope.canonical_bytes(signed)
    evidence_id = envelope.sha256_hex(canonical_bytes)
    now = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO evidence (evidence_id, claim_id, capsule, created_at) "
        "VALUES (?, ?, ?, ?)",
        (evidence_id, claim_id, json.dumps(signed, sort_keys=True, separators=(",", ":")), now),
    )
    conn.commit()
    conn.close()
    return evidence_id

# ---------------------------------------------------------------------------
# 6. list_evidence
#    Returns all evidence capsules for a given claim.
# ---------------------------------------------------------------------------
def list_evidence(db_path, claim_id):
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT capsule FROM evidence WHERE claim_id=? ORDER BY created_at ASC",
        (claim_id,),
    ).fetchall()
    conn.close()
    return [json.loads(r[0]) for r in rows]
