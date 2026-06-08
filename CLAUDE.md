# SysML v2 Kernel — Library Linking Guide

## The flat-package rule
Every notebook cell's top-level package **must be a single flat name**.

```sysml
// CORRECT — flat, importable from other cells
package BilgePump_Library { ... }

// BROKEN — nested; other cells can't import BilgePump::Library
package BilgePump { package Library { ... } }
```

## Cross-cell import syntax
```sysml
private import BilgePump_Library::*;   // imports all public members
private import ScalarValues::*;        // built-in scalar types (Real, Boolean, …)
```

## Required execution order
Cell 1 (Library) → Cell 2 (Architecture) → Cell 3 (Requirements) → Cell 4 (Analysis) → test cells.
Skipping any cell leaves names unresolved; re-run from the first skipped cell.

## What breaks
| Symptom | Cause |
|---|---|
| `unresolved name 'BilgePumpSystem'` | Architecture cell not yet executed |
| `unresolved name 'WaterLevelRequirement'` | Requirements cell not yet executed |
| import `BilgePump::Library::*` fails | Cell 1 used nested packages |

## Publishing
`%publish` — pushes the current session model to the SST API at `http://sysml2.intercax.com:9000`.
Run after all cells pass; not required for local constraint evaluation.

## STPA_Tool — not part of this project

The `STPA_Tool/` directory co-locates a **separate standalone application** (SQLite-backed STPA/STAMP web tool with Flask routes, chatbot, Excel export). It has its own `requirements.txt` and `pyproject.toml`.

**Do not:**
- Include `STPA_Tool/` in pytest testpaths
- Install from `STPA_Tool/requirements.txt` when working on SysMLInfra
- Reference `STPA_Tool/` in any model-building, CI, or verification scripts

## Scripts reference

| Script | Purpose | Kernel needed? |
|---|---|---|
| `verify.py` | Primary V&V entry point | Optional (`--fallback` skips it) |
| `scripts/sysml_check.py` | Check a single `.sysml` file | Optional (`--fallback` skips it) |
| `scripts/sensor_adapter.py` | Live sensor ingestion adapter | No |
| `scripts/bootstrap_traceability.py` | Populate `lib/traceability.json` from ingested docs | No |
| `scripts/fault_tracer.py` | Cross-layer fault localisation | No |
| `scripts/diagram_gen.py` | Generate topology/traceability diagrams | No |
| `scripts/ci_kernel_validate.py` | CI kernel runner (GitHub Actions) | Yes |

## Test harness

```bash
pytest tests/ -v            # all unit + model tests, no kernel needed (~15 s)
pytest tests/unit/ -v       # unit tests only (~5 s)
pytest tests/model/ -v      # model fallback tests (~10 s)
pytest tests/ -m z3 -v      # Z3 tests (requires z3-solver)
```

Layer execution order (fallback evaluator):
`RAAML → Library → Architecture → Requirements → Analysis → Safety`
FMEA.sysml and UQ.sysml are **excluded** from `validation_layers` (contain intentional violations).
