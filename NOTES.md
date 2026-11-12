# NOTES — substrate-layer (P9 Substrate)

NOTES.md — open questions, divergences and decisions for P9 Substrate.

## Open questions
- (none)

## Divergences from v1.2.1 specification
- (none)

## Decisions
- claim_id is content-addressed: sha256 of the canonical signed capsule.
  Two identical claims signed by the same key produce the same claim_id.
  This prevents silent duplication.
- History preservation: supersession marks old claims inactive but never
  deletes rows. The ledger (P4/P8) holds the immutable audit trail;
  the substrate holds the queryable active state.
- Evidence is itself a signed capsule, so it inherits P2's tamper
  detection for free.
