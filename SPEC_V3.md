# SPEC V3 — substrate-layer (P9 Substrate, read and attestation layer)

SPEC_V3.md — specification for substrate_v3.py, the layer above P9 v2.0.0.

Function:
    Gives P9's readers a real API so they stop reading `forge.db` with
    their own SQL, and defines where a human attestation lives.
    SPEC_V2.md remains authoritative for everything this document does
    not change; every v2 function is re-exported unchanged.

Layer:     P9 — Substrate, v3
Depends:   substrate_v2.py (P9 v2.0.0), envelope_v2 (P1), sign_v2 (P2)
Consumed:  The Cockpit, The Weaver, The Echo, SCP Substrate, The Legacy
Version:   SPEC V3 3.0.0
Licence:   MSL-1.0
Author:    James Gilbert (Giblets Forge)

---

## 1. Why v3

- P9 had no "list claims" call, so four consumers (Weaver, Echo, SCP
  Substrate, Legacy) read the `claims` table with hand-written SQL.
  The table layout became an undeclared contract, and none of them
  verified signatures on read.
- No layer said where a human attestation lives. SCP Substrate
  invented a convention (an evidence capsule with `kind:
  "attestation"`); P15 HAL seals went only to the ledger, so the
  viewer's attested glow could never light from a real approval.

## 2. Read-only API

All three functions open the database with SQLite `mode=ro` (a URI
from `pathlib.Path.as_uri()`), so they can never create or modify a
file. A missing database raises FileNotFoundError.

A **claim row** is a dict:
`{claim_id, signer, capsule, is_active (bool), superseded_by,
created_at}`. An **evidence row** is
`{evidence_id, claim_id, capsule, created_at}`. `capsule` is the
parsed dict, or None if the stored text is not a JSON object.

With `verify=True` every row also carries `verified` (bool) and
`verify_error` (str or None), using v2's verify-on-read rule
(SPEC_V2 §2.7: hash, canonical form, signer, P2 signature). Reads
never raise for a bad row: a viewer can still show it, marked
unverified.

### 2.1 list_claims(db_path, *, active_only=True, verify=False) -> list[dict]
Claims ordered by `created_at`, then insertion order.

### 2.2 read_claim(db_path, claim_id, *, verify=False) -> dict | None
One claim row, active or superseded; None if absent.

### 2.3 read_evidence(db_path, claim_id, *, verify=False) -> list[dict]
Evidence rows for a claim, in v2's order (SPEC_V2 §2.6).

## 3. Attestations (the rule SCP Substrate assumed, now defined)

A human decision on a claim is stored as one **evidence capsule**
linked to that claim:

    {
      "kind": "attestation" | "refusal",
      "decision": "approve" | "refuse",
      "by": "<did:key of the seal signer>",
      "note": "<seal rationale>",
      "at": <seal timestamp, epoch seconds>,
      "seal": { ...the signed P15 seal, unchanged... }
    }

`approve` → `kind: "attestation"`; `refuse` → `kind: "refusal"`. A
refusal is recorded (HAL: a refusal is an event) but is not an
attestation, so it never lights the viewer's glow.

### 3.1 link_attestation(db_path, claim_id, seal, private_key) -> str
- `seal` must be a dict with `decision` in {approve, refuse}, a str
  `rationale`, a number `timestamp`, and a P2 signature that verifies
  against the did in `signature.key_id`. Otherwise ValueError, nothing
  written. P9 cannot import P15 (it sits above P9); the caller checks
  HAL policy, such as quarantine, with `hal_v2.verify_seal` first. P9
  checks only that the seal is a genuine signed capsule.
- Builds the §3 evidence and calls v2 `link_evidence`, signed with
  `private_key`. Returns the evidence id. Unknown claim → KeyError.

### 3.2 latest_attestation(db_path, claim_id) -> dict | None
The newest evidence capsule for the claim whose `kind` is
`attestation` or `refusal`, read-only, or None.

## 4. Public API

v2 re-exported: init_db, write_claim, get_claim, supersede_claim,
link_evidence, list_evidence. New: list_claims, read_claim,
read_evidence, link_attestation, latest_attestation.

## 5. Tests (test_substrate_v3.py)

- v2 names are v2's objects.
- list_claims: active only by default, all with `active_only=False`,
  ordered; rows carry every field.
- Read-only: the file's bytes are unchanged after reads; a missing
  database raises FileNotFoundError and is not created.
- verify=True: good rows `verified=True`; a tampered row
  `verified=False` with an error, and the call does not raise.
- read_claim: present, superseded, absent.
- link_attestation: approve → kind attestation with by/note/at; refuse
  → kind refusal; unsigned, tampered or wrong-decision seal →
  ValueError, nothing written; unknown claim → KeyError.
- latest_attestation returns the newest of the two kinds, or None.

---

## Document control

- **SPEC V3 3.0.0** — 2026-11-13, by the VS Code AI on James's
  delegation ("fix all 11 issues").
