#!/usr/bin/env bash
# =============================================================================
# PHASE 2 — perf stat: aggregate counters (the "WHY" / character of the load)
# -----------------------------------------------------------------------------
# Answers: is this benchmark compute-bound, memory-bound, or speculation-bound?
# No code location here - that's Phase 3. This is the CPI-stack / top-down view.
#
# Usage:   bash 02_perf_stat.sh nbody
#          bash 02_perf_stat.sh raytrace
# Output:  perfstat_<bench>.txt
# =============================================================================
set -euo pipefail

BENCH="${1:?Usage: bash 02_perf_stat.sh <benchmark>}"
OUT="perfstat_${BENCH}.txt"

# We profile the debug interpreter running the benchmark module directly, so the
# counters reflect the actual work (not pyperformance's harness overhead).
RUN=(python3-dbg -m pyperformance run --bench "${BENCH}")

{
  echo "########## perf stat : core counter set (repeated x5 for std dev) ##########"
  perf stat -r 5 \
    -e cycles,instructions,cache-references,cache-misses,branches,branch-misses,context-switches,page-faults \
    -- "${RUN[@]}"

  echo ""
  echo "########## perf stat : L1 D-cache detail ##########"
  perf stat \
    -e L1-dcache-loads,L1-dcache-load-misses \
    -- "${RUN[@]}" || echo "(L1 dcache events may be unavailable inside a VM)"

  echo ""
  echo "########## perf stat : top-down (Retiring / Bad-Spec / Frontend / Backend) ##########"
  perf stat --topdown -- "${RUN[@]}" || echo "(--topdown may be unavailable inside a VM)"
} 2>&1 | tee "${OUT}"

echo ""
echo "  Saved counters to: ${OUT}"
echo "  Read it as: cycles + IPC (=instructions/cycles) + cache MISSES together."
echo "  Rule of thumb:"
echo "     high Backend-bound + low cache-miss   => FPU/compute-bound (expect: nbody)"
echo "     high Backend-bound + high cache traffic => memory/allocation-bound (expect: raytrace)"
