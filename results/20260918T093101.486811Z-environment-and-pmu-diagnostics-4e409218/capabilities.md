# Environment / PMU capability probes

Probes include startup and test sanity, not PMU fidelity or benchmark bottlenecks. Build flags do not prove valid stacks.

| Probe | Event selection | Result |
|---|---|---|
| cycles-alone | cycles:u | count_and_scheduling_sanity_passed |
| instructions-alone | instructions:u | count_and_scheduling_sanity_passed |
| pair | {cycles:u,instructions:u} | count_and_scheduling_sanity_passed |
| software | task-clock | count_and_scheduling_sanity_passed |

Each probe retains CSV, stdout/stderr, command and exit status. Reference cycles, when explicitly requested, are a separate diagnostic and never replace IPC.
