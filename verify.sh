#!/usr/bin/env bash
# =============================================================================
# verify.sh — Verify the base 4-layer model requirements against the
#             committed SysML v2 API project.
#
# SCOPE: This script evaluates the four original regulatory requirements
# (BPS-REQ-001 through BPS-REQ-004) defined in Requirements.sysml.
# For the extended safety layers (STPA UCA requirements, FMEA negative tests,
# and UQ parametric sweep), use bilgepump/Safety.ipynb instead:
#
#   bash run.sh safety   → opens Safety.ipynb
#
# How this works:
#   The SST SysML v2 REST API (sysml2.intercax.com:9000) is a JSON-LD model
#   element store. It accepts model elements from IDEs (VS Code SysML extension,
#   Eclipse SysIDE) but does NOT parse raw SysML textual notation — it stores
#   the text verbatim. The /analysis-evaluations endpoint is not available.
#
#   This script therefore does two things:
#     1. PERSISTENCE CHECK — confirm the project and all committed layers exist
#        on the SST API (proves the model was uploaded and is retrievable).
#     2. CONSTRAINT EVALUATION — parse Requirements.sysml and Analysis.sysml
#        locally and evaluate all 'require constraint' expressions in Python.
#        NOTE: This is a Python regex + eval approximation, NOT the SysML v2
#        kernel. It works reliably for arithmetic and boolean expressions.
#        See scripts/ci_kernel_validate.py for kernel-based validation.
#
# Usage:
#   bash verify.sh             # positive test (nominal values from Analysis.sysml)
#   bash verify.sh negative    # negative test (override pumpA.flowRate = 0)
#
# Prerequisites:
#   bash commit.sh must have been run first (lib/commit-ids.json must exist)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_BASE="${API_BASE:-http://sysml2.intercax.com:9000}"
TEST_MODE="${1:-positive}"

if [ ! -f "$SCRIPT_DIR/lib/commit-ids.json" ]; then
    echo "ERROR: lib/commit-ids.json not found."
    echo "       Run 'bash commit.sh' first to upload the model."
    exit 1
fi

export API_BASE
export TEST_MODE
export SCRIPT_DIR

# ------------------------------------------------------------------------------
# Step 1 — Persistence check: confirm project + commits exist on the SST API
# ------------------------------------------------------------------------------
python3 << 'PYEOF'
import json, os, sys, requests

api_base   = os.environ["API_BASE"]
script_dir = os.environ["SCRIPT_DIR"]

with open(os.path.join(script_dir, "lib/commit-ids.json")) as f:
    ids = json.load(f)

project_id = ids["project_id"]
commits    = ids["commits"]

print(f"=== Step 1: API Persistence Check ===")
print(f"  API     : {api_base}")
print(f"  Project : {project_id}")

# Confirm project exists
try:
    r = requests.get(f"{api_base}/projects/{project_id}", timeout=10)
    if r.status_code == 200:
        name = r.json().get("name") or r.json().get("alias", ["?"])[0]
        print(f"  Status  : EXISTS  ({name})")
    else:
        print(f"  Status  : HTTP {r.status_code} — project may have been removed from the shared server")
        sys.exit(1)
except Exception as e:
    print(f"  Status  : UNREACHABLE ({e})")
    sys.exit(1)

# Confirm all committed layers exist (keys read dynamically — generic for any project)
print(f"  Commits :")
for layer, cid in commits.items():
    r = requests.get(f"{api_base}/projects/{project_id}/commits/{cid}", timeout=10)
    status = "OK" if r.status_code == 200 else f"HTTP {r.status_code}"
    print(f"    {layer:<15} {cid[:8]}...  [{status}]")

print()
PYEOF

# ------------------------------------------------------------------------------
# Step 2 — Constraint evaluation: parse Analysis.sysml and evaluate locally
# ------------------------------------------------------------------------------
python3 << 'PYEOF'
import re, sys, os, json

script_dir = os.environ["SCRIPT_DIR"]
test_mode  = os.environ["TEST_MODE"]

def read(path):
    with open(os.path.join(script_dir, path)) as f:
        return f.read()

def strip_comments(txt):
    """Remove // line comments and /* */ block comments from SysML source."""
    txt = re.sub(r'/\*.*?\*/', '', txt, flags=re.DOTALL)  # block comments
    txt = re.sub(r'//[^\n]*', '', txt)                    # line comments
    return txt

# Derive layer paths from sysml-project.yml so verify.sh works regardless of
# where the .sysml files live (root, bilgepump/, or any other subfolder).
layers = []
in_layers = False
try:
    with open(os.path.join(script_dir, "sysml-project.yml")) as f:
        for line in f:
            s = line.strip()
            if s == "layers:":
                in_layers = True
            elif in_layers and s.startswith("- "):
                layers.append(s[2:].strip())
            elif in_layers and s and not s.startswith("- ") and not s.startswith("#"):
                in_layers = False
except FileNotFoundError:
    layers = ["Analysis.sysml", "Requirements.sysml"]

# Pick the analysis and requirements layers by name (case-insensitive).
# This works whether they live at root or in a subfolder like bilgepump/.
analysis_path     = next((l for l in layers if "analysis"     in l.lower()), layers[-1])
requirements_path = next((l for l in layers if "requirements" in l.lower()), layers[-2] if len(layers) >= 2 else layers[-1])

analysis_sysml     = strip_comments(read(analysis_path))
requirements_sysml = strip_comments(read(requirements_path))

print(f"=== Step 2: Constraint Evaluation ({test_mode.upper()} TEST) ===")
print(f"  analysis     : {analysis_path}")
print(f"  requirements : {requirements_path}")
print()

# Extract bind values from Analysis.sysml (numeric and boolean literals only)
bind_values = {}
for m in re.finditer(r'bind\s+([\w.]+)\s*=\s*([^;]+);', analysis_sysml):
    path  = m.group(1).strip()
    value = m.group(2).strip()
    if value.lower() == "true":
        bind_values[path] = True
    elif value.lower() == "false":
        bind_values[path] = False
    else:
        try:
            bind_values[path] = float(value)
        except ValueError:
            pass  # skip non-literal binds (e.g. bind x = sys.y.z)

# Also build a bare-name index: last segment of each path → value
# Used when a constraint references an attribute without the full path
# (e.g., 'designInflow' instead of 'dischargeCheck.designInflow')
bare_values = {}
for path, val in bind_values.items():
    bare = path.rsplit('.', 1)[-1]
    bare_values[bare] = val

# Negative test: override pumpA flowRate to simulate failure
if test_mode == "negative":
    for key in list(bind_values.keys()):
        if "pumpa" in key.lower() and "flowrate" in key.lower():
            bind_values[key] = 0.0
            bare_values[key.rsplit('.',1)[-1]] = 0.0
            print(f"  [NEGATIVE] Overriding {key} = 0.0 (pump A failure simulation)")

print(f"  Bound values:")
for k, v in bind_values.items():
    print(f"    {k} = {v}")
print()

# Evaluate require constraints from Requirements.sysml
# (comments already stripped so no false matches on comment text)
req_pattern = re.compile(
    r'requirement\s+def\s+(\w+).*?require\s+constraint\s*\{([^}]+)\}',
    re.DOTALL
)

results   = []
all_pass  = True
req_labels = {
    "WaterLevelRequirement":        "BPS-REQ-001  Water level <= 0.30 m",
    "PumpRedundancyRequirement":    "BPS-REQ-002  Pump B redundancy active",
    "AlarmResponseRequirement":     "BPS-REQ-003  Alarm delay <= 2.00 s",
    "DischargeCapacityRequirement": "BPS-REQ-004  Discharge >= design inflow",
}

print(f"{'='*62}")
for m in req_pattern.finditer(requirements_sysml):
    req_name   = m.group(1)
    constraint = m.group(2).strip()
    expr       = constraint
    # Substitute full-path values (longest paths first to avoid partial matches)
    for path, val in sorted(bind_values.items(), key=lambda x: -len(x[0])):
        expr = re.sub(r'\b' + re.escape(path) + r'\b', repr(val), expr)
    # Substitute bare-name values for any remaining unresolved names
    for bare, val in sorted(bare_values.items(), key=lambda x: -len(x[0])):
        expr = re.sub(r'\b' + re.escape(bare) + r'\b', repr(val), expr)
    # SysML boolean literals → Python
    expr = re.sub(r'\btrue\b',  'True',  expr)
    expr = re.sub(r'\bfalse\b', 'False', expr)
    # Drop unit annotations after numbers (e.g. "0.3 m")
    expr_clean = re.sub(r'(?<=[\d)])(\s+[a-zA-Z/\u00b3\u00b2\u00b0]+)+', '', expr).strip()
    try:
        result    = eval(expr_clean, {"__builtins__": {}})
        satisfied = bool(result)
    except Exception as e:
        satisfied = None
        result    = f"EVAL ERROR: {e} (expr: {expr_clean!r})"
    if satisfied is not True:
        all_pass = False
    status    = "SATISFIED \u2713" if satisfied is True else ("VIOLATED  \u2717" if satisfied is False else "UNKNOWN   ?")
    label_str = req_labels.get(req_name, req_name)
    print(f"  {status}   {label_str}")
    results.append({"requirement": req_name, "satisfied": satisfied})

print(f"{'='*62}")
pass_str = "ALL SATISFIED \u2713"
fail_str = "FAILURES DETECTED \u2717"
print(f"  Overall: {pass_str if all_pass else fail_str}")
print(f"{'='*62}")

os.makedirs(os.path.join(script_dir, "lib"), exist_ok=True)
with open(os.path.join(script_dir, "lib/verification-results.json"), "w") as f:
    json.dump({
        "method":        "local-constraint-evaluation",
        "test_mode":     test_mode,
        "all_satisfied": all_pass,
        "results":       results
    }, f, indent=2)
print(f"\n  Results written to lib/verification-results.json")
sys.exit(0 if all_pass else 1)
PYEOF
