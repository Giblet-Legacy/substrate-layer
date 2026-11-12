# SPEC V2 — substrate-layer (P9 Substrate, strict layer)

SPEC_V2.md — specification for substrate_v2.py, the layer above P9 v1.0.0.

Function:
    Specifies substrate_v2.py, a strict layer over the frozen P9
    v1.0.0 primitive (substrate.py). It closes the divergences D1–D7
    recorded in NOTES.md without editing substrate.py (Immutable
    Rule), and adds optional signature verification on read.

    SPEC.md v1.0.0 remains authoritative for everything this document
    does not change. Where this document is silent, SPEC.md v1.0.0
    applies unchanged.

Layer:     P9 — Substrate, v2 (strict)
Depends:   substrate.py (P9 v1.0.0), envelope_v2.py (P1 v2.0.0),
           sign_v2.py (P2 v2.0.0)
Consumed:  P12 Rules, P13 DataCube, SC-OS — new code imports
           substrate_v2, not substrate
Version:   SPEC V2 2.0.0
Licence:   MSL-1.0
Author:    James Gilbert (Giblets Forge)

---

## 1. Compatibility guarantee

- The database schema is SPEC.md §2, unchanged. init_db is v1's
  function, re-exported. A database written by v1 is read and
  extended by v2, and the reverse.
- Capsules are signed by P2 (sign_v2.sign_capsule, which is v1's
  sign_capsule). claim_id and evidence_id are computed exactly as in
  v1: sha256_hex of the canonical signed capsule. The same claim and
  key give the same id under v1 and v2.
- The stored capsule text is envelope_v2.canonicalise(signed). That is
  byte-identical to the text v1 stores, so sha256 of the stored text
  equals the id.

v2 differs from v1 only by **rejecting** operations that would break
the graph (orphans, forks, phantom supersession), by **returning the
existing id** where v1 crashed on a duplicate, and by an **optional**
verify flag on reads. That narrowing is why the major version is 2.

## 2. Changes from SPEC.md v1.0.0

### 2.1 Location-independent imports (resolves D1)

substrate_v2 locates P1 at `<dir of substrate_v2.py>/../envelope-layer`
and P2 at `<dir>/../sign-layer`, not relative to the working
directory. It imports envelope_v2 and sign_v2.

### 2.2 Connections (resolves D2)

Every function opens one connection, runs in one transaction, and
closes the connection in every case. On error the transaction is
rolled back. `PRAGMA foreign_keys = ON` is set on every connection.

### 2.3 write_claim is idempotent (resolves D3)

If claim_id already exists, write_claim returns it and changes
nothing (active state and superseded_by are untouched). v1 raised
sqlite3.IntegrityError.

### 2.4 supersede_claim is guarded and atomic (resolves D4, D5)

In one transaction:
- `KeyError` if old_claim_id does not exist.
- `ValueError` if the old claim is already inactive (superseded).
  A claim is superseded at most once, so the chain never forks.
- `ValueError` if the new claim_id already exists (this includes
  superseding a claim with identical content).
- Otherwise the old claim is marked is_active=0,
  superseded_by=new_id, and the new claim is inserted active.

On any error nothing is written.

### 2.5 link_evidence requires the claim (resolves D6)

- `KeyError` if claim_id does not exist. Linking to an inactive
  (superseded) claim is allowed: history keeps its evidence.
- If evidence_id already exists linked to the same claim, its id is
  returned and nothing changes.
- `ValueError` if evidence_id already exists linked to a different
  claim (evidence_id does not include claim_id; see NOTES Q2).

### 2.6 Deterministic evidence order (resolves D7)

list_evidence orders by created_at, then by insertion order (rowid),
so evidence written within the same timestamp keeps a stable order.
An unknown claim_id returns [] as in v1.

### 2.7 Verify on read (new)

`get_claim(db_path, claim_id, verify=False)` and
`list_evidence(db_path, claim_id, verify=False)`.

With verify=True, each returned capsule must pass all of:
1. sha256_hex of the stored text equals its stored id.
2. The stored text equals envelope_v2.canonicalise of the parsed
   capsule.
3. For a claim, signature.key_id equals the stored signer column.
4. sign_v2.verify_capsule passes against the public key decoded
   from signature.key_id (did:key).

Any failure raises `ValueError`. Not found still returns None
(get_claim). verify=False behaves as v1 (no checks).

## 3. Function contracts (v2)

Public API, numbered as in SPEC.md §3:
1. init_db(db_path) -> None — v1, unchanged.
2. write_claim(db_path, claim, private_key) -> str — §2.3.
3. get_claim(db_path, claim_id, verify=False) -> dict | None — §2.7.
4. supersede_claim(db_path, old_claim_id, new_claim, private_key) -> str — §2.4.
5. link_evidence(db_path, claim_id, evidence, private_key) -> str — §2.5.
6. list_evidence(db_path, claim_id, verify=False) -> list[dict] — §2.6, §2.7.

## 4. Not changed / declined

- Evidence soft-delete (suggested in PROMPT_P9.md) is declined: SPEC.md
  §4 says "No deletions. Supersession only." It needs a SPEC decision
  first (NOTES Q3).
- "LF-only capsule storage" (PROMPT_P9.md) needs no change: canonical
  JSON escapes every control character, so stored text never contains
  a raw CR or LF. Tested.
- Storage is still direct sqlite3, not P8 Store (NOTES Q1).

## 5. Tests (test_substrate_v2.py)

Written before substrate_v2.py and run red first. They cover: v1/v2
id and storage identity, v1 database read by v2, idempotent write,
each supersede guard with rollback, evidence guards, deterministic
order, every verify failure, LF-free storage, and import from any
working directory.
