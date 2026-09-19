#!/usr/bin/env bash
set -euo pipefail
if [[ ${1:-} != --whole-process ]]; then
    echo "Direct perf stat includes interpreter startup, imports and pyperf bookkeeping." >&2
    echo "For this explicitly broader scope: bash scripts/direct/02_perf_stat.sh --whole-process BENCH [VARIANT]" >&2
    echo "Benchmark-call-only counters require start/stop instrumentation; no counters were collected." >&2
    exit 2
fi
shift
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
prepare_direct 02_perf_stat "$@"
[[ ${1:-} == --help ]] && exit 0
command -v perf >/dev/null 2>&1 || { echo "perf is required." >&2; exit 2; }
positive_integer DIRECT_CALLS "${DIRECT_CALLS:-$DEFAULT_CALLS}"
positive_integer DIRECT_REPEATS "${DIRECT_REPEATS:-3}"
new_direct_result "WHOLE-PROCESS counters: startup, imports, fixed benchmark calls, pyperf bookkeeping and output. No custom Python driver. Each event group/repeat launches a fresh direct worker with no warmup and loops=1. These are NOT benchmark-call-only counts and are not equivalent to the existing gated pipeline results. config.json is not used."
GROUP_NAMES=(software ipc branches cache l1)
GROUP_EVENTS=("task-clock,context-switches,cpu-migrations,minor-faults,major-faults" \
    "{cycles:u,instructions:u}" "{branches:u,branch-misses:u}" \
    "{cache-references:u,cache-misses:u}" "{L1-dcache-loads:u,L1-dcache-load-misses:u}")
for index in "${!GROUP_NAMES[@]}"; do
    for ((repeat=1; repeat<=${DIRECT_REPEATS:-3}; repeat++)); do
        label="${GROUP_NAMES[$index]}-$repeat"
        echo "Whole-process counters: $label"
        run_direct perf stat -x ';' --no-big-num -o "$OUT/$label.csv" -e "${GROUP_EVENTS[$index]}" -- \
            "$PY" "$SOURCE" "${BENCH_ARGS[@]}" --worker --loops 1 --warmups 0 \
            --values "${DIRECT_CALLS:-$DEFAULT_CALLS}"
    done
done
echo "Raw counters: $OUT/*.csv; unsupported or multiplexed events require review."
