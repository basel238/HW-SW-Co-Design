# Start here — stages 1–3

**Required collection: complete.** Written interpretation and human stack review remain required.

Guide collection: **complete**. All measurements use debug Python (Py_DEBUG=1).

| Open | Purpose |
|---|---|
| [nbody/README.md](nbody/README.md) | Timing, top functions, counter validity, graphs and interpretation tasks |
| [raytrace/README.md](raytrace/README.md) | Timing, top functions, counter validity, graphs and interpretation tasks |
| [summary.json](summary.json) | Machine-readable status of every attempted stage |
| framework.json, if present | Genuine debug pyperformance reference |
| evidence.zip | Full recordings, logs, commands, source snapshots and toolkit, with checksums |

Only files from this new run are compacted. Previous results are untouched. To inspect raw evidence, extract evidence.zip into this run directory; it restores `details/`. Original absolute paths remain in provenance to document the measurement machine.

## Missing evidence and next actions

No required collection failures in the selected mode.

If perf failed: check the archived gate-probe logs first. Missing perf or permission errors require fixing the VM setup; do not change interpreter or silently substitute a py-spy graph. Zero hardware cycles may be a virtual-PMU limitation; the software-clock perf graph can still work.

## Supplementary limitations

None reported.

## Work needed for submission

- Review both stage-1 explanations and cite the selected frozen sources.
- Record the actual VM/host settings in ENVIRONMENT.md.
- Inspect native graphs, self tables, sample loss and stack-health warnings.
- Write benchmark-specific bottleneck conclusions using the new evidence; distinguish hypotheses from measured causes.

No benchmark optimization is applied. No previous results are merged into this run.
