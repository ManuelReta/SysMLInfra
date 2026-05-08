#!/usr/bin/env bash
# =============================================================================
# commit.sh — POST all four .sysml layers to the SysML v2 Pilot API via curl.
#
# This is the CLI equivalent of Verification.ipynb cells 2–6.
# Uses Python (already required by this project) to JSON-escape file contents,
# since 'jq' may not be installed and curl cannot directly embed multi-line
# files with special characters into a JSON body.
#
# Usage:
#   bash commit.sh                    # uses localhost:9000 and current directory
#   bash commit.sh http://host:9000   # override API base URL
#
# Output:
#   Prints PROJECT_ID and each COMMIT_ID to stdout.
#   Writes PROJECT_ID to lib/current-project-id.txt for use by other scripts.
#
# Prerequisites:
#   - bash run.sh must already be running (API server on :9000)
#   - Python 3 with 'requests' installed (pip install requests)
#
# What this script CANNOT do that the notebook does:
#   - Execute analysis-evaluations (cell 7/8) — that requires element ID lookup
#     which is a multi-step operation; see verify.sh for that.
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# API server URL resolution order (highest priority first):
#   1. SYSML_API_BASE env var   — used by CI (GitHub Actions secret)
#   2. $1 positional argument   — used interactively: bash commit.sh http://host:9000
#   3. Hardcoded SST pilot URL  — fallback for local dev with no args
API_BASE="${SYSML_API_BASE:-${1:-http://sysml2.intercax.com:9000}}"

# ------------------------------------------------------------------------------
# Helper: JSON-encode a file's content as a string value using Python.
# This handles newlines, quotes, backslashes, and Unicode correctly.
# 'jq' would do this too, but Python is already a declared dependency.
# ------------------------------------------------------------------------------
json_encode_file() {
    python3 -c "
import sys, json
with open(sys.argv[1], 'r') as f:
    content = f.read()
# Output only the JSON string value (with surrounding quotes), no trailing newline
sys.stdout.write(json.dumps(content))
" "$1"
}

# ------------------------------------------------------------------------------
# Helper: POST a .sysml file as a commit to the API.
# Returns the commit @id on stdout.
# ------------------------------------------------------------------------------
post_commit() {
    local project_id="$1"
    local filepath="$2"
    local description="$3"

    echo "  Encoding ${filepath}..." >&2

    # Build the JSON payload using Python to avoid escaping issues.
    # The SysML v2 Pilot API commit endpoint expects:
    #   POST /projects/{id}/commits
    #   Content-Type: application/json
    #   Body: {"description": "...", "changes": [{"@type": "TextualRepresentation", "body": "<sysml text>"}]}
    COMMIT_ID=$(python3 -c "
import sys, json, requests

api_base = sys.argv[1]
project_id = sys.argv[2]
filepath = sys.argv[3]
description = sys.argv[4]

with open(filepath, 'r') as f:
    content = f.read()

payload = {
    'description': description,
    'changes': [
        {
            '@type': 'TextualRepresentation',
            'body': content
        }
    ]
}

r = requests.post(
    f'{api_base}/projects/{project_id}/commits',
    json=payload,
    timeout=30
)

try:
    r.raise_for_status()
except Exception:
    print(f'ERROR: HTTP {r.status_code}', file=sys.stderr)
    print(r.text[:500], file=sys.stderr)
    sys.exit(1)

result = r.json()
print(result.get('@id', ''))
" "$API_BASE" "$project_id" "$filepath" "$description")

    echo "$COMMIT_ID"
}

# ------------------------------------------------------------------------------
# Step 1: Health check
# ------------------------------------------------------------------------------
echo "Checking API server at ${API_BASE}..."
if ! python3 -c "
import requests, sys
try:
    r = requests.get('${API_BASE}/', timeout=5)
    r.raise_for_status()
    print('  Server ready (HTTP', r.status_code, ')')
except Exception as e:
    print('ERROR:', e, file=sys.stderr)
    sys.exit(1)
"; then
    echo ""
    echo "API server is not responding at ${API_BASE}."
    echo "Run 'bash run.sh' first to start the server."
    exit 1
fi

# ------------------------------------------------------------------------------
# Step 2: Create project
# ------------------------------------------------------------------------------
echo ""
echo "Creating project..."
PROJECT_ID=$(python3 -c "
import requests, sys, os

# Read project name and description from sysml-project.yml if present.
# Falls back to generic defaults so commit.sh works without the manifest.
project_name = 'SysMLProject'
project_desc = ''
manifest = os.path.join('${SCRIPT_DIR}', 'sysml-project.yml')
try:
    with open(manifest) as f:
        for line in f:
            s = line.strip()
            if s.startswith('name:'):
                project_name = s.split(':', 1)[1].strip().strip(\"'\")
            elif s.startswith('description:'):
                project_desc = s.split(':', 1)[1].strip().strip(\"'\")
except FileNotFoundError:
    pass

r = requests.post(
    '${API_BASE}/projects',
    json={'name': project_name, 'description': project_desc},
    timeout=10
)
r.raise_for_status()
print(r.json().get('@id', ''))
")

if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: Failed to create project — empty @id returned."
    exit 1
fi

echo "  Project ID: ${PROJECT_ID}"

# Persist project ID for verify.sh and other scripts
mkdir -p "$SCRIPT_DIR/lib"
echo "$PROJECT_ID" > "$SCRIPT_DIR/lib/current-project-id.txt"
echo "  Saved to lib/current-project-id.txt"

# ------------------------------------------------------------------------------
# Step 3: Commit layers in dependency order
# Library must come first — Architecture, Requirements, Analysis all import it.
# Requirements and Analysis are order-independent after Library, but commit
# Architecture before Analysis so part usages are available.
# ------------------------------------------------------------------------------
echo ""
echo "Committing SysML layers..."

# Read layer list from sysml-project.yml and POST each file as a commit.
# Keys in commit-ids.json are the lowercased filename stems (without .sysml),
# matching the names verify.sh Step 1 reads dynamically from the JSON.
python3 -c "
import json, os, requests, sys

api_base   = '${API_BASE}'
project_id = '${PROJECT_ID}'
script_dir = '${SCRIPT_DIR}'

# Parse sysml-project.yml for the ordered layer list.
# No pyyaml needed — the manifest format is intentionally simple.
layers = []
in_layers = False
try:
    with open(os.path.join(script_dir, 'sysml-project.yml')) as f:
        for line in f:
            s = line.strip()
            if s == 'layers:':
                in_layers = True
            elif in_layers and s.startswith('- '):
                layers.append(s[2:].strip())
            elif in_layers and s and not s.startswith('- ') and not s.startswith('#'):
                in_layers = False
except FileNotFoundError:
    # Fallback: original BilgePump layer order for backward compatibility
    layers = ['Library.sysml', 'Architecture.sysml', 'Requirements.sysml', 'Analysis.sysml']

commits = {}
total = len(layers)
for i, layer_file in enumerate(layers, 1):
    filepath = os.path.join(script_dir, layer_file)
    key = (layer_file[:-6] if layer_file.endswith('.sysml') else layer_file).lower()
    print(f'[{i}/{total}] {layer_file}', flush=True)
    with open(filepath) as f:
        content = f.read()
    payload = {
        'description': f'Layer: {layer_file}',
        'changes': [{'@type': 'TextualRepresentation', 'body': content}]
    }
    r = requests.post(
        f'{api_base}/projects/{project_id}/commits',
        json=payload,
        timeout=30
    )
    try:
        r.raise_for_status()
    except Exception:
        print(f'ERROR: HTTP {r.status_code}', file=sys.stderr)
        print(r.text[:500], file=sys.stderr)
        sys.exit(1)
    cid = r.json().get('@id', '')
    commits[key] = cid
    print(f'       Commit ID: {cid}', flush=True)

os.makedirs(os.path.join(script_dir, 'lib'), exist_ok=True)
with open(os.path.join(script_dir, 'lib/commit-ids.json'), 'w') as f:
    json.dump({'project_id': project_id, 'commits': commits}, f, indent=2)
print('  Commit IDs saved to lib/commit-ids.json', flush=True)
"

echo ""
echo "======================================================"
echo " All layers committed."
echo " Project ID : ${PROJECT_ID}"
echo ""
echo " Next step:"
echo "   bash verify.sh          # run requirement verification"
echo "   bash query-elements.sh  # inspect model elements"
echo "======================================================"
