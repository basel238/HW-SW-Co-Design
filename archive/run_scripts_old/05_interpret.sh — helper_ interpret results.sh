#!/usr/bin/env bash
# =============================================================================
# HELPER — Interpret a pyperf result JSON in depth
# -----------------------------------------------------------------------------
# Detailed statistics + distribution for any result file. Ties to the course's
# Histogram / PDF / CDF material: judge a DISTRIBUTION, not a single number.
#
# Usage:   bash 05_interpret.sh nbody_base.json
#          bash 05_interpret.sh raytrace_opt.json
# =============================================================================
set -euo pipefail

JSON="${1:?Usage: bash 05_interpret.sh <result.json>}"
[ -f "${JSON}" ] || { echo "File not found: ${JSON}"; exit 1; }

echo "########## mean / median / min / max / std dev / outliers ##########"
python -m pyperf stats "${JSON}"

echo ""
echo "########## distribution (histogram) ##########"
python -m pyperf hist "${JSON}"

echo ""
echo "########## raw per-run values ##########"
python -m pyperf dump "${JSON}"

echo ""
echo "  What to look at:"
echo "     mean   = headline number"
echo "     stddev = measurement noise (keep the VM quiet to shrink it)"
echo "     hist   = shape of the distribution; a tight single peak = trustworthy run"
