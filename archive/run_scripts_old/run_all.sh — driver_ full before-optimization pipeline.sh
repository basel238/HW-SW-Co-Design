#!/usr/bin/env bash
# =============================================================================
# DRIVER — run the full BEFORE-optimization pipeline for one benchmark
# -----------------------------------------------------------------------------
# Convenience wrapper: baseline -> perf stat -> perf record + flame graph.
# (Run Phase 4 separately, after you have edited the benchmark code.)
#
# Usage:   bash run_all.sh nbody
#          bash run_all.sh raytrace
# =============================================================================
set -euo pipefail

BENCH="${1:?Usage: bash run_all.sh <benchmark>   e.g. nbody or raytrace}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==================== PHASE 1: baseline ===================="
bash "${DIR}/01_baseline.sh"          "${BENCH}"
echo "==================== PHASE 2: perf stat ===================="
bash "${DIR}/02_perf_stat.sh"         "${BENCH}"
echo "==================== PHASE 3: record + flame graph ===================="
bash "${DIR}/03_perf_record_flame.sh" "${BENCH}"

echo ""
echo "  BEFORE-optimization pipeline complete for '${BENCH}'."
echo "  Now: read report_${BENCH}.txt + ${BENCH}.svg, edit the code,"
echo "       then run:  bash ${DIR}/04_optimize_compare.sh ${BENCH}"
