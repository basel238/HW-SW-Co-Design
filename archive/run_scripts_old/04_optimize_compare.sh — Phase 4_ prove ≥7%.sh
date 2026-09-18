#!/usr/bin/env bash
# =============================================================================
# PHASE 4 — Optimized run & compare (PROVE the >= 7% improvement)
# -----------------------------------------------------------------------------
# Run AFTER you have edited the benchmark's own code (no library swaps).
# It runs the optimized version and compares it against the Phase-1 baseline.
# The project requires >= 7% (ratio >= ~1.075x) AND "Significant".
#
# Usage:   bash 04_optimize_compare.sh nbody
#          bash 04_optimize_compare.sh raytrace
# =============================================================================
set -euo pipefail

BENCH="${1:?Usage: bash 04_optimize_compare.sh <benchmark>}"
BASE="${BENCH}_base.json"
OPT="${BENCH}_opt.json"

[ -f "${BASE}" ] || { echo "Missing ${BASE}. Run Phase 1 (01_baseline.sh) first."; exit 1; }

echo "==> Running OPTIMIZED '${BENCH}' -> ${OPT} ..."
echo "    (make sure your edited benchmark code is the one being run)"
pyperformance run --bench "${BENCH}" -o "${OPT}"

echo ""
echo "==> Comparing baseline vs optimized ..."
pyperformance compare "${BASE}" "${OPT}"

echo ""
echo "  Interpret the output:"
echo "     '1.10x faster'  and  'Significant'   => PASS (>= 7% needs >= ~1.075x)"
echo "     'Not significant'                     => within noise; optimize more / quiet the VM"
echo ""
echo "  Do this for BOTH benchmarks to satisfy the project (>=7% on >= 2 benchmarks)."
