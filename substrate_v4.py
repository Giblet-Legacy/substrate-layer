"""
substrate_v4.py — P9 Substrate v4, entities and subjects over v3

Function:
    The layer new code imports instead of substrate_v3.py. Re-exports
    every v3 function unchanged and adds (SPEC_V4.md) the two nouns P9
    never stored: entities (distinct things) and subjects (categories,
    hubs; a repo is a subject), each a signed record with a unique
    case-insensitive name, plus signed membership of entities in
    subjects, and reads that go subject → entities → claims.
    Resolves NOTES Q4.

    substrate.py, substrate_v2.py and substrate_v3.py are not edited
    (Immutable Rule). Nothing is deleted or renamed.

Public API:
    (re-exported from v3: write_claim, get_claim, supersede_claim,
     link_evidence, list_evidence, list_claims, read_claim,
     read_evidence, link_attestation, latest_attestation)
    1.  init_db       — v3's tables, then entities, subjects, memberships
    2.  add_entity    — register a thing once; returns its id
    3.  add_subject   — register a category once; returns its id
    4.  add_member    — link an entity into a subject; returns its id
    5.  list_entities — entity rows, read-only, optional verify
    6.  list_subjects — subject rows, read-only, optional verify
    7.  members       — a subject's entities
    8.  subjects_of   — an entity's subjects
    9.  find          — the entity or subject with a name, or None
    10. claims_about  — active claims about a name (and its members)
    11. unregistered  — claim subjects not yet registered

Internal helpers (not exported):
    12. _key       — a checked name → (stripped name, key)
    13. _kind      — a checked kind
    14. _has_v4    — does a database have the v4 tables?
    15. _thing_row — table row → thing row dict
    16. _add_thing — shared body of add_entity / add_subject
    17. _things    — read thing rows with an optional WHERE clause

Layer:    P9 — Substrate, v4
Depends:  substrate_v3.py (P9 v3.0.0), substrate_v2 (_seal, _connect)
Consumed: The Cockpit (to write); LLLM, SCP Substrate, The Legacy (to read)
Spec:     SPEC_V4.md 4.0.0
Version:  4.0.0
Licence:  MSL-1.0
Author:   James Gilbert (Giblets Forge)
"""

import os
import sys
from contextlib import closing
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import substrate_v2 as _v2  # noqa: E402
import substrate_v3 as _v3  # noqa: E402

write_claim = _v3.write_claim
get_claim = _v3.get_claim
supersede_claim = _v3.supersede_claim
link_evidence = _v3.link_evidence
list_evidence = _v3.list_evidence
list_claims = _v3.list_claims
read_claim = _v3.read_claim
read_evidence = _v3.read_evidence
link_attestation = _v3.link_attestation
latest_attestation = _v3.latest_attestation

_TABLE = {"entity": ("entities", "entity_id"), "subject": ("subjects", "subject_id")}
_OTHER = {"entity": "subject", "subject": "entity"}


# ---------------------------------------------------------------------------
# 12. _key
#     SPEC_V4 §2: 1–200 characters once stripped; key is casefolded.
# ---------------------------------------------------------------------------
def _key(name):
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 200:
        raise ValueError("name must be a string of 1–200 characters")
    name = name.strip()
    return name, name.casefold()


# ---------------------------------------------------------------------------
# 13. _kind
# ---------------------------------------------------------------------------
def _kind(kind):
    if kind is not None and (not isinstance(kind, str) or not 1 <= len(kind) <= 60):
        raise ValueError("kind must be None or a string of 1–60 characters")
    return kind


# ---------------------------------------------------------------------------
# 1. init_db
#    SPEC_V4 §2.1. Idempotent; on a v3 database only adds tables.
# ---------------------------------------------------------------------------
def init_db(db_path):
    _v3.init_db(db_path)
    with closing(_v2._connect(db_path)) as conn, conn:
        for table, pk in _TABLE.values():
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({pk} TEXT PRIMARY KEY, "
                         "name_key TEXT NOT NULL UNIQUE, signer TEXT NOT NULL, "
                         "capsule TEXT NOT NULL, created_at TEXT NOT NULL)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memberships (
                membership_id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL REFERENCES subjects(subject_id),
                entity_id TEXT NOT NULL REFERENCES entities(entity_id),
                signer TEXT NOT NULL,
                capsule TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (subject_id, entity_id)
            )
        """)


# ---------------------------------------------------------------------------
# 14. _has_v4
# ---------------------------------------------------------------------------
def _has_v4(conn):
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {"entities", "subjects", "memberships"} <= names


# ---------------------------------------------------------------------------
# 16. _add_thing
#     SPEC_V4 §3.1–3.2: same type and key → existing id; other type →
#     ValueError; else sign and insert, in one transaction.
# ---------------------------------------------------------------------------
def _add_thing(db_path, kind_of, name, private_key, kind):
    name, key = _key(name)
    kind = _kind(kind)
    table, pk = _TABLE[kind_of]
    other_table, _ = _TABLE[_OTHER[kind_of]]
    thing_id, text, signed = _v2._seal({"type": kind_of, "name": name, "kind": kind}, private_key)
    now = datetime.now(timezone.utc).isoformat()
    with closing(_v2._connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(f"SELECT {pk} FROM {table} WHERE name_key=?", (key,)).fetchone()
        if row:
            return row[0]
        if conn.execute(f"SELECT 1 FROM {other_table} WHERE name_key=?", (key,)).fetchone():
            raise ValueError(f"{name!r} is already registered as a{'n' if kind_of == 'subject' else ''} "
                             f"{_OTHER[kind_of]}")
        conn.execute(f"INSERT INTO {table} ({pk}, name_key, signer, capsule, created_at) VALUES (?, ?, ?, ?, ?)",
                     (thing_id, key, signed["signature"]["key_id"], text, now))
    return thing_id


# ---------------------------------------------------------------------------
# 2. add_entity
# ---------------------------------------------------------------------------
def add_entity(db_path, name, private_key, kind=None):
    return _add_thing(db_path, "entity", name, private_key, kind)


# ---------------------------------------------------------------------------
# 3. add_subject
# ---------------------------------------------------------------------------
def add_subject(db_path, name, private_key, kind=None):
    return _add_thing(db_path, "subject", name, private_key, kind)


# ---------------------------------------------------------------------------
# 4. add_member
#    SPEC_V4 §3.3.
# ---------------------------------------------------------------------------
def add_member(db_path, subject_id, entity_id, private_key):
    capsule = {"type": "membership", "subject_id": subject_id, "entity_id": entity_id}
    member_id, text, signed = _v2._seal(capsule, private_key)
    now = datetime.now(timezone.utc).isoformat()
    with closing(_v2._connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        if not conn.execute("SELECT 1 FROM subjects WHERE subject_id=?", (subject_id,)).fetchone():
            raise KeyError(f"subject not found: {subject_id}")
        if not conn.execute("SELECT 1 FROM entities WHERE entity_id=?", (entity_id,)).fetchone():
            raise KeyError(f"entity not found: {entity_id}")
        row = conn.execute("SELECT membership_id FROM memberships WHERE subject_id=? AND entity_id=?",
                           (subject_id, entity_id)).fetchone()
        if row:
            return row[0]
        conn.execute("INSERT INTO memberships (membership_id, subject_id, entity_id, signer, capsule, created_at) "
                     "VALUES (?, ?, ?, ?, ?, ?)",
                     (member_id, subject_id, entity_id, signed["signature"]["key_id"], text, now))
    return member_id


# ---------------------------------------------------------------------------
# 15. _thing_row
#     SPEC_V4 §4: {id, type, name, kind, signer, capsule, created_at}.
# ---------------------------------------------------------------------------
def _thing_row(kind_of, row, verify):
    thing_id, signer, text, created_at = row
    capsule = _v3._parse(text)
    out = {"id": thing_id, "type": kind_of, "name": (capsule or {}).get("name"),
           "kind": (capsule or {}).get("kind"), "signer": signer, "capsule": capsule, "created_at": created_at}
    if verify:
        out["verified"], out["verify_error"] = _v3._check(thing_id, text, signer)
    return out


# ---------------------------------------------------------------------------
# 17. _things
#     Thing rows of one type, read-only. `join` and `where` narrow them;
#     a pre-v4 database has none.
# ---------------------------------------------------------------------------
def _things(db_path, kind_of, verify=False, join="", where="", args=(), order="t.created_at ASC, t.rowid ASC"):
    table, pk = _TABLE[kind_of]
    with closing(_v3._connect_ro(db_path)) as conn:
        if not _has_v4(conn):
            return []
        rows = conn.execute(f"SELECT t.{pk}, t.signer, t.capsule, t.created_at FROM {table} t {join} "
                            f"{where} ORDER BY {order}", args).fetchall()
    return [_thing_row(kind_of, r, verify) for r in rows]


# ---------------------------------------------------------------------------
# 5. list_entities
# ---------------------------------------------------------------------------
def list_entities(db_path, *, verify=False):
    return _things(db_path, "entity", verify)


# ---------------------------------------------------------------------------
# 6. list_subjects
# ---------------------------------------------------------------------------
def list_subjects(db_path, *, verify=False):
    return _things(db_path, "subject", verify)


# ---------------------------------------------------------------------------
# 7. members
#    SPEC_V4 §4.3: in membership order.
# ---------------------------------------------------------------------------
def members(db_path, subject_id):
    return _things(db_path, "entity", join="JOIN memberships m ON m.entity_id = t.entity_id",
                   where="WHERE m.subject_id = ?", args=(subject_id,), order="m.created_at ASC, m.rowid ASC")


# ---------------------------------------------------------------------------
# 8. subjects_of
# ---------------------------------------------------------------------------
def subjects_of(db_path, entity_id):
    return _things(db_path, "subject", join="JOIN memberships m ON m.subject_id = t.subject_id",
                   where="WHERE m.entity_id = ?", args=(entity_id,), order="m.created_at ASC, m.rowid ASC")


# ---------------------------------------------------------------------------
# 9. find
#    SPEC_V4 §4.5. Keys are unique across both types.
# ---------------------------------------------------------------------------
def find(db_path, name):
    try:
        _, key = _key(name)
    except ValueError:
        return None
    for kind_of in ("entity", "subject"):
        rows = _things(db_path, kind_of, where="WHERE t.name_key = ?", args=(key,))
        if rows:
            return rows[0]
    return None


# ---------------------------------------------------------------------------
# 10. claims_about
#     SPEC_V4 §4.6: claims naming `name`, then (for a subject) claims
#     naming each member entity; active only; each claim once.
# ---------------------------------------------------------------------------
def claims_about(db_path, name, *, verify=False):
    try:
        _, key = _key(name)
    except ValueError:
        return []
    keys = [key]
    thing = find(db_path, name)
    if thing and thing["type"] == "subject":
        keys += [e["name"].casefold() for e in members(db_path, thing["id"]) if isinstance(e["name"], str)]
    by_key = {}
    for row in list_claims(db_path, verify=verify):
        subject = (row["capsule"] or {}).get("subject")
        if isinstance(subject, str):
            by_key.setdefault(subject.strip().casefold(), []).append(row)
    out, seen = [], set()
    for k in keys:
        for row in by_key.get(k, []):
            if row["claim_id"] not in seen:
                seen.add(row["claim_id"])
                out.append(row)
    return out


# ---------------------------------------------------------------------------
# 11. unregistered
#     SPEC_V4 §4.7: first-seen names; P9 never registers by itself.
# ---------------------------------------------------------------------------
def unregistered(db_path):
    known = {r["name"].casefold() for kind_of in ("entity", "subject") for r in _things(db_path, kind_of)
             if isinstance(r["name"], str)}
    out, seen = [], set()
    for row in list_claims(db_path):
        subject = (row["capsule"] or {}).get("subject")
        if isinstance(subject, str) and subject.strip():
            key = subject.strip().casefold()
            if key not in known and key not in seen:
                seen.add(key)
                out.append(subject.strip())
    return out
