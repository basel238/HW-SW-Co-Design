#!/usr/bin/env python3
"""Run explicit local pyperformance sources; keep timing and profiling separate."""
import argparse
import csv
import datetime as dt
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import sysconfig
import uuid
from measurement_extras import (write_counter_summary, source_diff, probe_status,
                                jit_perf_version_supported)
from profile_evidence import assess_python_capture
from python_environment import require_debug_python

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
PY = sys.executable
BENCHMARKS = ("nbody", "raytrace")
RUN_ROOT = None  # Set only by the course workflow; child stages stay in one run.


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_hash(path):
    h = hashlib.sha256()
    for p in sorted(Path(path).rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
            h.update(p.relative_to(path).as_posix().encode() + b"\0")
            h.update(p.read_bytes() + b"\0")
    return h.hexdigest()


def config():
    c = json.loads((ROOT / "config.json").read_text())
    for key in ("processes", "values", "warmups", "loops"):
        value = c["timing"][key]
        if type(value) is not int or value < (0 if key == "warmups" else 1):
            raise ValueError("Invalid timing setting: " + key)
    if c["timing"]["loops"] != 1:
        raise ValueError("Keep loops=1 to preserve the documented per-call state policy.")
    for b in BENCHMARKS:
        for key, value in c[b].items():
            if type(value) is not int or value < (0 if key == "profile_warmups" else 1):
                raise ValueError("Invalid workload setting: " + b + "." + key)
    if min(c["raytrace"]["width"], c["raytrace"]["height"]) < 2:
        raise ValueError("raytrace dimensions must be at least 2.")
    for key in ("stat_repeats", "compare_rounds", "sample_frequency", "command_timeout_seconds"):
        if type(c[key]) is not int or c[key] < 1:
            raise ValueError("Invalid configuration: " + key)
    if c["compare_rounds"] < 2 or c["compare_rounds"] % 2:
        raise ValueError("Use an even number of comparison rounds, at least two, for balanced order.")
    if type(c["mpki"]) is not bool or type(c["pyspy"]["enabled"]) is not bool:
        raise ValueError("mpki and pyspy.enabled must be boolean.")
    if type(c["pyspy"]["rate"]) is not int or not 1 <= c["pyspy"]["rate"] <= 1000:
        raise ValueError("pyspy.rate must be an integer from 1 to 1000 Hz.")
    if c["affinity"] is not None and (not isinstance(c["affinity"], str) or
                                     not re.fullmatch(r"\d+(?:[-,]\d+)*", c["affinity"])):
        raise ValueError("affinity must be null or a CPU list such as '0' or '2-3'.")
    if not re.fullmatch(r"(?:dwarf(?:,\d+)?|fp(?:,\d+)?)", c["unwind"]):
        raise ValueError("unwind must be dwarf[,bytes] or fp[,depth].")
    return c


def clean_env():
    env = os.environ.copy()
    for name in tuple(env):
        if name.startswith("PYTHON") or name.startswith("PYPERF"):
            del env[name]
    env["LC_ALL"] = "C"
    return env


def command(argv, directory, name, timeout=1800, stdout_path=None, cwd=None):
    """Save exact argv/status; kill the entire child process group on timeout."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    dump(directory / (name + ".command.json"), {"argv": list(map(str, argv)),
         "cwd": str(cwd or ROOT), "environment_policy": "remove PYTHON*/PYPERF*; LC_ALL=C"})
    target = Path(stdout_path) if stdout_path else directory / (name + ".stdout.txt")
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    with target.open("wb") as out, (directory / (name + ".stderr.txt")).open("wb") as err:
        try:
            proc = subprocess.Popen(list(map(str, argv)), cwd=cwd or ROOT, env=clean_env(),
                                    stdout=out, stderr=err, start_new_session=True)
        except OSError as exc:
            rc = 127
            err.write(str(exc).encode())
        else:
            try:
                rc = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                rc = 124
            if rc:
                # A failed sampler may leave its workload child alive.
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
    dump(directory / (name + ".status.json"), {"returncode": rc, "started_utc": started,
         "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat()})
    return rc


def require(rc, message):
    if rc:
        raise RuntimeError(message + " (exit " + str(rc) + "; inspect saved stderr)")


def interpreter():
    real = Path(PY).resolve()
    return {"executable": PY, "real_executable": str(real),
            "executable_sha256": digest(real), "version": sys.version,
            "py_debug": bool(sysconfig.get_config_var("Py_DEBUG")),
            "compiler": platform.python_compiler(),
            "cflags": sysconfig.get_config_var("CFLAGS") or "",
            "config_args": sysconfig.get_config_var("CONFIG_ARGS") or ""}


def packages():
    return sorted({d.metadata["Name"].lower() + "==" + d.version
                   for d in importlib.metadata.distributions() if d.metadata.get("Name")})


def machine():
    info = Path("/proc/cpuinfo").read_text() if Path("/proc/cpuinfo").exists() else ""
    match = re.search(r"^model name\s*:\s*(.*)$", info, re.M)
    return {"platform": platform.platform(), "cpu_count": os.cpu_count(),
            "cpu_model": match.group(1) if match else platform.processor()}


def preflight():
    require_debug_python()
    if importlib.metadata.version("pyperf") != "2.10.0":
        raise RuntimeError("Install the pinned requirements with 00_setup.sh.")
    sources = json.loads((ROOT / "SOURCES.json").read_text())
    for item in sources["files"]:
        p = ROOT / "src" / "baseline" / item["benchmark"] / item["path"]
        if not p.is_file() or digest(p) != item["sha256"]:
            raise RuntimeError("Baseline changed or missing: " + str(p) +
                               ". Restore it; edit src/optimized instead.")
    config()
    for b in BENCHMARKS:
        if not (ROOT / "src" / "optimized" / b / "run_benchmark.py").is_file():
            raise RuntimeError("Missing optimized source: " + b)


def new_run(label):
    require_debug_python()
    if RUN_ROOT is not None:
        path = Path(RUN_ROOT) / label
        path.mkdir(parents=True, exist_ok=False)
    else:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        path = ROOT / "results" / (label + "-" + stamp + "-" + uuid.uuid4().hex[:4])
        path.mkdir(parents=True, exist_ok=False)
        print("Results:", path, flush=True)
    return path


def workload_params(c):
    return {"iterations": c["nbody"]["iterations"], "width": c["raytrace"]["width"],
            "height": c["raytrace"]["height"], "reference": "sun"}


def snapshot(bench, variant, out, c):
    source = ROOT / "src" / variant / bench
    shutil.copytree(source, out / "source", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    entry = out / "source" / "run_benchmark.py"
    prov = {"benchmark": bench, "variant": variant, "source_path": str(entry),
            "source_sha256": digest(entry), "source_tree_sha256": tree_hash(out / "source"),
            "interpreter": interpreter(), "packages": packages(), "machine": machine(),
            "workload": workload_params(c),
            "timing": dict(c["timing"], affinity=c["affinity"]),
            "toolkit_sha256": tree_hash(TOOLS), "configuration": c}
    dump(out / "provenance.json", prov)
    dump(out / "config.json", c)
    shutil.copyfile(ROOT / "ENVIRONMENT.md", out / "environment-notes.md")
    # Read-only diagnostics are outside all measured regions.
    for argv, name in [(["uname", "-a"], "uname"), (["lscpu"], "lscpu"),
                       (["perf", "--version"], "perf-version"),
                       (["git", "-C", str(ROOT), "rev-parse", "HEAD"], "git-head")]:
        command(argv, out / "environment", name, timeout=15)
    return entry


def pinned(argv, c):
    if c["affinity"] is None:
        return argv
    if not shutil.which("taskset"):
        raise RuntimeError("taskset required when affinity is configured")
    return ["taskset", "-c", str(c["affinity"])] + argv


def driver(bench, source, out, c, calls=None, warmups=None):
    p = workload_params(c)
    return [PY, str(TOOLS / "workload.py"), "--benchmark", bench, "--source", str(source),
            "--calls", str(c[bench]["profile_calls"] if calls is None else calls),
            "--warmups", str(c[bench]["profile_warmups"] if warmups is None else warmups),
            "--iterations", str(p["iterations"]), "--width", str(p["width"]),
            "--height", str(p["height"]), "--receipt", str(out / "workload.json")]


def timing(bench, variant, c):
    out = new_run(bench + "-" + variant + "-timing")
    source = snapshot(bench, variant, out, c)
    t = c["timing"]
    argv = [PY, str(TOOLS / "timing_runner.py"), "--benchmark", bench, "--source", str(source),
            "--output", str(out / "timing.json"),
            "--processes", str(t["processes"]), "--values", str(t["values"]),
            "--warmups", str(t["warmups"]), "--loops", "1"]
    argv += ["--iterations", str(c["nbody"]["iterations"]),
             "--width", str(c["raytrace"]["width"]), "--height", str(c["raytrace"]["height"])]
    if c["affinity"] is not None:
        argv += ["--affinity", str(c["affinity"])]
    print("Running unprofiled timing:", bench, variant, flush=True)
    require(command(argv, out, "timing", c["command_timeout_seconds"]), "Timing failed")
    import pyperf
    suite = pyperf.BenchmarkSuite.load(str(out / "timing.json"))
    if suite.get_benchmark_names() != [bench]:
        raise RuntimeError("Timing output does not identify the requested benchmark")
    values = suite.get_benchmark(bench).get_values()
    if len(values) != t["processes"] * t["values"] or any(not math.isfinite(x) or x <= 0 for x in values):
        raise RuntimeError("Timing output is incomplete or contains invalid values")
    for action in ("metadata", "check", "stats", "hist", "dump"):
        command([PY, "-m", "pyperf", action, str(out / "timing.json")], out, action, timeout=60)
    return out


def perf_gated(prefix, bench, source, out, c, name, scope=None, python_flags=()):
    out.mkdir(parents=True, exist_ok=True)
    ctl, ack = out / "control.fifo", out / "ack.fifo"
    os.mkfifo(ctl, 0o600)
    os.mkfifo(ack, 0o600)
    workload = driver(bench, source, out, c)
    workload[1:1] = list(python_flags)
    argv = prefix + ["--delay=-1", "--control", "fifo:" + str(ctl) + "," + str(ack),
                     "--"] + pinned(workload +
                     ["--control-fifo", str(ctl), "--ack-fifo", str(ack)], c)
    try:
        rc = command(argv, out, name, c["command_timeout_seconds"])
    finally:
        ctl.unlink(missing_ok=True)
        ack.unlink(missing_ok=True)
    try:
        receipt = json.loads((out / "workload.json").read_text())
    except (OSError, ValueError):
        receipt = {}
    issues = receipt_issues(receipt, bench, source, c)
    if not isinstance(receipt, dict):
        receipt = {}
    if rc:
        issues.append("perf/workload returned " + str(rc))
    for key in ("roi_gated", "enable_acknowledged", "disable_acknowledged"):
        if receipt.get(key) is not True:
            issues.append(key + " was not confirmed")
    ok = not issues
    dump(out / "collection.json", {"available": ok, "returncode": rc,
         "scope": scope or "target process; perf enable/disable handshake around fixed benchmark calls",
         "note": "Tiny boundary/driver overhead remains; perf elapsed includes excluded setup.",
         "completed_calls": receipt.get("completed_calls"), "validation_errors": issues,
         "workload_errors": receipt.get("errors", [])})
    return ok


def receipt_issues(receipt, bench, source, c):
    if not isinstance(receipt, dict):
        return ["Workload receipt is not an object"]
    expected = {"status": "ok", "benchmark": bench,
                "calls": c[bench]["profile_calls"],
                "completed_calls": c[bench]["profile_calls"],
                "warmups": c[bench]["profile_warmups"],
                "completed_warmups": c[bench]["profile_warmups"],
                "source_sha256": digest(source),
                "source_tree_sha256": tree_hash(Path(source).parent)}
    return [key + " does not match the requested workload"
            for key, value in expected.items() if receipt.get(key) != value]


def gate_probe(c):
    """Exercise the real control protocol before a long run, independently of PMU events."""
    probe = json.loads(json.dumps(c))
    probe["nbody"].update(iterations=2000, profile_calls=2, profile_warmups=1)
    out = new_run("perf-gate-probe")
    source = snapshot("nbody", "baseline", out, probe)
    observations = {}
    selections = [
        ("stat", ["perf", "stat", "-x", ";", "--no-big-num", "-e", "task-clock",
                  "-o", str(out / "stat" / "counters.csv")]),
        ("record", ["perf", "record", "-P", "-e", "cpu-clock:u", "-F", "99",
                    "--call-graph", c["unwind"], "-o", str(out / "record" / "perf.data")]),
    ]
    for label, prefix in selections:
        dest = out / label
        try:
            ok = perf_gated(prefix, "nbody", source, dest, probe, "perf-" + label)
            if label == "stat":
                events = parse_stat(dest / "counters.csv")
                metric = stat_metrics(events, None, ok)
                ok = ok and bool(events) and metric["all_emitted_events_usable"]
            else:
                ok = ok and (dest / "perf.data").is_file() and (dest / "perf.data").stat().st_size > 0
            observations[label] = {"passed": bool(ok), "directory": str(dest)}
        except (OSError, ValueError, RuntimeError) as exc:
            observations[label] = {"passed": False, "directory": str(dest), "error": str(exc)}
    passed = all(item["passed"] for item in observations.values())
    dump(out / "gate-probe.json", {"passed": passed, "probes": observations,
         "scope": "Short actual perf stat/record FIFO smoke tests, not benchmark results or PMU fidelity checks."})
    (out / "gate-probe.md").write_text("# Perf gate smoke test\n\n" +
        "\n".join(f"- {name}: {'passed' if item['passed'] else 'FAILED'}; {item['directory']}"
                  for name, item in observations.items()) +
        "\n\nBoth enable and disable acknowledgements and full workload receipts are required.\n")
    return out, passed


def parse_stat(path):
    events = {}
    if not path.exists():
        return events
    for row in csv.reader(path.read_text().splitlines(), delimiter=";"):
        if len(row) < 3 or row[0].startswith("#"):
            continue
        raw, unit, event = (x.strip() for x in row[:3])
        if not event or event in ("seconds time elapsed", "seconds user", "seconds sys"):
            continue
        try:
            count = float(raw)
            if not math.isfinite(count) or count < 0:
                raise ValueError
        except ValueError:
            count = None
        def number(index):
            try:
                value = float(row[index].strip().rstrip("%"))
                return value if math.isfinite(value) else None
            except (IndexError, ValueError):
                return None
        events[event] = {"count": count, "unit": unit, "raw_count": raw,
                         "counter_runtime": number(3), "running_percent": number(4)}
    return events


def stat_metrics(events, pair, collected):
    positive_events = {"cycles", "instructions", "branches",
                       "L1-dcache-loads", "task-clock"}
    for name, event in events.items():
        count = event["count"]
        if not collected:
            status = "collection_failed"
        elif count is None:
            status = "unsupported_or_unavailable"
        elif name.split(":")[0] in positive_events and count <= 0:
            status = "invalid_zero_for_active_workload"
        elif event.get("running_percent") is None:
            status = "running_fraction_unavailable"
        elif not 0 <= event["running_percent"] <= 100:
            status = "invalid_running_fraction"
        elif event.get("counter_runtime") is None or event["counter_runtime"] <= 0:
            status = "invalid_counter_runtime"
        elif event["running_percent"] < 95:
            status = "insufficient_running_fraction"
        else:
            status = "counted_sanity_checks_passed"
        event["status"] = status
        event["usable"] = status == "counted_sanity_checks_passed"
    result = {"events": events, "measurement_completed": collected,
              "any_usable_event": any(v["usable"] for v in events.values()),
              "all_emitted_events_usable": bool(events) and all(v["usable"] for v in events.values()),
              "validation": "nonzero/scheduling sanity only; PMU semantics still need verification"}
    if not pair:
        return result
    num_name, den_name, metric, factor = pair
    def find(name):
        return next((v for k, v in events.items() if k.split(":")[0] == name), {})
    num, den = find(num_name), find(den_name)
    reason = None
    if not collected:
        reason = "collection failed"
    elif num.get("count") is None or den.get("count") is None:
        reason = "missing or unsupported event"
    elif den["count"] <= 0 or (num_name == "instructions" and num["count"] <= 0):
        reason = "zero denominator or invalid instruction count"
    elif any(v.get("running_percent") is None for v in (num, den)):
        reason = "running fraction unavailable"
    elif min(num["running_percent"], den["running_percent"]) < 95:
        reason = "less than 95% counted; inspect multiplexing/scheduling"
    elif not num.get("usable") or not den.get("usable"):
        reason = "event count, runtime or running fraction failed validation"
    elif metric.endswith("_percent") and num["count"] > den["count"]:
        reason = "miss count exceeds reference count; investigate event semantics"
    result[metric] = None if reason else factor * num["count"] / den["count"]
    result["ratio_unavailable_reason"] = reason
    if metric == "ipc":
        result["cpi"] = (den["count"] / num["count"]) if not reason else None
    return result


def stat(bench, variant, c):
    out = new_run(bench + "-" + variant + "-stat")
    source = snapshot(bench, variant, out, c)
    groups = [
        ("software", "task-clock,context-switches,cpu-migrations,minor-faults,major-faults", None),
        ("ipc", "{cycles:u,instructions:u}", ("instructions", "cycles", "ipc", 1)),
        ("branches", "{branches:u,branch-misses:u}", ("branch-misses", "branches", "branch_miss_percent", 100)),
        ("cache", "{cache-references:u,cache-misses:u}", ("cache-misses", "cache-references", "generic_cache_miss_percent", 100)),
        ("l1", "{L1-dcache-loads:u,L1-dcache-load-misses:u}", ("L1-dcache-load-misses", "L1-dcache-loads", "l1_miss_percent", 100))]
    if c["mpki"]:
        # Separate two-event passes avoid assuming three programmable slots exist.
        for label, event, metric in (("branch-mpki", "branch-misses", "branch_mpki"),
                                     ("cache-mpki", "cache-misses", "generic_cache_mpki"),
                                     ("l1-mpki", "L1-dcache-load-misses", "l1_load_mpki")):
            groups.append((label, "{instructions:u," + event + ":u}", (event, "instructions", metric, 1000)))
    summaries = []
    for label, selection, pair in groups:
        for repeat in range(1, c["stat_repeats"] + 1):
            dest = out / (label + "-" + str(repeat))
            dest.mkdir()
            print("Counters:", bench, label, "repeat", repeat, flush=True)
            ok = perf_gated(["perf", "stat", "-x", ";", "--no-big-num", "-o", str(dest / "counters.csv"),
                             "-e", selection], bench, source, dest, c, "perf-stat")
            record = stat_metrics(parse_stat(dest / "counters.csv"), pair, ok)
            record.update(group=label, repeat=repeat, calls=c[bench]["profile_calls"])
            expected_names = {item.split(":")[0] for item in selection.strip("{}").split(",")}
            observed_names = {item.split(":")[0] for item in record["events"]}
            record["event_selection"] = selection
            record["event_names_match_request"] = expected_names == observed_names
            record["all_requested_events_usable"] = (record["all_emitted_events_usable"] and
                                                     record["event_names_match_request"] and
                                                     len(record["events"]) == len(expected_names))
            for event in record["events"].values():
                event["per_benchmark_call"] = event["count"] / c[bench]["profile_calls"] if event["usable"] else None
            dump(dest / "metrics.json", record)
            summaries.append(record)
    status = {"runs": summaries, "any_collection_completed": any(r["measurement_completed"] for r in summaries),
              "all_collection_completed": all(r["measurement_completed"] for r in summaries),
              "any_usable_event": any(r["any_usable_event"] for r in summaries),
              "all_requested_events_usable": all(r["all_requested_events_usable"] for r in summaries),
              "ipc_available": any(r.get("ipc") is not None for r in summaries),
              "scope_note": "Separate event groups repeat fixed useful work. Never combine counts across groups into ratios.",
              "unit_note": "per_benchmark_call is per simulation of configured iterations or per rendered frame; task-clock keeps perf's emitted unit."}
    dump(out / "stat-summary.json", status)
    write_counter_summary(out, summaries)
    print("Counters retained, IPC available:", status["ipc_available"], flush=True)
    return out, status["all_requested_events_usable"]


def native(bench, variant, c, python_mode=None):
    out = new_run(bench + "-" + variant + ("-python-perf-" + python_mode if python_mode else "-native"))
    source = snapshot(bench, variant, out, c)
    command(["perf", "version", "--build-options"], out, "perf-build-options", timeout=15)
    flags, extra, unwind = [], [], c["unwind"]
    if python_mode:
        info = {"mode": python_mode, "diagnostic_only": True,
                "have_perf_trampoline": bool(sysconfig.get_config_var("HAVE_PERF_TRAMPOLINE")),
                "python_version": sys.version, "available": False,
                "note": "Instrumentation changes execution; never use this run for timing or PMU comparisons."}
        command(["perf", "--version"], out, "trampoline-perf-version", timeout=15)
        version = (out / "trampoline-perf-version.stdout.txt").read_text()
        info["perf_version"] = version.strip()
        reason = None
        if not info["have_perf_trampoline"]:
            reason = "Python build has no HAVE_PERF_TRAMPOLINE support"
        elif python_mode == "map":
            if sys.version_info < (3, 12):
                reason = "perf map mode requires Python 3.12+"
            elif "-fno-omit-frame-pointer" not in (sysconfig.get_config_var("CFLAGS") or ""):
                reason = "No frame-pointer build evidence in CFLAGS; map mode not enabled"
            flags, unwind = ["-X", "perf"], "fp"
        elif python_mode == "jit":
            if sys.version_info < (3, 13):
                reason = "perf JIT mode requires Python 3.13+"
            elif not jit_perf_version_supported(version):
                reason = "perf JIT fix not established by version; see Python 3.13 perf documentation"
            flags, extra, unwind = ["-X", "perf_jit"], ["-k", "1"], "dwarf,16384"
        else:
            raise ValueError("Unknown Python/perf mode")
        info["unavailable_reason"] = reason
        dump(out / "python-perf-mode.json", info)
        if reason:
            print("Python/perf profile unavailable:", reason, flush=True)
            return out, False
    ok = perf_gated(["perf", "record", "-P", "-e", "cpu-clock:u", "-F", str(c["sample_frequency"]),
                     "--call-graph", unwind, "-o", str(out / "perf.data")] + extra,
                    bench, source, out, c, "perf-record", python_flags=flags)
    if not ok:
        dump(out / "native-status.json", {"recorded": False, "postprocessed": False,
             "human_review_required": True, "reason": "Gated recording failed; inspect collection.json"})
        if python_mode:
            info["unavailable_reason"] = "Recording or gated workload failed; inspect collection.json and perf-record.stderr.txt"
            dump(out / "python-perf-mode.json", info)
        print("Native profile unavailable; see collection.json and perf-record.stderr.txt.", flush=True)
        return out, False
    data = out / "perf.data"
    command(["perf", "buildid-list", "-i", str(data), "--with-hits"], out,
            "buildids", stdout_path=out / "buildids.txt", timeout=60)
    if python_mode == "jit":
        # JIT injection creates ELF sidecars: contain them in this run directory.
        rc = command(["perf", "inject", "-i", str(data), "--jit", "-o", str(out / "perf.jit.data")],
                     out, "jit-inject", cwd=out)
        if rc:
            info["unavailable_reason"] = "JIT injection failed; inspect jit-inject.stderr.txt"
            dump(out / "python-perf-mode.json", info)
            return out, False
        data = out / "perf.jit.data"
    for args, name, filename in [
        (["--header-only"], "header", "perf-header.txt"),
        (["--no-children", "-g", "none", "--percent-limit", "0.5", "--sort", "comm,dso,symbol"], "self", "native-self.txt"),
        ([], "callgraph", "native-callgraph.txt")]:
        require(command(["perf", "report", "-i", str(data), "--stdio"] + args,
                        out, name, stdout_path=out / filename), "perf report failed")
    require(command(["perf", "script", "-i", str(data), "-F", "+period"], out, "stacks",
                    stdout_path=out / "native-stacks.txt"), "perf script failed")
    fg = ROOT / "vendor" / "FlameGraph"
    for filename in ("stackcollapse-perf.pl", "flamegraph.pl"):
        if not (fg / filename).is_file():
            raise RuntimeError("Bundled FlameGraph file missing: " + filename)
    require(command(["perl", str(fg / "stackcollapse-perf.pl"), str(out / "native-stacks.txt")],
                    out, "collapse", stdout_path=out / "native.folded"), "Stack folding failed")
    require(command(["perl", str(fg / "flamegraph.pl"), "--countname", "ns",
                     "--title", bench + " native CPU profile", str(out / "native.folded")],
                    out, "flamegraph", stdout_path=out / "native.svg"), "Flame graph failed")
    require(command([PY, str(TOOLS / "stack_health.py"), "--folded", str(out / "native.folded"),
                     "--report", str(out / "native-callgraph.txt"), "--output", str(out / "stack-health.json")],
                    out, "stack-health"), "Stack review failed")
    health = json.loads((out / "stack-health.json").read_text())
    valid_output = (health["folded"]["total_period_weight"] > 0 and
                    health["folded"]["malformed_line_count"] == 0 and
                    "<svg" in (out / "native.svg").read_text())
    dump(out / "native-status.json", {"recorded": True, "postprocessed": valid_output,
         "human_review_required": True, "stack_review_status": health["status"],
         "stack_review_reasons": health["reasons"], "flamegraph_source": "perf record / perf script",
         "event": "cpu-clock:u", "width_unit": "nanoseconds of event period",
         "note": "A rendered graph is not automatically certified as valid ancestry."})
    if not valid_output:
        return out, False
    print("Inspect stack-health.json and native.svg before interpreting callers.", flush=True)
    if python_mode:
        frames_seen = "py::" in (out / "native.folded").read_text()
        info.update(available=frames_seen, python_frames_observed=frames_seen,
                    unavailable_reason=None if frames_seen else "No Python trampoline frames observed",
                    stack_review="Required even when Python names appear; not automatically certified.")
        dump(out / "python-perf-mode.json", info)
        return out, frames_seen
    return out, True


def python_profile(bench, variant, c):
    out = new_run(bench + "-" + variant + "-python")
    source = snapshot(bench, variant, out, c)
    argv = pinned(driver(bench, source, out, c) + ["--cprofile", str(out / "python.pstats")], c)
    require(command(argv, out, "cprofile", c["command_timeout_seconds"]), "Python profiling failed")
    receipt = json.loads((out / "workload.json").read_text())
    issues = receipt_issues(receipt, bench, source, c)
    if issues:
        raise RuntimeError("cProfile workload validation failed: " + "; ".join(issues))
    import pstats
    pstats.Stats(str(out / "python.pstats"))  # Reject an empty/truncated capture.
    return out


def pyspy_executable():
    return Path(PY).parent / "py-spy"


def pyspy_profile(bench, variant, c):
    out = new_run(bench + "-" + variant + "-pyspy")
    source = snapshot(bench, variant, out, c)
    binary = pyspy_executable()
    status = {"available": False, "sampling_hz": c["pyspy"]["rate"], "required_version": "0.4.2",
              "scope": "Whole fixed-work driver process: imports, in-process warmup, benchmark calls and receipt writing. NOT perf-gated.",
              "measurement": "Separate statistical Python profile; not timing or a PMU measurement.",
              "sample_policy": "py-spy defaults: active-thread heuristic, no GIL-only filter, no native extension unwinding",
              "unavailable_reason": None}
    def finish(reason=None):
        status["unavailable_reason"] = reason
        dump(out / "pyspy-status.json", status)
        (out / "README.md").write_text("# Python sampling profile\n\n" + status["scope"] + "\n\n" +
            status["measurement"] + "\n\n" + (reason or
            "Inspect python-sampled.svg and python-sampled.folded. Widths count samples, not function calls or nanoseconds.") +
            "\n\npython-sampled.svg retains startup/warmup. python-measured.svg selects stacks containing the measured-call wrapper. "
            "Widths count samples, not calls. This selection is supplementary and is not perf gating.\n")
        print("Python sampling:", reason or "SVG and raw folded samples saved", flush=True)
        return out, status["available"]
    if not binary.is_file():
        return finish("Pinned py-spy is not installed; run scripts/00_setup.sh with INSTALL_PYSPY=1.")
    rc = command([str(binary), "--version"], out, "pyspy-version", timeout=15)
    version = (out / "pyspy-version.stdout.txt").read_text().strip()
    status["version"] = version
    if rc or version != "py-spy 0.4.2":
        return finish("Unexpected py-spy version; install requirements-profile.txt.")
    raw = out / "python-sampled.folded"
    argv = [str(binary), "record", "--rate", str(c["pyspy"]["rate"]), "--full-filenames", "--format", "raw",
            "--output", str(raw), "--"] + driver(bench, source, out, c)
    # Pin sampler and child together when affinity is requested; record this choice.
    rc = command(pinned(argv, c), out, "pyspy", c["command_timeout_seconds"])
    try:
        receipt = json.loads((out / "workload.json").read_text())
        contents = raw.read_text()
    except (OSError, ValueError):
        receipt, contents = {}, ""
    def log(name):
        path = out / name
        return path.read_text() if path.is_file() else ""
    assessment, roi = assess_python_capture(rc, log("pyspy.stdout.txt"), log("pyspy.stderr.txt"),
        contents, receipt_issues(receipt, bench, source, c), (TOOLS / "workload.py").resolve())
    status.update(assessment)
    status["driver_sha256"] = digest(TOOLS / "workload.py")
    if not assessment["usable"]:
        return finish("Capture validation failed: " + "; ".join(assessment["errors"]))
    status["sample_count_warning"] = "Few measured samples; rankings may be unstable" if assessment["measured_sample_count"] < 1000 else None
    roi_path = out / "python-measured.folded"
    roi_path.write_text(roi)
    for name, path, title in (("python-sampled", raw, "includes startup/warmup"),
                              ("python-measured", roi_path, "measured-call stacks only")):
        rc = command(["perl", str(ROOT / "vendor/FlameGraph/flamegraph.pl"), "--countname", "samples",
                      "--title", bench + " supplementary Python sampling (" + title + ")", str(path)],
                     out, name + "-flamegraph", stdout_path=out / (name + ".svg"))
        if rc:
            return finish("Raw samples saved, but SVG generation failed; inspect " + name + "-flamegraph.stderr.txt")
    status["available"] = True
    return finish()


def correctness(bench, c):
    out = new_run(bench + "-correctness")
    # Helper output must be a new directory. Bind check to frozen copies.
    for variant in ("baseline", "optimized"):
        shutil.copytree(ROOT / "src" / variant / bench, out / variant,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    p = workload_params(c)
    argv = [PY, str(TOOLS / "correctness.py"), "--benchmark", bench,
            "--baseline", str(out / "baseline" / "run_benchmark.py"),
            "--optimized", str(out / "optimized" / "run_benchmark.py"),
            "--iterations", str(p["iterations"]), "--width", str(p["width"]),
            "--height", str(p["height"]), "--output", str(out / "check")]
    require(command(argv, out, "correctness", c["command_timeout_seconds"]), "Correctness check failed")
    return out / "check" / "correctness.json"


def compare(bench, c):
    evidence = correctness(bench, c)
    baseline, optimized = [], []
    for round_number in range(c["compare_rounds"]):
        order = ("baseline", "optimized") if round_number % 2 == 0 else ("optimized", "baseline")
        results = {}
        for variant in order:
            results[variant] = timing(bench, variant, c)
        baseline.append(results["baseline"])
        optimized.append(results["optimized"])
    out = new_run(bench + "-comparison")
    argv = [PY, str(TOOLS / "compare_results.py"), "--correctness", str(evidence),
            "--output", str(out / "summary")]
    for base, opt in zip(baseline, optimized):
        argv += ["--baseline", str(base), "--optimized", str(opt)]
    rc = command(argv, out, "compare", c["command_timeout_seconds"])
    source_diff(baseline[0] / "source", optimized[0] / "source", out)
    dump(out / "rounds.json", {"ordering": "AB, BA repeated; reduces order bias but cannot remove host interference",
         "rounds": [{"round": i + 1, "baseline": str(a), "optimized": str(b)}
                    for i, (a, b) in enumerate(zip(baseline, optimized))],
         "correctness": str(evidence), "comparison_exit": rc})
    print("Comparison exit:", rc, "(0=gate met; 3=below gate; 2=incompatible)", flush=True)
    return rc


def diagnose(c, raw_intel=False, reference_cycles=False):
    out = new_run("environment-and-pmu-diagnostics")
    dump(out / "interpreter.json", interpreter())
    dump(out / "packages.json", packages())
    for argv, name in [(["lscpu"], "lscpu"), (["uname", "-a"], "uname"),
                       (["perf", "--version"], "perf-version"), (["perf", "list", "--details"], "perf-list"),
                       (["dmesg"], "dmesg")]:
        command(argv, out, name, timeout=30)
    for path in ("/proc/sys/kernel/nmi_watchdog", "/proc/sys/kernel/perf_event_paranoid",
                 "/proc/sys/kernel/perf_event_max_stack", "/proc/cpuinfo"):
        try:
            (out / Path(path).name).write_text(Path(path).read_text())
        except OSError as exc:
            (out / (Path(path).name + ".unavailable.txt")).write_text(str(exc))
    busy = [PY, "-c", "x=0\nfor i in range(20_000_000):\n x=(x+i)&0xffffffff\nprint(x)"]
    probes = [("cycles-alone", "cycles:u"), ("instructions-alone", "instructions:u"),
              ("pair", "{cycles:u,instructions:u}"), ("software", "task-clock")]
    if raw_intel:
        probes.append(("raw-intel-cycles", "cpu/event=0x3c,umask=0x00/u"))
    if reference_cycles:
        probes.append(("reference-cycles", "{ref-cycles:u,instructions:u}"))
    results = []
    for name, selection in probes:
        csv_path = out / (name + ".csv")
        rc = command(["perf", "stat", "-v", "-x", ";", "--no-big-num", "-o", str(csv_path),
                      "-e", selection, "--"] + pinned(busy, c), out, name, c["command_timeout_seconds"])
        events = parse_stat(csv_path)
        diagnostic = (out / (name + ".stderr.txt")).read_text() + (csv_path.read_text() if csv_path.exists() else "")
        result = {"probe": name, "selection": selection, "returncode": rc, "events": events,
                  "status": probe_status(rc, diagnostic, events)}
        if name == "reference-cycles":
            ratio = stat_metrics(events, ("instructions", "ref-cycles", "instructions_per_reference_cycle", 1), rc == 0)
            result["instructions_per_reference_cycle"] = ratio["instructions_per_reference_cycle"]
            result["note"] = "Distinct diagnostic throughput; NOT core-cycle IPC. No substitution is performed."
        results.append(result)
    report = {"probes": results, "have_perf_trampoline": bool(sysconfig.get_config_var("HAVE_PERF_TRAMPOLINE")),
              "frame_pointer_flag_present": "-fno-omit-frame-pointer" in (sysconfig.get_config_var("CFLAGS") or ""),
              "note": "Probes include startup and test sanity, not PMU fidelity or benchmark bottlenecks. Build flags do not prove valid stacks."}
    dump(out / "capabilities.json", report)
    lines = ["# Environment / PMU capability probes", "", report["note"], "",
             "| Probe | Event selection | Result |", "|---|---|---|"]
    lines += [f"| {r['probe']} | {r['selection']} | {r['status']} |" for r in results]
    lines += ["", "Each probe retains CSV, stdout/stderr, command and exit status. "
              "Reference cycles, when explicitly requested, are a separate diagnostic and never replace IPC.", ""]
    (out / "capabilities.md").write_text("\n".join(lines))
    print("No watchdog, permissions or VM settings were changed.", flush=True)
    return out


def topdown(bench, variant, c, cpu):
    out = new_run(bench + "-" + variant + "-topdown-systemwide")
    source = snapshot(bench, variant, out, c)
    # Explicit user invocation; never part of default pipeline.
    scoped = dict(c, affinity=str(cpu))
    ok = perf_gated(["perf", "stat", "-a", "-C", str(cpu), "--topdown",
                     "-o", str(out / "topdown.txt")], bench, source, out, scoped, "topdown",
                     scope="SYSTEM-WIDE on guest CPU " + str(cpu) + "; other tasks included")
    dump(out / "scope.json", {"scope": "SYSTEM-WIDE on guest CPU " + str(cpu),
         "warning": "Other tasks and kernel work on this CPU are included, even with one vCPU.",
         "collection_completed": ok,
         "interpretation": "Completion is not validation of PMU/top-down metrics. Inspect output."})
    return out, ok


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("preflight")
    sub.add_parser("gate-probe", help="Short real perf stat and record FIFO smoke tests")
    diag = sub.add_parser("diagnose")
    diag.add_argument("--raw-intel-cycles", action="store_true",
                      help="Only after verifying that Intel raw event 0x3c/0 maps correctly on this CPU.")
    diag.add_argument("--reference-cycles", action="store_true", help="Separate reference-cycle diagnostic; never substitutes for IPC.")
    for action in ("time", "stat", "native", "python", "pyspy", "python-perf", "all", "topdown"):
        p = sub.add_parser(action)
        p.add_argument("benchmark", choices=BENCHMARKS)
        p.add_argument("variant", choices=("baseline", "optimized"), nargs="?", default="baseline")
        if action == "topdown":
            p.add_argument("--cpu", type=int, required=True)
        if action == "python-perf":
            p.add_argument("--mode", choices=("map", "jit"), required=True)
    for action in ("compare", "check"):
        p = sub.add_parser(action)
        p.add_argument("benchmark", choices=BENCHMARKS)
    p = sub.add_parser("interpret")
    p.add_argument("json_file", type=Path)
    args = parser.parse_args()
    preflight()
    c = config()
    if args.action == "preflight":
        print("Preflight passed:", PY, "; baseline source hashes match pinned upstream.")
        return 0
    if args.action == "gate-probe":
        return 0 if gate_probe(c)[1] else 3
    if args.action in ("stat", "native", "python-perf", "topdown"):
        probe_dir, passed = gate_probe(c)
        if not passed:
            print("Perf gate preflight failed; long collection skipped. Inspect " + str(probe_dir), flush=True)
            return 3
    if args.action == "diagnose":
        diagnose(c, args.raw_intel_cycles, args.reference_cycles)
        return 0
    if args.action == "interpret":
        out = new_run("interpret")
        for action in ("metadata", "check", "stats", "hist", "dump"):
            require(command([PY, "-m", "pyperf", action, str(args.json_file.resolve())],
                            out, action, timeout=60), "pyperf " + action + " failed")
        return 0
    if args.action == "compare":
        return compare(args.benchmark, c)
    if args.action == "check":
        correctness(args.benchmark, c)
        return 0
    if args.action == "topdown":
        if args.cpu < 0:
            raise ValueError("cpu must be nonnegative")
        return 0 if topdown(args.benchmark, args.variant, c, args.cpu)[1] else 3
    if args.action == "time":
        timing(args.benchmark, args.variant, c)
        return 0
    if args.action == "python":
        python_profile(args.benchmark, args.variant, c)
        return 0
    if args.action == "pyspy":
        return 0 if pyspy_profile(args.benchmark, args.variant, c)[1] else 3
    if args.action == "python-perf":
        return 0 if native(args.benchmark, args.variant, c, args.mode)[1] else 3
    if args.action == "stat":
        return 0 if stat(args.benchmark, args.variant, c)[1] else 3
    if args.action == "native":
        return 0 if native(args.benchmark, args.variant, c)[1] else 3
    # Finish Python attribution before optional native tooling can fail.
    t = timing(args.benchmark, args.variant, c)
    p = python_profile(args.benchmark, args.variant, c)
    errors = {}
    s = n = sampled = capabilities = None
    stat_ok = native_ok = sampled_ok = False
    try:
        capabilities = diagnose(c)
    except (OSError, ValueError, RuntimeError) as exc:
        errors["diagnose"] = str(exc)
    stages = [("pyspy", pyspy_profile)] if c["pyspy"]["enabled"] else []
    probe_dir, gate_ok = gate_probe(c)
    if gate_ok:
        stages += [("stat", stat), ("native", native)]
    else:
        errors["gate_probe"] = "Failed; stat/native skipped. Inspect " + str(probe_dir)
    for action, fn in stages:
        try:
            path, ok = fn(args.benchmark, args.variant, c)
            if action == "stat":
                s, stat_ok = path, ok
            elif action == "native":
                n, native_ok = path, ok
            else:
                sampled, sampled_ok = path, ok
        except (OSError, ValueError, RuntimeError) as exc:
            errors[action] = str(exc)
            print("Optional profiling failed:", action, exc, flush=True)
    status = {"timing": str(t), "stat": str(s) if s else None, "native": str(n) if n else None, "python": str(p),
              "pyspy": str(sampled) if sampled else None, "capabilities": str(capabilities) if capabilities else None,
              "pyspy_enabled": c["pyspy"]["enabled"], "pyspy_completed": sampled_ok,
              "perf_stat_all_requested_events_usable": stat_ok, "perf_record_completed": native_ok,
              "perf_gate_probe": str(probe_dir), "profiling_errors": errors,
              "course_completion": "This legacy initial pipeline is not the stages1-3 deliverables check. Use scripts/13_course_stages.sh."}
    dump(t / "pipeline-summary.json", status)
    print(json.dumps(status, indent=2))
    return 0 if stat_ok and native_ok and (sampled_ok or not c["pyspy"]["enabled"]) and not errors else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError, importlib.metadata.PackageNotFoundError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        raise SystemExit(2)
