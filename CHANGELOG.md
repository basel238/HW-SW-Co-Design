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
