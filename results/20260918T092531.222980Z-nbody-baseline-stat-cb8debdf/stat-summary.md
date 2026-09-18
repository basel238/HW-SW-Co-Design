# Hardware-counter summary

Each group/repeat measures the same configured useful work after warmup. Ratios use only simultaneous events within that run. Counts include small driver/boundary costs.

A passed scheduling/count sanity check does not validate virtual-PMU semantics. Generic-cache MPKI is not DRAM MPKI. Missing IPC stays unavailable.

| Group / repeat | Event | Count | Unit | Running % | Per call | Status |
|---|---|---:|---|---:|---:|---|
| software / 1 | task-clock | 9213.73 | msec | 100 | unavailable | collection_failed |
| software / 1 | context-switches | 310 | count | 100 | unavailable | collection_failed |
| software / 1 | cpu-migrations | 0 | count | 100 | unavailable | collection_failed |
| software / 1 | minor-faults | 1 | count | 100 | unavailable | collection_failed |
| software / 1 | major-faults | 0 | count | 100 | unavailable | collection_failed |
| software / 2 | task-clock | 9169.92 | msec | 100 | unavailable | collection_failed |
| software / 2 | context-switches | 249 | count | 100 | unavailable | collection_failed |
| software / 2 | cpu-migrations | 0 | count | 100 | unavailable | collection_failed |
| software / 2 | minor-faults | 1 | count | 100 | unavailable | collection_failed |
| software / 2 | major-faults | 0 | count | 100 | unavailable | collection_failed |
| software / 3 | task-clock | 9473.29 | msec | 100 | unavailable | collection_failed |
| software / 3 | context-switches | 259 | count | 100 | unavailable | collection_failed |
| software / 3 | cpu-migrations | 0 | count | 100 | unavailable | collection_failed |
| software / 3 | minor-faults | 1 | count | 100 | unavailable | collection_failed |
| software / 3 | major-faults | 0 | count | 100 | unavailable | collection_failed |
| ipc / 1 | cycles:u | 2.19387e+10 | count | 100 | unavailable | collection_failed |
| ipc / 1 | instructions:u | 6.75594e+10 | count | 100 | unavailable | collection_failed |
| ipc / 2 | cycles:u | 2.21079e+10 | count | 100 | unavailable | collection_failed |
| ipc / 2 | instructions:u | 6.75608e+10 | count | 100 | unavailable | collection_failed |
| ipc / 3 | cycles:u | 2.19097e+10 | count | 100 | unavailable | collection_failed |
| ipc / 3 | instructions:u | 6.7553e+10 | count | 100 | unavailable | collection_failed |
| branches / 1 | branches:u | 1.15511e+10 | count | 100 | unavailable | collection_failed |
| branches / 1 | branch-misses:u | 2.99971e+07 | count | 100 | unavailable | collection_failed |
| branches / 2 | branches:u | 1.15511e+10 | count | 100 | unavailable | collection_failed |
| branches / 2 | branch-misses:u | 3.0329e+07 | count | 100 | unavailable | collection_failed |
| branches / 3 | branches:u | 1.1547e+10 | count | 100 | unavailable | collection_failed |
| branches / 3 | branch-misses:u | 3.1093e+07 | count | 100 | unavailable | collection_failed |
| cache / 1 | cache-references:u | 396243 | count | 100 | unavailable | collection_failed |
| cache / 1 | cache-misses:u | 3099 | count | 100 | unavailable | collection_failed |
| cache / 2 | cache-references:u | 341083 | count | 100 | unavailable | collection_failed |
| cache / 2 | cache-misses:u | 2985 | count | 100 | unavailable | collection_failed |
| cache / 3 | cache-references:u | 354730 | count | 100 | unavailable | collection_failed |
| cache / 3 | cache-misses:u | 2668 | count | 100 | unavailable | collection_failed |
| l1 / 1 | L1-dcache-loads | 2.13398e+10 | count | 100 | unavailable | collection_failed |
| l1 / 1 | L1-dcache-load-misses | 6.00903e+06 | count | 100 | unavailable | collection_failed |
| l1 / 2 | L1-dcache-loads | 2.13398e+10 | count | 100 | unavailable | collection_failed |
| l1 / 2 | L1-dcache-load-misses | 5.40223e+06 | count | 100 | unavailable | collection_failed |
| l1 / 3 | L1-dcache-loads | 2.13398e+10 | count | 100 | unavailable | collection_failed |
| l1 / 3 | L1-dcache-load-misses | 6.41869e+06 | count | 100 | unavailable | collection_failed |
| branch-mpki / 1 | instructions:u | 6.75594e+10 | count | 100 | unavailable | collection_failed |
| branch-mpki / 1 | branch-misses:u | 2.93744e+07 | count | 100 | unavailable | collection_failed |
| branch-mpki / 2 | instructions:u | 6.75626e+10 | count | 100 | unavailable | collection_failed |
| branch-mpki / 2 | branch-misses:u | 4.71516e+07 | count | 100 | unavailable | collection_failed |
| branch-mpki / 3 | instructions:u | 6.75594e+10 | count | 100 | unavailable | collection_failed |
| branch-mpki / 3 | branch-misses:u | 3.12473e+07 | count | 100 | unavailable | collection_failed |
| cache-mpki / 1 | instructions:u | 6.75608e+10 | count | 100 | unavailable | collection_failed |
| cache-mpki / 1 | cache-misses:u | 3022 | count | 100 | unavailable | collection_failed |
| cache-mpki / 2 | instructions:u | 6.75612e+10 | count | 100 | unavailable | collection_failed |
| cache-mpki / 2 | cache-misses:u | 3556 | count | 100 | unavailable | collection_failed |
| cache-mpki / 3 | instructions:u | 6.7553e+10 | count | 100 | unavailable | collection_failed |
| cache-mpki / 3 | cache-misses:u | 2877 | count | 100 | unavailable | collection_failed |
| l1-mpki / 1 | instructions:u | 6.75594e+10 | count | 100 | unavailable | collection_failed |
| l1-mpki / 1 | L1-dcache-load-misses | 5.27146e+06 | count | 100 | unavailable | collection_failed |
| l1-mpki / 2 | instructions:u | 6.75626e+10 | count | 100 | unavailable | collection_failed |
| l1-mpki / 2 | L1-dcache-load-misses | 6.35328e+06 | count | 100 | unavailable | collection_failed |
| l1-mpki / 3 | instructions:u | 6.75594e+10 | count | 100 | unavailable | collection_failed |
| l1-mpki / 3 | L1-dcache-load-misses | 5.07724e+06 | count | 100 | unavailable | collection_failed |

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
