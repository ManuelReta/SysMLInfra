#!/usr/bin/env bash
# =============================================================================
# run.sh — Verify API connectivity and open a notebook.
#
# The SysML v2 API is provided by the SST public server:
#   http://sysml2.intercax.com:9000
#
# Three notebooks are available:
#   Verification.ipynb — Python kernel; commits model layers, local constraint eval
#   Analysis.ipynb     — SysML v2 kernel (native); evaluates assert requirement natively
#   Safety.ipynb       — Python kernel; STPA/FMEA/UQ evaluation for the extended model
#
# Usage:
#   bash run.sh             # opens Verification.ipynb (Python, default)
#   bash run.sh analysis    # opens Analysis.ipynb (SysML v2 kernel)
#   bash run.sh safety      # opens Safety.ipynb (Python kernel — STPA/FMEA/UQ)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_URL="http://sysml2.intercax.com:9000"
NOTEBOOK="${1:-verification}"

# Derive the project notebook directory from the first layer path in sysml-project.yml
NOTEBOOK_DIR="$SCRIPT_DIR"
MANIFEST="$SCRIPT_DIR/sysml-project.yml"
if [[ -f "$MANIFEST" ]]; then
    FIRST_LAYER=$(awk '/^layers:/{in_l=1; next} in_l && /^  - /{print substr($0,5); exit}' "$MANIFEST")
    if [[ -n "$FIRST_LAYER" ]]; then
        NOTEBOOK_DIR="$SCRIPT_DIR/$(dirname "$FIRST_LAYER")"
    fi
fi

# ------------------------------------------------------------------------------
# Health check — confirm SST server is reachable
# ------------------------------------------------------------------------------
echo "Checking SysML v2 API server at ${API_URL}..."

if curl -sf --max-time 8 "${API_URL}/projects" -o /dev/null; then
    echo "  Server reachable (optional — not required for local verification)."
else
    echo "  Note: SST API not reachable — notebooks that commit to the API will skip that step."
    echo "  Local verification (python3 verify.py) works without internet."
fi

echo ""
echo "API base      : ${API_URL}"
echo "Notebook dir  : ${NOTEBOOK_DIR}"
echo ""

# ------------------------------------------------------------------------------
# Launch Jupyter with the selected notebook
# For Analysis.ipynb the SysML kernel must be available:
#   conda env: sysmlv2  (installed by setup.sh)
#   kernel:    sysml    (registered at ~/.local/share/jupyter/kernels/sysml)
# ------------------------------------------------------------------------------
if [[ "$NOTEBOOK" == "analysis" ]]; then
    echo "Launching Analysis.ipynb (SysML v2 kernel)..."
    JUPYTER=/home/manret/miniconda3/envs/sysmlv2/bin/jupyter
    if [[ ! -x "$JUPYTER" ]]; then
        echo "ERROR: conda env 'sysmlv2' not found. Run 'bash setup.sh' first."
        exit 1
    fi
    cd "$NOTEBOOK_DIR"
    "$JUPYTER" lab Analysis.ipynb

elif [[ "$NOTEBOOK" == "safety" ]]; then
    echo "Launching Safety.ipynb (Python kernel — STPA/FMEA/UQ evaluation)..."
    echo ""
    echo "  This notebook covers the 4 extended layers:"
    echo "    RAAML.sysml · Safety.sysml · FMEA.sysml · UQ.sysml"
    echo "  Prerequisites: bash commit.sh must have been run first."
    echo "  The notebook will commit all 8 layers and evaluate constraints."
    echo ""
    cd "$NOTEBOOK_DIR"
    jupyter notebook Safety.ipynb

else
    echo "Launching Verification.ipynb (Python kernel — base 4-layer model)..."
    cd "$NOTEBOOK_DIR"
    jupyter notebook Verification.ipynb
fi
