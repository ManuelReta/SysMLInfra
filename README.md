# SysMLInfra

A **local-first SysML v2 CI/CD infrastructure** with a maritime bilge pump system as the reference project.

| Layer | Contents | Who touches it |
|---|---|---|
| **Infrastructure** (root) | `verify.py`, `setup.sh`, `scripts/`, `.github/workflows/`, `sysml-project.yml` | Anyone reusing this for a new SysML v2 project |
| **BilgePump model** (`bilgepump/`) | Nine `.sysml` layers, Jupyter notebooks, engineering source documents | Systems engineers working on this specific system |

---

## Quick Start

### Step 1 — Install prerequisites

```bash
bash setup.sh
```

This checks Python 3, installs pip dependencies (`requirements.txt`), and installs the SysML v2 Jupyter kernel into a `sysmlv2` conda environment. Requires Miniconda at `~/miniconda3` and Java 21 for the kernel step — if these are absent, verification still works via the Python fallback (see below).

### Step 2 — Run the model

```bash
python3 verify.py
```

That's it. The engine automatically:
1. Detects the registered `sysml` Jupyter kernel
2. Compiles all 7 `validation_layers` through the kernel (syntax, imports, `assert requirement`)
3. Extracts per-requirement pass/fail status for structured output and fault tracing
4. Writes `lib/verification-results.json`

**Expected output:**
```
════════════════════════════════════════════════════════════════════
  SysML v2 Verification — BilgePumpSystem
════════════════════════════════════════════════════════════════════
  Engine  : SysML v2 kernel (sysml)
  Mode    : positive test (validation_layers)
────────────────────────────────────────────────────────────────────

  Starting SysML v2 kernel — this takes ~10 s on first run...

  Kernel layer compilation:
    ✓  RAAML.sysml
    ✓  Library.sysml
    ...
    ✓  StateMachine.sysml

  Requirement evaluation:
  ──────────────────────────────────────────────────────────────────
  ✓  SATISFIED   BPS-REQ-001  Water level ≤ 0.30 m
  ✓  SATISFIED   BPS-REQ-002  Pump B redundancy active
  ...
  ──────────────────────────────────────────────────────────────────
  Overall:  ALL SATISFIED ✓
```

### All `verify.py` flags

| Flag | What it does |
|---|---|
| *(none)* | Kernel run, positive test — all `validation_layers` |
| `--negative` | Inject `pumpA.flowRate = 0` (pump A failure); show fault trace to UCA + FMEA |
| `--visual` | Also generate 3 diagrams in `bilgepump/docs/` (requires networkx) |
| `--dry-run` | List layer files and sizes; do not start kernel |
| `--fallback` | Python regex/eval only — no kernel required (useful without Miniconda/Java) |
| `--all` | Run all 9 layers including FMEA negative tests and UQ sweep |
| `--publish` | After verification, push model to SST API (optional, no auth needed) |
| `--verbose` | Show constraint expression under each requirement result |
| `--z3` | Run Z3 SMT formal analysis (6 levels) after SysML verification (requires `z3-solver`) |
| `--live CONFIG` | Load bind values from a live sensor adapter config (see `scripts/sensor_adapter.py`) |

### Simulating a fault (negative test)

```bash
python3 verify.py --negative
```

Overrides `pumpA.flowRate = 0` and shows which requirement is violated plus a full safety trace:

```
  ✗  VIOLATED    BPS-REQ-004  Discharge ≥ design inflow

  Safety Fault Trace — Negative Test
  ✗ DischargeCapacityRequirement
  Constraint : (sys.pumpA.flowRate + sys.pumpB.flowRate) >= designInflow
  Defined at  : bilgepump/Requirements.sysml:124
  Bind values :
    sys.pumpA.flowRate = 0.0  [[negative-test override]:0]  ◀ FAULT
    sys.pumpB.flowRate = 0.025  [bilgepump/UQ.sysml:446]
  UCA trace   :
    UCA-001 — ActivatePumpA (Not Provided) → hazards: H-1,HS-1
    ...
  FMEA trace  :
    FM-C-003 — Failover path not triggered (S=9 O=2 D=5 RPN=90)
```

### Without Miniconda/Java (fallback mode)

If the SysML kernel is not installed, `verify.py` automatically falls back to Python regex/eval and prints a one-line warning. You can also request it explicitly:

```bash
python3 verify.py --fallback
```

The fallback evaluates `require constraint` expressions by parsing `bind` statements from `Analysis.sysml` and evaluating arithmetic in Python. It does **not** run the SysML v2 type checker — use the kernel for authoritative results.

### Unit and model tests (no kernel required)

```bash
# All unit + model tests (~15 s):
pytest tests/ -v

# Unit tests only (~5 s):
pytest tests/unit/ -v

# Model fallback tests only (~10 s):
pytest tests/model/ -v

# Z3 formal analysis tests (requires z3-solver):
pytest tests/ -m z3 -v
```

Tests cover `verify.py` helpers (`_eval_requirement`, `_build_bind_values`, `_read_manifest`, `_save_results`), `fault_tracer.py` bind index parsing, `formal_analysis.py` level outcomes, and the full Python fallback evaluator positive/negative test matrix.

### Checking a single .sysml file

```bash
# Quick syntax + requirement check, no kernel (~1 s):
python scripts/sysml_check.py bilgepump/Analysis.sysml --fallback

# Full kernel check:
python scripts/sysml_check.py bilgepump/Requirements.sysml

# Negative-test file (expect violations — exit 0 when violations present):
python scripts/sysml_check.py bilgepump/FMEA.sysml --expect-violations

# Check multiple files:
python scripts/sysml_check.py bilgepump/Architecture.sysml bilgepump/Safety.sysml
```

### Z3 formal analysis

```bash
python3 verify.py --fallback --z3
```

Runs 6 escalating Z3 SMT levels after the fallback evaluation, writing a gap report to `lib/z3-analysis-results.json`. Requires `pip install z3-solver`. The 6 levels cover: symbolic baseline proof (L1), efficiency floor discovery (L2), parametric accuracy envelope (L3), cross-component timing window (L4), adversarial counterexample for original REQ set (L5 — G-5 closed by BPS-FT-002), and bounded temporal override ordering (L6 — closed by `OverrideOrderingRequirement`).

### Live sensor mode

```bash
python scripts/sensor_adapter.py --demo           # mock demo (6 scenarios)
python3 verify.py --fallback --live sensors.json  # real sensor snapshot + V&V
```

The sensor adapter connects to MQTT, OPC-UA, or REST endpoints and normalises readings into SysML bind values. See `scripts/sensor_adapter.py` for the full config schema. Demo mode runs without hardware.

---

## Step 3 — Build the model from scratch (cold start)

To build the `.sysml` layers from engineering source documents, open a GitHub Copilot chat in agent mode and invoke:

```
@SysML Orchestrator — run full pipeline on ./docs/ingested/
```

The Orchestrator scans all `bilgepump/docs/ingested/` subdirectories, determines which mapper agents to activate, writes the phase schedule to `lib/build-state.json`, and delegates in dependency order:

```
Phase 1: PortDefMapper + AttributeDefMapper  [parallel]
           └─► Phase 2: PartDefMapper + ConnectMapper
                 └─► Phase 3: RequirementMapper + ConstraintMapper  [parallel]
                       └─► Phase 3.5: RequirementMapper-STPA + ConstraintMapper-FMEA + RAAMLMapper
                             └─► Phase 4: AllocationMapper
                                   └─► Phase 5: AnalysisMapper  [nominal + FMEA + STPA + UQ]
                                         └─► Phase 6: TraceabilityAgent + VerificationAgent
                                               └─► Phase 7: AnalysisMapper-UQ  [optional]
```

After all agents complete, validate:

```bash
python3 scripts/ci_kernel_validate.py --dry-run   # file existence check
python3 scripts/ci_kernel_validate.py             # kernel compilation check
python3 verify.py                                  # full verification + results
```

---

## Step 4 — Update after a document change (delta run)

When any file in `bilgepump/docs/ingested/` changes (new CFD export, updated FMEA table, revised regulatory extract):

```
@SysML Orchestrator — delta run, docs/ingested/fmea/ changed
```

The Orchestrator sets `"mode": "delta"` in `lib/build-state.json`, identifies affected phases, and re-runs only those agents.

| Changed subdirectory | Agents re-run |
|---|---|
| `hazards/` | RequirementMapper-STPA → RAAMLMapper → AnalysisMapper-STPA |
| `fmea/` | ConstraintMapper-FMEA → RAAMLMapper → AnalysisMapper-FMEA |
| `uq/` | AnalysisMapper-UQ (Phase 7) |
| `interfaces/` or `components/` | PortDefMapper + AttributeDefMapper → PartDefMapper |
| `requirements/` or `constraints/` | RequirementMapper + ConstraintMapper |
| `allocations/` | AllocationMapper |

After the delta, re-run `python3 verify.py` to confirm all requirements still SATISFIED.

---

## The BilgePump Reference Project

The `bilgepump/` subfolder contains a SysML v2 model of a **maritime bilge pump system** — the automated machinery that removes water accumulating in a vessel's bilge.

### Regulatory traceability

| Standard | What it governs in this model |
|---|---|
| **SOLAS II-1** | Power redundancy — dual-feed requirement for bilge pumps |
| **MARPOL Annex I** | Overboard discharge must be below 15 ppm oily water |
| **DNV Rules Pt.4 Ch.6** | Redundant pump (Pump B), independent power feed, alarm table |
| **IEC 60945 §4.3** | Alarm activation delay ≤ 2.0 s for Class A alarms |

### The nine SysML v2 layers

Each layer is a separate `.sysml` file listed in `sysml-project.yml`. They must be executed in strict dependency order.

```
bilgepump/RAAML.sysml          ← no imports (must be first)
bilgepump/Library.sysml        ← imports nothing
bilgepump/Architecture.sysml   ← imports Library
bilgepump/Requirements.sysml   ← imports Library + Architecture
bilgepump/Analysis.sysml       ← imports all three above
bilgepump/Safety.sysml         ← imports RAAML + Library + Architecture + Requirements
bilgepump/FMEA.sysml           ← imports RAAML + all above + Safety    (negative tests)
bilgepump/UQ.sysml             ← imports Library + Architecture + Requirements + Analysis
bilgepump/StateMachine.sysml   ← imports Library + Architecture
```

The `validation_layers` key in `sysml-project.yml` lists the 7 layers that form the positive-test set (FMEA and UQ are excluded — they contain intentional violations; run them with `--all`).

| Layer | Package | Contents |
|---|---|---|
| `RAAML.sysml` | `BilgePump_RAAML` | 6 OMG RAAML v1.0 `metadata def` stereotypes |
| `Library.sysml` | `BilgePump_Library` | All `part def`, `port def`, `attribute def` — 8 components |
| `Architecture.sysml` | `BilgePump_Architecture` | `BilgePumpSystem` with 8 part usages and 11 `connect` statements |
| `Requirements.sysml` | `BilgePump_Requirements` | 4 `requirement def` blocks (BPS-REQ-001–004) |
| `Analysis.sysml` | `BilgePump_Analysis` | `PumpFlowPhysics` constraint + `BilgePumpVerification` positive test |
| `Safety.sysml` | `BilgePump_Safety` | STPA Losses, Hazards; 5 UCA-derived `requirement def` blocks |
| `FMEA.sysml` | `BilgePump_FMEA` | RPN / reliability / NPSH constraints; 4 negative-test `analysis def` |
| `UQ.sysml` | `BilgePump_UQ` | N=10 deterministic parametric uncertainty sweep |
| `StateMachine.sysml` | `BilgePump_StateMachine` | 7-state `PumpControllerBehavior` state machine |

### Notebooks (interactive exploration)

These notebooks are for interactive exploration — not required for CI or verification.

| Notebook | Kernel | When to use |
|---|---|---|
| `Analysis.ipynb` | SysML v2 | Interactive native model execution — run `assert requirement` cell-by-cell |
| `Safety.ipynb` | Python | STPA/FMEA/UQ detailed evaluation; tabular FMEA output; UQ sweep plots |
| `Results.ipynb` | Python | Post-verification result inspection using `lib/verification-results.json` |

Open interactively:
```bash
bash run.sh analysis    # Analysis.ipynb (SysML v2 kernel)
bash run.sh safety      # Safety.ipynb (Python kernel)
```

---

## Shell Scripts

### `setup.sh` — one-time environment setup

```bash
bash setup.sh
```

1. Checks Python 3 is available
2. Installs pip dependencies from `requirements.txt`
3. Creates conda env `sysmlv2` with `jupyter-sysml-kernel=0.58.0` and registers the `sysml` kernel (requires Miniconda + Java 21)

The SysML v2 kernel is the primary evaluation engine. Without it, `verify.py` falls back to Python regex/eval automatically.

### `commit.sh` — publish the model to the SST API (optional)

```bash
bash commit.sh                         # uses http://sysml2.intercax.com:9000
bash commit.sh http://localhost:9000   # override with a self-hosted server
```

Reads `sysml-project.yml` `layers` and POSTs all `.sysml` files to the SST API. Writes `lib/commit-ids.json`. This is **not required for local verification** — `verify.py` runs entirely offline. Use `verify.py --publish` for the equivalent one-step operation.

**Note:** `http://sysml2.intercax.com:9000` is a public research server with no uptime SLA. It stores model text verbatim — it does not parse, compile, or evaluate SysML.

### `run.sh` — open a notebook interactively

```bash
bash run.sh analysis    # Analysis.ipynb (SysML v2 kernel)
bash run.sh safety      # Safety.ipynb   (Python kernel)
```

---

## CI/CD Pipeline

```
  Developer opens PR touching *.sysml / tests/** / requirements-ci.txt
           │
           ▼
  ┌─────────────────────┐
  │  unit-tests         │
  │  ~15 seconds        │
  │  Python 3.11, no JVM│
  │  pytest tests/ -x   │
  └────────┬────────────┘
           │ pass
           ▼
  ┌────────────────────┐   ┌─────────────────────────────────────────────┐
  │  check-manifest    │   │  validate-sysml  (needs check-manifest pass) │
  │  ~4 seconds        │──▶│  conda + Java 21 + SysML v2 kernel  ~52s    │
  │  stdlib Python     │   │  Runs validation_layers only (see below)     │
  │  - files exist?    │   │  - syntax valid?                             │
  │  - manifest valid? │   │  - imports resolve?                          │
  └────────────────────┘   │  - positive-test assertions pass?            │
                            └─────────────────────────────────────────────┘
           │
    All three green?
     Yes → PR can be merged
     No  → PR is blocked
           │
           ▼  (merge to main only — optional)
  publish-to-api.yml
  - bash commit.sh (reads sysml-project.yml 'layers' — all 9)
  - POST all layers to SysML v2 API
  - Upload lib/commit-ids.json as Actions artifact
```

**Why `validation_layers` excludes FMEA and UQ:** `FMEA.sysml` contains 4 negative-test `analysis def` blocks that assert VIOLATED requirements by design. `UQ.sysml` has `UQ_Sweep_10` which violates `DischargeCapacityRequirement` at combined 3σ. Both would cause false CI failures if fed to the kernel.

### Setting up for a new project

1. Copy the infrastructure files:
   ```
   sysml-project.yml  verify.py  setup.sh  commit.sh  pyproject.toml
   scripts/ci_kernel_validate.py  scripts/fault_tracer.py  scripts/diagram_gen.py
   scripts/sysml_check.py  scripts/sensor_adapter.py  scripts/bootstrap_traceability.py
   requirements.txt  requirements-ci.txt
   .github/workflows/validate-pr.yml
   tests/  (copy the whole directory)
   ```

2. Edit `sysml-project.yml` for your project:
   ```yaml
   name: MyProject
   layers:
     - myproject/Library.sysml
     - myproject/Architecture.sysml
     - myproject/Requirements.sysml
     - myproject/Analysis.sysml
   validation_layers:    # omit any negative-test layers
     - myproject/Library.sysml
     - myproject/Architecture.sysml
     - myproject/Requirements.sysml
     - myproject/Analysis.sysml
   ```

3. Run locally:
   ```bash
   bash setup.sh
   python3 verify.py
   ```

---

## Assumptions, Caveats & Future Developments

### What works today

| Capability | Status |
|---|---|
| 9-layer SysML v2 model | **Fully functional** — kernel-validated, 7/7 positive-test layers pass |
| `verify.py` — kernel + fallback + fault trace + diagrams | **Fully functional** — primary verification entry point |
| `Safety.ipynb` Python evaluations (STPA/FMEA/UQ) | **Fully functional** |
| `sysml-project.yml` + `ci_kernel_validate.py` + CI workflows | **Fully functional** |
| Copilot mapper agents (14 agents) | **Invocation-ready** via GitHub Copilot agent mode |

### Known limitations

**1. RAAML `metadata def` syntax — Pilot API JAR version dependency**

`RAAML.sysml` uses `metadata def` and `#Annotation { }` blocks from the OMG RAAML v1.0 spec. This syntax requires the SysML v2 Pilot API JAR ≥ 2022-06. The SST public server version is not published. If the server rejects `RAAML.sysml` at commit time, apply the documented fallback: replace every `metadata def` with `attribute def` and remove all `#Annotation { }` blocks in `Safety.sysml` and `FMEA.sysml`. The requirement, constraint, and analysis logic remains valid without annotations.

**2. Python `require constraint` evaluator is a supplement, not a replacement**

`verify.py` uses the SysML v2 kernel as the primary evaluation engine. The Python regex/eval pass runs *after* the kernel as a structured extraction step (requirements → pass/fail → fault trace → JSON). The Python evaluator works reliably for arithmetic comparisons and boolean equality; it silently fails for chained attribute paths and unit-aware arithmetic. Use `--fallback` only when the kernel is unavailable.

**3. Copilot agents are invocation patterns, not executable scripts**

All files in `.github/agents/` are natural-language instruction sets for GitHub Copilot agent mode. They cannot be run directly. The full pipeline described in Step 3 requires a human to progress each phase or a Copilot session with tool access.

**4. UQ methodology — deterministic sweep, not Monte Carlo**

The N=10 sweep in `UQ.sysml` covers ±1σ and ±3σ individual deviations plus two combined worst-case points. A proper probabilistic UQ requires ≥10,000 samples, a correlation matrix, and Sobol sensitivity indices.

**5. FMEA reliability numbers are illustrative**

λ values, S/O/D ratings, and RPN thresholds reference real standards (IEC 61508-6, MIL-STD-1629A, Hydraulic Institute) but are not derived from field failure data.

**6. TraceabilityAgent does not scan `metadata def` constructs**

`lib/traceability.json` will not contain RAAML annotation elements. This is flagged in `Safety.ipynb` Cell 9 as a known gap.

### Future developments roadmap

| Priority | Development | Unlocks |
|---|---|---|
| High | Self-hosted SysML v2 API server (local JAR or Docker) | Persistent project storage, no SST dependency |
| High | Extend TraceabilityAgent to scan `metadata def` | Full RAAML traceability gate |
| Medium | STPA tool MCP (XSTAMPP API) | Live UCA extraction from STPA tool |
| Medium | FMEA tool MCP (ReliaSoft XFMEA, Windchill) | Live failure mode sync |
| Medium | Proper Monte Carlo UQ (OpenTURNS, SALib) | Statistically valid uncertainty quantification |
| Low | Extend AllocationMapper + VerificationAgent for Safety/FMEA layers | Full 9-layer traceability |

---

## Project Structure

```
sysml-project.yml           manifest: layer order, validation subset, project name
verify.py                   PRIMARY: local SysML v2 verification engine
setup.sh                    one-time: pip deps + SysML v2 kernel install
commit.sh                   POST all layers to SST API (optional)
run.sh                      open notebook interactively (analysis/safety)
requirements.txt            Python deps: jupyter, matplotlib, networkx, requests
requirements-ci.txt         CI-only Python deps: nbformat, nbclient
CLAUDE.md                   SysML v2 kernel flat-package rules (AI assistant context)

scripts/
  ci_kernel_validate.py     headless kernel validator (used in CI); --dry-run, --all-layers
  fault_tracer.py           cross-layer fault localizer (used by verify.py)
  diagram_gen.py            PNG diagram generator (used by verify.py --visual)

.github/
  workflows/
    validate-pr.yml         PR gate: check-manifest + validate-sysml (kernel)
    publish-to-api.yml      post-merge: publish to SST API (optional)
  agents/                   14 Copilot mapper agents for model element mapping

lib/
  build-state.json          Orchestrator phase state (phases 1–7)
  commit-ids.json           project UUID + per-layer commit UUIDs (written by commit.sh)
  traceability.json         element → source document map (written by TraceabilityAgent)
  verification-results.json last verify.py run output
  part-registry.json        part def names → file locations (written by PartDefMapper)

bilgepump/                  BilgePump reference project
  RAAML.sysml               OMG RAAML v1.0 metadata def stereotypes
  Library.sysml             part def, port def, attribute def (8 components)
  Architecture.sysml        BilgePumpSystem: 8 part usages + 11 connect statements
  Requirements.sysml        BPS-REQ-001 through BPS-REQ-004 + 5 UCA safety requirements
  Analysis.sysml            PumpFlowPhysics + BilgePumpVerification (positive test)
  Safety.sysml              STPA Losses, Hazards; 5 UCA requirement defs
  FMEA.sysml                RPN/reliability/NPSH constraints; 4 negative-test analysis defs
  UQ.sysml                  N=10 parametric uncertainty sweep analysis defs
  StateMachine.sysml        7-state PumpControllerBehavior state machine
  Analysis.ipynb            SysML v2 kernel: interactive model execution
  Safety.ipynb              Python: STPA/FMEA/UQ evaluation pipeline
  Results.ipynb             Python: result inspection
  docs/
    ingested/               Source documents for mapper agents (see Step 3)
    system_topology.png     Generated by verify.py --visual
    requirement_status.png  Generated by verify.py --visual
    traceability.png        Generated by verify.py --visual
```
