# P9 Substrate — Laptop Audit Prompt

P9 substrate-layer is frozen at v1.0.0 on the phone with 6/6 tests passing.

## Your Task

1. Pull `Giblet-Legacy/substrate-layer`.
2. Audit against SPEC.md and CHANGELOG.md.
3. Run `pytest -q` — expect 6 passed.
4. If you find gaps, create `substrate_v2.py` (do NOT edit v1).
5. Suggested V2 hardening: verify signatures on read (get_claim should optionally verify), add soft-delete for evidence, enforce LF-only capsule storage.
6. Push when green so the phone can verify.
