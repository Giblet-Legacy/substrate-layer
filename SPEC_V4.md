# SPEC V4 — substrate-layer (P9 Substrate, entities and subjects)

SPEC_V4.md — specification for substrate_v4.py, the layer above P9 v3.0.0.

Function:
    Gives P9 the two nouns CLAUDE.md has always listed but no layer
    stored: **entities** and **subjects**, with signed membership
    between them, and a way to read every claim about either. Resolves
    NOTES Q4. SPEC_V3.md remains authoritative for everything this
    document does not change; every v3 function is re-exported
    unchanged. substrate.py, substrate_v2.py and substrate_v3.py are
    not edited.

Layer:     P9 — Substrate, v4
Depends:   substrate_v3.py (P9 v3.0.0), envelope_v2 (P1), sign_v2 (P2)
Consumed:  The Cockpit (to write), LLLM, SCP Substrate, The Legacy (to read)
Version:   SPEC V4 4.0.0
Licence:   MSL-1.0
Author:    James Gilbert (Giblets Forge)

---

## 1. Why v4

P9's claims carry a free-text `subject` inside the capsule, and nothing
else. James's model (2026-11-13):

- **Entity** — the noun. A distinct thing: a person, device, project or
  concept. It exists once, has an id and a name, and holds no truth of
  its own.
- **Subject** — the category, or hub. What a claim is talking about. A
  repo is a subject with its own cluster of claims. A subject can group
  entities.
- **Claim** — the sentence, about an entity or a subject (P9 v1–v3,
  unchanged). Evidence proves a claim.

v4 stores entities, subjects and membership as signed records, so the
Voice can go subject → entities → claims, and the Field can draw
subjects as hubs, without guessing from text.

## 2. Records

Every record is a capsule signed with P2 and stored in canonical form,
exactly as claims are (v2 `_seal`): the id is the SHA-256 hex of the
canonical signed text, and v2's verify-on-read rule (SPEC_V2 §2.7)
applies.

| Record | Capsule |
|---|---|
| entity | `{"type": "entity", "name": str, "kind": str or null}` |
| subject | `{"type": "subject", "name": str, "kind": str or null}` |
| membership | `{"type": "membership", "subject_id": str, "entity_id": str}` |

**Names.** A name is a string, stripped of surrounding space, 1–200
characters. Its **key** is the stripped name case-folded
(`str.casefold`). Keys are unique across entities and subjects
together: one name is one thing, so a claim's subject resolves to at
most one record. `kind` is null or a string of 1–60 characters (for
example "repo", "device", "person"); it is free text.

Nothing is deleted or renamed (SPEC.md §4). A wrong record stays; a
correction is a new record under a new name.

### 2.1 Tables

`init_db` creates v3's tables, then, if absent:

    entities    (entity_id PK, name_key UNIQUE, signer, capsule, created_at)
    subjects    (subject_id PK, name_key UNIQUE, signer, capsule, created_at)
    memberships (membership_id PK, subject_id FK → subjects,
                 entity_id FK → entities, signer, capsule, created_at,
                 UNIQUE (subject_id, entity_id))

`init_db` on an existing v3 database adds the tables and changes
nothing else. The read functions treat a database without them (made
before v4) as having no entities, subjects or memberships.

## 3. Writes

### 3.1 add_entity(db_path, name, private_key, kind=None) -> str
### 3.2 add_subject(db_path, name, private_key, kind=None) -> str
- A bad name or kind raises ValueError; nothing is written.
- If a record of the **same type** already has the key, its id is
  returned and nothing is written (it exists once). The stored name and
  kind are the first ones.
- If a record of the **other type** has the key, ValueError.
- Otherwise the record is signed, stored and its id returned.

### 3.3 add_member(db_path, subject_id, entity_id, private_key) -> str
- An unknown subject or entity raises KeyError; nothing is written.
- If the pair is already linked, the existing id is returned.
- Otherwise the membership is signed, stored and its id returned.

## 4. Reads (read-only, SQLite mode=ro, as SPEC_V3 §2)

A **thing row** is `{id, type, name, kind, signer, capsule,
created_at}`, plus `verified` and `verify_error` with `verify=True`
(never raises for a bad row). Lists are ordered by `created_at`, then
insertion order.

### 4.1 list_entities(db_path, *, verify=False) -> list[dict]
### 4.2 list_subjects(db_path, *, verify=False) -> list[dict]
### 4.3 members(db_path, subject_id) -> list[dict]
The subject's entities (thing rows), in membership order.
### 4.4 subjects_of(db_path, entity_id) -> list[dict]
The subjects an entity belongs to (thing rows).
### 4.5 find(db_path, name) -> dict | None
The entity or subject whose key matches `name`'s key, or None.
### 4.6 claims_about(db_path, name, *, verify=False) -> list[dict]
Active claim rows (SPEC_V3 §2) whose capsule `subject` has the same
key as `name`. If `name` is a registered subject, claims about each of
its member entities follow, in membership order. Each claim appears
once. An unregistered name still returns the claims that name it (a
claim does not need a registered subject; v1–v3 claims stay valid).
### 4.7 unregistered(db_path) -> list[str]
The distinct `subject` names of active claims whose key is neither an
entity nor a subject, in first-seen order, so a caller (the Cockpit)
can offer to register them. P9 never registers anything by itself.

## 5. Public API

v3 re-exported: write_claim, get_claim, supersede_claim, link_evidence,
list_evidence, list_claims, read_claim, read_evidence,
link_attestation, latest_attestation. Replaced: init_db (§2.1). New:
add_entity, add_subject, add_member, list_entities, list_subjects,
members, subjects_of, find, claims_about, unregistered.

## 6. Tests (test_substrate_v4.py)

- v3 names are v3's objects; init_db on a v3 database keeps its claims
  and adds the tables; reads on a pre-v4 database return empty.
- add_entity / add_subject: signed, verifiable rows; same name (any
  case, surrounding space) returns the same id with nothing written;
  a name of the other type, an empty or over-long name, or a bad kind
  raises ValueError.
- add_member: links; the same pair returns the same id; unknown ids
  raise KeyError.
- members, subjects_of, find (case-insensitive; None if absent).
- claims_about: by subject name, including member entities' claims,
  each once, active only; an unregistered name still works.
- unregistered lists claim subjects not yet registered.
- Reads leave the file's bytes unchanged; verify=True marks a tampered
  row without raising.

---

## Document control

- **SPEC V4 4.0.0** — 2026-11-13, by the VS Code AI on James's
  delegation ("ok spec it and build"), from James's Entity → Subject →
  Claim model and "a repo is a subject with its own cluster of claims".
  Decisions taken: names unique across both types; no deletion or
  rename; P9 never auto-registers (the Cockpit offers).
