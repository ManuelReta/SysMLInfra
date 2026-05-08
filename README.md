# SysMLInfra

A **generic SysML v2 CI/CD infrastructure** with a maritime bilge pump system as the reference project.

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
