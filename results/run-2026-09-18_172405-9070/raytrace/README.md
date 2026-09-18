# raytrace — baseline evidence

Read this file, then open the graphs. All raw data and full reports are in `../evidence.zip`.

## Timing

Unprofiled debug runtime: **2138.528 ms per call**; SD 26.059 ms across 60 recorded values.

pyperf stability check:

```text
WARNING: the benchmark result may be unstable
* Not enough samples to get a stable result (95% certainly of less than 1% variation)

Try to rerun the benchmark with more runs, values and/or loops.
Run 'python -m pyperf system tune' command to reduce the system jitter.
Use pyperf stats, pyperf dump and pyperf hist to analyze results.
Use --quiet option to hide these warnings.
```

This SD describes spread, not a confidence interval. Values within a worker are correlated. Use `timing.json` for analysis; do not use profiled runtime or whole-command elapsed time.

## Required perf profile

[Open perf.svg](perf.svg). Built from perf record → perf script → FlameGraph. Widths are sampled cpu-clock event-period weights in nanoseconds, not call counts. Horizontal position is not a timeline; tall stacks are call depth.

Stack health: **needs_review**. At least one folded stack reaches depth 127 or more, including its command frame.

Check ancestry, unknown frames, truncation and sample loss before interpreting callers. A large CPython evaluator share is expected for interpreted code and does not identify a specific Python line.

Native Self table (first 35 lines; full table archived):

```text
# To display the perf.data header info, please use --header/--header-only options.
#
#
# Total Lost Samples: 0
#
# Samples: 10K of event 'cpu-clock:u'
# Event count (approx.): 21460921672
#
# Overhead  Command  Shared Object     Symbol                                      IPC   [IPC Coverage]
# ........  .......  ................  ..........................................  ....................
#
    28.37%  python   python3.10d       [.] _PyEval_EvalFrameDefault                -      -            
     3.40%  python   python3.10d       [.] call_function.lto_priv.0                -      -            
     3.31%  python   python3.10d       [.] frame_dealloc.lto_priv.0                -      -            
     3.14%  python   python3.10d       [.] _PyEval_MakeFrameVector                 -      -            
     2.38%  python   python3.10d       [.] PyTuple_GetItem                         -      -            
     2.21%  python   python3.10d       [.] _PyDict_GetItemHint                     -      -            
     2.10%  python   python3.10d       [.] binary_op1                              -      -            
     1.99%  python   python3.10d       [.] _PyType_Lookup                          -      -            
     1.95%  python   python3.10d       [.] _PyObject_VectorcallTstate.lto_priv.10  -      -            
     1.94%  python   python3.10d       [.] lookdict_unicode_nodummy                -      -            
     1.76%  python   python3.10d       [.] _PyObject_GetMethod                     -      -            
     1.58%  python   python3.10d       [.] lookdict_split.lto_priv.0               -      -            
     1.56%  python   python3.10d       [.] _PyMem_DebugCheckAddress                -      -            
     1.20%  python   python3.10d       [.] _PyEval_Vector                          -      -            
     1.19%  python   python3.10d       [.] _PyFrame_New_NoTrack                    -      -            
     1.15%  python   python3.10d       [.] _Py_CheckFunctionResult                 -      -            
     1.13%  python   libc.so.6         [.] pthread_getspecific@@GLIBC_2.34         -      -            
     1.11%  python   python3.10d       [.] PyFloat_FromDouble                      -      -            
     1.07%  python   python3.10d       [.] insertdict                              -      -            
     0.99%  python   python3.10d       [.] float_dealloc.lto_priv.0                -      -            
     0.94%  python   python3.10d       [.] subtype_dealloc.lto_priv.0              -      -            
     0.93%  python   python3.10d       [.] _PyFunction_Vectorcall                  -      -            
     0.92%  python   python3.10d       [.] PyType_IsSubtype                        -      -            
     0.91%  python   python3.10d       [.] PyObject_SetAttr                        -      -            
```

## Supplementary Python view

Python sampling: Explicitly disabled supplementary sampling.

cProfile: top 12 by self time, then cumulative time. Instrumentation changes costs; use this to locate Python operations, not to estimate unprofiled speedup.

```text
Fri Sep 18 18:05:11 2026    /root/HW-SW-Co-Design/results/run-2026-09-18_172405-9070/details/raytrace-baseline-python/python.pstats

         30863102 function calls (30794332 primitive calls) in 33.630 seconds

   Ordered by: internal time
   List reduced from 54 to 12 due to restriction <12>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
  5098710    5.494    0.000    6.510    0.000 run_benchmark.py:51(dot)
  2778650    4.877    0.000    7.322    0.000 run_benchmark.py:113(__sub__)
  1794570    4.121    0.000   13.448    0.000 run_benchmark.py:142(intersectionTime)
  4529430    3.026    0.000    3.026    0.000 run_benchmark.py:24(__init__)
   106660    2.558    0.000   15.849    0.000 run_benchmark.py:283(_lightIsVisible)
  1497430    1.756    0.000    2.750    0.000 run_benchmark.py:48(scale)
  1098870    1.390    0.000    6.149    0.000 run_benchmark.py:61(normalized)
   152650    1.276    0.000    9.637    0.000 run_benchmark.py:271(<listcomp>)
  1098870    1.134    0.000    2.755    0.000 run_benchmark.py:35(magnitude)
  5205390    1.037    0.000    1.037    0.000 run_benchmark.py:76(mustBeVector)
   981720    0.991    0.000    6.489    0.000 run_benchmark.py:177(__init__)
       10    0.891    0.089   33.543    3.354 run_benchmark.py:245(render)


Fri Sep 18 18:05:11 2026    /root/HW-SW-Co-Design/results/run-2026-09-18_172405-9070/details/raytrace-baseline-python/python.pstats

         30863102 function calls (30794332 primitive calls) in 33.630 seconds

   Ordered by: cumulative time
   List reduced from 54 to 12 due to restriction <12>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000   33.630   33.630 workload.py:204(run_measured_calls)
       10    0.000    0.000   33.630    3.363 workload.py:100(<lambda>)
       10    0.001    0.000   33.630    3.363 run_benchmark.py:357(bench_raytrace)
       10    0.891    0.089   33.543    3.354 run_benchmark.py:245(render)
153330/100000    0.584    0.000   30.256    0.000 run_benchmark.py:266(rayColour)
53330/37890    0.763    0.000   23.009    0.001 run_benchmark.py:315(colourAt)
    53330    0.175    0.000   16.047    0.000 run_benchmark.py:290(visibleLights)
   106660    2.558    0.000   15.849    0.000 run_benchmark.py:283(_lightIsVisible)
  1794570    4.121    0.000   13.448    0.000 run_benchmark.py:142(intersectionTime)
   152650    1.276    0.000    9.637    0.000 run_benchmark.py:271(<listcomp>)
  2778650    4.877    0.000    7.322    0.000 run_benchmark.py:113(__sub__)
  5098710    5.494    0.000    6.510    0.000 run_benchmark.py:51(dot)
```

## Counters

| Metric | Median | Min–max | Usable / attempted |
|---|---:|---:|---:|
| ipc | 2.0785 | 2.0779–2.0869 | 3/3 |
| cpi | 0.48112 | 0.47918–0.48125 | 3/3 |
| branch_miss_percent | 0.88754 | 0.84395–0.89373 | 3/3 |
| generic_cache_miss_percent | 0.00032585 | 0.00031249–0.00034036 | 3/3 |
| l1_miss_percent | 1.9818 | 1.8628–2.0549 | 3/3 |
| branch_mpki | 2.1169 | 2.0907–2.1189 | 3/3 |
| generic_cache_mpki | 1.7168e-06 | 1.2953e-06–1.9172e-06 | 3/3 |
| l1_load_mpki | 5.3673 | 5.3343–5.6073 | 3/3 |

| Event | Median per benchmark call | Unit | Usable / attempted |
|---|---:|---|---:|
| L1-dcache-load-misses | 6.1987e+07 | count | 3/3 |
| L1-dcache-loads | 3.1066e+09 | count | 3/3 |
| branch-misses:u | 2.2589e+07 | count | 3/3 |
| branches:u | 2.5506e+09 | count | 3/3 |
| cache-misses:u | 18.7 | count | 3/3 |
| cache-references:u | 5.7388e+06 | count | 3/3 |
| context-switches | 58.2 | count | 3/3 |
| cpu-migrations | 0 | count | 3/3 |
| cycles:u | 5.0784e+09 | count | 3/3 |
| instructions:u | 1.0598e+10 | count | 3/3 |
| major-faults | 0 | count | 3/3 |
| minor-faults | 0.1 | count | 3/3 |
| task-clock | 2149.9 | msec | 3/3 |

Descriptive medians/ranges, not confidence intervals. Each ratio uses simultaneous events from its own pass. Per-call means one configured simulation or one rendered frame. A zero cycles counter makes IPC/CPI unavailable. Generic cache misses do not establish DRAM traffic or a memory bottleneck. Full repeat validity and running fractions are archived.

## Interpretation to finish

- Review the source explanation in `docs/stage1-raytrace.md` (also archived).
- Identify hot functions from this run and explain their algorithms/data structures.
- Separate observed cost from a proposed cause; no FPU-bound or memory-bound claim follows from a function name alone.
- Use fresh unprofiled debug timings for both variants in any later optimization comparison. This run implements no optimization.
