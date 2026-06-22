#!/usr/bin/env bash
# =============================================================================
# setup.sh — One-time project setup
# Run this once after cloning the repository.
# Safe to re-run: every step checks before acting.
#
# What this script does:
#   1. Installs the SysML v2 Jupyter kernel (REQUIRED — requires Miniconda + Java 21)
#   2. Checks Python 3 and pip are available
#   3. Installs Python dependencies (requirements.txt)
#
# PRIMARY entry point after setup:
#   python verify.py              — run local verification (kernel required)
#   python verify.py --visual     — also generate diagrams
#   python verify.py --negative   — inject a component failure
#   python verify.py --dry-run    — check files only
#
# IMPORTANT: The SysML v2 Jupyter kernel is REQUIRED for constraint evaluation.
# Without it, requirement assertions cannot be evaluated. Do NOT skip step 1.
# The Python regex/eval fallback (--fallback) is for development testing only.
#
# The remote SST API is NOT required for verification.
# To publish the model to the SST public server (optional, for sharing):
#   python verify.py --publish
#
# Requirements:
#   - Miniconda (~/miniconda3) for the SysML kernel — REQUIRED
#   - Java 21+ for the SysML kernel JAR — REQUIRED
#   - Python 3.8+ with pip
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONDA_BASE="${CONDA_BASE:-$(conda info --base)}"
SYSML_ENV="sysmlv2"
SYSML_VERSION="0.58.0"

echo "======================================================"
echo " SysML v2 MBSE Framework — Environment Setup"
echo "======================================================"

# ------------------------------------------------------------------------------
# Step 1: SysML v2 Jupyter kernel  *** REQUIRED ***
# The kernel is the ONLY valid evaluation engine for SysML v2 constraint
# and requirement assertions. Python regex/eval fallback (--fallback) is for
# development and CI testing ONLY — it does NOT evaluate SysML semantics.
# Requires: Miniconda, Java 21+
# ------------------------------------------------------------------------------
echo ""
echo "[1/3] Installing SysML v2 Jupyter kernel (REQUIRED)..."

if [[ ! -x "$CONDA_BASE/bin/conda" ]]; then
    echo ""
    echo "  ════════════════════════════════════════════════════════════"
    echo "  ║  SETUP FAILED — Miniconda not found at $CONDA_BASE          ║"
    echo "  ║                                                              ║"
    echo "  ║  The SysML v2 Jupyter kernel is REQUIRED.                   ║"
    echo "  ║  Without it, requirement assertions cannot be evaluated.     ║"
    echo "  ║                                                              ║"
    echo "  ║  1. Install Miniconda:                                       ║"
    echo "  ║     https://repo.anaconda.com/miniconda/                     ║"
    echo "  ║  2. Re-run: bash setup.sh                                    ║"
    echo "  ════════════════════════════════════════════════════════════"
    exit 1
fi

# Check Java 21
JAVA_VER=$(java -version 2>&1 | awk -F '"' '/version/ {print $2}' | cut -d. -f1 2>/dev/null || echo "0")
if [[ "${JAVA_VER:-0}" -lt 21 ]]; then
    echo ""
    echo "  ════════════════════════════════════════════════════════════"
    echo "  ║  SETUP FAILED — Java 21+ is required for the SysML kernel   ║"
    echo "  ║  Found: Java ${JAVA_VER:-none}                                         ║"
    echo "  ║                                                              ║"
    echo "  ║  Install:                                                    ║"
    echo "  ║    sudo apt-get install openjdk-21-jre-headless              ║"
    echo "  ║  Then re-run: bash setup.sh                                  ║"
    echo "  ════════════════════════════════════════════════════════════"
    exit 1
fi
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
    echo "      Kernel spec installed."
else
    echo ""
    echo "  ════════════════════════════════════════════════════════════"
    echo "  ║  SETUP FAILED — kernel spec not found at:                   ║"
    echo "  ║  $KERNEL_SPEC"
    echo "  ║                                                              ║"
    echo "  ║  The conda install may have failed. Check the output above.  ║"
    echo "  ║  Try: conda activate $SYSML_ENV && jupyter kernelspec list   ║"
    echo "  ════════════════════════════════════════════════════════════"
    exit 1
fi

# Post-install validation: verify kernel is registered
if uv run jupyter kernelspec list 2>/dev/null | grep -iq sysml; then
    echo "      ✓ SysML v2 kernel registered and ready."
else
    echo ""
    echo "  ════════════════════════════════════════════════════════════"
    echo "  ║  SETUP FAILED — SysML kernel not visible to jupyter          ║"
    echo "  ║                                                              ║"
    echo "  ║  Run: jupyter kernelspec list                                ║"
    echo "  ║  Expected: a 'sysml' or 'sysml2' entry in the list           ║"
    echo "  ║  If missing, re-run: bash setup.sh                           ║"
    echo "  ════════════════════════════════════════════════════════════"
    exit 1
fi

# ------------------------------------------------------------------------------
# Step 2: Check Python 3
# ------------------------------------------------------------------------------
echo ""
echo "[2/3] Checking Python 3..."
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
# Step 3: Python dependencies
# ------------------------------------------------------------------------------
echo ""
echo "[3/3] Installing Python dependencies..."
"$PYTHON_BIN" -m pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
echo "      Dependencies installed."

# Install CI notebook execution deps if not already present
"$PYTHON_BIN" -m pip install --quiet nbclient nbformat 2>/dev/null && \
    echo "      nbclient/nbformat installed (kernel execution support)." || true

chmod +x "$SCRIPT_DIR/commit.sh" 2>/dev/null || true
mkdir -p "$SCRIPT_DIR/lib"

echo ""
echo "======================================================"
echo " Setup complete."
echo ""
echo " \u2713 SysML v2 kernel: registered"
echo ""
echo " Run the model:"
echo "   python verify.py                \u2014 verify all requirements (SysML kernel)"
echo "   python verify.py --negative     \u2014 inject a component failure"
echo "   python verify.py --visual       \u2014 + generate diagrams"
echo "   python verify.py --dry-run      \u2014 check layer files only"
echo "   python verify.py --require-kernel \u2014 exit 2 if kernel not found"
echo "   python verify.py --fallback     \u2014 Python regex/eval DEV/TEST only"
echo "   python verify.py --publish      \u2014 also push to SST API (optional)"
echo ""
echo " Interactive exploration (notebooks \u2014 in examples/<project>/):"
echo "   bash run.sh analysis            \u2014 Analysis.ipynb (SysML v2 kernel)"
echo "   bash run.sh safety              \u2014 Safety.ipynb (STPA/FMEA/UQ)"
echo "======================================================"
