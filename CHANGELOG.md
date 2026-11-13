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

## [v3.0.0] — 2026-11-13 — FROZEN

### Good

- `SPEC_V3.md`, `test_substrate_v3.py` (8 tests, run red first) and `substrate_v3.py`: a read-only API (`list_claims`, `read_claim`, `read_evidence`, SQLite `mode=ro`, optional per-row verification that never raises) so the Weaver, Echo, SCP Substrate and Legacy can stop reading `forge.db` with their own SQL.
- The attestation rule is now defined (SPEC_V3 §3): a HAL seal is stored as evidence of kind `attestation` (approve) or `refusal` (refuse), via `link_attestation`; `latest_attestation` reads it back. This is the shape SCP Substrate already assumed, so its glow can light from a real approval.
- 33/33 pass from the repo root and from the parent directory. Built on James's delegation ("fix all 11 issues"). Frozen at 3.0.0 on James's sign-off ("freeze all", 2026-11-13).

### Bad

- Frozen on the laptop run alone (2026-11-13); the S24 run is still to be confirmed.

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
