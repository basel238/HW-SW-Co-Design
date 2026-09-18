# Collect the first three stages

Install this package at the repository root. Existing v4/v4.1 users should follow **UPDATING.md** instead of running the old migration again.

On the Ubuntu VM, from your repository:

```bash
bash scripts/00_setup.sh
bash scripts/13_course_stages.sh
```

Setup uses the existing release `.venv` for all main measurements. It installs pinned pyperformance 1.14.0, pyperf 2.10.0 and, by default, supplementary py-spy 0.4.2. If `python3-dbg` is installed, it prepares `.venv-guide` separately. System packages are not installed automatically. On the course Ubuntu image, the relevant packages normally include `python3-venv`, `python3-dbg`, `perl`, `linux-tools-common` and the linux-tools package matching `uname -r`. Check availability for your guest kernel; do not change VM permissions just to hide an error.

The main command collects **both** benchmarks in one run. The root wrappers `bash script_nbody.sh` and `bash script_raytrace.sh` collect one benchmark each, using the same workflow. `bash scripts/run_all.sh` also runs the compact course workflow.

## What to read

The command prints one path: `results/run-YYYY-MM-DD_HHMMSS-abcd/README.md`.

| Output | Read it for |
|---|---|
| README.md | Overall completeness, failures and next actions |
| nbody/README.md and raytrace/README.md | Runtime, native Self table, Python hotspots, compact counter table, interpretation tasks |
| Each benchmark's perf.svg | Required graph generated from **perf**, with cpu-clock period weights |
| Each benchmark's python.svg, if available | Supplementary Python samples from the measured-call wrapper |
| Each benchmark's guide-perf.svg, if available | Separately labelled debug-interpreter perf reference |
| Each benchmark's timing.json | Clean release timing data for later analysis |
| framework.json, if available | Actual release `python -m pyperformance run` result |
| summary.json | Status of all stages, with relative paths into the evidence |
| evidence.zip | Raw recordings, full reports, exact commands, receipts, configuration, frozen source, toolkit and checksums |

Normally that is **14 visible files across one run directory and two benchmark directories**, when all graphs are available. Failed artifacts are omitted rather than replaced with placeholders. Intermediate stages no longer create sibling timestamped result directories in this workflow. Console output gives one short status per stage.

The detailed evidence is compressed only after capture ends. Each archived file is checked against its SHA-256 before the expanded `details/` directory is removed. Existing runs are untouched. If compaction fails, expanded evidence remains. Use `--keep-details` to retain the expanded form too. To reprocess a normal run, unzip its `evidence.zip` into that same run directory. Original absolute paths are retained in historical provenance; `summary.json` uses relative paths for navigation after extraction.

Raw evidence is excluded from ordinary Git commits. **Keep/copy evidence.zip separately**; a Git-only checkout does not contain it. To share an entire run with its readable view, use `scripts/14_export_results.sh` as described in UPDATING.md.

## Requirement check against Project(2).pdf

| Requirement | What this revision supplies | What still needs your work |
|---|---|---|
| §1, p3: purpose, libraries, algorithms and data structures | Source-specific notes in `docs/stage1-nbody.md` and `docs/stage1-raytrace.md`; unchanged source and hashes | Read the source, review the notes and explain them in your report/demo |
| §2, p3: run/capture/interpret pyperformance | Genuine pinned framework execution using a custom manifest of the frozen sources; separate controlled release timing | Discuss timing distributions, stability, workload and VM conditions |
| §3, p3; overview p2: flame graphs for both benchmarks using perf | Required `perf record → perf script → stackcollapse-perf.pl → flamegraph.pl`; native Self table, full graph and stack-health diagnostics | Inspect valid ancestry, lost samples and unknown frames; explain observed hotspots |
| Guide p1: python3-dbg | Separate debug pyperformance reference and perf graphs, never mixed into release results | Ensure the debug interpreter exists and its capture completes |
| Reproducibility/report/AI history | Source/configuration/tool snapshots, root benchmark wrappers and revision prompt notes | Fill ENVIRONMENT.md, finish written reports and append your complete AI interaction history |

The guide's command is adapted to keep dependency installation, imports and warmup outside the perf-enabled region. The same frozen pyperformance benchmark functions run under the named interpreter. This is not a byte-for-byte replay of its illustrative 999 Hz whole-harness command; the default uses 499 Hz, software CPU-time events and DWARF unwinding. These choices and the separate debug reference are explicit in the evidence.

The scripts **cannot certify coursework completion** merely because an SVG exists. `automated_collection_complete` means the required artifacts were collected in the selected mode; `coursework_complete` stays false pending your interpretation. A stack-health warning remains a warning requiring review. For a single-benchmark run, completeness applies only to the selected benchmark.

IPC, CPI, cache/branch metrics and top-down support the analysis; they are not individually enumerated requirements of the first three stages. A failed optional PMU group is recorded without replacing a required perf graph. No optimization, 7% improvement or hardware implementation is claimed here; those belong to later stages.

## Useful options

```bash
# Main workflow, expanded evidence retained for debugging:
bash scripts/13_course_stages.sh --keep-details

# Explicitly postpone the guide's debug-interpreter reference:
bash scripts/13_course_stages.sh --release-only

# Shorter collection while retaining required timing/framework/native stages:
bash scripts/13_course_stages.sh --skip-optional-counters --skip-python-sampling

# Short FIFO-control test before spending time on a full run:
bash scripts/15_perf_gate_probe.sh
```

Exit 0 means required collection completed in the selected mode. Exit 3 means required evidence is incomplete; open the run README. Exit 2 indicates a configuration/setup error. `--release-only` explicitly defers the guide interpreter and sets literal-guide collection incomplete. Supplementary failures remain visible in the summary even if required collection succeeds.

## ACK repair and interpreting profiles

The perf 5.15 reply can be `ack` + newline + NUL. The parser now accepts that boundary padding across consecutive replies, including fragmented reads, while rejecting corrupt tokens, missing replies and oversized input. It still requires acknowledged enable **and** disable plus a completed, source-matched workload. A short gated stat/record test runs before long perf work. This fixes the observed `b'\x00ack'` failure; it does not repair an unavailable hardware counter or missing permissions.

The native profile uses DWARF, without assuming that a debug Python build preserves frame pointers. A large `_PyEval_EvalFrameDefault` share on Python 3.10 is normal C-level attribution; a thin, implausibly tall stack with unknown ancestors needs unwind review. py-spy and cProfile provide separate source-level context. Their percentages are not interchangeable with native perf percentages or unprofiled timings.

The known py-spy child-reaping error is accepted only when raw sample totals, zero sampler errors, measured-stack markers and a complete source-matched workload all validate. Other failures remain failures. The normal Python graph selects measured-wrapper stacks; the unfiltered capture remains archived. No missing IPC is synthesized from nominal frequency or reference cycles.

Primary references: [perf record](https://man7.org/linux/man-pages/man1/perf-record.1.html), [Python perf support](https://docs.python.org/3.12/howto/perf_profiling.html), [pyperformance custom benchmarks](https://pyperformance.readthedocs.io/custom_benchmarks.html), and the [Linux 5.15 ACK writer](https://github.com/torvalds/linux/blob/v5.15/tools/perf/util/evlist.c).
