# SPEC — substrate-layer (P9 Substrate)

SPEC.md — the complete layer specification for P9 Substrate.

Function:
    This document is the authoritative specification for primitive
    layer P9 of the Forge Stack. It defines the semantic memory graph:
    claims, evidence, and supersession.

Layer:     P9 — Substrate
Depends:   P1 Envelope v2, P2 Sign, P8 Store
Consumed:  P12 Rules, P13 DataCube, SC-OS
Version:   SPEC 1.0.0
Licence:   MSL-1.0
Author:    James Gilbert (Giblets Forge)

## 1. The Substrate Rule

The substrate is semantic memory. It stores signed claims (via P2)
and their evidence. It tracks supersession: when a new claim replaces
an old one, the old one is marked inactive but never deleted. History
is preserved.

## 2. Database Schema

CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    signer TEXT NOT NULL,
    capsule TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    superseded_by TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    capsule TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
);

CREATE INDEX IF NOT EXISTS idx_claims_signer ON claims(signer);
CREATE INDEX IF NOT EXISTS idx_evidence_claim ON evidence(claim_id);

## 3. Function Contracts

### 3.1 init_db(db_path: str) -> None
- Creates claims and evidence tables.
- Idempotent — safe to call repeatedly.

### 3.2 write_claim(db_path: str, claim: dict, private_key) -> str
- Signs the claim via P2's sign_capsule.
- Computes claim_id as sha256_hex of the canonical signed capsule.
- Inserts with is_active=1.
- Returns the claim_id.

### 3.3 get_claim(db_path: str, claim_id: str) -> dict
- Returns the signed capsule, or None if not found.

### 3.4 supersede_claim(db_path: str, old_claim_id: str, new_claim: dict, private_key) -> str
- Signs the new claim via P2.
- Marks the old claim is_active=0, superseded_by=new_claim_id.
- Inserts the new claim as active.
- Returns the new claim_id.

### 3.5 link_evidence(db_path: str, claim_id: str, evidence: dict, private_key) -> str
- Signs the evidence via P2.
- Computes evidence_id as sha256_hex of the canonical signed evidence.
- Inserts linked to claim_id.
- Returns evidence_id.

### 3.6 list_evidence(db_path: str, claim_id: str) -> list[dict]
- Returns all evidence capsules for a given claim.

## 4. Known Limitations (P9 v1.0.0)

- No cross-substrate linking (evidence from one substrate to another).
- No deletions. Supersession only.
- No face classification. That is P13 (DataCube).
- No trust scoring. That is P10/P11.
