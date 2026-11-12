# NOTES — substrate-layer (P9 Substrate)

NOTES.md — open questions, divergences and decisions for P9 Substrate.

Function:
    Records open questions and divergences between substrate.py
    v1.0.0 and SPEC.md v1.0.0 / CLAUDE.md. substrate.py is never
    edited (Immutable Rule), so a fix means a new layer above it,
    after a SPEC version describes it. Each divergence below names
    the layer and section that resolves it.

## Open questions

- **Q1 — P8 Store is not used.** CLAUDE.md and the v1 header say P9
  depends on and delegates storage to P8 Store, but substrate.py
  calls sqlite3 directly and there is no P8 checkout beside this repo
  (`../store-layer` does not exist on the laptop). Moving storage to
  P8 needs P8's API first; until then v1 and v2 use sqlite3 directly.
- **Q2 — evidence_id ignores claim_id.** evidence_id is the hash of
  the signed evidence alone, so the same evidence capsule signed by
  the same key cannot be linked to two claims (primary key clash).
  v2 raises ValueError for that case (SPEC_V2 §2.5). Changing the id
  to include claim_id would break v1 id compatibility — needs a SPEC
  decision.
- **Q3 — evidence soft-delete.** Suggested in PROMPT_P9.md, but SPEC.md
  §4 says "No deletions. Supersession only." Declined for v2 until
  the SPEC says otherwise.
- **Q4 — Entities and Subjects.** CLAUDE.md lists Entities, Subjects,
  Claims and Evidence. SPEC.md v1.0.0 only defines claims and
  evidence; subjects live inside the claim capsule. No tables for
  entities or subjects exist yet.
- **Q5 — no "current claim" lookup.** Nothing follows a supersession
  chain to its active head. P12 Rules will likely need one.

## Divergences — substrate.py v1.0.0 vs SPEC.md v1.0.0

Found in laptop audit 2026-11-12 (PROMPT_P9.md). Each was reproduced
by a probe before the fix. D1–D7 are resolved by `substrate_v2.py`
(SPEC_V2.md 2.0.0); substrate.py and test_substrate.py are unchanged.

- **D1 — CWD-relative imports.** `substrate.py:32-33` and
  `test_substrate.py:20-21` insert `os.path.abspath('../…-layer')`,
  resolved against the working directory. Running pytest from the
  parent directory failed at collection. **Resolved:** SPEC_V2 §2.1;
  substrate_v2 locates P1/P2 from `__file__`. `conftest.py` does the
  same for pytest, so the frozen v1 tests also run from anywhere.
- **D2 — leaked connections.** No try/finally: any exception left the
  sqlite connection open (and, in supersede_claim, an uncommitted
  UPDATE pending). **Resolved:** SPEC_V2 §2.2.
- **D3 — duplicate claim crashes.** Writing the same claim with the
  same key (Ed25519 is deterministic, so same claim_id) raised a raw
  `sqlite3.IntegrityError`. **Resolved:** SPEC_V2 §2.3, returns the
  existing id.
- **D4 — phantom supersession.** `supersede_claim` on a claim_id that
  does not exist updated zero rows and still inserted the new claim
  as if it superseded something. **Resolved:** SPEC_V2 §2.4, KeyError.
- **D5 — supersession fork.** Superseding an already-superseded claim
  overwrote its `superseded_by` and left two active claims, orphaning
  the first successor from the chain. Superseding with identical
  content raised a raw IntegrityError. **Resolved:** SPEC_V2 §2.4,
  ValueError, nothing written.
- **D6 — orphan evidence.** SQLite does not enforce FOREIGN KEY unless
  `PRAGMA foreign_keys=ON`, so evidence linked to a nonexistent claim
  was accepted. **Resolved:** SPEC_V2 §2.2, §2.5, KeyError.
- **D7 — unstable evidence order.** list_evidence ordered by
  created_at only; equal timestamps had no defined order.
  **Resolved:** SPEC_V2 §2.6, rowid tiebreak.

Not a divergence, but added in v2 per PROMPT_P9.md: get_claim and
list_evidence take `verify=True` to check hash, canonical form,
signer and P2 signature on read (SPEC_V2 §2.7). v1 returned a
tampered capsule silently.

Header discipline: substrate.py's header says it "delegates storage
to standard sqlite3" while also listing P8 as a dependency (see Q1),
and test_substrate.py's functions have no numbered headers. Both
files are frozen; the v2 files follow the discipline in full.

## Decisions

- claim_id is content-addressed: sha256 of the canonical signed capsule.
  Two identical claims signed by the same key produce the same claim_id.
  This prevents silent duplication. v2 makes the repeat write a no-op
  that returns the id.
- History preservation: supersession marks old claims inactive but never
  deletes rows. The ledger (P4/P8) holds the immutable audit trail;
  the substrate holds the queryable active state.
- Evidence is itself a signed capsule, so it inherits P2's tamper
  detection for free. v2 exposes that check on read.
- A claim is superseded at most once (v2). Evidence may still be
  linked to a superseded claim, so history keeps its evidence.
- LF-only storage needs no code: canonical JSON escapes every control
  character, so stored capsule text never holds a raw CR or LF (tested
  in test_substrate_v2.py).
