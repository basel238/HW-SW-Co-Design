# HW/SW Co-design Project (00460882) — pyperformance Benchmark Optimization

> Analyze, profile, and accelerate two pure-Python **pyperformance** benchmarks
> (**`nbody`** and **`raytrace`**) using `perf` and flame graphs, demonstrate a
> **≥ 7 %** software speedup on each, and propose a hardware accelerator.

---

## 📌 Overview

This repository contains the full submission for the Hardware/Software Co-design
final project. The workflow follows the course methodology end-to-end:

1. **Understand** each benchmark — purpose, libraries, data structures, algorithms.
2. **Profile** it with `perf` (`stat`, `record`, `report`) and **flame graphs**.
3. **Detect the bottleneck** using two complementary views — flame graph + `perf report` Self % (the *where*) and the CPI-stack / top-down counters (the *why*).
4. **Optimize the benchmark's own code** (no library swaps) and prove a **≥ 7 %** improvement with `pyperformance compare`.
5. **Propose a hardware accelerator** (Verilog/SystemVerilog) for the shared multiply-accumulate hotspot.

### Chosen benchmarks

| Benchmark  | Domain              | Bottleneck type                         | Hotspot |
|------------|---------------------|-----------------------------------------|---------|
| `nbody`    | Physics simulation  | FPU / compute-bound                     | `advance()` inner loop (the `(...)**(-1.5)` power op) |
| `raytrace` | 3-D graphics render | Object-churn + method-call (mixed)      | `Vector.*` methods & `Sphere.intersectionTime` |

---

## 📁 Repository structure

```
.
├── README.md                     # this file
├── .gitignore                    # excludes venv/, perf.data, FlameGraph/, ...
│
├── docs/
│   ├── benchmark-analysis.pdf    # Instruction #1: benchmark analysis (nbody & raytrace)
│   └── profiling-manual.pdf      # how-to manual: pyperformance + perf + flame graphs
│
├── scripts/
│   ├── 00_setup.sh               # install python3-dbg, perf, venv, pyperformance, FlameGraph
│   ├── 01_baseline.sh <bench>    # baseline run -> <bench>_base.json
│   ├── 02_perf_stat.sh <bench>   # aggregate counters (the "why")
│   ├── 03_perf_record_flame.sh   # perf record + report_<bench>.txt + <bench>.svg (the "where")
│   ├── 04_optimize_compare.sh    # optimized run + compare (prove >= 7%)
│   ├── 05_interpret.sh <json>    # detailed pyperf stats / hist / dump
│   ├── run_all.sh <bench>        # driver: phases 1 -> 3 for one benchmark
│   └── git_setup.sh              # initialize + connect this repo
│
├── script_nbody.sh               # end-to-end run script (deliverable)
├── script_raytrace.sh            # end-to-end run script (deliverable)
│
├── report_nbody.txt              # perf report output + written analysis (deliverable)
├── report_raytrace.txt           # perf report output + written analysis (deliverable)
│
├── results/
│   ├── nbody_base.json           # pyperf result — before optimization
│   ├── nbody_opt.json            # pyperf result — after optimization
│   ├── raytrace_base.json
│   └── raytrace_opt.json
│
├── flamegraphs/
│   ├── nbody.svg
│   └── raytrace.svg
│
├── src/                          # the modified benchmark code
│   ├── bm_nbody/
│   └── bm_raytrace/
│
├── hw/                           # hardware-acceleration proposal
│   ├── mac_unit.sv               # Verilog/SystemVerilog accelerator
│   ├── block_diagram.png         # accelerator + interfaces + integration
│   └── proposal.md               # inputs/outputs, interface, trade-offs
│
└── prompt.txt                    # AI-tool prompts used during the project
```

---

## ⚙️ Prerequisites

- Ubuntu Linux (the course **QEMU VM image**).
- Root/sudo access (to install `linux-tools` and lower `perf_event_paranoid`).
- Internet access to `pip install pyperformance` and clone FlameGraph.

Key packages (installed automatically by `scripts/00_setup.sh`):

- `python3-dbg` — debug build of CPython. Ships **symbols + frame pointers** so
  `perf` can resolve internal Python function names and unwind call stacks.
- `linux-tools-common` + `linux-tools-$(uname -r)` — the `perf` tool.
- `python3-venv`, `pyperformance` (pulls in `pyperf`).
- Brendan Gregg's **FlameGraph** scripts.

---

## 🚀 Quick start

```bash
# 1) One-time environment setup
bash scripts/00_setup.sh

# 2) Activate the virtual environment (repeat in every new terminal)
source venv/bin/activate

# 3) Full BEFORE-optimization pipeline for a benchmark
bash scripts/run_all.sh nbody       # baseline + perf stat + flame graph
bash scripts/run_all.sh raytrace

# 4) ... edit the benchmark's own code in src/ ...

# 5) Prove the >= 7% improvement
bash scripts/04_optimize_compare.sh nbody
bash scripts/04_optimize_compare.sh raytrace
```

---

## 🔬 Step-by-step

### 1. Run a benchmark & capture the baseline
```bash
bash scripts/01_baseline.sh nbody          # -> nbody_base.json
pyperformance show nbody_base.json          # mean +/- std dev
```
`pyperformance` runs the benchmark many times (warmups + measured values) via
`pyperf` for statistically stable numbers.

### 2. Aggregate counters — the *why*
```bash
bash scripts/02_perf_stat.sh nbody          # -> perfstat_nbody.txt
```
Captures `cycles, instructions, cache-references, cache-misses, branches,
branch-misses, context-switches` (with `-r 5` for std dev) plus a `--topdown`
CPI-stack breakdown (Retiring / Bad-Spec / Frontend / Backend).

> **Golden rule:** never judge on one number. Read **cycles + IPC + cache
> behaviour together**, and always report **absolute counts, not just rates** —
> a version can show a *higher* cache-miss % yet be *faster* because it issues
> far fewer total references.

### 3. Locate the hotspot — the *where*
```bash
bash scripts/03_perf_record_flame.sh nbody  # -> report_nbody.txt + nbody.svg
firefox flamegraphs/nbody.svg
```
- **`perf report`** — read the **Self %** column (leaf functions where CPU time is actually spent). `Children %` = self + everything called.
- **Flame graph** — *y-axis* = stack depth (top = on-CPU leaf), *x-axis* = sample share (**not time**), **width = CPU time**. The **widest top plateau is the hotspot**.

### 4. Interpret a result file in depth
```bash
bash scripts/05_interpret.sh nbody_base.json
# pyperf stats  -> mean/median/min/max/std dev/outliers
# pyperf hist   -> distribution (judge the shape, not one point)
# pyperf dump   -> raw per-run values
```

### 5. Optimize & prove ≥ 7 %
```bash
bash scripts/04_optimize_compare.sh nbody
# reads:  "1.10x faster" + "Significant"  => PASS   (>= 7% needs >= ~1.075x)
```
Optimizations are **code-level** (the pure-Python constraint): e.g. replacing
`nbody`'s `(...)**(-1.5)` with `1/(d2*sqrt(d2))`, and adding `__slots__` +
inlining the hot vector math in `raytrace`.

---

## ✅ Deliverables checklist

- [ ] `report_nbody.txt` — perf report + written analysis
- [ ] `report_raytrace.txt` — perf report + written analysis
- [ ] `script_nbody.sh` / `script_raytrace.sh` — setup + run + profile + compare
- [ ] Flame graphs for both benchmarks (`flamegraphs/*.svg`)
- [ ] `pyperformance compare` output showing **≥ 7 %** and **Significant** for **both** benchmarks
- [ ] Hardware-acceleration proposal in `hw/` (Verilog/SystemVerilog + block diagram + trade-offs)
- [ ] `prompt.txt` documenting AI-tool prompts
- [ ] Clear, well-structured commit history (**+5 bonus**)

---

## 🧩 Hardware acceleration (summary)

Both benchmarks reduce to repeated **multiply-accumulate** work, so the proposal
is a **MAC / reciprocal-square-root unit** (see `hw/`). It obeys the course's
accelerator interface rules:

1. **Don't force users to rewrite their code.**
2. **If software must change, confine it to libraries/runtime.**
3. **Don't break user code — fall back to the CPU** for unsupported ops.

Full inputs/outputs, data widths, operating frequency, HW/SW interface (MMIO/DMA),
and performance/area/power trade-offs are documented in `hw/proposal.md`.

---

## 🔁 Reproducing from scratch

```bash
git clone <REPO_URL>
cd <repo>
bash scripts/00_setup.sh
source venv/bin/activate
bash scripts/run_all.sh nbody
bash scripts/run_all.sh raytrace
# edit src/ ... then:
bash scripts/04_optimize_compare.sh nbody
bash scripts/04_optimize_compare.sh raytrace
```

---

## 🛠️ Git workflow

```bash
git add -A
git commit -m "feat: optimize nbody advance() inner loop"
git push
```
Commit at each milestone with descriptive messages (analysis → optimization →
hardware). See `scripts/git_setup.sh` to initialize and connect the repo.

---

## 🤖 AI tools

AI assistance is permitted; all prompts used are recorded in `prompt.txt`.
The tools were used as an aid — the analysis, optimizations, and hardware design
reflect our own understanding of the material.

---

## 👥 Authors

- *`<Your name>`* — `<ID>`
- *`<Teammate name>`* — `<ID>`

*Course 00460882 — Hardware/Software Co-design*
