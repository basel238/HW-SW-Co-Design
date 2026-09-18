# Start here — v4.2

Already using v4/v4.1? Follow **UPDATING.md** for the local update, GitHub push and VM pull. Keep the same release Python version for comparable measurements. Install at the repository root.

On the VM, from the repository:

```bash
bash scripts/00_setup.sh
bash scripts/13_course_stages.sh
```

This collects both benchmarks into **one** `results/run-.../` folder. Open its **README.md** first, then `nbody/README.md` and `raytrace/README.md`. They contain compact timing/counter summaries and links to `perf.svg`, supplementary `python.svg` and separate debug `guide-perf.svg`, when available. Complete raw evidence is in **evidence.zip**, with checked hashes. Old runs are untouched.

The default requires genuine pyperformance execution and perf graphs. It attempts the guide's separate debug reference. To intentionally postpone that reference, pass `--release-only`; the summary will not claim literal guide completeness. Missing perf evidence produces exit 3 and a clear report. Unsupported optional counters never manufacture IPC or replace the required graph.

Read **STAGES_1_3.md** for the requirement matrix, output meanings and interpretation tasks. Review `docs/stage1-nbody.md` and `docs/stage1-raytrace.md`, fill `ENVIRONMENT.md`, and write your report from fresh measurements.

For one benchmark only, run `bash script_nbody.sh` or `bash script_raytrace.sh`. For a short ACK check: `bash scripts/15_perf_gate_probe.sh`. For expanded raw output, append `--keep-details` to the course command. Lower-level diagnostic scripts still expose detailed stage output for troubleshooting.

No optimization is applied. Later, edit only `src/optimized/`, then run `bash scripts/04_optimize_compare.sh nbody` or `raytrace` for correctness and fresh paired timing. Unchanged candidate sources do not count as an optimization.
