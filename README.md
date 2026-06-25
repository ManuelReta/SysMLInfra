# SysMLInfra

A **reusable SysML v2 MBSE framework** for building traceable, kernel-verified system models
from engineering source documents, with CI/CD integration and AI-assisted model generation.

> **The SysML v2 Jupyter kernel is required.**
> Without it, `assert requirement` statements cannot be evaluated.
> The Python regex/eval fallback (`--fallback`) is for development and CI iteration ONLY.
> Run `bash setup.sh` first — it installs and validates the kernel.

| Layer | Contents | Who touches it |
|---|---|---|
| **Framework** (root) | `verify.py`, `setup.sh`, `scripts/`, `.github/workflows/`, `sysml-project.yml` | Anyone reusing for a new SysML v2 project |
| **Reference example** (`examples/bilgepump/`) | Nine `.sysml` layers, Jupyter notebooks, engineering source documents | Engineers exploring or adapting the framework |

---

## Prerequisites (REQUIRED before anything else)

| Requirement | Why |
|---|---|
| **Miniconda** (`~/miniconda3`) | Creates the `sysmlv2` conda environment |
| **Java 21+** | Powers the SysML v2 kernel JAR |
| **Python 3.8+** | Runs `verify.py`, scripts, and tests |

Install Miniconda: <https://repo.anaconda.com/miniconda/>
Install Java 21: `sudo apt-get install openjdk-21-jre-headless`

Then run setup — it enforces these requirements and exits with a clear error if anything is missing:

```bash
bash setup.sh
```

Setup installs the `jupyter-sysml-kernel=0.58.0` into a `sysmlv2` conda environment, registers
the `sysml` kernel spec, and validates with `jupyter kernelspec list`. **It will exit non-zero
if the kernel cannot be registered.**

---

## Quick Start (reference example)

```bash
# Verify the bilge pump reference model against all requirements:
uv run python -m sys_infra.entry verify

# Run the negative test — inject a pump failure:
uv run python -m sys_infra.entry verify --negative

# Check all layer files exist without running the kernel:
uv run python -m sys_infra.entry verify --dry-run

# Run unit and model tests (no kernel required):
uv run pytest tests/ -v
```

Expected output:

```
════════════════════════════════════════════════════════════════════
  SysML v2 Verification
════════════════════════════════════════════════════════════════════
  Engine  : SysML v2 kernel (sysml)
  Mode    : positive test (validation_layers)
────────────────────────────────────────────────────────────────────

  Kernel layer compilation:
    ✓  RAAML.sysml
    ✓  Library.sysml
    ✓  Architecture.sysml
    ✓  Requirements.sysml
    ✓  Analysis.sysml
    ✓  Safety.sysml
    ✓  StateMachine.sysml

  Requirement evaluation:
  ──────────────────────────────────────────────────────────────────
  ✓  SATISFIED   <REQ-001>  ...
  ✓  SATISFIED   <REQ-002>  ...
  ──────────────────────────────────────────────────────────────────
  Overall:  ALL SATISFIED ✓
```

### All `verify.py` flags

| Flag | What it does |
|---|---|
| *(none)* | Kernel run, positive test — all `validation_layers` |
| `--negative` | Inject a component failure; show fault trace to UCA + FMEA |
| `--visual` | Also generate topology/traceability diagrams |
| `--dry-run` | List layer files and sizes; do not start kernel |
| `--require-kernel` | Exit code 2 if kernel not found (use in CI to hard-fail) |
| `--fallback` | Python regex/eval **DEV/TEST only** — does not evaluate SysML semantics |
| `--all` | Run all layers including negative-test (FMEA) and UQ sweep |
| `--publish` | After verification, push model to SST API (optional) |
| `--verbose` | Show constraint expression under each requirement result |
| `--z3` | Run Z3 SMT formal analysis after SysML verification (requires `z3-solver`) |
| `--live CONFIG` | Load bind values from a live sensor adapter config |

---

## Starting a New Project

1. **Clone this repository**

2. **Run setup** (kernel install + Python deps):
   ```bash
   bash setup.sh
   ```

3. **Create your project directory** under `examples/`:
   ```
   examples/
     myproject/
       docs/ingested/    ← place pre-extracted engineering documents here
       Library.sysml     ← framework generates these from docs
       Architecture.sysml
       Requirements.sysml
       Analysis.sysml
   ```

4. **Edit `sysml-project.yml`**:
   ```yaml
   name: MyProject
   layers:
     - examples/myproject/RAAML.sysml
     - examples/myproject/Library.sysml
     - examples/myproject/Architecture.sysml
     - examples/myproject/Requirements.sysml
     - examples/myproject/Analysis.sysml
   validation_layers:
     - examples/myproject/Library.sysml
     - examples/myproject/Architecture.sysml
     - examples/myproject/Requirements.sysml
     - examples/myproject/Analysis.sysml
   ```

5. **Invoke the Copilot Orchestrator** to build the model from your documents:
   ```
   @SysML Orchestrator — run full pipeline on examples/myproject/docs/ingested/
   ```

6. **Verify**:
   ```bash
   python verify.py
   ```

### SysML v2 Layer Architecture

Every SysML v2 project built with this framework uses this 9-layer structure.
The flat-package rule is mandatory (see [CLAUDE.md](CLAUDE.md)):

```
RAAML.sysml          ← RAAML v1.0 metadata def stereotypes (no imports)
Library.sysml        ← all part def, port def, attribute def
Architecture.sysml   ← system composition (part usages + connect)
Requirements.sysml   ← requirement def blocks with require constraint
Analysis.sysml       ← constraint def + analysis def (bind + assert)
Safety.sysml         ← STPA losses, hazards, UCA-derived requirements
FMEA.sysml           ← RPN/reliability constraints (negative tests — excluded from CI gate)
UQ.sysml             ← parametric uncertainty sweep (excluded from CI gate)
StateMachine.sysml   ← state def + transition blocks
```

**Execution order is strict.** Each layer imports from all prior layers via the flat-package rule:
```sysml
private import <Project>_Library::*;
private import <Project>_Architecture::*;
```

---

## AI-Assisted Model Generation (Copilot Agents)

The `.github/agents/` directory contains 14 Copilot agent files that map engineering
source documents to SysML v2 model elements. These agents are invoked in agent mode
via GitHub Copilot and are reusable for any project — not bilge-pump-specific.

### Agent pipeline

```
Phase 1: PortDefMapper + AttributeDefMapper  [parallel]
           └─► Phase 2: PartDefMapper + ConnectMapper
                 └─► Phase 3: RequirementMapper + ConstraintMapper  [parallel]
                       └─► Phase 3.5: RequirementMapper-STPA + ConstraintMapper-FMEA + RAAMLMapper
                             └─► Phase 4: AllocationMapper
                                   └─► Phase 5: AnalysisMapper  [nominal + FMEA + STPA + UQ]
                                         └─► Phase 6: TraceabilityAgent + VerificationAgent
                                               └─► Phase 7: StateMachineMapper  [optional]
```

### Input document structure (`docs/ingested/`)

Each subdirectory feeds a specific set of agents:

| Subdirectory | Fed to | Produces |
|---|---|---|
| `interfaces/` | PortDefMapper | `port def` blocks in Library.sysml |
| `attributes/` | AttributeDefMapper | `attribute def` blocks in Library.sysml |
| `components/` | PartDefMapper | `part def` blocks in Library.sysml |
| `connections/` | ConnectMapper | `connect` statements in Architecture.sysml |
| `requirements/` | RequirementMapper | `requirement def` in Requirements.sysml |
| `constraints/` | ConstraintMapper | `constraint def` in Analysis.sysml |
| `allocations/` | AllocationMapper | `allocate`/`satisfy` in Architecture.sysml |
| `analyses/` | AnalysisMapper | `analysis def` blocks in Analysis.sysml |
| `hazards/` | RequirementMapper-STPA, RAAMLMapper | Safety.sysml |
| `fmea/` | ConstraintMapper-FMEA, RAAMLMapper | FMEA.sysml |
| `states/` | StateMachineMapper | StateMachine.sysml |

---

## CI/CD Pipeline

```
PR opened touching *.sysml / tests/** / requirements-ci.txt
         │
         ▼
  ┌───────────────┐
  │  unit-tests   │  pytest tests/ -x   (~15 s, no kernel)
  └───────┬───────┘
          │ pass
          ▼
  ┌──────────────────┐   ┌──────────────────────────────────────┐
  │ check-manifest   │──▶│ validate-sysml                       │
  │ (~4 s)           │   │ conda + Java 21 + SysML v2 kernel    │
  │ - files exist?   │   │ validation_layers only  (~52 s)      │
  │ - manifest valid?│   │ - syntax + imports + assert req pass?│
  └──────────────────┘   └──────────────────────────────────────┘
          │ all green → merge allowed
          ▼  (merge to main — optional)
  publish-to-api.yml  →  POST all layers to SST API
```

**`--require-kernel` in CI**: Add this flag to any CI step that must hard-fail if the kernel
is not registered. Exit code 2 distinguishes "kernel missing" from other errors.

---

## The BilgePump Reference Example

`examples/bilgepump/` contains a complete 9-layer SysML v2 model of a maritime bilge pump
system. It demonstrates every capability of this framework:

- Full regulatory traceability (SOLAS, MARPOL, DNV, IEC 60945)
- STPA safety analysis with UCA-derived requirements
- FMEA with RPN thresholds and negative-test scenarios
- Z3 formal analysis (6 levels)
- Parametric UQ sweep
- 7-state controller state machine
- All 14 Copilot agents have been applied to produce this model

To explore it interactively:
```bash
bash run.sh analysis    # Analysis.ipynb (SysML v2 kernel)
bash run.sh safety      # Safety.ipynb (STPA/FMEA/UQ, Python kernel)
```

---

## Testing

```bash
pytest tests/ -v            # all unit + model tests (~15 s, no kernel)
pytest tests/unit/ -v       # unit tests only (~5 s)
pytest tests/model/ -v      # model fallback tests (~10 s)
pytest tests/ -m z3 -v      # Z3 tests (requires z3-solver)
```

Single-file kernel check:
```bash
python scripts/sysml_check.py examples/bilgepump/Analysis.sysml --fallback  # ~1 s, no kernel
python scripts/sysml_check.py examples/bilgepump/Requirements.sysml          # full kernel
python scripts/sysml_check.py examples/bilgepump/FMEA.sysml --expect-violations
```

---

## Project Structure

```
sysml-project.yml              manifest: layer order, validation subset
verify.py                      PRIMARY: verification engine (kernel + fallback + fault trace)
setup.sh                       one-time: kernel install + Python deps (REQUIRED first)
commit.sh                      POST all layers to SST API (optional)
run.sh                         open notebook interactively
requirements.txt               Python deps
requirements-ci.txt            CI-only Python deps

scripts/
  ci_kernel_validate.py        headless kernel validator (used in CI)
  fault_tracer.py              cross-layer fault localizer (used by verify.py)
  diagram_gen.py               PNG diagram generator (verify.py --visual)
  sysml_check.py               single-file checker for local development
  bootstrap_traceability.py    populate lib/traceability.json from ingested docs
  sensor_adapter.py            live sensor ingestion adapter

.github/
  workflows/
    validate-pr.yml            PR gate: unit-tests + check-manifest + validate-sysml
    publish-to-api.yml         post-merge: publish to SST API
  agents/                      14 reusable Copilot mapper agents

lib/
  build-state.json             Orchestrator phase state
  commit-ids.json              per-layer SST API commit UUIDs
  traceability.json            element → source document map
  verification-results.json    last verify.py run output
  part-registry.json           part def names → file locations

examples/
  bilgepump/                   Maritime bilge pump reference model
    RAAML.sysml                OMG RAAML v1.0 metadata def stereotypes
    Library.sysml              Part/port/attribute definitions
    Architecture.sysml         System composition
    Requirements.sysml         Requirement defs with constraints
    Analysis.sysml             Constraint defs + verification analysis
    Safety.sysml               STPA/UCA safety requirements
    FMEA.sysml                 Failure mode analyses (negative tests)
    UQ.sysml                   Parametric uncertainty sweep
    StateMachine.sysml         Controller state machine
    Analysis.ipynb             Interactive SysML v2 notebook
    Safety.ipynb               STPA/FMEA/UQ Python notebook
    Results.ipynb              Result inspection notebook
    docs/ingested/             Pre-extracted source documents for agents

tests/
  unit/                        verify.py + helper unit tests
  model/                       full-layer fallback evaluator tests
  conftest.py                  shared pytest fixtures
```

---

## Caveats

**1. `--fallback` is not verification**
The Python regex/eval pass does not run the SysML v2 type checker.
It works reliably for simple arithmetic comparisons but silently ignores complex
attribute path chains and unit semantics. Use the kernel for authoritative results.

**2. RAAML `metadata def` requires JAR ≥ 2022-06**
If the SST public server rejects `RAAML.sysml`, replace `metadata def` with `attribute def`
and remove `#Annotation { }` blocks. The requirement/constraint/analysis logic remains valid.

**3. Copilot agents are instruction sets, not scripts**
Files in `.github/agents/` are natural-language instructions for Copilot agent mode.
They require a human to advance each phase or a Copilot session with tool access.

**4. UQ is a deterministic sweep, not Monte Carlo**
The N=10 sweep covers ±1σ and ±3σ deviations. A proper probabilistic UQ requires
≥10,000 samples with a correlation matrix.



## Dependency manager
Use uv as dependency manager. 
```
uv tool install pre-commit --with pre-commit-uv
uv run pre-commit install
uv run python /mnt/c/Users/SINKAA/Desktop/code/reactor_sys/jupyer-kernel/install.py --sys-prefix
```



## Containerised sysml v2 pilot API
To build image docker or podman 
```
docker build -f Dockerfile_pilot_api . --tag sysmlv2-pilot-api
```
```
podman build -f Dockerfile_pilot_api . --tag sysmlv2-pilot-api
```

To build and run the pilot api with postgres container with docker/podman: 
```
docker compose up --build
```
```
podman-compose up --build
```
You need podman-compose for this. 
```
sudo apt install podman-compose
```
### Certificate issue in docker container: 
Due to the dnv proxy certificates have to be manually mounted into the container runtime. Follow instructions from here and add the env variable
CERT_PATH=/path/to/cerfile.cert in .env file of repo. 

https://sslinsights.com/pkix-path-building-failed-unable-to-find-valid-certification-path/

Copy zscaler.cert from. 
In mount this file volume into /etc/ssl/certs





## Suggestions

#### Specifying External Tools (to be implemented)
The configuration for launching external tools is given in e.g. a metadata definition which is connected to an analysis def. This contains all info needed for launching an analysis job and storing data at an appropriate location. 

```
package LayeredSystem {

    private import ScalarValues::Real;
    private import ScalarValues::Boolean;

    part def PumpSystem {

        attribute flowRate   : Real;
        attribute efficiency : Real;
        attribute powerInput : Real;

        attribute hydraulicPower : Real = flowRate * 1000;
        attribute usefulPower    : Real = hydraulicPower * efficiency;
        attribute loss           : Real = powerInput - usefulPower;

        attribute isEfficient : Boolean = efficiency > 0.75;
        attribute isSafe      : Boolean = loss >= 0 and efficiency <= 1.0;
    }

    // Requirement definitions
    requirement def LossRequirement {
        subject s : PumpSystem;
        require constraint {
            s.loss >= 0
        }
    }

    requirement def EfficiencyRequirement {
        subject s : PumpSystem;
        require constraint {
            s.efficiency >= 0.7
        }
    }

    requirement def SafeOperation {
        subject s : PumpSystem;
        require constraint test {
            s.loss >= 0 and s.efficiency <= 1.0
        }
    }

    // System initialisation
    part pump : PumpSystem {
        :>> flowRate   = 0.0;
        :>> efficiency = 0.9;
        :>> powerInput = 1000;
    }

    // Requirement usage
    requirement r_loss : LossRequirement {
        subject s = pump;
    }

    requirement r_eff : EfficiencyRequirement {
        subject s = pump;
    }

    requirement <R1> r_safe : SafeOperation {
        
    }

    satisfy R1 by pump; 

    // Metadata annotation
    metadata def ExternalAnalysisConfig {
      runner: String
      repo: String
      entrypoint: String
      storage: String
    }

    // Analysis definition
    analysis def some_analysis {
        ExternalAnalysisConfig {
          runner: some_runner
          repo: some-organisation/some-repo@some-branch
          storage: some-azure-blob
        }

        in some_input: Real;
        out some_output: Real;
    }

}

```
#### Python requirements solver (to be made) (before ship and reactor model)
- Dedicated python tool fetches analyses to be run, walks the dependency tree for constraints.
- Queries the API (or postgres DB directly) for unsolved constraints and variables and rolls up values. 
- Parameters from model for external analyses is sent to the backend jobs orchestrator. 
  -  Queued, ordering matters here (some analyses may require parameters from other external analyses). How to store this? 


#### Backend jobs orchestrator (to be made) (at some later point)
- Backend pushes these to a DB. 
- For kubernetes clusters: 
  - A run orchestrator takes these. E.g. KEDA (kubernetes based). 
  - Can run this locally on computer using e.g. minikube/kind
- For HPCs: 
  - A run orchestrator launches slurm jobs
- For STC
  - ???

