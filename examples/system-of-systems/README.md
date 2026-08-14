# Vessel Drainage System-of-Systems Experiment

This fixture treats each constituent as if a different team created and versioned it independently:

| Project | Version | DNV rules | Public contract |
|---|---:|---:|---|
| `pumping-unit` | 1.1.0 | 9 | capacity, availability, priming, and approval evidence |
| `piping-network` | 2.2.0 | 10 | geometry, configuration, protection, and flow-path compatibility |
| `well-monitoring` | 0.9.0 | 9 | drainage demand, arrangement, access, and operator feedback |
| `composition` | 0.2.0 | 5 SoS rules | compatibility and emergent end-to-end claims |

Each constituent has its own manifest and can compile or publish without either peer. Constituents never import one another. The composition manifest is the integration baseline: it pins the exact source layer order, loads all three public contracts, and owns only cross-system requirements and verdicts.

`SOS-002-NEG` injects an older piping contract limited to 80 m3/h against a 100 m3/h pumping output. Its expected `false` verdict proves incompatible independently evolved systems are rejected.

The split follows the assurance viewpoints, not a mandatory file taxonomy:

- `Library.sysml`: stable public types and contract surface.
- `Architecture.sysml`: independently configured constituent.
- `Requirements.sysml`: source-traced claims from the supplied DNV extraction.
- `Analysis.sysml`: kernel-evaluable evidence obligations.
- `composition/*`: interface compatibility plus emergent SoS assurance.

The refined checks demonstrate more than scalar limits:

- conditional applicability, such as centrifugal pump priming and optional emergency suction;
- derived values, such as circular pipe areas calculated from diameters;
- evidence-dependent acceptance for high-velocity pressure-loss approval;
- configuration logic for cargo-hold protection and below-floor access;
- negative contract testing using an intentionally incompatible historical subsystem.

See [METHOD.md](METHOD.md) for the interaction method, contract boundary, and derivation of the five emergent rules.

See [runtime-mvp/README.md](runtime-mvp/README.md) for a working local example of immutable packages, dependency locking, locked federation, contract-version testing, synchronous mock coupling, asynchronous stale-data handling, and append-only evidence.

The first experiment deliberately stays inside one composition publication. Separate API publications require a dependency lock containing project UUID, commit, content hash, and contract version; cross-project reference retrieval is not yet proven by this repository.

Validate each historical constituent independently, then the assembled baseline:

```bash
PY=/home/manret/SysMLInfra/.venv/bin/python

cd pumping-unit
$PY -m sys_infra.entry check --project-dir . Library.sysml Architecture.sysml Requirements.sysml Analysis.sysml

cd ../piping-network
$PY -m sys_infra.entry check --project-dir . Library.sysml Architecture.sysml Requirements.sysml Analysis.sysml

cd ../well-monitoring
$PY -m sys_infra.entry check --project-dir . Library.sysml Architecture.sysml Requirements.sysml Analysis.sysml

cd ../composition
$PY -m sys_infra.entry check --project-dir . \
  ../pumping-unit/Library.sysml ../pumping-unit/Architecture.sysml ../pumping-unit/Requirements.sysml ../pumping-unit/Analysis.sysml \
  ../piping-network/Library.sysml ../piping-network/Architecture.sysml ../piping-network/Requirements.sysml ../piping-network/Analysis.sysml \
  ../well-monitoring/Library.sysml ../well-monitoring/Architecture.sysml ../well-monitoring/Requirements.sysml ../well-monitoring/Analysis.sysml \
  Architecture.sysml Requirements.sysml Analysis.sysml
```