> Historical review before integration. The selected additions were implemented in v3; see CHANGELOG.md. References below to a release environment describe that earlier policy. Current measurements and optimization comparisons use debug Python exclusively; see README.md.

# Review of the alternative updated measurement scripts

Reviewed 17 September 2026. Inputs: the newly supplied common.sh, 02_perf_stat.sh, 03_perf_record_flame.sh and 04_optimize_compare.sh; the original scripts and audit; Project(2).pdf; and our project-scripts-v2 package. Line references below refer to the newly supplied files.

**Recommendation: retain project-scripts-v2 as the measurement foundation and incorporate selected ideas.** The new scripts substantially improve the original workflow, but their comments overstate several guarantees. Their most useful addition over our package is a statistical Python flame graph using py-spy. A convenient source diff, a concise counter summary and carefully validated MPKI would also improve our package.

This is a review and integration proposal. No measurement scripts were changed or merged during this review.

## 1. What genuinely improved

| Change | Assessment against the original and our replacement |
|---|---|
| Shared interpreter/source helpers | Better than hard-coded python3-dbg. Our package already uses one explicit release environment and records stronger provenance. |
| Direct benchmark worker invocation | Removes the outer pyperformance installer and manager. It does not isolate the benchmark region. Our fixed-work driver and perf control gate are stronger. |
| Cycle-counter probes | Useful diagnosis before interpreting metrics. Our package already offers separate known-work probes; an automatic readable capability summary would be useful. |
| Simultaneous event pairs | Correct direction for IPC and miss fractions. MPKI denominators still need proper grouping and scheduling validation. |
| DWARF and newer Python/perf modes | DWARF is already our native default. Explicitly supported Python trampoline modes are worth considering later. |
| Separate Python flame graph with py-spy | The clearest new capability. Our existing Python view uses deterministic cProfile tables, which can distort call-heavy code. A separate sampling view would complement it. |
| Benchmark/variant-specific filenames | Fixes nbody overwriting raytrace, but repeated runs still overwrite earlier runs. Our unique run directories already solve both. |
| Fresh original/candidate runs in alternating order | Correct direction and already present in our package. It reduces order bias but cannot eliminate environmental bias. |
| Saved code diff | Useful addition for reviewing and presenting an optimization. Add a diff of complete frozen source trees, alongside existing snapshots/hashes. |
| Explicit improvement verdict | Better than merely printing compare_to. Their verdict cannot be audited without the missing helper, and correctness is not enforced. |

## 2. Blocking issue: the delivered set is incomplete

common.sh line 28 requires a sibling `_tools.py`. That file is not attached. It supplies at least:

- `pyinfo`: Python version, debug-build, frame-pointer and trampoline facts;
- `meta`: baseline metadata extraction;
- `sanity`: baseline compatibility/timing checks;
- `perfstat`: counter parsing and derived metrics;
- `stackq`: flame-stack quality analysis;
- `compare`: improvement calculation and statistical verdict.

I tested the first interpreter-resolution step. It exits with `can't open file .../upload/_tools.py`, followed by `ERROR: cannot query ...`. All four shell files pass `bash -n`, but that does not make the workflow runnable.

The missing helper is necessary before judging its CSV handling, frame-pointer detection, zero/unsupported counter behavior, stack-quality thresholds or Welch-test implementation. Do not assume those parts work from the shell comments. This does not prevent assessing the visible shell-level problems below.

The path helper also assumes the files live inside a `scripts/` directory: it changes to the parent of their directory. Place them according to that layout if independently testing the alternative package.

## 3. Counter measurement: good direction, important remaining errors

### Reference cycles are not a replacement for core cycles

02_perf_stat.sh lines 75–105 probes generic cycles, a raw event, then ref-cycles. If only ref-cycles works, it puts that event into the instruction/cycle group and describes the result as an IPC approximation.

Keep these definitions distinct:

    IPC = retired instructions / measured core cycles
    reference-cycle throughput = retired instructions / measured reference cycles

Reference cycles use a different clock basis. For example, 300 million instructions, 200 million core cycles and 100 million reference cycles give IPC 1.5 and reference-cycle throughput 3.0. Substituting the denominator changes the metric. A virtualized counter adds further uncertainty.

**Needed:** preserve unavailable IPC/CPI when core cycles are unusable. A validated ref-cycles count may be recorded as a separate, clearly named diagnostic. A raw event may replace the generic alias only after verifying its model-specific semantics, privilege filters and scheduling. A positive number alone is insufficient. Linux documents the distinction between core/reference cycles and the simultaneous scheduling of group members in [perf_event_open](https://man7.org/linux/man-pages/man2/perf_event_open.2.html).

The vendor selection at lines 68–71 treats every non-AMD/Hygon CPU as Intel. That is not a portable raw-event selection rule. Lines 101–102 also state a hypervisor cause more confidently than the probes establish. A zero remains a diagnosis problem, not proof of one mechanism.

### Grouping does not make every advertised ratio reliable

The main pass groups cycles/instructions, branches/branch-misses and cache-references/cache-misses separately (lines 110–118). Those pairs are the right shape for their respective ratios, provided the events are supported and adequately scheduled.

However:

- Branch/cache MPKI needs instructions in the same scheduled group as the corresponding misses.
- The L1 pass has standalone instructions alongside a separate L1 pair (lines 123–124), so it does not guarantee simultaneous instruction/miss sampling under multiplexing.
- Several groups in one pass can still multiplex. Braces alone do not prove adequate event-running time or virtual-PMU accuracy.
- `perf stat -r` saves aggregate statistics here; it does not preserve each repetition's complete raw observations as our separate-repeat workflow does.

**Needed:** for an MPKI extension, use small separate passes such as `{instructions:u,branches:u,branch-misses:u}` and analogous cache/L1 groups when supported. Compute ratios only within a valid pass, save each repetition, check running fractions and retain failures. Generic cache MPKI must not be renamed DRAM MPKI.

### The measured window still includes framework work

common.sh lines 189–193 launches pyperf `--worker`; 02 lines 56 and 118 run separate complete processes. This removes pyperformance's outer environment preparation, but the measured process still imports code, warms up, collects metadata and writes results. Some metadata collection may itself launch helper commands. The final report admits startup at lines 177–178, contradicting the stronger header claims.

A prior process can warm OS caches; it does not preserve the next process's initialized Python state. Furthermore, pyperf documents `--worker` as an internal option, rather than its public runner interface. [pyperf Runner documentation](https://pyperf.readthedocs.io/en/latest/runner.html)

**Needed:** retain our in-process warmup followed by the perf enable/disable acknowledgment gate. State the small remaining driver/boundary overhead. Keep multi-worker unprofiled timing separate.

### Top-down and automatic interpretation

Adding `-a` addresses the original invocation error. But 02 defaults TOPDOWN=1 and collects across all guest CPUs without explicit affinity (lines 31, 132–134). This is system-wide evidence, including unrelated guest work, even with one vCPU. A working raw/reference-cycle probe does not validate the events used by top-down itself.

The report's rule at line 179—backend-bound plus low MPKI implies compute-bound, high MPKI implies memory-bound—is too strong. Memory stalls depend on latency, parallelism, cache level, TLB behavior and other effects, not only miss frequency. Many misses may overlap without dominating runtime.

**Needed:** retain optional, CPU-scoped, separately labeled top-down; replace automatic bottleneck labels with observations and hypotheses. Keep failed top-down outputs rather than replacing all diagnostics with a short generic message. [perf-stat documentation](https://man7.org/linux/man-pages/man1/perf-stat.1.html)

## 4. Profiling: py-spy is worth adding, automatic trust is not

### Add a separate py-spy profile

03 lines 130–155 add a useful sampling-based Python view that can identify functions such as advance and vector operations on the existing Python 3.10 interpreter. This avoids upgrading solely to obtain Python names. It complements native perf and our cProfile diagnostics; its output does not establish hardware bottlenecks.

For integration:

1. Pin the profiler version during setup, record it with the run, and use the exact same frozen source and release interpreter.
2. Save SVG plus raw or speedscope data, command, sampling rate, errors and scope.
3. Use a separately verified sampling window. If startup and warmup remain included, explicitly label them; do not imply perf's FIFO gate also controls py-spy.
4. Keep timing/counters uninstrumented. Sampling has overhead too; do not use profiled elapsed time for the speedup claim.
5. Let Python profiling run independently when native perf is unavailable.

Their implementation does not satisfy the last point: line 36 requires perf, and failures at lines 74/76 stop execution before py-spy starts. Forced py-spy may also reuse a command containing perf trampolines unnecessarily. Its generic failure message recommends root or relaxing ptrace without diagnosing the actual error; Linux child-process profiling can often work without root. [py-spy documentation](https://github.com/benfred/py-spy)

### Treat Python/perf trampoline modes as optional capabilities

common.sh lines 171–176 recognize `-X perf` and `-X perf_jit`. This is useful, but not ready to merge unchanged:

- Python 3.12+ perf-map mode requires the supported build and suitable unwind behavior.
- Python 3.13+ JIT/DWARF mode also requires a perf build with the relevant JIT fix. Official documentation describes versions higher than 6.8 or the 6.7.2 backport, and warns that distro suffixes do not establish the upstream patch level. Do not assume the course's perf 5.15 works just because Python was upgraded.
- The selector can silently replace a requested `fp` or `lbr` mode with DWARF.
- It sets `PY_NAMES=1` from selected options, not from observed successful Python-frame attribution.
- Compiler flags and version checks are useful evidence, not proof that every native frame unwinds.

**Needed:** explicit opt-in modes, an actual capability probe, retained errors, and inspection of representative Python/native stacks. Keep the current Python version for the first clean rerun. Trampolines add instrumentation and should not be enabled in timing/counter runs. [CPython perf integration](https://docs.python.org/3.13/howto/perf_profiling.html)

### Preserve correct flame weights and durable outputs

03 does not explicitly request sample periods during recording/extraction or specify a flamegraph unit (lines 73, 111–116). stackcollapse-perf uses periods when present and otherwise counts records. Consequently the default “samples” label is not guaranteed to describe the total. Our explicit period recording/extraction and cpu-clock `ns` label should remain.

Per-benchmark filenames still overwrite the same benchmark's earlier report, log, folded stacks and SVG. The new shallow FlameGraph clone and unpinned py-spy installation also introduce version drift. Only flamegraph.pl is checked; stackcollapse-perf.pl may still be absent. Keep our pinned tools and unique run directories.

A “widest top plateau” is not a complete hotspot analysis: a function may be split across many callers. Aggregate Self, inspect valid inclusive paths, and distinguish unknown ancestry from unresolved leaves. The missing stackq helper cannot currently substantiate any trust verdict. Neither a heuristic checker nor our own stack-health warnings certify a recording.

Default `cpu-clock` includes a different privilege scope from our `cpu-clock:u`; both can be deliberate choices, but do not compare percentages as if their denominators were identical. LBR additionally needs suitable hardware/virtualization; it is not a universal unwind fallback. [perf-record documentation](https://man7.org/linux/man-pages/man1/perf-record.1.html)

## 5. Comparison and shared environment: retain our stronger checks

| Issue | Evidence and required handling |
|---|---|
| Correctness is advisory | 04 lines 70–75 only check that the candidate exits successfully. A wrong or reduced workload could pass a speed test. Retain automated nbody state and raytrace image checks tied to source hashes. |
| ABBA is overclaimed | Lines 12–13 say VM drift cannot fake improvement. Balanced order helps approximately monotonic drift; it cannot remove host contention, frequency changes or phase-specific interference. Retain separate rounds and their uncertainty. |
| Statistical method is unreviewable | The actual comparison and Welch test are in missing _tools.py. A Welch test may be useful with appropriate independent observations, but treating several values from one worker as independent exaggerates effective sample size. Statistical significance also does not establish equivalent output or a 7% effect. |
| Old results are deleted | Lines 79–82 remove existing original/candidate JSON and append all rounds to fixed replacement files. Retain immutable run directories and explicit round identity. |
| Only the entry file is compared | Lines 51–61 use cmp/diff on run_benchmark.py. Legitimate helper-module-only changes can be rejected; unrecorded helper changes can also escape the diff. Diff and hash whole frozen source trees. |
| Source discovery is not source identity | common lines 95–107 find whichever pyperformance copy is available through several interpreters. That need not be the original baseline's revision. Retain pinned baseline sources and full snapshots. |
| Environment mismatch only warns | common lines 141–160 can reuse a profiling venv keyed by interpreter basename, then continue after detecting a different interpreter/version. A release-build check alone does not prove baseline equivalence. Require compatibility for comparisons. |
| External environment can enable instrumentation | Clearing PYFLAGS in 02 does not clear inherited PYTHONPERFSUPPORT or other Python behavior variables. Preserve our explicit environment policy and recorded settings. |
| Defaults are not enforced settings | 04 line 82 relies on pyperf defaults unless PYPERF_OPTS is supplied. The stated 20 workers/3 values/1 warmup matches local non-JIT pyperf 2.10 defaults, with automatic loop calibration, but historical settings are not explicitly enforced. ROUNDS is also unvalidated; one or odd rounds lose full order balance. |
| Unjustified optimization restriction | 04 line 47 says “no library swaps.” Project(2).pdf explicitly encourages more efficient libraries and algorithms. Remove that restriction while retaining correctness and equivalent-work requirements. |

The saved diff is worth adopting. The historical-baseline sanity check is also useful as an informational compatibility report, provided it never substitutes for fresh matched measurements or silently permits mismatches.

One small improvement applies to our package too: it requires at least two rounds, but currently permits an odd larger number. The default two rounds are balanced; to promise balanced ordering for every configuration, enforce an even round count or explicitly report the imbalance.

## 6. Recommended changes to our package, in priority order

| Priority | Proposed addition | Acceptance criteria |
|---|---|---|
| 1 | Optional py-spy Python flame graph | Works with the current release interpreter; independent of perf success; pinned version; exact source identity; raw data and SVG; explicit sampling scope and failure status. |
| 2 | Human-readable measurement summary | One table linking raw repeat counts, event-running fractions, normalized counts, valid ratios and unavailability reasons. No automatic hardware-bottleneck verdict. |
| 2 | Automatic capability summary | Nonmutating known-work probes distinguish unsupported, permission-denied, zero, poorly scheduled and plausible counters. Raw logs remain available. A probe passing is not proof of PMU fidelity. |
| 2 | Full-source optimization diff | Generate from the same frozen trees used for correctness and comparison, including helper files. Keep snapshots and hashes. |
| 2 | Balanced round-count validation | Require an even count of at least two for the declared balanced-order experiment; our current default already meets this. |
| 3 | Additional MPKI metrics | Instructions and corresponding misses counted simultaneously with matching filters; sufficient scheduling; separate raw repeats; correct event-specific names. |
| 4 | Optional Python/perf trampoline integration | Verify Python/build/perf support and real stack attribution. Do not upgrade the measurement interpreter automatically. |
| Optional | Reference-cycle diagnostic | Separate count/throughput with explicit semantics; never relabel it IPC or use it to imply repaired core cycles. |

Do not import their reference-cycle IPC fallback, automatic system-wide top-down, fixed output paths, advisory-only correctness, blanket hardware-bound rules, or unverified stack trust logic.

## 7. Validation and limits of this review

I read all four files, compared them against the original scripts and our replacement implementation, checked the assignment's optimization rules, and checked relevant official documentation. All four shell files passed syntax checking. The first interpreter-resolution call reproduced the missing-helper failure. Mode-selection behavior was also checked with synthetic capability values.

I did not run this incomplete alternative pipeline, install its dependencies, change system permissions, or test hardware counters in your original VM. No performance improvement is claimed by this review. Providing _tools.py would allow a further review of the missing parser/statistical/unwind checks; it would not fix the visible scope, correctness, denominator and overwrite problems by itself.
