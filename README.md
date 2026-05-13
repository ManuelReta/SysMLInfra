# SysMLInfra

A **generic SysML v2 CI/CD infrastructure** with a maritime bilge pump system as the reference project.

| Layer | Contents | Who touches it |
|---|---|---|
| **Infrastructure** (root) | `commit.sh`, `verify.sh`, `run.sh`, `setup.sh`, `scripts/`, `.github/workflows/`, `sysml-project.yml` | Anyone reusing this for a new SysML v2 project |
| **BilgePump model** (`bilgepump/`) | Eight `.sysml` layers, Jupyter notebooks, engineering source documents | Systems engineers working on this specific system |

---

## Quick Start

### Step 1 — Build the model from scratch (cold start)

Open a GitHub Copilot chat in agent mode and invoke:

```
@SysML Orchestrator — run full pipeline on ./docs/ingested/
```

The Orchestrator scans all `docs/ingested/` subdirectories, determines which agents to activate, writes the phase schedule to `lib/build-state.json`, and delegates to each specialist agent in dependency order:

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

After all agents complete, validate and publish:

```bash
# 1. Syntax and file existence check (no kernel required):
python3 scripts/ci_kernel_validate.py --dry-run

# 2. Kernel validation — positive-test layers only (setup.sh required):
conda activate sysmlv2
python3 scripts/ci_kernel_validate.py

# 3. Commit all 8 layers to the SysML v2 API:
bash commit.sh

# 4. Verify base 4-layer requirements (Python eval):
bash verify.sh

# 5. Verify extended safety layers (STPA / FMEA / UQ):
bash run.sh safety        # opens Safety.ipynb — run all cells top to bottom
```

---

### Step 4 — Update after a document change (delta run)

When any file in `docs/ingested/` changes (new CFD export, updated FMEA table, revised regulatory extract), invoke:

```
@SysML Orchestrator — delta run, docs/ingested/fmea/ changed
```

The Orchestrator sets `"mode": "delta"` in `lib/build-state.json`, identifies which phases are affected by the changed subdirectory, re-runs only those agents, and re-gates. Agents whose source documents are unchanged are skipped.

| Changed subdirectory | Agents re-run |
|---|---|
| `hazards/` | RequirementMapper-STPA → RAAMLMapper → AnalysisMapper-STPA |
| `fmea/` | ConstraintMapper-FMEA → RAAMLMapper → AnalysisMapper-FMEA |
| `uq/` | AnalysisMapper-UQ (Phase 7) |
| `interfaces/` or `components/` | PortDefMapper + AttributeDefMapper → PartDefMapper |
| `requirements/` or `constraints/` | RequirementMapper + ConstraintMapper |
| `allocations/` | AllocationMapper |

After the delta, re-run the validation sequence from Step 1 starting at step 2.

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

### The eight SysML v2 layers

Each layer is a separate `.sysml` file listed in `sysml-project.yml`. They must be committed and executed in strict dependency order — first in the list has no imports.

```
bilgepump/RAAML.sysml          ← no imports (must be first)
bilgepump/Library.sysml        ← imports nothing
bilgepump/Architecture.sysml   ← imports Library
bilgepump/Requirements.sysml   ← imports Library + Architecture
bilgepump/Analysis.sysml       ← imports all three above
bilgepump/Safety.sysml         ← imports RAAML + Library + Architecture + Requirements
bilgepump/FMEA.sysml           ← imports RAAML + all above + Safety
bilgepump/UQ.sysml             ← imports Library + Architecture + Requirements + Analysis
```

| Layer | Package | Contents |
|---|---|---|
| `RAAML.sysml` | `BilgePump::RAAML` | 6 OMG RAAML v1.0 `metadata def` stereotypes: Hazard, Loss, UCA, FailureMode, FaultTree, SafetyRequirement |
| `Library.sysml` | `BilgePump::Library` | All `part def`, `port def`, `attribute def` — 8 components, no values |
| `Architecture.sysml` | `BilgePump::Architecture` | `BilgePumpSystem` with 8 part usages and 11 `connect` statements |
| `Requirements.sysml` | `BilgePump::Requirements` | 4 `requirement def` blocks (BPS-REQ-001–004) with `require constraint` |
| `Analysis.sysml` | `BilgePump::Analysis` | `PumpFlowPhysics` constraint + `BilgePumpVerification` nominal positive test |
| `Safety.sysml` | `BilgePump::Safety` | STPA Losses, Hazards; 5 UCA-derived `requirement def` blocks |
| `FMEA.sysml` | `BilgePump::FMEA` | RPN / parallel failure rate / NPSH `constraint def`; 4 negative-test `analysis def` |
| `UQ.sysml` | `BilgePump::UQ` | N=10 deterministic parametric uncertainty sweep `analysis def` blocks |

### Notebooks

| Notebook | Kernel | When to use |
|---|---|---|
| `Verification.ipynb` | Python | Base 4-layer workflow: commit, API persistence check, constraint evaluation |
| `Analysis.ipynb` | SysML v2 | Native model execution — runs `assert requirement` in the kernel |
| `Safety.ipynb` | Python | Full extended pipeline: commits all 8 layers; STPA positive test; FMEA negative tests; STPA loss scenarios; reliability metrics; UQ sweep; traceability summary |
| `Results.ipynb` | Python | Post-verification result inspection and reporting |

---

## Shell Scripts

### `setup.sh` — one-time environment setup

```bash
bash setup.sh
```

1. Checks network reachability of the SST SysML v2 API
2. Installs Python dependencies (`jupyter`, `requests`) via pip
3. Creates a conda environment `sysmlv2` and installs `jupyter-sysml-kernel=0.58.0` (requires Miniconda at `~/miniconda3` and Java 21)

The SysML v2 kernel is only needed to run `Analysis.ipynb` and `ci_kernel_validate.py`. All other scripts and notebooks run on a standard Python kernel.

### `commit.sh` — publish the model to the SysML v2 API

```bash
bash commit.sh                         # uses http://sysml2.intercax.com:9000
bash commit.sh http://localhost:9000   # override with a self-hosted server
```

Reads `sysml-project.yml` `layers` list and POSTs all eight `.sysml` files to the SST API as separate commits inside a single project. Writes `lib/commit-ids.json` and `lib/current-project-id.txt`.

**API URL resolution order** (highest priority first):
1. `SYSML_API_BASE` environment variable — used by CI via GitHub Actions secret
2. First positional argument (`$1`)
3. Hardcoded fallback: `http://sysml2.intercax.com:9000`

### `verify.sh` — verify base requirements against the committed model

```bash
bash verify.sh             # positive test — BPS-REQ-001 through 004 must be SATISFIED
bash verify.sh negative    # negative test — simulates pump A failure
```

**Scope:** evaluates only the four original regulatory requirements (BPS-REQ-001–004).
For STPA, FMEA, and UQ evaluation use `bash run.sh safety` → Safety.ipynb.

**Step 1** — API persistence check: confirms every committed layer still exists on the server.

**Step 2** — Constraint evaluation: parses `Requirements.sysml` and `Analysis.sysml`, evaluates all `require constraint` expressions in Python, writes `lib/verification-results.json`.

Expected results:

| Test | BPS-REQ-001 | BPS-REQ-002 | BPS-REQ-003 | BPS-REQ-004 |
|---|---|---|---|---|
| Positive (nominal) | SATISFIED | SATISFIED | SATISFIED | SATISFIED |
| Negative (pumpA=0) | VIOLATED | SATISFIED | SATISFIED | SATISFIED |

### `run.sh` — health-check the API and open a notebook

```bash
bash run.sh             # Verification.ipynb (Python kernel — base 4-layer)
bash run.sh analysis    # Analysis.ipynb     (SysML v2 kernel — native execution)
bash run.sh safety      # Safety.ipynb       (Python kernel — STPA/FMEA/UQ)
```

---

## CI/CD Pipeline

Only models that pass the kernel gate reach the API. The pipeline never contacts the SysML v2 API during PR validation.

```
  Developer opens PR touching *.sysml
           │
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
    Both green?
     Yes → PR can be merged
     No  → PR is blocked
           │
           ▼  (merge to main only)
  publish-to-api.yml
  - bash commit.sh (reads sysml-project.yml 'layers' — all 8)
  - POST all layers to SysML v2 API
  - Upload lib/commit-ids.json as Actions artifact
```

**Why `validation_layers` excludes FMEA and UQ:** `FMEA.sysml` contains 4 negative-test `analysis def` blocks that assert VIOLATED requirements by design. `UQ.sysml` has `UQ_Sweep_10` which violates `DischargeCapacityRequirement` at combined 3σ. Both would cause false CI failures if fed to the kernel. They are validated by `Safety.ipynb` instead, which evaluates them in Python and explicitly checks for the expected violations.

### Setting up for a new project

1. Copy the infrastructure files (all are generic — no BilgePump references):
   ```
   sysml-project.yml  commit.sh  verify.sh  run.sh  setup.sh
   scripts/ci_kernel_validate.py
   requirements.txt  requirements-ci.txt
   .github/workflows/validate-pr.yml
   .github/workflows/publish-to-api.yml
   ```

2. Edit `sysml-project.yml` for your project:
   ```yaml
   name: MyProject
   description: "Short description"
   layers:
     - myproject/Library.sysml
     - myproject/Architecture.sysml
     - myproject/Requirements.sysml
     - myproject/Analysis.sysml
   validation_layers:    # omit FMEA/negative-test layers
     - myproject/Library.sysml
     - myproject/Architecture.sysml
     - myproject/Requirements.sysml
     - myproject/Analysis.sysml
   ```

3. Add GitHub secret and branch protection:
   ```bash
   gh secret set SYSML_API_BASE --body "http://sysml2.intercax.com:9000"
   gh api repos/OWNER/REPO/branches/main/protection --method PUT --input - << 'EOF'
   {"required_status_checks":{"strict":true,"contexts":["check-manifest","validate-sysml"]},"enforce_admins":false,"required_pull_request_reviews":null,"restrictions":null}
   EOF
   ```

### Local CI validation

```bash
# File existence check — no kernel needed:
python3 scripts/ci_kernel_validate.py --dry-run

# Kernel validation — positive-test layers only (setup.sh required first):
conda activate sysmlv2 && pip install nbclient nbformat
python3 scripts/ci_kernel_validate.py

# Force kernel validation on ALL layers (shows expected FMEA/UQ violations):
python3 scripts/ci_kernel_validate.py --all-layers
```

---

## Assumptions, Caveats & Future Developments

### What works today

| Capability | Status |
|---|---|
| Base 4-layer model (Library → Analysis) | **Fully functional** — commit, verify, CI pipeline all work end-to-end |
| `Safety.ipynb` Python evaluations (STPA/FMEA/UQ) | **Fully functional** — all evaluations execute in Python against realistic mock data |
| 16 engineering mock JSON files | **Structurally valid** — realistic S/O/D values, CFD curves, σ-step sweep points |
| `sysml-project.yml` + `ci_kernel_validate.py` + CI workflows | **Fully functional** with `validation_layers` separation |
| Copilot agent files (12 agents) | **Invocation-ready** — invocable via GitHub Copilot agent mode |

### Known limitations (caveats)

**1. RAAML `metadata def` syntax — Pilot API JAR version dependency**

`RAAML.sysml` uses `metadata def` and `#Annotation { }` blocks from the OMG RAAML v1.0 spec. This syntax requires the SysML v2 Pilot API JAR ≥ 2022-06. The SST public server version is not published. If the server rejects RAAML.sysml at commit time, apply the documented fallback: replace every `metadata def` with `attribute def` and remove all `#Annotation { }` blocks in `Safety.sysml` and `FMEA.sysml`. The requirement, constraint, and analysis logic remains valid without annotations.

**2. Python constraint evaluator ≠ SysML v2 kernel**

`verify.sh` Step 2 and `Safety.ipynb` evaluate `require constraint` expressions using Python `regex + eval`. This is not the SysML v2 type system. It works reliably for:
- Arithmetic comparisons (`flowRate * efficiency * (1 - pipeLoss) >= designInflow`)
- Boolean equality (`isRedundant == true`)

It will silently fail or produce incorrect results for:
- Chained attribute paths in `bind` statements (`bind x = sys.y.z` — non-literal)
- Expressions requiring unit-aware arithmetic (e.g., mixing m/s and m³/s)
- `constraint def` equations with named intermediate values

`ci_kernel_validate.py` uses the actual SysML v2 kernel and is the authoritative pass/fail gate for the positive-test layers.

**3. Copilot agents are invocation patterns, not executable scripts**

All files in `.github/agents/` are natural-language instruction sets for GitHub Copilot agent mode. They are not executable. The Orchestrator cannot spawn subagents programmatically — it delegates by naming an agent in the Copilot chat context. The full pipeline described in Step 1 requires a human to progress each phase or a Copilot session with tool access to invoke subagents.

**4. SST public API — no persistence guarantee**

`http://sysml2.intercax.com:9000` is a public research server maintained by the SysML Submission Team. It has no uptime SLA, no authentication, and is periodically reset. Projects and commits created by `commit.sh` may be deleted at any time. `lib/commit-ids.json` stores the UUIDs but they become stale after a server reset. The API stores model text verbatim — it does not parse, compile, or evaluate it.

**5. UQ methodology — deterministic sweep, not Monte Carlo**

The N=10 sweep in `UQ.sysml` covers ±1σ and ±3σ individual deviations plus two combined worst-case points. This is a structural sensitivity analysis, not a full probabilistic UQ. Specifically:
- The three uncertain parameters (`flowRate_A`, `efficiency`, `pipeLoss`) are assumed to be **independent** — this is asserted, not verified. In practice, cavitation simultaneously degrades both flow rate and efficiency, introducing correlation.
- A proper probabilistic UQ requires ≥10,000 samples, a correlation matrix, and Sobol sensitivity indices (e.g., via Dakota, OpenTURNS, or SALib).

**6. FMEA reliability numbers are illustrative**

λ values (`1.5×10⁻⁵ failures/hour`), S/O/D ratings, and RPN thresholds in `pump-fmea-table.json` reference real standards (IEC 61508-6, MIL-STD-1629A, Hydraulic Institute) but are not derived from field failure data. They are chosen to produce realistic-looking results that demonstrate the pipeline, not to characterise an actual pump model.

**7. TraceabilityAgent does not scan `metadata def` constructs**

The current `sysml-traceability.agent.md` scans six construct types: `part def`, `port def`, `attribute def`, `requirement def`, `constraint def`, `analysis def`. It does not scan `metadata def` blocks in `RAAML.sysml`. RAAML annotation elements will not appear in `lib/traceability.json` and will not satisfy the TraceabilityAgent gate criteria. This is flagged in `Safety.ipynb` Cell 9 as a known gap.

**8. AllocationMapper, ConnectMapper, and VerificationAgent cover only the base 4-layer model**

These agents were designed for the original four layers. They have not been extended to handle the `allocate` / `satisfy` relationships that would link Safety/FMEA elements to physical parts, or to run VerificationAgent assertions against the UCA requirement defs. AllocationMapper can be invoked against `functional-allocation.json` independently — it writes to `Architecture.sysml`, not to the safety layers.

### Future developments roadmap

| Priority | Development | Unlocks |
|---|---|---|
| High | Self-hosted SysML v2 API server (e.g., local JAR or Docker) | Persistent project storage, no SST dependency, `metadata def` support |
| High | Extend TraceabilityAgent to scan `metadata def` | Full RAAML traceability gate — closes gap #7 |
| Medium | STPA tool MCP (XSTAMPP API, STAMP Web Tools) | Live UCA extraction direct from STPA tool — eliminates manual JSON export |
| Medium | FMEA tool MCP (ReliaSoft XFMEA, APIS IQ-FMEA, Windchill FMEA) | Live failure mode sync — eliminates RPN transcription errors |
| Medium | Proper Monte Carlo UQ (Dakota, OpenTURNS, SALib) | Statistically valid uncertainty quantification with Sobol indices |
| Low | SysML v2 kernel unit expressions | Unit-aware constraint evaluation — eliminates Python re-implementation |
| Low | Extend AllocationMapper + VerificationAgent for Safety/FMEA layers | Close gap #8 — full 8-layer traceability and verification pipeline |
| Low | Regulatory text search MCP (IEC/IMO/DNV indexed corpus) | RequirementMapper can extract "shall" statements directly from PDF standards |

---

## Project Structure

```
sysml-project.yml           manifest: layer order, validation subset, project name
commit.sh                   POST all layers to SysML v2 API (reads manifest 'layers')
verify.sh                   API persistence check + base 4-layer constraint eval
run.sh                      health-check API + open notebook (verification/analysis/safety)
setup.sh                    one-time: pip deps + SysML v2 kernel install
requirements.txt            local Python deps: jupyter, requests
requirements-ci.txt         CI-only Python deps: nbformat, nbclient
CLAUDE.md                   SysML v2 kernel flat-package rules and import syntax

scripts/
  ci_kernel_validate.py     headless SysML v2 kernel runner; uses 'validation_layers'
                            (excludes FMEA/UQ negative tests); --dry-run, --all-layers flags

.github/
  workflows/
    validate-pr.yml         PR gate: check-manifest + validate-sysml
    publish-to-api.yml      post-merge: publish to API, upload artifact
  agents/                   13 Copilot agents for model element mapping
    sysml-orchestrator.agent.md
    sysml-port-def-mapper.agent.md
    sysml-attribute-def-mapper.agent.md
    sysml-part-def-mapper.agent.md
    sysml-connect-mapper.agent.md
    sysml-requirement-mapper.agent.md    ← extended: STPA UCA requirements
    sysml-constraint-mapper.agent.md     ← extended: FMEA constraint defs
    sysml-analysis-mapper.agent.md       ← extended: FMEA/STPA/UQ analysis defs
    sysml-allocation-mapper.agent.md
    sysml-raaml-mapper.agent.md          ← new: OMG RAAML v1.0 annotation index
    sysml-traceability.agent.md
    sysml-verification.agent.md
    sysml-conflict-resolution.agent.md

lib/
  build-state.json          Orchestrator phase state (phases 1–7 including 3.5)
  commit-ids.json           project UUID + per-layer commit UUIDs (written by commit.sh)
  traceability.json         element → source document map (written by TraceabilityAgent)
  verification-results.json last verify.sh run output
  part-registry.json        part def names → file locations (written by PartDefMapper)
  staged-attribute-values.json  staged defaults for AnalysisMapper bindings

bilgepump/                  BilgePump reference project
  RAAML.sysml               OMG RAAML v1.0 metadata def stereotypes (6 blocks)
  Library.sysml             part def, port def, attribute def (8 components)
  Architecture.sysml        BilgePumpSystem: 8 part usages + 11 connect statements
  Requirements.sysml        BPS-REQ-001 through BPS-REQ-004
  Analysis.sysml            PumpFlowPhysics + BilgePumpVerification (positive test)
  Safety.sysml              STPA Losses, Hazards; 5 UCA requirement defs
  FMEA.sysml                RPN/reliability/NPSH constraints; 4 negative-test analysis defs
  UQ.sysml                  N=10 parametric uncertainty sweep analysis defs
  Verification.ipynb        Python: base 4-layer API workflow
  Analysis.ipynb            SysML v2 kernel: native model execution
  Safety.ipynb              Python: full STPA/FMEA/UQ evaluation pipeline
  Results.ipynb             Python: result inspection
  docs/ingested/
    interfaces/             N2 matrix, ICD → PortDefMapper
    attributes/             CFD exports, datasheets → AttributeDefMapper
    components/             BOM → PartDefMapper
    connections/            P&ID → ConnectMapper
    requirements/           SOLAS/MARPOL/DNV/IEC extracts → RequirementMapper
    constraints/            OpenFOAM, Simulink exports → ConstraintMapper
    allocations/            FFBD functional decomposition → AllocationMapper
    analyses/               test procedures → AnalysisMapper
    hazards/                STPA hazards, UCAs, loss scenarios → RequirementMapper-STPA
    fmea/                   FMEA table, constraints, scenarios → ConstraintMapper-FMEA
    uq/                     UQ configuration, sweep points → AnalysisMapper-UQ
```

The repository has two concerns kept deliberately separate:

| Layer | Contents | Who touches it |
|---|---|---|
| **Infrastructure** (root) | `commit.sh`, `verify.sh`, `run.sh`, `setup.sh`, `scripts/`, `.github/workflows/`, `sysml-project.yml` | Anyone reusing this for a new SysML v2 project |
| **BilgePump model** (`bilgepump/`) | Four `.sysml` layers, Jupyter notebooks, engineering source documents | Systems engineers working on this specific system |

---

## The BilgePump Reference Project

The `bilgepump/` subfolder contains a SysML v2 model of a **maritime bilge pump system** — the automated machinery that removes water accumulating in a vessel's bilge. The model is traceable to maritime regulatory standards:

| Standard | What it governs in this model |
|---|---|
| **SOLAS II-1** | Power redundancy — dual-feed requirement for bilge pumps |
| **MARPOL Annex I** | Overboard discharge must be below 15 ppm oily water |
| **DNV Rules Pt.4 Ch.6** | Redundant pump (Pump B), independent power feed, alarm table |
| **IEC 60945 §4.3** | Alarm activation delay ≤ 2.0 s for Class A alarms |

### The four SysML v2 layers

Each layer is a separate `.sysml` file. They import each other in strict dependency order — the same order declared in `sysml-project.yml` and enforced by the CI pipeline.

```
bilgepump/Library.sysml          ← imported by nothing (must execute first)
bilgepump/Architecture.sysml     ← imports Library
bilgepump/Requirements.sysml     ← imports Library + Architecture
bilgepump/Analysis.sysml         ← imports all three above (must execute last)
```

**`Library.sysml`** — the type vocabulary. Defines all `part def`, `port def`, and `attribute def` blocks. No values assigned here; no connections. Everything else imports from this layer.

Components defined: `BilgeWaterSensor`, `PumpController`, `PowerSupply`, `BilgePumpA`, `BilgePumpB`, `DischargeLine`, `AlarmSystem`, `OperatorInterface`.

**`Architecture.sysml`** — the system topology. Instantiates all eight components as `part` usages inside `BilgePumpSystem` and wires them with `connect` statements. Assigns nominal attribute values (flow rates, efficiencies, trigger levels, etc.).

**`Requirements.sysml`** — formal requirements. Defines four `requirement def` blocks (`BPS-REQ-001` through `BPS-REQ-004`), each with a `require constraint` expression that can evaluate to SATISFIED or VIOLATED.

**`Analysis.sysml`** — the test runner. Defines `PumpFlowPhysics` (a parametric constraint implementing the Darcy-Weisbach discharge equation) and `BilgePumpVerification` (an `analysis def` that binds attribute values from the system and asserts all four requirements). This is the layer the CI pipeline executes last.

### Notebooks

| Notebook | Kernel | Purpose |
|---|---|---|
| `bilgepump/Verification.ipynb` | Python | Interactive API workflow: commit layers, check persistence, evaluate constraints |
| `bilgepump/Analysis.ipynb` | SysML v2 | Native model execution — runs `assert requirement` directly in the kernel |
| `bilgepump/Results.ipynb` | Python | Post-verification result inspection and reporting |

---

## Shell Scripts

### `setup.sh` — one-time environment setup

Run once before using the project. Safe to re-run.

```bash
bash setup.sh
```

1. Checks network reachability of the SST SysML v2 API at `http://sysml2.intercax.com:9000`
2. Installs Python dependencies (`jupyter`, `requests`) via pip
3. Creates a conda environment `sysmlv2` and installs `jupyter-sysml-kernel=0.58.0` (requires Miniconda at `~/miniconda3` and Java 21)

The SysML v2 kernel is only needed to run `Analysis.ipynb` natively. `Verification.ipynb` runs on a standard Python kernel.

---

### `commit.sh` — publish the model to the SysML v2 API

```bash
bash commit.sh                         # uses http://sysml2.intercax.com:9000
bash commit.sh http://localhost:9000   # override with a self-hosted server
```

Reads `sysml-project.yml` to determine the layer list and order, then POSTs each `.sysml` file to the SST API as a separate commit inside a single project. Writes `lib/commit-ids.json` (project UUID + per-layer commit UUIDs) and `lib/current-project-id.txt`.

**API URL resolution order** (highest priority first):
1. `SYSML_API_BASE` environment variable — used by CI via GitHub Actions secret
2. First positional argument (`$1`)
3. Hardcoded fallback: `http://sysml2.intercax.com:9000`

The CI pipeline (`publish-to-api.yml`) calls this script automatically on every merge to `main`.

---

### `verify.sh` — verify requirements against the committed model

```bash
bash verify.sh             # positive test — all requirements must be SATISFIED
bash verify.sh negative    # negative test — simulates pump A failure
```

Two steps:

**Step 1 — API persistence check:** Reads `lib/commit-ids.json` and confirms every layer commit still exists on the API server. Exits 1 if any commit is missing.

**Step 2 — Constraint evaluation:** Reads the analysis and requirements layer paths from `sysml-project.yml`, parses `bind` values and `require constraint` expressions, and evaluates them in Python. Prints SATISFIED/VIOLATED per requirement and writes `lib/verification-results.json`.

Expected results:

| Test | BPS-REQ-001 | BPS-REQ-002 | BPS-REQ-003 | BPS-REQ-004 |
|---|---|---|---|---|
| Positive (nominal) | SATISFIED | SATISFIED | SATISFIED | SATISFIED |
| Negative (pumpA=0) | VIOLATED | SATISFIED | SATISFIED | SATISFIED |

**Note:** Step 2 uses a Python re-implementation of the constraint expressions, not the SysML v2 kernel. It covers arithmetic and boolean constraints reliably. The CI pipeline uses the kernel instead, which evaluates constraints natively.

---

### `run.sh` — health-check the API and open a notebook

```bash
bash run.sh             # opens bilgepump/Verification.ipynb (Python kernel)
bash run.sh analysis    # opens bilgepump/Analysis.ipynb (SysML v2 kernel)
```

Confirms the SST API is reachable, derives the notebook directory from the first layer path in `sysml-project.yml`, then launches Jupyter. The `analysis` mode uses the `sysmlv2` conda environment installed by `setup.sh`.

---

## CI/CD Pipeline

The pipeline protects the SysML v2 API server (the single source of truth) from receiving unvalidated or partial-branch models. Only models that pass the kernel gate reach the API.

```
  Developer opens PR touching *.sysml
           │
           ▼
  ┌────────────────────┐   ┌─────────────────────────────────────┐
  │  check-manifest    │   │  validate-sysml  (needs check-      │
  │  ~4 seconds        │──▶│  manifest to pass first)  ~52s      │
  │  stdlib Python     │   │  conda + Java 21 + SysML v2 kernel  │
  │  - files exist?    │   │  - syntax valid?                     │
  │  - manifest valid? │   │  - imports resolve?                  │
  └────────────────────┘   │  - types compatible?                 │
                            │  - assert requirements pass?         │
                            └─────────────────────────────────────┘
           │
    Both green?
     Yes → PR can be merged
     No  → PR is blocked
           │
           ▼  (merge to main only)
  publish-to-api.yml
  - bash commit.sh (reads sysml-project.yml)
  - POST all layers to SysML v2 API
  - Upload lib/commit-ids.json as Actions artifact
```

The SysML v2 API is **never contacted** during PR validation. It only receives clean, compiled, assertion-passing models after a merge to `main`.

### Setting up this pipeline for a new project

1. Copy the infrastructure files (all are generic — no BilgePump references):
   ```
   sysml-project.yml
   commit.sh  verify.sh  run.sh  setup.sh
   scripts/ci_kernel_validate.py
   requirements.txt  requirements-ci.txt
   .github/workflows/validate-pr.yml
   .github/workflows/publish-to-api.yml
   ```

2. Create your project folder (e.g. `myproject/`) and edit `sysml-project.yml`:
   ```yaml
   name: MyProject
   description: "Short description"
   layers:
     - myproject/Library.sysml
     - myproject/Architecture.sysml
     - myproject/Requirements.sysml
     - myproject/Analysis.sysml
   ```

3. Add GitHub repository secret via the terminal:
   ```bash
   gh secret set SYSML_API_BASE --body "http://sysml2.intercax.com:9000"
   ```

4. Enable branch protection via the terminal:
   ```bash
   gh api repos/OWNER/REPO/branches/main/protection \
     --method PUT \
     --input - << 'EOF'
   {"required_status_checks":{"strict":true,"contexts":["check-manifest","validate-sysml"]},"enforce_admins":false,"required_pull_request_reviews":null,"restrictions":null}
   EOF
   ```

5. Open a PR — both CI jobs fire automatically.

### Local CI validation (no push required)

```bash
# Verify manifest and file existence — no kernel needed
python3 scripts/ci_kernel_validate.py --dry-run

# Full kernel validation — requires sysmlv2 conda env (setup.sh)
conda activate sysmlv2
pip install nbclient nbformat
python3 scripts/ci_kernel_validate.py
```

---

## Project Structure

```
sysml-project.yml           manifest: layer order, project name, description
commit.sh                   POST layers to SysML v2 API (reads manifest)
verify.sh                   API persistence check + constraint evaluation
run.sh                      health-check API + open notebook (reads manifest)
setup.sh                    one-time: pip deps + SysML v2 kernel install
requirements.txt            local Python deps: jupyter, requests
requirements-ci.txt         CI-only Python deps: nbformat, nbclient
CLAUDE.md                   SysML v2 kernel flat-package rules and import syntax

scripts/
  ci_kernel_validate.py     headless SysML v2 kernel runner; reads manifest;
                            auto-discovers registered kernel name at runtime

.github/
  workflows/
    validate-pr.yml         PR gate: check-manifest + validate-sysml
    publish-to-api.yml      post-merge: publish to API, upload artifact
  agents/                   12 Copilot agents for model element mapping

bilgepump/                  BilgePump reference project (all project-specific files)
  Library.sysml             part def, port def, attribute def
  Architecture.sysml        BilgePumpSystem composition + connect statements
  Requirements.sysml        BPS-REQ-001 through BPS-REQ-004
  Analysis.sysml            PumpFlowPhysics constraint + BilgePumpVerification
  Verification.ipynb        Python kernel: interactive API workflow
  Analysis.ipynb            SysML v2 kernel: native model execution
  Results.ipynb             Python kernel: result inspection
  docs/ingested/            engineering source documents for Copilot agents
    interfaces/             → PortDefMapper input
    attributes/             → AttributeDefMapper input
    components/             → PartDefMapper input
    connections/            → ConnectMapper input
    requirements/           → RequirementMapper input
    constraints/            → ConstraintMapper input
    allocations/            → AllocationMapper input
    analyses/               → AnalysisMapper input

lib/                        runtime state — excluded from git (.gitignore)
  commit-ids.json           project UUID + per-layer commit UUIDs (from commit.sh)
  current-project-id.txt   project UUID shortcut
  verification-results.json SATISFIED/VIOLATED results (from verify.sh)
  build-state.json          Copilot agent orchestrator phase state
  traceability.json         element-to-source traceability index
  part-registry.json        part def → instance name map
  staged-attribute-values.json numeric values staged between agents
```

---

## API Server

| Item | Value |
|---|---|
| Host | `http://sysml2.intercax.com:9000` |
| Type | SST-hosted SysML v2 Pilot Implementation |
| Auth | None (public) |
| Persistence | Projects survive restarts; server is shared — treat content as public |

After a merge to `main`, the `sysml-api-publish-state` artifact in the Actions run contains `lib/commit-ids.json` with the project ID and per-layer commit IDs needed to query the API directly.


---
