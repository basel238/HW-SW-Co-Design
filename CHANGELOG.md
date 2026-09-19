# Direct shell benchmark commands

- Added independent shell timing and native-profile scripts, also selected by `--direct` on scripts 01 and 03. They execute the unchanged benchmark entry points and never load the custom Python toolkit.
- Native profiling uses pyperf 2.10.0's built-in perf hook with initially disabled events, one worker, no warmup and fixed benchmark calls. Retains raw samples, native Self and a flame graph, with explicit hook/boundary scope.
- Direct counters require `--whole-process`; startup/import/harness counts are never described as benchmark-only. Existing gated workflow, compact output, ACK fix, sources and results are unchanged.

# Debug-only measurement update

- All framework runs, timing, perf profiling, counters, Python profiling and optimization comparisons use debug CPython (`Py_DEBUG=1`) without `-O`/`-OO`.
- Setup defaults to `python3-dbg`, validates the environment before installing dependencies and preserves existing release environments for an explicit move aside. Cached pyperformance workers are checked before measurement; comparisons reject release evidence.
- Removed the duplicate guide-debug stage, guide worker, `guide-perf.svg`, `--guide` and `--release-only`. The main debug run covers the guide interpreter requirement.
- Kept compact summaries, verified evidence archives and the Linux 5.15 newline/NUL ACK fix. Existing results, configuration and benchmark edits are preserved; new comparisons require fresh debug measurements.

# v4.2 — reliable course collection and compact results (historical)

- Fixed newline/NUL perf ACK framing; retained strict timeouts, token checks, complete source-matched workloads and enable/disable acknowledgement requirements. Added a short gated preflight.
- Genuine pinned pyperformance references with validated worker identity and frozen sources. Guide python3-dbg reference runs remain separate from release measurements.
- Required perf-derived graphs. Supplementary Python sampling selects measured-wrapper stacks, retains unfiltered evidence and narrowly handles the validated child-exit warning.
- One run folder, readable summaries, simple graph names and verified evidence.zip. Expanded details are removed only after hash verification; old results are untouched.
- Source-study notes, compliance matrix, safe hash-checked updater and complete evidence export. No automatic claim that the student's interpretation is finished.
- Baseline/candidate functions remain unchanged. No optimization is implemented.

# v4.1 — confirmed orphan FlameGraph migration

Handles the supplied root FlameGraph gitlink without .gitmodules at the exact bundled commit. Records the original pointer, preserves local contents and uses regular vendor files. Other submodules remain refused. Measurement scripts are unchanged.

# v4 — repository-root installation and Git migration

Measurement behavior is unchanged from v3. Added a dry-run/apply migration helper, timestamped archives, root-layout instructions, results/ and hw/ documentation. Migration creates a branch and local commit without pushing or rewriting history.

# v3 — integrated measurement improvements

This is a complete standalone replacement package, not a patch set. It preserves the v2 benchmark sources, correctness policy, separate timing/profiling boundaries, source snapshots, per-run directories and uncertainty-aware comparison.

## Integrated from the alternative scripts/review

- **Statistical Python flame graphs:** py-spy 0.4.2, pinned installation, raw folded samples and SVG from one recording, sample-count warning, independent operation when perf fails. Whole-driver sampling scope is explicit; imports/warmup are included.
- **Readable measurement output:** per-repeat event counts/units, running percentages, per-call normalized counts, valid ratios, unavailability reasons, and descriptive ratio medians/ranges in stat-summary.md.
- **MPKI:** three additional two-event passes for branch, generic-cache and L1-load misses with simultaneous user-mode instruction denominators. Configurable without altering the existing miss fractions.
- **Capability summaries:** automatic nonmutating known-work probes in the initial workflow, human/machine-readable classifications, retained commands and raw data. Optional reference-cycle throughput has its own name and never replaces IPC/CPI.
- **Complete optimization diff:** source.diff and source-changes.json from measured snapshots, including helper files and binary changes, plus an explicit paired-round manifest.
- **Balanced comparison configuration:** even rounds, at least two. The default remains two. This reduces order bias; it does not eliminate host/VM interference.
- **Opt-in combined Python/native profiles:** explicit map/JIT modes with Python/build/perf compatibility checks, observed-frame checks and retained stack-quality diagnostics. JIT injection artifacts are contained in their run directory.
- **Failure cleanup:** failed command process groups are terminated so a failed sampler cannot leave a workload running in the background.
- **Reproducible guard tests:** zero/unsupported counters, MPKI, missing cycles, reference-cycle separation, multiplexing, capability classification, JIT version interpretation, balanced rounds and full-tree diffs.

## Deliberately excluded

- Ref-cycles relabeled as ordinary IPC/CPI.
- Automatic system-wide top-down or automatic changes to watchdog/ptrace/perf policy.
- Acceptance based only on a candidate successfully exiting, or a statistically significant timing difference without correctness/provenance.
- Mutable installed baseline source and overwritten result directories.
- Automatic Python upgrades, unpinned profiler downloads during measurement, and unsupported claims that low MPKI proves compute-bound behavior.

The original alternate package's `_tools.py` was not supplied. This version implements its needed functionality with the included reviewed Python helpers; it has no dependency on that missing file.
