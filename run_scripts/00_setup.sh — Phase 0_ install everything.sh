#!/usr/bin/env bash
# =============================================================================
# PHASE 0 — Environment setup
# HW/SW Co-design (00460882) — pyperformance profiling project
# -----------------------------------------------------------------------------
# Installs everything you need ONCE inside the Ubuntu QEMU VM:
#   - python debug build (symbols + frame pointers for perf)
#   - perf (linux-tools) matching your kernel
#   - a Python venv with pyperformance
#   - Brendan Gregg's FlameGraph scripts
#
# Usage:   bash 00_setup.sh
# =============================================================================
set -euo pipefail

echo "==> [0/5] Updating apt and installing system packages ..."
sudo apt update
sudo apt install -y \
    python3-dbg python3-venv python3-pip \
    linux-tools-common "linux-tools-$(uname -r)" \
    git firefox

echo "==> [1/5] Verifying perf ..."
perf --version

echo "==> [2/5] Creating Python virtual environment (./venv) ..."
python3 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate

echo "==> [3/5] Installing pyperformance (pulls in pyperf) ..."
pip install --upgrade pip
pip install pyperformance
pyperformance --version

echo "==> [4/5] Cloning FlameGraph scripts (for .svg flame graphs) ..."
if [ ! -d FlameGraph ]; then
    git clone https://github.com/brendangregg/FlameGraph
fi

echo "==> [5/5] Allowing perf for non-root sampling (this session) ..."
# Lets 'perf record' capture kernel+user stacks without sudo.
sudo sysctl -w kernel.perf_event_paranoid=1 || true

echo ""
echo "  Setup complete."
echo "  IMPORTANT: in every new terminal, re-activate the venv with:"
echo "      source venv/bin/activate"
