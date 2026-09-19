# Direct benchmark commands

These Bash scripts launch `src/<variant>/<benchmark>/run_benchmark.py` directly. They never run or import `tools/pipeline.py`, `tools/workload.py`, `tools/timing_runner.py`, or any other custom Python helper. The benchmark's existing pyperf Runner remains; benchmark source files are unchanged. The short inline interpreter check runs before measurement.

After the usual debug setup, run:

```bash
bash scripts/01_baseline.sh --direct nbody
bash scripts/01_baseline.sh --direct raytrace
bash scripts/03_perf_record_flame.sh --direct nbody
bash scripts/03_perf_record_flame.sh --direct raytrace
```

Equivalently, invoke `scripts/direct/01_baseline.sh` or `scripts/direct/03_perf_record_flame.sh` without `--direct`. Append `optimized` to select the candidate source. `PYTHON_BIN=/path/to/debug/python` overrides `.venv/bin/python`; release Python, Python optimization flags, and an unpinned pyperf version are rejected.

Each invocation creates a unique `results/direct-.../` directory and prints its location. It retains interpreter identity, the entry-file SHA-256, the measured command, logs and an explicit `SCOPE.txt`. Existing results are preserved. There is no source snapshot, full-tree provenance check, correctness check, automatic comparison gate, stack-health check or evidence ZIP in this simpler path. Do not edit sources during a measurement. Direct timing JSONs do not contain the provenance required by `04_optimize_compare.sh`.

## Timing

`01_baseline.sh` invokes the original benchmark's pyperf CLI. The reported timing comes from the benchmark's internal timer. The default is 20 fresh workers, 3 values and 1 warmup per worker, with `loops=1`. Output is `timing.json`. For example:

```bash
DIRECT_PROCESSES=2 DIRECT_VALUES=2 DIRECT_ITERATIONS=2000 \
  bash scripts/01_baseline.sh --direct nbody
```

The direct scripts use the settings below, independently of `config.json`:

| Variable | Default | Meaning |
|---|---|---|
| `DIRECT_ITERATIONS` | 20000 | nbody steps per call; reference remains sun |
| `DIRECT_WIDTH`, `DIRECT_HEIGHT` | 100, 100 | Raytrace image size |
| `DIRECT_PROCESSES` | 20 | Timing workers |
| `DIRECT_VALUES` | 3 | Timing values per worker |
| `DIRECT_WARMUPS` | 1 | Timing warmups per worker |
| `DIRECT_CALLS` | 40 nbody / 10 raytrace | Calls in a profiling/counter worker |
| `DIRECT_FREQUENCY` | 499 | Native sampling frequency in Hz |
| `DIRECT_TIMEOUT` | 300 | Native profiling timeout in seconds |
| `DIRECT_REPEATS` | 3 | Whole-process counter repetitions per event group |

## Native perf profile

`03_perf_record_flame.sh` uses pyperf 2.10.0's built-in `--hook perf_record`. A single direct worker executes the configured number of calls. `--delay=-1` starts perf disabled; the upstream hook enables/disables sampling around each benchmark call. Imports and pyperf metadata/report generation are outside those enabled intervals. There is no warmup or calibration in this diagnostic run, so only one hook recording is produced.

This is benchmark-call profiling, with interpreter execution and small upstream hook/call-boundary overhead still present. It cannot mean literally only algorithm instructions: Python executes the algorithm through its interpreter. The scope includes complete calls, including nbody momentum adjustment outside its internal timing boundary. The first call has no explicit warmup; these profiles are not interchangeable with historical warmed/gated captures.

Sampling uses `cpu-clock:u`, DWARF unwinding and period weights. The script retains the raw `perf.data.*`, `native-self.txt`, `native-stacks.txt`, `native.folded` and `perf.svg`. `profile-timing.json` is diagnostic output collected under perf and must not be used for a speedup claim. Inspect stack ancestry and unknown frames manually.

Linux `perf`, Perl and GNU `timeout` are required. The timeout bounds upstream FIFO waits when perf cannot attach; pyperf's hook suppresses perf's stderr, so a timeout may require checking perf permissions/capabilities separately. This path uses upstream hook handling; the existing pipeline's strict ACK validation and ACK fix remain unchanged.

Upstream documentation: [pyperf perf-record hook](https://pyperf.readthedocs.io/en/latest/run_benchmark.html#profiling-benchmarks-using-perf-record).

## Hardware counters: explicit broader scope

An unmodified benchmark has no built-in perf-stat hook. A direct `perf stat` launch therefore counts startup, imports and pyperf bookkeeping as well as benchmark calls. The script requires an explicit option before collecting that broader measurement:

```bash
bash scripts/02_perf_stat.sh --direct --whole-process nbody
```

It saves separate CSVs for software, IPC, branch, generic cache and L1 event groups, with a fresh worker for each repetition. Unsupported events and running fractions remain visible in raw perf output. It does not calculate trusted ratios or subtract estimated wrapper/startup costs. Exact counters restricted to benchmark calls require start/stop instrumentation or the existing gated driver; these direct whole-process counts must not be described as benchmark-only.

The ordinary commands without `--direct`, including `13_course_stages.sh`, continue to use the existing validated pipeline.
