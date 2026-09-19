#!/usr/bin/env bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
prepare_direct 03_perf_record_flame "$@"
[[ ${1:-} == --help ]] && exit 0
for required in perf perl timeout; do
    command -v "$required" >/dev/null 2>&1 || { echo "Required command missing: $required" >&2; exit 2; }
done
positive_integer DIRECT_CALLS "${DIRECT_CALLS:-$DEFAULT_CALLS}"
positive_integer DIRECT_FREQUENCY "${DIRECT_FREQUENCY:-499}"
positive_integer DIRECT_TIMEOUT "${DIRECT_TIMEOUT:-300}"
new_direct_result "Direct benchmark, one pyperf worker, loops=1, no warmup, fixed values/calls. pyperf's built-in perf_record hook gates benchmark calls; hook/call-boundary overhead remains. cpu-clock:u period-weighted native samples, not hardware counts. profile-timing.json is profiled diagnostic data, not speedup evidence. config.json is not used."
export PYPERF_PERF_RECORD_DATA_DIR="$OUT"
export PYPERF_PERF_RECORD_EXTRA_OPTS="--delay=-1 -P -e cpu-clock:u -F ${DIRECT_FREQUENCY:-499} --call-graph dwarf,16384"
printf 'PYPERF_PERF_RECORD_DATA_DIR=%q\nPYPERF_PERF_RECORD_EXTRA_OPTS=%q\n' \
    "$PYPERF_PERF_RECORD_DATA_DIR" "$PYPERF_PERF_RECORD_EXTRA_OPTS" > "$OUT/perf-environment.sh"
# A direct worker avoids profiling the pyperf manager and needs no env forwarding.
# The timeout bounds FIFO waits if perf exits before opening the hook's pipes.
run_direct timeout --signal=TERM --kill-after=5s "${DIRECT_TIMEOUT:-300}s" \
    "$PY" "$SOURCE" "${BENCH_ARGS[@]}" --worker --loops 1 --warmups 0 \
    --values "${DIRECT_CALLS:-$DEFAULT_CALLS}" --hook perf_record --output "$OUT/profile-timing.json"
DATA=("$OUT"/perf.data.*)
[[ ${#DATA[@]} == 1 && -s "${DATA[0]}" ]] || { echo "Expected one nonempty perf recording in $OUT." >&2; exit 3; }
# Keep the readable tables and stack processing out of the recorded interval.
perf report -i "${DATA[0]}" --stdio --no-children -g none --percent-limit 0.5 \
    > "$OUT/native-self.txt" 2>> "$OUT/stderr.log"
perf script -i "${DATA[0]}" -F +period > "$OUT/native-stacks.txt" 2>> "$OUT/stderr.log"
perl "$ROOT/vendor/FlameGraph/stackcollapse-perf.pl" "$OUT/native-stacks.txt" \
    > "$OUT/native.folded" 2>> "$OUT/stderr.log"
[[ -s "$OUT/native.folded" ]] || { echo "No usable folded stacks in $OUT." >&2; exit 3; }
perl "$ROOT/vendor/FlameGraph/flamegraph.pl" --countname ns --title "$BENCH direct debug profile" \
    "$OUT/native.folded" > "$OUT/perf.svg" 2>> "$OUT/stderr.log"
echo "Open: $OUT/perf.svg (inspect native-self.txt and stack ancestry before interpreting)"
