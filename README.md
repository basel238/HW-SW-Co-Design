# Reproducible nbody / raytrace measurement scripts — v4 repository layout

For an existing repository, start with **MIGRATION.md**. Install at the repository root; do not nest this package inside run_scripts/. Historical scripts and results are preserved under archive/.

This package replaces the original setup, baseline, counters, profiling and comparison pipeline. It supports release CPython 3.10 or newer on Linux. For continuity, start in the same Ubuntu VM with the same release Python version used for your previous baseline.

**Collect fresh baselines with this package.** The old JSONs remain historical evidence; their source identity and measurement conditions cannot be assumed identical to this experiment.

The benchmark functions are unchanged copies from pyperformance 1.14.0. The timing adapter uses pyperf 2.10.0's public Runner API, forwards all workload parameters to workers, and calls those exact functions. It does not invoke pyperformance's environment installer during measurement.

## Start here

From the extracted project-repo-v4.1 directory, inside the Ubuntu VM:

    # Pick the same release interpreter as before; Python 3.12 is not required.
    PYTHON_BIN=/usr/bin/python3 bash scripts/00_setup.sh

    # Read-only environment and PMU diagnostics; may log permission failures.
    bash scripts/07_diagnose_pmu.sh

    # Complete initial workflow for each benchmark.
    bash script_nbody.sh
    bash script_raytrace.sh

No activation is needed. Every wrapper resolves paths relative to the package and uses its .venv/bin/python. You can invoke a wrapper from another working directory.

The setup installs pinned Python dependencies and py-spy 0.4.2 into this local venv. Set INSTALL_PYSPY=0 to skip its optional installation; set pyspy.enabled=false in config.json to omit its stage from the full pipeline. It does not install system packages, change sysctls, disable the watchdog, recreate your old environment, or alter existing project files. FlameGraph tools are already included at a recorded commit.

If perf is missing, install the package appropriate to the **guest kernel**:

    sudo apt install python3-venv linux-tools-common "linux-tools-$(uname -r)" perl

Package availability depends on the Ubuntu image/kernel repositories. Check perf --version afterwards. A restricted perf policy may still prevent profiling; see the saved errors and the course's machine policy. Do not run all setup/benchmarks as root merely to hide a permissions problem.

Results go into new UTC-stamped directories under results/. A profiling-stage exit code 3 means some requested measurements were unavailable or failed sanity checks; clean timing and the Python profile are still retained. It is not a benchmark correctness failure.

## What is included

| File | Purpose |
|---|---|
| MIGRATION.md / tools/migrate_repository.py | Archive the old layout, install at root, create a branch and local commit |
| results/ | Fresh timestamped measurement output |
| hw/ | Hardware source location; implementation not supplied |
| archive/ | Historical files preserved by migration |
| scripts/00_setup.sh | One explicit release interpreter and pinned Python dependencies |
| scripts/01_baseline.sh BENCH [VARIANT] | Unprofiled multi-worker timing; VARIANT defaults to baseline |
| scripts/02_perf_stat.sh BENCH [VARIANT] | Gated fixed-work counters, separate event groups and raw repeats |
| scripts/03_perf_record_flame.sh BENCH [VARIANT] | Native perf recording, readable Self table, full call graph, folded stacks, SVG and stack review |
| scripts/04_optimize_compare.sh BENCH | Correctness check and fresh alternating baseline/optimized comparisons |
| scripts/05_interpret.sh TIMING_JSON | Metadata, check, stats, histogram and raw-value reports |
| scripts/06_python_profile.sh BENCH [VARIANT] | Python source-function attribution using cProfile |
| scripts/07_diagnose_pmu.sh | Separate counter probes and environment information |
| scripts/08_check_correctness.sh BENCH | Run output/state regression checks without a timing comparison |
| scripts/09_topdown_optional.sh BENCH [VARIANT] --cpu CPU | Explicitly requested, separately labeled system-wide top-down |
| scripts/10_python_sampling.sh BENCH [VARIANT] | Independent py-spy raw samples and Python SVG |
| scripts/11_python_perf.sh BENCH [VARIANT] --mode map or --mode jit | Opt-in Python/native trampoline profile after capability checks |
| scripts/run_all.sh BENCH [VARIANT] | Timing, cProfile, capability probes, py-spy, counters and native profile |
| script_nbody.sh / script_raytrace.sh | Per-benchmark initial-workflow wrappers |
| src/baseline/ | Upstream source locked by hashes; do not edit |
| src/optimized/ | Initially identical candidate copies; edit here |
| tools/ | Timing, fixed-work, correctness, comparison and profile-validation helpers |
| config.json | Workload, repetition, affinity and sampling settings |
| ANALYSIS_REVIEW.md | Agreement and corrections to the pasted critique |
| TESTING.md | What was tested and what still requires your VM |
| CHANGELOG.md / QUICKSTART.md | Integrated changes and short operating instructions |
| tests/ | Reproducible synthetic measurement-guard tests |
| ENVIRONMENT.md | Host/QEMU details to fill in before final measurements |
| reports/ | Written report templates; scripts never overwrite them |
| prompt.txt | User requests recorded for this revision; supplement your earlier AI history |
| SOURCES.json / licenses/ | Benchmark version, upstream hashes and license |
| vendor/FlameGraph/ | Pinned plotting/folding tools, source provenance and CDDL text |

BENCH is exactly nbody or raytrace. VARIANT is baseline or optimized. Names such as raytrace_base are rejected by the command parser.

## The three measurement types

### 1. Timing for the final improvement claim

Timing uses the original bench_nbody / bench_raytrace functions through pyperf.Runner.bench_time_func. Defaults: 20 workers, 3 measured values per worker, 1 warmup value and 1 benchmark loop per value. One loop is already substantial for the default workloads. Every custom parameter is forwarded to workers by our adapter, rather than relying on the upstream script's incomplete forwarding of the nbody reference argument.

- nbody: 20,000 simulation steps, sun reference.
- raytrace: 100 by 100 pixels, original scene.
- No perf, cProfile, image writes, installer or package manager is inside the benchmark timing.
- The original timing boundary is preserved: nbody's momentum adjustment precedes its internal timer; raytrace's original timer includes scene/canvas construction and rendering.
- The nbody module's state continues across calls within a worker, as in the original benchmark. Every worker starts from a fresh import.

The adapter's JSON contains source hashes and workload parameters. Each run also saves provenance.json, source snapshots, configuration, dependencies, interpreter identity/build flags, guest CPU information and commands. A wider histogram or slow worker is retained rather than filtered out.

### 2. Counters and native profiles

A separate driver imports the exact source snapshot, performs in-process warmup, then sends perf an enable command and waits for its acknowledgment. After the fixed workload it disables events and waits again before writing results.

The default perf command uses --delay=-1 and the FIFO control interface available in Linux perf 5.15. **Imports, dependency preparation, warmup and result writing are outside the enabled region.** Small driver-loop, timer, FIFO-boundary and function-entry costs remain. Counters cover complete benchmark calls, including nbody's momentum adjustment; their boundary is slightly wider than the original internal pyperf timer.

Each repetition runs in a fresh process. Within it, nbody's state continues from warmup through a fixed number of calls. Do not change this state policy when comparing variants.

Defaults are 40 nbody calls or 10 raytrace calls per profiling run, one warmup call, and three counter repetitions per event group. Every repetition has the same configured useful-work count. The event groups execute separately; never divide an L1 count by instructions from another group. MPKI adds three separate two-event groups by default (set mpki=false to skip): instructions/branch-misses, instructions/generic-cache-misses, and instructions/L1-load-misses. Each uses matching user-mode filters and its own instruction denominator.

| Group | Events / treatment |
|---|---|
| Software | task-clock, context switches, CPU migrations, minor faults, major faults |
| IPC | Simultaneous user-mode cycles and instructions |
| Branches | Simultaneous user-mode branches and branch misses |
| Generic cache | Simultaneous user-mode cache references and misses |
| L1 | Simultaneous user-mode L1 data loads and misses |
| MPKI (three extra passes) | Simultaneous instructions and corresponding misses; misses per 1,000 instructions |

Missing/unsupported counts, zero cycles/instructions on active work, and running fractions below 95% do not produce trusted ratios. Zero misses/faults are permitted. Raw observations remain in the files; unavailability becomes null with a reason. A sanity check is not proof that the virtual PMU implements the event correctly.

The scripts keep each repeat's CSV rather than hiding the distributions behind a single -r aggregate. stat-summary.md shows counts, units, running fractions, normalized counts, derived metrics and invalidity reasons; its median/range summaries are descriptive, not confidence intervals. They normalize usable values per full benchmark call. They do not calculate ratios across passes or invent IPC from nominal frequency.

Native sampling uses cpu-clock:u at 499 Hz, explicit sample periods, and DWARF unwinding with a 16 KiB stack dump. This profiles user execution and avoids depending on hardware cycles. DWARF support and unwind information must actually be present; failure is retained, not silently replaced with a differently scoped measurement.

The default lower frequency is an overhead-conscious starting point, not an accuracy guarantee. Inspect sample counts, lost-sample warnings, native call paths and stack-health.json. Adjust frequency/stack depth only if the diagnostic evidence warrants it.

Flame widths are weighted by cpu-clock periods and labeled **ns**. They are not billions of independent samples. Stack review checks unknown ancestry, impossible-looking addresses, extreme depths and missing/lost-sample information; it never certifies a graph as correct automatically.

### 3. Python-function attribution

cProfile runs separately over the fixed useful work, excluding imports and warmup. It writes python.pstats and python.pstats.txt with cumulative and self rankings, including actual Python function names.

This is diagnostic instrumentation. It distorts call-heavy code and is not the timing result used for the 7% claim. The cProfile table is distinct from the additional statistical Python flame graph described below. The native SVG and Python table answer complementary questions.

Python 3.10 is sufficient for this workflow. Built-in -X perf Python mapping is a separate 3.12+ feature requiring a supported build; changing versions requires fresh baselines. This package does not assume that Ubuntu 24.04 supplies Python frame pointers.

### 4. Statistical Python sampling (new in v3)

The full workflow separately invokes pinned py-spy 0.4.2 at 250 Hz, even when perf is unavailable. You can also run:

    bash scripts/10_python_sampling.sh nbody
    bash scripts/10_python_sampling.sh raytrace optimized

It produces python-sampled.folded, python-sampled.svg and pyspy-status.json from the same source snapshot and fixed-work driver. The SVG is generated from the retained raw recording; widths count **samples**, not function calls or nanoseconds. Fewer than 1,000 samples triggers a quality warning, not automatic rejection or certification. Increase profile_calls if needed.

**This profile covers the driver process, including imports and its warmup.** It does not use perf's FIFO measurement gate, and these frames have not been silently filtered out. Keep that scope distinction when comparing it with native perf or cProfile. Sampling is diagnostic: it can perturb execution, especially on a single vCPU. With affinity configured, sampler and child use the selected CPU set. Errors are retained without changing ptrace settings or requiring root automatically.

### 5. Optional combined Python/native frames

These are opt-in diagnostics, separate from default native sampling and all timing/counters:

    bash scripts/11_python_perf.sh nbody --mode map
    bash scripts/11_python_perf.sh nbody --mode jit

map requires Python 3.12+, trampoline support and frame-pointer evidence, and explicitly uses FP unwinding. jit requires Python 3.13+, trampoline support and a perf version satisfying the conservative documented JIT-fix check (>6.8 or the documented 6.7.2+ backport); it uses DWARF, monotonic-clock recording and perf inject --jit. Unknown or older backports are refused; Python is never upgraded automatically. Distro version suffixes are not treated as upstream patch versions.

The actual recorded folded stacks must contain Python trampoline names before this mode reports available. This confirms observed attribution, not complete stack correctness; inspect stack-health.json. Instrumentation changes execution and cannot be used for the timing improvement claim. Injected ELF sidecars stay in the unique run directory.

## Make and compare an optimization

Edit only the candidate copy:

    src/optimized/nbody/run_benchmark.py
    src/optimized/raytrace/run_benchmark.py

Sibling helper modules are supported and are included in the source-tree hashes. Preserve the public benchmark entry points:

    bench_nbody(loops, reference, iterations)
    bench_raytrace(loops, width, height, filename)

The benchmark functions must retain the workload and output semantics. The driver calls these functions directly; changes solely to the upstream file's __main__ block do not change the experiment. If you change the public API or data representation beyond what the correctness adapter supports, update and review the adapter rather than bypassing the check.

More efficient libraries are allowed by the supplied assignment. Install any additional dependency into this .venv, pin it in requirements.txt, and use the same installed environment for both variants. Package versions are compared.

Run:

    bash scripts/08_check_correctness.sh nbody
    bash scripts/04_optimize_compare.sh nbody

    bash scripts/08_check_correctness.sh raytrace
    bash scripts/04_optimize_compare.sh raytrace

The comparison saves source.diff, source-changes.json and rounds.json from the actual frozen measured sources. It includes helper additions/removals and records binary changes.

The comparison command repeats correctness itself, then collects fresh paired measurements in alternating order: baseline/optimized, then optimized/baseline. The default is two rounds; configuration requires an even count of at least two. It does not compare a new candidate against an old, possibly drifted baseline automatically.

Correctness checks:

- **nbody:** fresh isolated variants, matching initial bodies, then complete body states after each of three consecutive configured calls. Every value must be finite; relative tolerance 1e-10 and absolute tolerance 1e-12 are recorded.
- **raytrace:** exact PPM output comparison at the configured resolution and scene.
- Evidence is tied to both entry-file and full source-tree hashes. A stale successful check cannot validate different code.
- These finite regression checks do not prove all possible inputs or semantics. A legitimate larger numerical change may require a separately justified correctness policy; no tolerance is silently loosened.

The comparison validates interpreter/build, dependencies, machine metadata, benchmark/workload settings, timing configuration and measurement-tool hashes. It retains pyperf comparison output but does not use a successful tool exit status as evidence of speedup.

For every round, it reports:

    runtime reduction = 1 - optimized_mean / baseline_mean
    speedup = baseline_mean / optimized_mean

Its declared evidence gate requires at least 7% mean runtime reduction, a positive lower bound for the worker-bootstrap 95% improvement interval, correct output, and a changed source tree. This is a methodology choice, not a quoted assignment requirement. A positive lower bound does not establish that the whole interval exceeds 7%; the stronger condition is reported separately.

The bootstrap resamples whole worker means rather than pretending all values inside one worker are independent. It does not account for every form of host interference or systematic bias. Inspect both rounds and the raw distribution.

Comparison exits:

- 0: declared evidence gate met in every round.
- 3: valid experiment below the gate, noisy evidence, or unchanged source tree.
- 2: incompatible or invalid evidence/correctness failure.

Both candidate copies initially equal baseline. A comparison should therefore **not** claim an optimization success until you implement and verify a change.

## PMU diagnosis and optional top-down

    bash scripts/07_diagnose_pmu.sh

The full initial workflow also runs these nonmutating probes automatically, outside every measurement. capabilities.md and capabilities.json distinguish missing tools, permission failures, unsupported events, zero counts, insufficient running fraction and plausible counts. Plausible does not mean validated hardware.

The diagnostic saves interpreter/configuration, lscpu, available events, dmesg where permitted, and watchdog/perf policy values. It runs cycles alone, instructions alone, their group, and task-clock on known CPU work. It does not change system settings. These diagnostics intentionally include a small command's startup and are not project benchmark results.

Only after checking the exposed CPU/event mapping, you can request the Intel-specific raw-cycle probe:

    bash scripts/07_diagnose_pmu.sh --raw-intel-cycles

A separate optional reference-cycle probe is also available:

    bash scripts/07_diagnose_pmu.sh --reference-cycles

It reports instructions_per_reference_cycle as a distinct diagnostic. It never populates ordinary IPC/CPI or changes the benchmark counter selection.

That raw event is a diagnostic, not a universal repair or a guarantee of using a different physical counter. Keep its output alongside the generic events.

If top-down is useful and supported, explicitly choose the guest CPU:

    bash scripts/09_topdown_optional.sh nbody baseline --cpu 0

This uses -a -C 0 --topdown and pins the workload to that CPU, with the same enable/disable region. It is **system-wide on that CPU** and includes other tasks. One vCPU does not make it equivalent to process profiling. Additional PMU events and privileges are required; repairing cycles alone does not guarantee top-down support.

Do not automatically disable the watchdog or relax permissions. Record any administrator-approved change in ENVIRONMENT.md and restore it appropriately after the experiment.

## Important output files

Each invocation prints its new directory. Look for:

- timing.json, provenance.json, stats.stdout.txt, hist.stdout.txt and dump.stdout.txt;
- stat-summary.md / stat-summary.json plus each group's counters.csv, metrics.json and workload.json;
- capabilities.md / capabilities.json and their raw probe files;
- native-self.txt, native-callgraph.txt, native.svg and stack-health.json;
- perf.data, native-stacks.txt and native.folded for later reanalysis;
- python.pstats.txt for instrumented Python source attribution;
- python-sampled.svg, python-sampled.folded and pyspy-status.json for statistical Python attribution;
- correctness.json and state/image evidence;
- comparison summary/summary.md and summary.json, plus source.diff, source-changes.json and rounds.json.

Raw perf dumps and authored report files have separate names. The scripts never overwrite your written reports. All command arguments, errors and exit statuses are retained. An unavailable counter is not described as a hardware bottleneck.

Recordings and some large intermediate files are ignored by Git, but are kept locally. Archive them with matching source/provenance before deleting or moving the environment. Ignoring a file is not an archive strategy.

## Interpreting the expected results

- A wide _PyEval_EvalFrameDefault can be normal on Python 3.10.
- Impossible addresses or mostly unknown ancestry require an unwind/symbol investigation.
- Native Self is more robust to failed ancestry, but still describes the sampled build and workload.
- Small cache/branch miss fractions do not establish the absence of stalls.
- Many allocations do not automatically imply DRAM-bandwidth limitation.
- A tiny sum of arithmetic-native Self functions is not an Amdahl fraction for offloading an entire Python operation.
- Default profiling control failures are explicit. There is no silent fallback to whole-process scope.

See ANALYSIS_REVIEW.md for the full assessment of the additional critique.

## References

- [pyperf public Runner API](https://pyperf.readthedocs.io/en/latest/api.html)
- [pyperf Runner CLI and worker structure](https://pyperf.readthedocs.io/en/latest/runner.html)
- [Python perf integration](https://docs.python.org/3.12/howto/perf_profiling.html)
- [perf stat](https://man7.org/linux/man-pages/man1/perf-stat.1.html)
- [perf record: unwind modes and control interface](https://man7.org/linux/man-pages/man1/perf-record.1.html)
- [Canonical frame-pointer policy and exceptions](https://ubuntu.com/blog/ubuntu-performance-engineering-with-frame-pointers-by-default)

- [py-spy documentation](https://github.com/benfred/py-spy)
- [CPython 3.13 JIT/perf requirements](https://docs.python.org/3.13/howto/perf_profiling.html)
