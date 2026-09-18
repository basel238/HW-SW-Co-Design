# Hardware-counter summary

Each group/repeat measures the same configured useful work after warmup. Ratios use only simultaneous events within that run. Counts include small driver/boundary costs.

A passed scheduling/count sanity check does not validate virtual-PMU semantics. Generic-cache MPKI is not DRAM MPKI. Missing IPC stays unavailable.

| Group / repeat | Event | Count | Unit | Running % | Per call | Status |
|---|---|---:|---|---:|---:|---|
| software / 1 | task-clock | 7959.72 | msec | 100 | unavailable | collection_failed |
| software / 1 | context-switches | 292 | count | 100 | unavailable | collection_failed |
| software / 1 | cpu-migrations | 0 | count | 100 | unavailable | collection_failed |
| software / 1 | minor-faults | 0 | count | 100 | unavailable | collection_failed |
| software / 1 | major-faults | 0 | count | 100 | unavailable | collection_failed |
| software / 2 | task-clock | 7870.54 | msec | 100 | unavailable | collection_failed |
| software / 2 | context-switches | 255 | count | 100 | unavailable | collection_failed |
| software / 2 | cpu-migrations | 0 | count | 100 | unavailable | collection_failed |
| software / 2 | minor-faults | 0 | count | 100 | unavailable | collection_failed |
| software / 2 | major-faults | 0 | count | 100 | unavailable | collection_failed |
| software / 3 | task-clock | 7937.34 | msec | 100 | unavailable | collection_failed |
| software / 3 | context-switches | 225 | count | 100 | unavailable | collection_failed |
| software / 3 | cpu-migrations | 0 | count | 100 | unavailable | collection_failed |
| software / 3 | minor-faults | 0 | count | 100 | unavailable | collection_failed |
| software / 3 | major-faults | 0 | count | 100 | unavailable | collection_failed |
| ipc / 1 | cycles:u | 1.89893e+10 | count | 100 | unavailable | collection_failed |
| ipc / 1 | instructions:u | 5.07593e+10 | count | 100 | unavailable | collection_failed |
| ipc / 2 | cycles:u | 1.91007e+10 | count | 100 | unavailable | collection_failed |
| ipc / 2 | instructions:u | 5.06532e+10 | count | 100 | unavailable | collection_failed |
| ipc / 3 | cycles:u | 1.87983e+10 | count | 100 | unavailable | collection_failed |
| ipc / 3 | instructions:u | 5.05627e+10 | count | 100 | unavailable | collection_failed |
| branches / 1 | branches:u | 9.74151e+09 | count | 100 | unavailable | collection_failed |
| branches / 1 | branch-misses:u | 2.69172e+07 | count | 100 | unavailable | collection_failed |
| branches / 2 | branches:u | 9.6797e+09 | count | 100 | unavailable | collection_failed |
| branches / 2 | branch-misses:u | 2.71861e+07 | count | 100 | unavailable | collection_failed |
| branches / 3 | branches:u | 9.69196e+09 | count | 100 | unavailable | collection_failed |
| branches / 3 | branch-misses:u | 2.63876e+07 | count | 100 | unavailable | collection_failed |
| cache / 1 | cache-references:u | 3.47487e+07 | count | 100 | unavailable | collection_failed |
| cache / 1 | cache-misses:u | 13702 | count | 100 | unavailable | collection_failed |
| cache / 2 | cache-references:u | 3.15254e+07 | count | 100 | unavailable | collection_failed |
| cache / 2 | cache-misses:u | 13527 | count | 100 | unavailable | collection_failed |
| cache / 3 | cache-references:u | 2.80819e+07 | count | 100 | unavailable | collection_failed |
| cache / 3 | cache-misses:u | 12725 | count | 100 | unavailable | collection_failed |
| l1 / 1 | L1-dcache-loads | 1.62813e+10 | count | 100 | unavailable | collection_failed |
| l1 / 1 | L1-dcache-load-misses | 4.71358e+08 | count | 100 | unavailable | collection_failed |
| l1 / 2 | L1-dcache-loads | 1.63599e+10 | count | 100 | unavailable | collection_failed |
| l1 / 2 | L1-dcache-load-misses | 4.41596e+08 | count | 100 | unavailable | collection_failed |
| l1 / 3 | L1-dcache-loads | 1.64217e+10 | count | 100 | unavailable | collection_failed |
| l1 / 3 | L1-dcache-load-misses | 4.68933e+08 | count | 100 | unavailable | collection_failed |
| branch-mpki / 1 | instructions:u | 5.06569e+10 | count | 100 | unavailable | collection_failed |
| branch-mpki / 1 | branch-misses:u | 2.57276e+07 | count | 100 | unavailable | collection_failed |
| branch-mpki / 2 | instructions:u | 5.08629e+10 | count | 100 | unavailable | collection_failed |
| branch-mpki / 2 | branch-misses:u | 2.54819e+07 | count | 100 | unavailable | collection_failed |
| branch-mpki / 3 | instructions:u | 5.06874e+10 | count | 100 | unavailable | collection_failed |
| branch-mpki / 3 | branch-misses:u | 2.60948e+07 | count | 100 | unavailable | collection_failed |
| cache-mpki / 1 | instructions:u | 5.1262e+10 | count | 100 | unavailable | collection_failed |
| cache-mpki / 1 | cache-misses:u | 13030 | count | 100 | unavailable | collection_failed |
| cache-mpki / 2 | instructions:u | 5.06462e+10 | count | 100 | unavailable | collection_failed |
| cache-mpki / 2 | cache-misses:u | 12949 | count | 100 | unavailable | collection_failed |
| cache-mpki / 3 | instructions:u | 5.04523e+10 | count | 100 | unavailable | collection_failed |
| cache-mpki / 3 | cache-misses:u | 12694 | count | 100 | unavailable | collection_failed |
| l1-mpki / 1 | instructions:u | 5.0746e+10 | count | 100 | unavailable | collection_failed |
| l1-mpki / 1 | L1-dcache-load-misses | 4.93947e+08 | count | 100 | unavailable | collection_failed |
| l1-mpki / 2 | instructions:u | 5.07933e+10 | count | 100 | unavailable | collection_failed |
| l1-mpki / 2 | L1-dcache-load-misses | 4.97665e+08 | count | 100 | unavailable | collection_failed |
| l1-mpki / 3 | instructions:u | 5.0591e+10 | count | 100 | unavailable | collection_failed |
| l1-mpki / 3 | L1-dcache-load-misses | 4.9442e+08 | count | 100 | unavailable | collection_failed |

## Ratios by repetition

| Group / repeat | Metric | Value | Unavailability reason |
|---|---|---:|---|
| ipc / 1 | ipc | unavailable | collection failed |
| ipc / 1 | cpi | unavailable | collection failed |
| ipc / 2 | ipc | unavailable | collection failed |
| ipc / 2 | cpi | unavailable | collection failed |
| ipc / 3 | ipc | unavailable | collection failed |
| ipc / 3 | cpi | unavailable | collection failed |
| branches / 1 | branch_miss_percent | unavailable | collection failed |
| branches / 2 | branch_miss_percent | unavailable | collection failed |
| branches / 3 | branch_miss_percent | unavailable | collection failed |
| cache / 1 | generic_cache_miss_percent | unavailable | collection failed |
| cache / 2 | generic_cache_miss_percent | unavailable | collection failed |
| cache / 3 | generic_cache_miss_percent | unavailable | collection failed |
| l1 / 1 | l1_miss_percent | unavailable | collection failed |
| l1 / 2 | l1_miss_percent | unavailable | collection failed |
| l1 / 3 | l1_miss_percent | unavailable | collection failed |
| branch-mpki / 1 | branch_mpki | unavailable | collection failed |
| branch-mpki / 2 | branch_mpki | unavailable | collection failed |
| branch-mpki / 3 | branch_mpki | unavailable | collection failed |
| cache-mpki / 1 | generic_cache_mpki | unavailable | collection failed |
| cache-mpki / 2 | generic_cache_mpki | unavailable | collection failed |
| cache-mpki / 3 | generic_cache_mpki | unavailable | collection failed |
| l1-mpki / 1 | l1_load_mpki | unavailable | collection failed |
| l1-mpki / 2 | l1_load_mpki | unavailable | collection failed |
| l1-mpki / 3 | l1_load_mpki | unavailable | collection failed |

## Descriptive spread of usable ratios

These medians/ranges are not confidence intervals or ratios of counts pooled across passes.

| Metric | Usable repetitions | Median | Min | Max |
|---|---:|---:|---:|---:|

IPC: instructions/core cycles; CPI: core cycles/instruction. MPKI: misses per 1,000 instructions. No reference-cycle substitution is used. Percent metrics use the matching reference event.

The matching raw CSV, collection status, workload receipt and logs are in each group/repeat directory.
