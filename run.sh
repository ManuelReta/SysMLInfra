#!/usr/bin/env bash
# =============================================================================
# run.sh — Verify API connectivity and open a notebook.
#
# The SysML v2 API is provided by the SST public server:
#   http://sysml2.intercax.com:9000
#
# Two notebooks are available:
#   Verification.ipynb — Python kernel; commits model layers, local constraint eval
#   Analysis.ipynb     — SysML v2 kernel (native); evaluates assert requirement natively
#
# Usage:
#   bash run.sh             # opens Verification.ipynb (Python, default)
#   bash run.sh analysis    # opens Analysis.ipynb (SysML v2 kernel)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_URL="http://sysml2.intercax.com:9000"
NOTEBOOK="${1:-verification}"

# ------------------------------------------------------------------------------
# Health check — confirm SST server is reachable
# ------------------------------------------------------------------------------
echo "Checking SysML v2 API server at ${API_URL}..."

if curl -sf --max-time 8 "${API_URL}/projects" -o /dev/null; then
    echo "  Server ready."
else
    echo ""
    echo "ERROR: Cannot reach ${API_URL}/projects"
    echo "       Check your internet connection or firewall."
    exit 1
fi

echo ""
echo "API base : ${API_URL}"
echo ""

# ------------------------------------------------------------------------------
# Launch Jupyter with the selected notebook
# For Analysis.ipynb the SysML kernel must be available:
#   conda env: sysmlv2  (installed by setup.sh)
#   kernel:    sysml    (registered at ~/.local/share/jupyter/kernels/sysml)
# ------------------------------------------------------------------------------
if [[ "$NOTEBOOK" == "analysis" ]]; then
    echo "Launching Analysis.ipynb (SysML v2 kernel)..."
    # Use the conda env's jupyter so the sysml kernel is on PATH
    JUPYTER=/home/manret/miniconda3/envs/sysmlv2/bin/jupyter
    if [[ ! -x "$JUPYTER" ]]; then
        echo "ERROR: conda env 'sysmlv2' not found. Run 'bash setup.sh' first."
        exit 1
    fi
    # Derive the notebook directory from the first layer path in sysml-project.yml
    NOTEBOOK_DIR="$SCRIPT_DIR"
    MANIFEST="$SCRIPT_DIR/sysml-project.yml"
    if [[ -f "$MANIFEST" ]]; then
        FIRST_LAYER=$(awk '/^layers:/{in_l=1; next} in_l && /^  - /{print substr($0,5); exit}' "$MANIFEST")
        if [[ -n "$FIRST_LAYER" ]]; then
            NOTEBOOK_DIR="$SCRIPT_DIR/$(dirname "$FIRST_LAYER")"
        fi
    fi
    cd "$NOTEBOOK_DIR"
    "$JUPYTER" lab Analysis.ipynb
else
    echo "Launching Verification.ipynb (Python kernel)..."
    # Derive the notebook directory from the first layer path in sysml-project.yml
    NOTEBOOK_DIR="$SCRIPT_DIR"
    MANIFEST="$SCRIPT_DIR/sysml-project.yml"
    if [[ -f "$MANIFEST" ]]; then
        FIRST_LAYER=$(awk '/^layers:/{in_l=1; next} in_l && /^  - /{print substr($0,5); exit}' "$MANIFEST")
        if [[ -n "$FIRST_LAYER" ]]; then
            NOTEBOOK_DIR="$SCRIPT_DIR/$(dirname "$FIRST_LAYER")"
        fi
    fi
    cd "$NOTEBOOK_DIR"
    jupyter notebook Verification.ipynb
fi
