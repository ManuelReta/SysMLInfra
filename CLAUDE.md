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
