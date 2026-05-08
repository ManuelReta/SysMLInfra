# SysML v2 Bilge Pump System

A SysML v2 model of a maritime bilge pump system with requirements traceability
to IMO MARPOL, DNV, IEC 60945, and SOLAS.

No local server install needed. The project uses the **SST public SysML v2 API**
hosted by the SysML Submission Team at `http://sysml2.intercax.com:9000`.

---

## Quick Start

```bash
bash setup.sh    # one-time: installs Python deps + confirms API reachability
bash commit.sh   # POST all 4 .sysml layers to the SST API server
bash verify.sh   # run requirement verification (POSITIVE test)
```

Or use the Jupyter notebook for interactive exploration:
```bash
bash run.sh      # health-checks API then opens Verification.ipynb
```

---

## API Server

| Item | Value |
|------|-------|
| Host | `http://sysml2.intercax.com:9000` |
| Type | SST-hosted SysML v2 Pilot Implementation |
| Auth | None (public) |
| Persistence | Projects survive server restarts but the server is shared |

Projects you create are visible to everyone on the server. Treat committed
content as public. Use `lib/current-project-id.txt` to track your project ID.

---

## Verifying the Model: Three Methods

### Method 1 — `bash verify.sh` (recommended first attempt)

Runs both a positive test (all pumps working) and the built-in negative test
(pump A failed). Calls the API to retrieve your committed elements, checks
that all `assert requirement` statements in `Analysis.sysml` are present,
and optionally invokes `/analysis-evaluations` if available.

```bash
bash verify.sh             # positive test: all requirements must be SATISFIED
bash verify.sh negative    # negative test: pump A flowRate=0 → BPS-REQ-001 must be VIOLATED
```

Expected results:

| Test | BPS-REQ-001 | BPS-REQ-002 | BPS-REQ-003 | BPS-REQ-004 |
|------|-------------|-------------|-------------|-------------|
| Positive | SATISFIED | SATISFIED | SATISFIED | SATISFIED |
| Negative (pumpA=0) | VIOLATED | SATISFIED | SATISFIED | SATISFIED |

Results are written to `lib/verification-results.json`.

### Method 2 — `bash check-requirements-manually.sh` (fallback)

The SST server's `/analysis-evaluations` endpoint is not always available
(returns HTTP 404/501 depending on the server build). This script is the
deliberate fallback for that case.

It reads `Analysis.sysml` to extract the `bind` values, then re-evaluates
all `require constraint` expressions in Python. It is **not** the SysML v2
engine — it is a Python re-implementation that handles arithmetic and boolean
constraints only. Complex SysML constraint semantics are not supported.

Use it when:
- `verify.sh` exits with a 404/501 on `/analysis-evaluations`
- You want a quick local sanity check without an API round-trip

```bash
bash check-requirements-manually.sh
```

### Method 3 — Direct API inspection with `curl`

Once you have committed the model, you can inspect any part of it with `curl`.

**List your project's elements (after `commit.sh` has run):**
```bash
PROJECT_ID=$(cat lib/current-project-id.txt)
curl -s http://sysml2.intercax.com:9000/projects/$PROJECT_ID/commits \
  | python3 -m json.tool | head -60
```

**Fetch all elements in the latest commit:**
```bash
PROJECT_ID=$(cat lib/current-project-id.txt)
COMMIT_ID=$(python3 -c "
import json
data = json.load(open('lib/commit-ids.json'))
print(data['analysis'])
")
curl -s "http://sysml2.intercax.com:9000/projects/$PROJECT_ID/commits/$COMMIT_ID/elements" \
  | python3 -m json.tool | head -100
```

**Search for a specific element by name (e.g. BilgePumpA):**
```bash
PROJECT_ID=$(cat lib/current-project-id.txt)
COMMIT_ID=$(python3 -c "
import json; data=json.load(open('lib/commit-ids.json')); print(data['analysis'])
")
curl -s "http://sysml2.intercax.com:9000/projects/$PROJECT_ID/commits/$COMMIT_ID/elements" \
  | python3 -c "
import json,sys
els = json.load(sys.stdin)
for e in els:
    if 'BilgePump' in str(e.get('name','')) or 'BilgePump' in str(e.get('@type','')):
        print(json.dumps(e, indent=2))
"
```

**Why you cannot `curl -d @Library.sysml` directly:**

The commit endpoint requires a JSON payload with the SysML source as an
escaped string, not a raw body:
```json
{"changes": [{"@type": "TextualRepresentation", "body": "<json-escaped sysml>"}]}
```
`commit.sh` handles the escaping via `python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'`.

---

## Project Structure

```
Library.sysml           — part def, port def, attribute def (the type vocabulary)
Architecture.sysml      — BilgePumpSystem composition + connect statements
Requirements.sysml      — requirement def blocks (BPS-REQ-001 through 004)
Analysis.sysml          — constraint def + analysis def + bind + assert requirement
Verification.ipynb      — interactive Jupyter notebook for API-driven verification
setup.sh                — one-time setup (pip deps + connectivity check)
run.sh                  — health-check SST server then open notebook
commit.sh               — POST all 4 layers to the API in dependency order
verify.sh               — run positive/negative verification tests
check-requirements-manually.sh  — Python fallback when /analysis-evaluations is unavailable

.github/agents/         — 12 specialist agents (Orchestrator + mappers + validators)
docs/ingested/          — structured engineering input documents for agent processing
  interfaces/           → PortDefMapper agent input
  attributes/           → AttributeDefMapper agent input
  components/           → PartDefMapper agent input
  connections/          → ConnectMapper agent input
  requirements/         → RequirementMapper agent input
  constraints/          → ConstraintMapper agent input
  allocations/          → AllocationMapper agent input
  analyses/             → AnalysisMapper agent input
lib/
  build-state.json      — Orchestrator phase state machine
  traceability.json     — element-to-source traceability index
  part-registry.json    — part def → instance name map (for ConnectMapper)
  staged-attribute-values.json — numeric values from AttributeDefMapper → AnalysisMapper
  current-project-id.txt — project UUID written by commit.sh
  commit-ids.json       — commit UUIDs per layer, written by commit.sh
  verification-results.json — written by verify.sh or check-requirements-manually.sh
scripts/
  ci_kernel_validate.py — headless SysML v2 kernel runner for CI (see below)
.github/workflows/
  validate-pr.yml       — PR gate: runs kernel validation on every PR to main
  publish-to-api.yml    — post-merge: publishes validated model to the API server
sysml-project.yml       — project manifest: layer order, name, description
requirements-ci.txt     — CI-only Python deps (nbformat, nbclient)
```

---

## CI/CD Infrastructure

This repository ships a generic CI/CD pipeline that works for **any SysML v2
project**, not just the BilgePump example.  The three core files you need to
understand are described below.

### How it works

```
  PR opened / commit pushed
        │
        ▼
  validate-pr.yml   ◄─── sysml-project.yml (layer order)
  (GitHub Actions)        ├── Layer 1 compiled by kernel
        │                 ├── Layer 2 compiled by kernel  ← unresolved imports caught here
        │                 ├── Layer 3 compiled by kernel  ← type mismatches caught here
        │                 └── Layer 4 (Analysis) executed ← failed assertions caught here
        │
  All cells OK?
   Yes → PR can be merged
   No  → PR is blocked (red check)
        │
        ▼  (on merge to main only)
  publish-to-api.yml
  (GitHub Actions)
        │
        └── commit.sh → POST layers to SysML v2 API → API is the single source of truth
```

### 1. `sysml-project.yml` — the only file you change per project

```yaml
name: YourProjectName
description: "Short description for the API project entry"

layers:
  - YourLibrary.sysml          # imported by nothing — must come first
  - YourArchitecture.sysml     # imports Library
  - YourRequirements.sysml     # imports Library + Architecture
  - YourAnalysis.sysml         # imports all of the above
```

Both the CI workflow (`validate-pr.yml`) and `commit.sh` read this file.  The
`scripts/ci_kernel_validate.py` script and `commit.sh` require no changes when
you adapt the project; they are fully driven by this manifest.

### 2. `scripts/ci_kernel_validate.py` — the kernel runner

Builds an in-memory Jupyter notebook from the manifest layers and executes it
against the `sysml2` kernel.  Does **not** call the API (no `%publish` cell).
Exits 1 on any compiler error, unresolved name, or failed `assert requirement`.

Run locally for debugging:

```bash
# Check files are present and ordered correctly (no kernel needed)
python scripts/ci_kernel_validate.py --dry-run

# Full validation (requires sysmlv2 conda env from setup.sh)
conda activate sysmlv2
python scripts/ci_kernel_validate.py
```

### 3. GitHub Actions workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `validate-pr.yml` | PR → `main` touching `*.sysml` | Kernel validation gate — blocks bad PRs |
| `publish-to-api.yml` | Push to `main` touching `*.sysml` | Publishes validated model to the API |

### Setting up CI for a new project

1. Copy these files into your repository root:
   - `sysml-project.yml` (edit `name`, `description`, `layers`)
   - `scripts/ci_kernel_validate.py` (no changes needed)
   - `requirements-ci.txt` (no changes needed)
   - `.github/workflows/validate-pr.yml` (no changes needed)
   - `.github/workflows/publish-to-api.yml` (no changes needed)
   - `commit.sh` (no changes needed)

2. Add a GitHub repository secret named `SYSML_API_BASE`:
   - Go to **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `SYSML_API_BASE`
   - Value: `http://sysml2.intercax.com:9000` (or your self-hosted server URL)
   - If you do not add this secret, the publish workflow falls back to the
     public SST server automatically.

3. Enable branch protection on `main`:
   - **Settings → Branches → Add branch protection rule**
   - Branch name pattern: `main`
   - ✅ Require a pull request before merging
   - ✅ Require status checks to pass before merging
   - Required status check: `validate-sysml`

4. Open a PR.  The `validate-sysml` check will run automatically.

### Testing the CI pipeline locally before pushing

```bash
# 1. Dry-run: verify manifest and file presence (no conda or kernel needed)
python scripts/ci_kernel_validate.py --dry-run

# 2. Full kernel validation (activate the sysmlv2 conda env first)
conda activate sysmlv2
pip install nbclient nbformat    # one-time, adds CI deps to the local env
python scripts/ci_kernel_validate.py

# 3. Test the publish path manually
bash commit.sh                   # uses http://sysml2.intercax.com:9000
bash verify.sh                   # step 1: API persistence; step 2: constraints
```

### Key architectural decisions

| Decision | Rationale |
|----------|-----------|
| Kernel validation in CI (not a custom parser) | The `sysml2` kernel validates syntax, imports, types, and assertions natively. A custom Python regex parser would be fragile and miss semantic errors. |
| conda (not Docker) in validate-pr | `jupyter-sysml-kernel` is on conda-forge and registers its kernel spec automatically on install. The `conda-incubator/setup-miniconda` action provides an isolated, reproducible environment equivalent to `setup.sh`. |
| No `%publish` in CI validation notebook | PRs must never write to the API. Only a merge to `main` triggers publication. |
| Manifest-driven layer order | The layer list is declared once in `sysml-project.yml`. Neither the CI scripts nor `commit.sh` hardcode filenames, so both are reusable across projects. |
| `lib/commit-ids.json` as artifact only | Not committed back to git. Download from the Actions tab → workflow run → Artifacts → `sysml-api-publish-state`. |
