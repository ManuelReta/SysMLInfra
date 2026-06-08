#!/usr/bin/env bash
# =============================================================================
# setup.sh — One-time project setup
# Run this once after cloning the repository.
# Safe to re-run: every step checks before acting.
#
# What this script does:
#   1. Checks Python 3 and pip are available
#   2. Installs Python dependencies (requirements.txt)
#   3. Installs the SysML v2 Jupyter kernel (requires Miniconda + Java 21)
#
# PRIMARY entry point after setup:
#   python verify.py              — run local verification (no internet needed)
#   python verify.py --visual     — also generate diagrams
#   python verify.py --negative   — simulate pump A failure
#   python verify.py --dry-run    — check files only
#
# The remote SST API is NOT required for verification.
# To publish the model to the SST public server (optional, for sharing):
#   python verify.py --publish
#
# Requirements:
#   - Python 3.8+ with pip
#   - Miniconda (~/miniconda3) for the SysML kernel — see step 3
#   - Java 21+ for the SysML kernel JAR
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONDA_BASE="${CONDA_BASE:-/home/manret/miniconda3}"
SYSML_ENV="sysmlv2"
SYSML_VERSION="0.58.0"

echo "======================================================"
echo " SysML v2 Bilge Pump System — Environment Setup"
echo "======================================================"

# ------------------------------------------------------------------------------
# Step 1: Check Python 3
# ------------------------------------------------------------------------------
echo ""
echo "[1/3] Checking Python 3..."
PYTHON_BIN=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        VER=$("$candidate" --version 2>&1 | awk '{print $2}')
        MAJOR=$(echo "$VER" | cut -d. -f1)
        if [[ "$MAJOR" -ge 3 ]]; then
            PYTHON_BIN="$candidate"
            echo "      Found: $candidate $VER — OK"
            break
        fi
    fi
done
if [[ -z "$PYTHON_BIN" ]]; then
    echo "      ERROR: Python 3.8+ not found. Install Python 3 and re-run."
    exit 1
fi

# ------------------------------------------------------------------------------
# Step 2: Python dependencies
# ------------------------------------------------------------------------------
echo ""
echo "[2/3] Installing Python dependencies..."
"$PYTHON_BIN" -m pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
echo "      Dependencies installed (jupyter, matplotlib, networkx, requests)."

# Install CI notebook execution deps if not already present
"$PYTHON_BIN" -m pip install --quiet nbclient nbformat 2>/dev/null && \
    echo "      nbclient/nbformat installed (kernel execution support)." || true

# ------------------------------------------------------------------------------
# Step 3: SysML v2 Jupyter kernel
# The kernel is required for native SysML v2 constraint evaluation.
# Without it, verify.py falls back to Python regex/eval automatically.
# Requires: Miniconda, Java 21+
# ------------------------------------------------------------------------------
echo ""
echo "[3/3] Setting up SysML v2 Jupyter kernel..."

if [[ ! -x "$CONDA_BASE/bin/conda" ]]; then
    echo "      WARNING: Miniconda not found at $CONDA_BASE."
    echo "               verify.py will use the Python regex/eval fallback until installed."
    echo "               To install the kernel later:"
    echo "                 1. Install Miniconda: https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    echo "                 2. Re-run: bash setup.sh"
    echo "               (Verification still works without the kernel — just less precise)"
else
    # Check Java 21
    JAVA_VER=$(java -version 2>&1 | awk -F '"' '/version/ {print $2}' | cut -d. -f1 2>/dev/null || echo "0")
    if [[ "${JAVA_VER:-0}" -lt 21 ]]; then
        echo "      WARNING: Java 21+ required for SysML kernel (found Java ${JAVA_VER:-none})."
        echo "               Install: sudo apt-get install openjdk-21-jre-headless"
        echo "               verify.py will use Python regex/eval fallback in the meantime."
    else
        echo "      Java $JAVA_VER — OK."

        # Create conda environment
        if "$CONDA_BASE/bin/conda" env list | grep -q "^$SYSML_ENV "; then
            echo "      Conda env '$SYSML_ENV' already exists — skipping create."
        else
            echo "      Creating conda env '$SYSML_ENV' (jupyter-sysml-kernel $SYSML_VERSION)..."
            echo "      This may take a few minutes on first run..."
            "$CONDA_BASE/bin/conda" create -n "$SYSML_ENV" \
                "jupyter-sysml-kernel=$SYSML_VERSION" "jupyterlab=4.*" "python=3.*" \
                -c conda-forge -y 2>&1 | tail -5
            echo "      Conda env created."
        fi

        # Register kernel spec for the current user
        KERNEL_SPEC="$CONDA_BASE/envs/$SYSML_ENV/share/jupyter/kernels/sysml"
        if [[ -d "$KERNEL_SPEC" ]]; then
            "$CONDA_BASE/envs/$SYSML_ENV/bin/python" -m jupyter kernelspec install \
                "$KERNEL_SPEC" --user --replace 2>&1 | grep -v "^$" | head -3
            echo "      SysML kernel registered — OK."
        else
            echo "      WARNING: kernel spec not found at $KERNEL_SPEC"
        fi
    fi
fi

chmod +x "$SCRIPT_DIR/commit.sh" 2>/dev/null || true
mkdir -p "$SCRIPT_DIR/lib"

echo ""
echo "======================================================"
echo " Setup complete."
echo ""
echo " Run the model:"
echo "   python verify.py                — verify all requirements (local kernel)"
echo "   python verify.py --negative     — simulate pump A failure"
echo "   python verify.py --visual       — + generate diagrams in bilgepump/docs/"
echo "   python verify.py --dry-run      — check layer files only"
echo "   python verify.py --fallback     — Python eval only (no kernel needed)"
echo "   python verify.py --publish      — also push to SST API (optional)"
echo ""
echo " Interactive exploration (notebooks):"
echo "   bash run.sh analysis            — Analysis.ipynb (SysML v2 kernel)"
echo "   bash run.sh safety              — Safety.ipynb (STPA/FMEA/UQ)"
echo "======================================================"
