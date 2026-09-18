# nbody — baseline evidence

Read this file, then open the graphs. All raw data and full reports are in `../evidence.zip`.

## Timing

Unprofiled debug runtime: **477.874 ms per call**; SD 1.521 ms across 60 recorded values.

pyperf stability check:

```text
Benchmark was run more times than necessary to get a stable result.
Consider passing processes=2 to the Runner constructor to save time.
The benchmark seems to be stable
```

This SD describes spread, not a confidence interval. Values within a worker are correlated. Use `timing.json` for analysis; do not use profiled runtime or whole-command elapsed time.

## Required perf profile

[Open perf.svg](perf.svg). Built from perf record → perf script → FlameGraph. Widths are sampled cpu-clock event-period weights in nanoseconds, not call counts. Horizontal position is not a timeline; tall stacks are call depth.

Stack health: **review_required**. No configured red flag fired; inspect native call paths and symbols manually before drawing conclusions.

Check ancestry, unknown frames, truncation and sample loss before interpreting callers. A large CPython evaluator share is expected for interpreted code and does not identify a specific Python line.

Native Self table (first 35 lines; full table archived):

```text
# To display the perf.data header info, please use --header/--header-only options.
#
#
# Total Lost Samples: 0
#
# Samples: 9K of event 'cpu-clock:u'
# Event count (approx.): 19262524896
#
# Overhead  Command  Shared Object     Symbol                               IPC   [IPC Coverage]
# ........  .......  ................  ...................................  ....................
#
    46.31%  python   python3.10d       [.] _PyEval_EvalFrameDefault         -      -            
     5.66%  python   python3.10d       [.] binary_op1                       -      -            
     4.05%  python   python3.10d       [.] float_mul.lto_priv.0             -      -            
     3.85%  python   python3.10d       [.] PyFloat_FromDouble               -      -            
     3.28%  python   python3.10d       [.] float_dealloc.lto_priv.0         -      -            
     2.88%  python   python3.10d       [.] list_ass_item.lto_priv.0         -      -            
     2.34%  python   python3.10d       [.] PyNumber_AsSsize_t               -      -            
     2.29%  python   python3.10d       [.] float_add.lto_priv.0             -      -            
     2.10%  python   python3.10d       [.] _Py_CheckSlotResult              -      -            
     1.88%  python   libm.so.6         [.] __ieee754_pow_fma                -      -            
     1.78%  python   python3.10d       [.] float_sub.lto_priv.0             -      -            
     1.76%  python   python3.10d       [.] list_ass_subscript.lto_priv.0    -      -            
     1.63%  python   python3.10d       [.] binary_iop1                      -      -            
     1.53%  python   python3.10d       [.] _Py_Dealloc                      -      -            
     1.52%  python   python3.10d       [.] _PyNumber_Index                  -      -            
     1.50%  python   python3.10d       [.] PyObject_GetItem                 -      -            
     1.49%  python   python3.10d       [.] PyObject_SetItem                 -      -            
     1.37%  python   python3.10d       [.] _Py_NewReference                 -      -            
     1.37%  python   python3.10d       [.] get_float_state                  -      -            
     1.33%  python   python3.10d       [.] list_subscript.lto_priv.0        -      -            
     1.29%  python   python3.10d       [.] list_item.lto_priv.0             -      -            
     1.14%  python   python3.10d       [.] PyLong_AsSsize_t                 -      -            
     1.02%  python   python3.10d       [.] PyNumber_Multiply                -      -            
     0.94%  python   python3.10d       [.] listiter_next.lto_priv.0         -      -            
```

## Supplementary Python view

Python sampling: Explicitly disabled supplementary sampling.

cProfile: top 12 by self time, then cumulative time. Instrumentation changes costs; use this to locate Python operations, not to estimate unprofiled speedup.

```text
Fri Sep 18 17:36:21 2026    /root/HW-SW-Co-Design/results/run-2026-09-18_172405-9070/details/nbody-baseline-python/python.pstats

         362 function calls in 20.128 seconds

   Ordered by: internal time

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
       40   20.126    0.503   20.126    0.503 run_benchmark.py:78(advance)
       80    0.001    0.000    0.001    0.000 run_benchmark.py:100(report_energy)
       40    0.000    0.000   20.127    0.503 run_benchmark.py:123(bench_nbody)
        1    0.000    0.000   20.128   20.128 workload.py:204(run_measured_calls)
       40    0.000    0.000    0.000    0.000 run_benchmark.py:112(offset_momentum)
       40    0.000    0.000   20.127    0.503 workload.py:98(<lambda>)
       80    0.000    0.000    0.000    0.000 {built-in method time.perf_counter}
       40    0.000    0.000    0.000    0.000 {method 'append' of 'list' objects}
        1    0.000    0.000    0.000    0.000 {method 'disable' of '_lsprof.Profiler' objects}


Fri Sep 18 17:36:21 2026    /root/HW-SW-Co-Design/results/run-2026-09-18_172405-9070/details/nbody-baseline-python/python.pstats

         362 function calls in 20.128 seconds

   Ordered by: cumulative time

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000   20.128   20.128 workload.py:204(run_measured_calls)
       40    0.000    0.000   20.127    0.503 workload.py:98(<lambda>)
       40    0.000    0.000   20.127    0.503 run_benchmark.py:123(bench_nbody)
       40   20.126    0.503   20.126    0.503 run_benchmark.py:78(advance)
       80    0.001    0.000    0.001    0.000 run_benchmark.py:100(report_energy)
       40    0.000    0.000    0.000    0.000 run_benchmark.py:112(offset_momentum)
       80    0.000    0.000    0.000    0.000 {built-in method time.perf_counter}
       40    0.000    0.000    0.000    0.000 {method 'append' of 'list' objects}
        1    0.000    0.000    0.000    0.000 {method 'disable' of '_lsprof.Profiler' objects}
```

## Counters

| Metric | Median | Min–max | Usable / attempted |
|---|---:|---:|---:|
| ipc | 2.5509 | 2.5152–2.551 | 3/3 |
| cpi | 0.39203 | 0.39201–0.39759 | 3/3 |
| branch_miss_percent | 0.47751 | 0.47203–0.47771 | 3/3 |
| generic_cache_miss_percent | 0.016679 | 0.013464–0.018208 | 3/3 |
| l1_miss_percent | 0.028887 | 0.024552–0.029349 | 3/3 |
| branch_mpki | 1.0915 | 1.0867–1.0942 | 3/3 |
| generic_cache_mpki | 9.9968e-07 | 9.3901e-07–1.1631e-06 | 3/3 |
| l1_load_mpki | 0.089084 | 0.088739–0.0974 | 3/3 |

| Event | Median per benchmark call | Unit | Usable / attempted |
|---|---:|---|---:|
| L1-dcache-load-misses | 2.5725e+05 | count | 3/3 |
| L1-dcache-loads | 8.9016e+08 | count | 3/3 |
| branch-misses:u | 3.1555e+06 | count | 3/3 |
| branches:u | 6.6081e+08 | count | 3/3 |
| cache-misses:u | 3.025 | count | 3/3 |
| cache-references:u | 19085 | count | 3/3 |
| context-switches | 13.3 | count | 3/3 |
| cpu-migrations | 0 | count | 3/3 |
| cycles:u | 1.1376e+09 | count | 3/3 |
| instructions:u | 2.9019e+09 | count | 3/3 |
| major-faults | 0 | count | 3/3 |
| minor-faults | 0.025 | count | 3/3 |
| task-clock | 476.59 | msec | 3/3 |

Descriptive medians/ranges, not confidence intervals. Each ratio uses simultaneous events from its own pass. Per-call means one configured simulation or one rendered frame. A zero cycles counter makes IPC/CPI unavailable. Generic cache misses do not establish DRAM traffic or a memory bottleneck. Full repeat validity and running fractions are archived.

## Interpretation to finish

- Review the source explanation in `docs/stage1-nbody.md` (also archived).
- Identify hot functions from this run and explain their algorithms/data structures.
- Separate observed cost from a proposed cause; no FPU-bound or memory-bound claim follows from a function name alone.
- Use fresh unprofiled debug timings for both variants in any later optimization comparison. This run implements no optimization.
