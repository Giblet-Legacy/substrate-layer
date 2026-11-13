"""
substrate_v3.py — P9 Substrate v3, the read and attestation layer over v2

Function:
    The layer new code imports instead of substrate_v2.py. Re-exports
    every v2 function unchanged and adds (SPEC_V3.md):
    - a read-only API (SQLite mode=ro) that lists and reads claims and
      evidence, optionally verifying each row without raising, so
      consumers stop reading forge.db with their own SQL;
    - the attestation rule: a human decision on a claim is a P9
      evidence capsule of kind "attestation" (approve) or "refusal"
      (refuse) that carries the signed P15 seal.

    substrate.py and substrate_v2.py are not edited (Immutable Rule).

Public API:
    (re-exported from v2: init_db, write_claim, get_claim,
     supersede_claim, link_evidence, list_evidence)
    1. list_claims        — claim rows, read-only, optional verify
    2. read_claim         — one claim row, read-only, optional verify
    3. read_evidence      — evidence rows for a claim, read-only
    4. link_attestation   — store a signed HAL seal as evidence
    5. latest_attestation — newest attestation / refusal, or None

Internal helpers (not exported):
    6. _connect_ro  — SQLite connection that cannot write or create
    7. _parse       — stored text → dict, or None
    8. _check       — v2 verify-on-read as (verified, error)
    9. _claim_row   — claims row tuple → claim row dict
    10. _check_seal — a genuine P2-signed seal, else ValueError

Layer:    P9 — Substrate, v3
Depends:  substrate_v2.py (P9 v2.0.0), envelope_v2 (P1), sign_v2 (P2)
Consumed: The Cockpit, The Weaver, The Echo, SCP Substrate, The Legacy
Spec:     SPEC_V3.md 3.0.0
Version:  3.0.0
Licence:  MSL-1.0
Author:   James Gilbert (Giblets Forge)
"""

import json
import math
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import substrate_v2 as _v2  # noqa: E402  (puts P1 and P2 on sys.path)
import envelope_v2 as _envelope  # noqa: E402
import sign_v2 as _sign  # noqa: E402

init_db = _v2.init_db
write_claim = _v2.write_claim
get_claim = _v2.get_claim
supersede_claim = _v2.supersede_claim
link_evidence = _v2.link_evidence
list_evidence = _v2.list_evidence

_DECISION_KIND = {"approve": "attestation", "refuse": "refusal"}
_CLAIM_COLS = "claim_id, signer, capsule, is_active, superseded_by, created_at"


# ---------------------------------------------------------------------------
# 6. _connect_ro
#    SPEC_V3 §2. mode=ro via a file: URI, so SQLite itself refuses
#    writes and never creates a missing file.
# ---------------------------------------------------------------------------
def _connect_ro(db_path):
    if not os.path.isfile(db_path):
        raise FileNotFoundError(f"substrate database not found: {db_path}")
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


# ---------------------------------------------------------------------------
# 7. _parse
# ---------------------------------------------------------------------------
def _parse(text):
    try:
        obj = json.loads(text)
    except (TypeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


# ---------------------------------------------------------------------------
# 8. _check
#    v2's verify-on-read rule (SPEC_V2 §2.7), reported instead of raised.
# ---------------------------------------------------------------------------
def _check(row_id, text, signer=None):
    try:
        _v2._verify_text(row_id, text, signer=signer)
        return True, None
    except (ValueError, TypeError) as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# 9. _claim_row
# ---------------------------------------------------------------------------
def _claim_row(row, verify):
    claim_id, signer, text, active, superseded_by, created_at = row
    out = {
        "claim_id": claim_id, "signer": signer, "capsule": _parse(text),
        "is_active": bool(active), "superseded_by": superseded_by,
        "created_at": created_at,
    }
    if verify:
        out["verified"], out["verify_error"] = _check(claim_id, text, signer)
    return out


# ---------------------------------------------------------------------------
# 1. list_claims
#    SPEC_V3 §2.1.
# ---------------------------------------------------------------------------
def list_claims(db_path, *, active_only=True, verify=False):
    where = "WHERE is_active = 1 " if active_only else ""
    with closing(_connect_ro(db_path)) as conn:
        rows = conn.execute(
            f"SELECT {_CLAIM_COLS} FROM claims {where}ORDER BY created_at ASC, rowid ASC"
        ).fetchall()
    return [_claim_row(r, verify) for r in rows]


# ---------------------------------------------------------------------------
# 2. read_claim
#    SPEC_V3 §2.2.
# ---------------------------------------------------------------------------
def read_claim(db_path, claim_id, *, verify=False):
    with closing(_connect_ro(db_path)) as conn:
        row = conn.execute(
            f"SELECT {_CLAIM_COLS} FROM claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
    return None if row is None else _claim_row(row, verify)


# ---------------------------------------------------------------------------
# 3. read_evidence
#    SPEC_V3 §2.3. Same order as v2 list_evidence (SPEC_V2 §2.6).
# ---------------------------------------------------------------------------
def read_evidence(db_path, claim_id, *, verify=False):
    with closing(_connect_ro(db_path)) as conn:
        rows = conn.execute(
            "SELECT evidence_id, claim_id, capsule, created_at FROM evidence "
            "WHERE claim_id = ? ORDER BY created_at ASC, rowid ASC",
            (claim_id,),
        ).fetchall()
    out = []
    for evidence_id, cid, text, created_at in rows:
        row = {"evidence_id": evidence_id, "claim_id": cid,
               "capsule": _parse(text), "created_at": created_at}
        if verify:
            row["verified"], row["verify_error"] = _check(evidence_id, text)
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# 10. _check_seal
#     SPEC_V3 §3.1: shape, then a P2 signature that verifies against the
#     did it names. HAL policy (quarantine, separation) is the caller's.
# ---------------------------------------------------------------------------
def _check_seal(seal):
    if not isinstance(seal, dict):
        raise ValueError("seal must be a dict")
    if seal.get("decision") not in _DECISION_KIND:
        raise ValueError("seal decision must be 'approve' or 'refuse'")
    if not isinstance(seal.get("rationale"), str):
        raise ValueError("seal rationale must be a str")
    ts = seal.get("timestamp")
    if isinstance(ts, bool) or not isinstance(ts, (int, float)) or not math.isfinite(ts):
        raise ValueError("seal timestamp must be a finite number")
    sig = seal.get("signature")
    key_id = sig.get("key_id") if isinstance(sig, dict) else None
    try:
        public_key = _envelope.did_key_decode(key_id)
    except (ValueError, TypeError):
        raise ValueError("seal is not signed by a valid did:key") from None
    if not _sign.verify_capsule(seal, public_key):
        raise ValueError("seal signature does not verify")
    return key_id


# ---------------------------------------------------------------------------
# 4. link_attestation
#    SPEC_V3 §3.1.
# ---------------------------------------------------------------------------
def link_attestation(db_path, claim_id, seal, private_key):
    by = _check_seal(seal)
    evidence = {
        "kind": _DECISION_KIND[seal["decision"]],
        "decision": seal["decision"],
        "by": by,
        "note": seal["rationale"],
        "at": seal["timestamp"],
        "seal": seal,
    }
    return link_evidence(db_path, claim_id, evidence, private_key)


# ---------------------------------------------------------------------------
# 5. latest_attestation
#    SPEC_V3 §3.2.
# ---------------------------------------------------------------------------
def latest_attestation(db_path, claim_id):
    for row in reversed(read_evidence(db_path, claim_id)):
        cap = row["capsule"]
        if cap is not None and cap.get("kind") in ("attestation", "refusal"):
            return cap
    return None
