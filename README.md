# substrate-layer — P9 Substrate

README.md — repository purpose and layer contract for P9 Substrate.

Function:
    This repository implements primitive layer P9 of the Forge Stack:
    the semantic memory graph. It stores signed Claims and their
    Evidence, and manages claim supersession. It consumes P1 and P2
    for its underlying primitives.

Layer:    P9 — Substrate
Depends:  P1 Envelope v2, P2 Sign v2, P8 Store (planned, NOTES Q1)
Consumed: P12 Rules, P13 DataCube, SC-OS
Licence:  MSL-1.0
Author:   James Gilbert (Giblets Forge)
Status:   2.0.0 (frozen). substrate_v3.py (SPEC_V3.md) is built over it,
          frozen at 3.0.0. New code imports substrate_v3.
          substrate_v4.py (SPEC_V4.md: entities and subjects) is frozen
          at 4.0.0 over v3.

## Files

| File                  | Role                                          |
|-----------------------|-----------------------------------------------|
| `substrate_v2.py`     | Current layer (SPEC_V2.md). Import this.      |
| `substrate.py`        | Frozen v1.0.0 primitive (SPEC.md). Never edit.|
| `SPEC.md`/`SPEC_V2.md`| Specifications, v1 and the v2 changes.        |
| `test_substrate*.py`  | v1 (6) and v2 (19) test suites.               |
| `conftest.py`         | Puts P1/P2 on sys.path for pytest.            |
| `NOTES.md`            | Divergences, open questions, decisions.       |

## Layout and tests

Sibling checkouts are expected beside this repo:
`../envelope-layer` (P1) and `../sign-layer` (P2).

    pytest -q        # 25 passed, from any working directory
