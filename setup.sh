#!/usr/bin/env bash
# =============================================================================
# setup.sh — One-time project setup
# Run this once before using the project for the first time.
# Safe to re-run: every step checks before acting.
#
# What this script does:
#   1. Checks network reachability of the SST public SysML v2 API server
#   2. Installs Python dependencies (jupyter + requests)
#   3. Installs the SysML v2 Jupyter kernel (requires Miniconda + Java 21)
#
# API server: http://sysml2.intercax.com:9000  (SST public server, no local setup)
#
# Two notebooks:
#   Verification.ipynb  — Python kernel; commits .sysml files, local constraint eval
#   Analysis.ipynb      — SysML v2 kernel (native); evaluates assert requirement natively
#
# Requirements:
#   - Internet access to sysml2.intercax.com:9000
#   - Python 3 with pip
#   - Miniconda (~/miniconda3) for the SysML kernel step
#   - Java 21+ for the SysML kernel JAR
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_BASE="http://sysml2.intercax.com:9000"
CONDA_BASE="/home/manret/miniconda3"
SYSML_ENV="sysmlv2"
SYSML_VERSION="0.58.0"

echo "======================================================"
echo " SysML v2 Bilge Pump System — Environment Setup"
echo "======================================================"

# ------------------------------------------------------------------------------
# Step 1: Check SST API server reachability
# ------------------------------------------------------------------------------
echo ""
echo "[1/3] Checking SST API server at ${API_BASE}..."

if curl -sf --max-time 8 "${API_BASE}/projects" -o /dev/null; then
    echo "      Server reachable — OK."
else
    echo ""
    echo "WARNING: Cannot reach ${API_BASE}/projects."
    echo "         Check your internet connection or network/firewall settings."
    echo "         Continuing setup anyway — connectivity may return before use."
fi

# ------------------------------------------------------------------------------
# Step 2: Python dependencies (for Verification.ipynb)
# ------------------------------------------------------------------------------
echo ""
echo "[2/3] Installing Python dependencies..."
pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
echo "      Python dependencies installed."

# ------------------------------------------------------------------------------
# Step 3: SysML v2 Jupyter kernel (for Analysis.ipynb)
# Requires: Miniconda at ~/miniconda3, Java 21+
# ------------------------------------------------------------------------------
echo ""
echo "[3/3] Setting up SysML v2 Jupyter kernel..."

if [[ ! -x "$CONDA_BASE/bin/conda" ]]; then
    echo "      WARNING: Miniconda not found at $CONDA_BASE."
    echo "               Install Miniconda first, then re-run setup.sh."
    echo "               Download: https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    echo "               Skipping SysML kernel install — Analysis.ipynb will not be available."
else
    # Check Java 21
    JAVA_VER=$(java -version 2>&1 | awk -F '"' '/version/ {print $2}' | cut -d. -f1)
    if [[ "$JAVA_VER" -lt 21 ]]; then
        echo "      WARNING: Java 21+ required for SysML kernel (found Java $JAVA_VER)."
        echo "               Install: sudo apt-get install openjdk-21-jre-headless"
        echo "               Skipping SysML kernel install."
    else
        echo "      Java $JAVA_VER — OK."

        # Create/update conda environment
        if "$CONDA_BASE/bin/conda" env list | grep -q "^$SYSML_ENV "; then
            echo "      Conda env '$SYSML_ENV' already exists — skipping create."
        else
            echo "      Creating conda env '$SYSML_ENV' with jupyter-sysml-kernel $SYSML_VERSION..."
            "$CONDA_BASE/bin/conda" create -n "$SYSML_ENV" \
                "jupyter-sysml-kernel=$SYSML_VERSION" "jupyterlab=4.*" "python=3.*" \
                -c conda-forge -y 2>&1 | tail -5
            echo "      Conda env created."
        fi

        # Register the kernel spec for the current user
        KERNEL_SPEC="$CONDA_BASE/envs/$SYSML_ENV/share/jupyter/kernels/sysml"
        if [[ -d "$KERNEL_SPEC" ]]; then
            "$CONDA_BASE/envs/$SYSML_ENV/bin/python" -m jupyter kernelspec install \
                "$KERNEL_SPEC" --user --replace 2>&1 | grep -v "^$" | head -3
            echo "      SysML kernel registered."
        else
            echo "      WARNING: kernel spec not found at $KERNEL_SPEC"
        fi
    fi
fi

chmod +x "$SCRIPT_DIR/run.sh" "$SCRIPT_DIR/commit.sh" "$SCRIPT_DIR/verify.sh" 2>/dev/null || true
mkdir -p "$SCRIPT_DIR/lib"

echo ""
echo "======================================================"
echo " Setup complete."
echo " API endpoint : ${API_BASE}"
echo ""
echo " Notebooks:"
echo "   bash run.sh             → Verification.ipynb (Python)"
echo "   bash run.sh analysis    → Analysis.ipynb (SysML v2 kernel)"
echo ""
echo " CLI:"
echo "   bash commit.sh          → POST all 4 .sysml layers to API"
echo "   bash verify.sh          → run positive verification test"
echo "   bash verify.sh negative → run negative (pump A failure) test"
echo "======================================================"
