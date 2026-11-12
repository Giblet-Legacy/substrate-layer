# Forge Stack Context — P9 Substrate

CLAUDE.md — Context briefing for AI assistants working in this repository.

## The Immutable Rule
Never rewrite a primitive. Add a layer.

## Dual-Device Workflow
We build on an S24 (Termux) and a laptop (VS Code). State is confirmed, never assumed. Always use LF line endings. Commit messages must be clear. We use the Good/Bad/Ugly CHANGELOG format (latest at top).

## Header Discipline
Every file MUST have a top header paragraph explaining its function.
Every function MUST have a numbered header.

## P9 Architecture Specifics
- Depends on `envelope_v2` (P1), `sign` (P2), and `store` (P8).
- Implements the semantic memory graph: Entities, Subjects, Claims, Evidence.
- Manages supersession: replacing an old claim with a new one.
- No ledger logic — delegates to P8 for storage.
