# Start here — v4.2

Install at the repository root. All measurements now use one debug CPython environment (`Py_DEBUG=1`); collect fresh matched baselines and candidates. **UPDATING.md** describes transferring a reviewed update to the VM.

On the VM, from the repository:

```bash
PYTHON_BIN=python3-dbg bash scripts/00_setup.sh
bash scripts/13_course_stages.sh
```

Setup requires debug CPython 3.10+ without `-O`/`-OO`. On Ubuntu, install `python3-dbg` and matching `python3-venv` support if needed. A custom debug executable can be selected with `PYTHON_BIN=/path/to/python` when creating `.venv`. An existing debug `.venv` is reused; an existing release or broken `.venv` is refused before dependency installation. Preserve that old environment by moving it aside once, then rerun setup:

```bash
# Only if setup reports an existing release or broken .venv:
mv .venv ".venv-before-debug-$(date +%Y%m%dT%H%M%S)"
PYTHON_BIN=python3-dbg bash scripts/00_setup.sh
```

The old `.venv-guide` and `.course-cache` may remain; neither is merged into `.venv`. The framework selects a cache by interpreter identity and validates its debug worker before measurement. Existing results and benchmark edits are preserved. Historical release results must not be used in new debug optimization comparisons.

The course command collects both benchmarks into **one** `results/run-.../` folder. Open its **README.md** first, then `nbody/README.md` and `raytrace/README.md`. They contain compact debug timing/counter summaries and links to `perf.svg` and supplementary `python.svg`, when available. Complete raw evidence is in **evidence.zip**, with checked hashes. Old runs are untouched.

The default requires genuine debug pyperformance execution and debug perf graphs. Those main measurements also cover the guide interpreter requirement; the duplicate guide stage and release mode have been removed. Missing perf evidence produces exit 3 and a clear report. Unsupported optional counters never manufacture IPC or replace the required graph.

Read **STAGES_1_3.md** for the requirement matrix, output meanings and interpretation tasks. Review `docs/stage1-nbody.md` and `docs/stage1-raytrace.md`, fill `ENVIRONMENT.md`, and write your report from fresh measurements.

For one benchmark only, run `bash script_nbody.sh` or `bash script_raytrace.sh`. For a short ACK check: `bash scripts/15_perf_gate_probe.sh`. For expanded raw output, append `--keep-details` to the course command. Lower-level diagnostic scripts still expose detailed stage output for troubleshooting.

No optimization is applied. Later, edit only `src/optimized/`, then run `bash scripts/04_optimize_compare.sh nbody` or `raytrace` for correctness and fresh paired timing. Unchanged candidate sources do not count as an optimization.
