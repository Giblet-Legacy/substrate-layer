# CHANGELOG — substrate-layer (P9 Substrate)

CHANGELOG.md — build history for P9 Substrate, latest entry at top.

Function:
    Records the Good / Bad / Ugly of every build step for this layer.
    Updated at every sign-off. The format never changes shape, even
    when a section is empty.

## [Unreleased]

### Good

- (none)

### Bad

- (none)

### Ugly

- (none)

## [v4.0.0] — 2026-11-13 — FROZEN

### Good

- `SPEC_V4.md`, `test_substrate_v4.py` (9 tests, run red first) and
  `substrate_v4.py`: entities and subjects at last (NOTES Q4). Each is a
  signed record with a name that is unique, case-insensitively, across
  both types; entities join subjects through signed memberships. Reads:
  `list_entities`, `list_subjects`, `members`, `subjects_of`, `find`,
  `claims_about` (a subject's own claims, then its member entities'),
  `unregistered` (claim subjects not yet registered, for the Cockpit to
  offer). `init_db` upgrades a v3 database in place by adding tables;
  reads on a pre-v4 database return empty.
- 42/42 pass from the repo root and from the parent directory.
  substrate.py, substrate_v2.py and substrate_v3.py untouched. Built on
  James's delegation ("ok spec it and build"). Frozen at 4.0.0 (James: "freeze commmit and push", 2026-11-13); laptop run, S24 run
  still to be confirmed.

### Bad

- Nothing writes entities or subjects yet: the Cockpit needs a command
  (a Cockpit v1.3), and the Field, Legacy and Voice still read claims
  only. P9 is ready for them; they are not wired.

### Ugly

- Claims still name their subject as free text inside the signed
  capsule, so the link from claim to subject is by name key, not by id.
  Changing that would mean re-signing claims; v4 resolves names instead.
- `claims_about` scans active claims in Python rather than by index;
  fine at thousands of claims, to revisit if memory grows far past that.

## [v3.0.0] — 2026-11-13 — FROZEN

### Good

- `SPEC_V3.md`, `test_substrate_v3.py` (8 tests, run red first) and `substrate_v3.py`: a read-only API (`list_claims`, `read_claim`, `read_evidence`, SQLite `mode=ro`, optional per-row verification that never raises) so the Weaver, Echo, SCP Substrate and Legacy can stop reading `forge.db` with their own SQL.
- The attestation rule is now defined (SPEC_V3 §3): a HAL seal is stored as evidence of kind `attestation` (approve) or `refusal` (refuse), via `link_attestation`; `latest_attestation` reads it back. This is the shape SCP Substrate already assumed, so its glow can light from a real approval.
- 33/33 pass from the repo root and from the parent directory. Built on James's delegation ("fix all 11 issues"). Frozen at 3.0.0 on James's sign-off ("freeze all", 2026-11-13).

### Bad

- Frozen on the laptop run alone (2026-11-13); confirmed on the S24 by James, 2026-11-13.

### Ugly

- v3 calls v2's private `_verify_text` for verify-on-read, rather than reimplement it. Safe while v2 is frozen.

## [v2.0.0] — 2026-11-12

### Good

- Laptop audit per `PROMPT_P9.md`. `substrate_v2.py`: strict layer
  above the frozen P9 v1.0.0, specified in `SPEC_V2.md` before any
  code. Same schema, same ids, byte-identical stored text, so v1 and
  v2 share databases (tested both ways).
- Resolves NOTES D1–D7: P1/P2 imported from the file's own location;
  connections always closed and writes atomic; duplicate claims
  return the existing id; superseding a missing or already-superseded
  claim is rejected, so the history chain can no longer fork;
  evidence cannot be linked to a missing claim; evidence order is
  deterministic.
- New: `verify=True` on get_claim and list_evidence checks hash,
  canonical form, signer and P2 signature on read.
- `test_substrate_v2.py`: 19 tests, written before substrate_v2.py and
  run red first. Full suite 25/25 from the repo, its parent and `C:\`.
- `conftest.py`: pytest finds P1/P2 from its own location, so the
  frozen v1 tests also run from any directory.
- README status updated (was still `0.0.0-dev`).

### Bad

- substrate.py v1.0.0 accepted orphan evidence, phantom supersession
  and forked supersession chains, and leaked connections on error
  (NOTES D2–D6). Fixed in v2; v1 left frozen.

### Ugly

- P9 still talks to sqlite3 directly, not P8 Store, and has no tables
  for Entities/Subjects (NOTES Q1, Q4). Evidence soft-delete declined
  pending a SPEC decision (Q3).

## [v1.0.0] — 2026-11-12

### Good

- `substrate.py` implemented to SPEC v1.0.0.
- 6/6 pytest tests pass.
- Semantic memory: claims, evidence, supersession.
- Content-addressed claim_ids (sha256 of canonical signed capsule).
- History preserved: superseded claims remain in the database.

### Bad

- (none)

### Ugly

- (none)

## [scaffold] — 2026-11-12

### Good

- Repository scaffolded: `Giblet-Legacy/substrate-layer` created for P9.
- Depends on P1 Envelope v2.0.0, P2 Sign v1.0.0, P8 Store v1.0.0.

### Bad

- (none)

### Ugly

- (none)
