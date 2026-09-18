# Start here — complete v3 package

Extract the whole directory into your Ubuntu VM. Keep the same release Python version as before; Python 3.12/3.13 is not required for the main workflow.

```bash
cd project-scripts-v3
PYTHON_BIN=/usr/bin/python3 bash scripts/00_setup.sh
bash script_nbody.sh
bash script_raytrace.sh
```

Setup creates a local environment and installs the pinned benchmark/profiling dependencies. It attempts to install py-spy by default. It never installs system packages or changes permissions/sysctls. If required, Ubuntu's matching guest-kernel perf package and Perl must be installed separately as described in README.md.

The wrappers collect fresh timing, cProfile, PMU capability probes, a Python sampling flame graph, grouped counters/MPKI, and a native flame graph. Each stage creates a unique results directory. The timing directory's pipeline-summary.json links all stages. **Exit 3 means a requested diagnostic was unavailable or failed validation; inspect the saved files.** Timing and other completed stages are retained. Missing cycles stays missing IPC.

If py-spy cannot be installed or run, the remaining measurements still work. Set `pyspy.enabled` to false in config.json to omit it from the full workflow. This does not affect the standalone sampling command.

## What to inspect

| Output | Purpose |
|---|---|
| timing.json, stats.stdout.txt, hist.stdout.txt | Unprofiled timing and variability |
| capabilities.md / capabilities.json | Counter probe results and specific failure categories |
| stat-summary.md / stat-summary.json | Counters, miss fractions, MPKI, IPC/CPI when valid, per-call normalization |
| native.svg, native-self.txt, stack-health.json | Native sampled hotspots and unwind warnings |
| python-sampled.svg, python-sampled.folded, pyspy-status.json | Python statistical sampling and recorded scope/status |
| python.pstats.txt | Python function call counts and instrumented self/cumulative rankings |

The py-spy recording includes driver startup and warmup. Native perf counters/samples use the gated benchmark region. These are explicitly different scopes. Neither profiler's elapsed time is the optimization timing result.

## Optimize and compare

Edit the candidate under `src/optimized/nbody/` or `src/optimized/raytrace/`; preserve the benchmark entry points and workload semantics. Baseline source is verified against recorded upstream hashes.

```bash
bash scripts/04_optimize_compare.sh nbody
bash scripts/04_optimize_compare.sh raytrace
```

This checks numerical/image correctness, runs fresh AB/BA timing rounds, validates provenance and computes worker-based uncertainty. It saves summary/summary.md, source.diff, source-changes.json and rounds.json. Candidate files initially equal baseline, so an unmodified candidate should return exit 3, not claim success.

Comparison exit codes: 0 = declared evidence gate met; 3 = valid evidence below the gate or unchanged source; 2 = invalid/incompatible evidence or correctness failure. See README.md for the distinction between a 7% point estimate and an interval entirely above 7%.

To profile an optimized variant separately:

```bash
bash script_nbody.sh optimized
bash script_raytrace.sh optimized
```

## Optional diagnostics

```bash
bash scripts/07_diagnose_pmu.sh --reference-cycles
bash scripts/10_python_sampling.sh nbody
bash scripts/09_topdown_optional.sh nbody baseline --cpu 0
# Supported newer Python/perf builds only; never required for baseline timing:
bash scripts/11_python_perf.sh nbody --mode map
bash scripts/11_python_perf.sh nbody --mode jit
```

Reference cycles are never substituted for core cycles. Top-down is explicitly system-wide on the selected CPU. Python/perf map/JIT profiles are instrumented diagnostics and require documented capabilities; unsupported modes exit 3 with a reason.

## Reproduce software guard tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

These use synthetic observations to verify measurement decisions, not your hardware. Fill in ENVIRONMENT.md before collecting final report data. TESTING.md records what was verified during preparation and which hardware checks remain.
