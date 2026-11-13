# Forge Stack Context — P9 Substrate

CLAUDE.md — Context briefing for AI assistants working in this repository.

Function:
    Instructs the AI assistant on the strict architectural rules of the
    Forge Stack. Do not hallucinate external frameworks. Reason strictly
    within these boundaries.

## The Immutable Rule
Never rewrite a primitive. Add a layer.
If `substrate.py` needs a change, we do NOT edit it. We create a v2 layer above it.

## Dual-Device Workflow
We build on an S24 (Termux) and a laptop (VS Code). State is confirmed, never assumed. Always use LF line endings. Commit messages must be clear. We use the Good/Bad/Ugly CHANGELOG format (latest at top).

## Header Discipline
Every file MUST have a top header paragraph explaining its function.
Every function MUST have a numbered header (e.g., `# 2. write_claim`).

## P9 Architecture Specifics
- Depends on `envelope_v2` (P1), `sign_v2` (P2), and `store` (P8, not yet wired — NOTES Q1).
- `substrate_v2.py` (P9 v2.0.0, SPEC_V2.md) is frozen over frozen v1 `substrate.py`.
- Current layer is `substrate_v3.py` (SPEC_V3.md, frozen 3.0.0): read-only API and the attestation rule. New code imports `substrate_v3`.
- `substrate_v4.py` (SPEC_V4.md, frozen 4.0.0): entities, subjects and
  signed membership; `claims_about` and `unregistered`. Resolves NOTES Q4.
- Implements the semantic memory graph: Entities, Subjects, Claims, Evidence.
- Manages supersession: replacing an old claim with a new one.
- No ledger logic — delegates to P8 for storage.
