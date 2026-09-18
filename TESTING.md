# Debug-only validation

Validated 18 September 2026: **55 automated tests passed, with no skips**, under a temporary debug CPython 3.12.10 build (`Py_DEBUG=1`) on macOS. The suite covers debug-only launchers/workers, rejection of release comparison evidence and mismatched cached framework workers, removed CLI modes, setup preservation, the existing FIFO ACK framing checks and compact evidence archives. The synthetic sampler fixture now resolves its temporary driver path so it matches macOS's `/var` to `/private/var` alias.

An isolated setup using the debug interpreter passed with the pinned dependencies. A genuine pyperformance 1.14.0 `--smoke` run passed for both benchmarks (2,000 nbody iterations and 24×24 raytrace), including cached worker debug flags and executable-hash validation before measurement. These smoke results were written outside this repository and are not performance evidence. All shell scripts passed `bash -n`, all toolkit/test Python files compiled, and `git diff --check` passed.

The integration suite executes real debug benchmark timing, cProfile, workload/FIFO exchanges and FlameGraph rendering; its perf observations and course framework fixture remain synthetic. Actual Linux perf/PMU behavior, native stack quality and live py-spy sampling still require the VM. The first sandboxed test attempt could not read macOS system metadata through psutil; the complete suite passed with that read permitted. No measurement was substituted with release Python.

On the VM after debug setup:

```bash
.venv/bin/python -m unittest discover -s tests -v
bash scripts/12_course_reference.sh --smoke
bash scripts/15_perf_gate_probe.sh
```

Running the unit suite with a release interpreter skips tests that execute workloads; it is not a substitute for the full debug suite. Existing results and benchmark sources are untouched. Earlier validation below records historical release behavior and does not describe the current interpreter policy.

# v4.2 validation (historical)

Validated 18 September 2026. **48 automated tests passed** under release CPython 3.12, including real FIFO ACK exchanges, invalid/missing replies, workload receipts, sampler validation, verified compaction, safe repository updates and evidence export.

The compact course integration tests run both real shortened benchmark timings and cProfile captures, the actual FIFO workload driver and bundled Perl renderer. Perf observations and their framework reference are explicitly synthetic fixtures. They verify one run directory with both benchmark summaries/graphs/timings and a verified archive containing raw recordings and source snapshots. A failed-gate run still produces an incomplete report and cannot be replaced by a Python graph.

Separately, **actual pyperformance 1.14.0 smoke runs passed for both benchmarks**, using 2,000 nbody iterations and 24×24 raytrace, one value each. These validate genuine framework invocation, manifest paths, dependencies, worker interpreter executable hash and source identity. Smoke numbers are not performance evidence. Delivered defaults remain 20,000 iterations / 100×100 and 20 timing workers.

Real Linux perf/PMU measurements, DWARF unwinding, the debug-interpreter guide workflow and successful live py-spy sampling require a rerun on the VM. There is no usable perf installation here. Synthetic tests do not validate virtual-PMU accuracy, caller ancestry or an optimization. The new gate probe and output checks expose target-machine failures.

The complete packaged updater also passed a temporary v4.1 Git-repository integration check: dry-run changed nothing; apply replaced 35 toolkit files; every backup hash matched; custom configuration, an edited candidate and historical results survived; HEAD was unchanged. After committing the fixture update, reapplication was a no-op. All 21 shell scripts passed `bash -n`; all 21 toolkit/test Python files parsed successfully. These Git checks did not access your local or remote repository.

After setup, run `.venv/bin/python -m unittest discover -s tests -v`. Earlier validation below is historical context; earlier failed results are not repaired by this update.

# v4.1 orphan-gitlink validation

Reproduced the supplied stage-0 FlameGraph gitlink at 41fee1f99f9276008b7cd112fca19dc3ea84ac32 without .gitmodules. Tested empty and populated local directories: plan left HEAD/files unchanged; apply created a clean branch/commit; MIGRATION.json preserved path and SHA; local contents survived in the archive; the original pointer remained in HEAD^; installed vendor tools were ordinary files. An unrelated submodule was refused without changes. A missing working-tree gitlink directory is a dirty-tree case and remains refused by the existing clean-tree check. Tests ran on temporary repositories, not the user checkout.

# v4 migration validation

Measurement behavior is unchanged from v3. The migration was tested against temporary Git repositories: dirty worktrees were refused before changes; dry-run left files and HEAD unchanged; apply created a branch and commit; old scripts, tracked perf data, original README/.gitignore and ignored local data survived; ignored data was not newly committed; the final checkout was clean. No operations were performed on the user's actual remote repository.

# v3 validation

Validation date: 2026-09-17. These are software checks, not new performance results for the target VM.

## Executed for v3

- **Fresh setup:** ran 00_setup.sh in an isolated copy under release CPython 3.12.14; it successfully installed pyperf 2.10.0, psutil 7.2.2 and py-spy 0.4.2 and validated the baseline hashes.
- **Guard suite:** all 11 tests in tests/test_measurement_guards.py passed. They check missing/zero cycles, valid MPKI without cycles, zero misses, invalid instruction denominators, low scheduling fractions, failed collection, distinct reference-cycle semantics, capability categories, JIT version handling, even comparison rounds and helper/binary source diffs. One test generates the Python SVG using real bundled Perl tools from explicitly synthetic samples.
- **Both initial workflows:** completed real reduced-workload timing and cProfile runs, capability collection, attempted py-spy, unavailable-counter reporting and unavailable-native reporting. Exit 3 correctly retained useful outputs instead of claiming complete profiling success.
- **Real py-spy attempt:** the runtime rejected process suspension with EPERM. A shorter attempt also hit a process-exit/executable lookup race. These errors were retained. No ptrace/sysctl permissions were changed. Successful actual py-spy sampling still needs the target VM; its successful file-processing path was separately tested with clearly synthetic samples.
- **Both comparisons:** fresh baseline/optimized then optimized/baseline timing rounds completed, correctness passed for identical sources, and the unchanged-source gate correctly returned 3. Full-source diffs and round manifests were produced.
- **Mock perf integration:** actual fixed-work child processes and FIFO enable/disable acknowledgments, with synthetic counter observations, tested zero cycles, valid IPC/CPI, unsupported L1 counters, and all three new simultaneous MPKI pairs. Expected branch/generic-cache/L1 MPKI values were 1.0/0.1/0.5. Counter summaries were emitted. Native folding/rendering preserved the synthetic 6,000,000 ns period total.
- **Optional Python/perf:** an unsupported local build returned exit 3 with the capability reason. The version guard rejects ambiguous distro suffixes and old versions; actual map/JIT recording/injection is not validated on this host.
- **Syntax and archive:** all shell scripts pass bash -n; Python sources compile. The archive excludes environments, generated benchmark results, bytecode and temporary test fixtures.

Reduced v3 workloads used 1,000 nbody iterations, a 32-by-32 raytrace image, two workers/two values, and reduced profiling calls/repeats. Some independent software checks ran concurrently. Their timing numbers are not reported as performance evidence. The delivered default remains 20,000 nbody iterations / 100-by-100 raytrace, 20 workers, and three counter repeats.

## Reproduce the included software checks

From the extracted package after setup:

    .venv/bin/python -m unittest discover -s tests -v

The sampler test is explicitly synthetic and is skipped if Perl is absent. It does not execute py-spy or validate sampling accuracy. Temporary mock perf executables and fabricated result files are not shipped as project data.

## Target-VM validation remains necessary

There is no usable perf installation or access to the original QEMU guest here. Native unwinding, PMU fidelity, top-down, actual py-spy capture and supported newer Python/perf trampoline modes still need to be exercised there. Local execution used Python 3.12; Python 3.10 compatibility has not been executed here. Preserve the same release interpreter for fresh matched baselines and candidates, inspect the retained logs/stack diagnostics, and fill in ENVIRONMENT.md.

This package contains no benchmark optimization and claims no speedup. A valid measurement method cannot repair an unavailable virtual counter.

---

# Earlier v2 validation (historical)

Validation date: 2026-09-17. These checks establish software behavior, not a new performance result for your VM.

## Earlier executed checks

| Area | Check and outcome |
|---|---|
| Shell/Python syntax | All 15 shell entry points/helpers passed `bash -n`; all six Python helpers compiled. |
| Real benchmark execution | Both vendored benchmarks completed reduced-workload unprofiled pyperf runs, fixed-work calls, and separate cProfile runs under release CPython 3.12 with pyperf 2.10.0. |
| Worker configuration | Both benchmarks ran with two workers and two measured values per worker. Distinctive workload parameters and source hashes reached the effective metadata of every worker. |
| Correctness | Identical baseline/candidate sources passed for both benchmarks. A deliberately changed nbody timestep and a deliberately changed raytrace image failed. |
| Source isolation | Separate source imports and full-tree hashes distinguish variants, including changes to sibling helper modules. |
| End-to-end comparison | Both benchmarks completed fresh baseline/optimized then optimized/baseline rounds. The unchanged candidate trees correctly returned exit 3 and did not claim an optimization, despite noisy timing differences. |
| Comparison rejection | Thirteen synthetic comparison cases covered incompatible interpreter/build/workload, noise, insufficient evidence, stale/failed correctness, unchanged sources and helper-only source changes. Additional tests rejected conflicting or absent source/workload metadata inside pyperf JSON, including per-worker overrides. |
| Counter validity | Zero cycles produced null IPC/CPI. A valid simultaneous pair produced the expected ratios. Low event-running percentage suppressed derived ratios. Legitimate zero cache references remained a usable count but produced no zero-denominator miss ratio. |
| Missing perf | The complete initial workflow retained timing and Python profiles and reported unavailable counter/native stages with exit 3. |
| Control protocol | Real workload processes exercised enable/acknowledge and disable/acknowledge FIFO exchanges. Missing acknowledgments timed out rather than waiting indefinitely. |
| Failure evidence | Workload exceptions produced error receipts; existing output paths were not overwritten. |
| Stack review | Synthetic unknown ancestry, extreme depth and malformed stack cases were flagged. The helper does not automatically certify native unwind correctness. |

The reduced functional runs used 100 nbody iterations and a 16-by-16 raytrace image, two workers, two values, and small profiling call counts. Some independent smoke checks ran concurrently. Their elapsed times are intentionally **not performance evidence** and are not included as project results. The delivered configuration retains the full 20,000-step / 100-by-100 workloads and 20 timing workers.

## Simulated perf integration

A temporary fake perf executable exercised the actual driver process, FIFO control protocol, event parser, run directories and failure propagation. Synthetic counter cases covered zero cycles, valid cycles/instructions, and an unsupported L1 group while preserving other groups. The real bundled Perl tools folded synthetic native stacks and produced an SVG; three periods of 2,000,000 ns produced a folded total of 6,000,000 ns.

These are integration tests using synthetic observations. They do **not** validate a physical or virtual PMU. The fake executable and its fabricated results are excluded from the deliverable.

## What still requires the target VM

There was no usable Linux perf installation or access to your original QEMU guest in this execution environment. Therefore the following have not been established here:

- Whether that VM provides usable cycles or other hardware events.
- Whether its installed perf build supports the requested FIFO control and DWARF features in practice. Command syntax was checked against the perf 5.15 implementation, but the actual guest build must be exercised.
- Whether native stacks from the selected release interpreter unwind reliably, or whether sampling loses records or adds material overhead.
- Whether system-wide top-down works and what unrelated guest activity it includes.
- Full-workload timing stability, thermal/frequency/host interference, or any optimization speedup.
- Execution on CPython 3.10: the code targets 3.10+, but local functional runs used 3.12. Use the same release interpreter as your historical baseline for continuity and collect fresh matched results.

Run setup, the PMU diagnostic, and each benchmark wrapper in the target VM as described in README.md. Review raw errors, event running percentages, sample/stack diagnostics and timing distributions before making architectural claims. Fill in ENVIRONMENT.md with the actual host and QEMU configuration.

The optimized sources initially equal baseline. This package improves measurement; it does not contain or claim a benchmark optimization.
