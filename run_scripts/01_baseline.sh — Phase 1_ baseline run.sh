#!/usr/bin/env bash
# =============================================================================
# PHASE 1 — Baseline run & capture (BEFORE any optimization)
# -----------------------------------------------------------------------------
# Runs one benchmark through pyperformance and stores the baseline result JSON.
# This JSON is what you compare against later to prove the >= 7% improvement.
#
# Usage:   bash 01_baseline.sh nbody
#          bash 01_baseline.sh raytrace
# =============================================================================
set -euo pipefail

BENCH="${1:?Usage: bash 01_baseline.sh <benchmark>   e.g. nbody or raytrace}"
OUT="${BENCH}_base.json"

# Make sure we are in the venv (pyperformance must be importable).
command -v pyperformance >/dev/null 2>&1 || {
    echo "pyperformance not found. Run:  source venv/bin/activate"; exit 1; }

echo "==> Confirming '${BENCH}' exists in the suite ..."
pyperformance list | grep -iw "${BENCH}" || {
    echo "Benchmark '${BENCH}' not in list. Run 'pyperformance list' to see names."; exit 1; }

echo "==> Running baseline for '${BENCH}' (warmups + measured runs via pyperf) ..."
pyperformance run --bench "${BENCH}" -o "${OUT}"

echo ""
echo "==> Baseline mean +/- std dev:"
pyperformance show "${OUT}"
echo ""
echo "  Baseline saved to: ${OUT}"
echo "  Keep this file - Phase 4 compares against it."
