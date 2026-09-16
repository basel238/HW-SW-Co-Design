#!/usr/bin/env bash
# =============================================================================
# PHASE 3 — perf record + report + flame graph (the "WHERE" / which code)
# -----------------------------------------------------------------------------
# Produces the project deliverables:
#   - report_<bench>.txt   (perf report, Self vs Children columns)
#   - <bench>.svg          (flame graph you can open in a browser)
#
# Usage:   bash 03_perf_record_flame.sh nbody
#          bash 03_perf_record_flame.sh raytrace
# =============================================================================
set -euo pipefail

BENCH="${1:?Usage: bash 03_perf_record_flame.sh <benchmark>}"
REPORT="report_${BENCH}.txt"
SVG="${BENCH}.svg"

# python3-dbg gives symbols + frame pointers so -g can unwind the call graph
# and reveal internal CPython + Python-level frames.
RUN=(python3-dbg -m pyperformance run --bench "${BENCH}")

echo "==> [1/4] Recording samples at ~999 Hz with call graphs ..."
perf record -F 999 -g -- "${RUN[@]}"
# If stacks look broken (missing frames), swap the line above for:
#   perf record -F 999 --call-graph dwarf -- "${RUN[@]}"

echo "==> [2/4] Exporting perf report -> ${REPORT} ..."
perf report --stdio > "${REPORT}"

echo "==> [3/4] Building flame graph -> ${SVG} ..."
if [ -d FlameGraph ]; then
    perf script > out.perf
    ./FlameGraph/stackcollapse-perf.pl out.perf > out.folded
    ./FlameGraph/flamegraph.pl out.folded > "${SVG}"
else
    # Fallback: perf's native HTML flamegraph
    perf script report flamegraph
    SVG="flamegraph.html"
fi

echo "==> [4/4] Done."
echo ""
echo "  report : ${REPORT}   (look for the highest 'Self%' = leaf hotspot)"
echo "  flame  : ${SVG}       (open in a browser; widest TOP plateau = hotspot)"
echo ""
echo "  Open the flame graph with:   firefox ${SVG}"
