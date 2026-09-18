"""Presentation and provenance helpers; never substitute missing measurements."""
import difflib
import hashlib
import json
import re
import statistics
from pathlib import Path


def write_counter_summary(out, runs):
    lines = ["# Hardware-counter summary", "",
             "Each group/repeat measures the same configured useful work after warmup. "
             "Ratios use only simultaneous events within that run. Counts include small driver/boundary costs.", "",
             "A passed scheduling/count sanity check does not validate virtual-PMU semantics. "
             "Generic-cache MPKI is not DRAM MPKI. Missing IPC stays unavailable.", "",
             "| Group / repeat | Event | Count | Unit | Running % | Per call | Status |",
             "|---|---|---:|---|---:|---:|---|"]
    def fmt(value):
        return "unavailable" if value is None else f"{value:.6g}"
    for run in runs:
        if not run["events"]:
            lines.append(f"| {run['group']} / {run['repeat']} | no events | unavailable | | | | collection failed; inspect logs |")
        for name, event in run["events"].items():
            lines.append(f"| {run['group']} / {run['repeat']} | {name} | {fmt(event['count'])} | "
                         f"{event['unit'] or 'count'} | {fmt(event['running_percent'])} | "
                         f"{fmt(event.get('per_benchmark_call'))} | {event['status']} |")
    lines += ["", "## Ratios by repetition", "",
              "| Group / repeat | Metric | Value | Unavailability reason |", "|---|---|---:|---|"]
    metrics = ("ipc", "cpi", "branch_miss_percent", "generic_cache_miss_percent", "l1_miss_percent",
               "branch_mpki", "generic_cache_mpki", "l1_load_mpki")
    values = {}
    for run in runs:
        for key in metrics:
            if key in run:
                lines.append(f"| {run['group']} / {run['repeat']} | {key} | {fmt(run[key])} | "
                             f"{run.get('ratio_unavailable_reason') or ''} |")
                if run[key] is not None:
                    values.setdefault(key, []).append(run[key])
    lines += ["", "## Descriptive spread of usable ratios", "",
              "These medians/ranges are not confidence intervals or ratios of counts pooled across passes.", "",
              "| Metric | Usable repetitions | Median | Min | Max |", "|---|---:|---:|---:|---:|"]
    for key, numbers in values.items():
        lines.append(f"| {key} | {len(numbers)} | {fmt(statistics.median(numbers))} | {fmt(min(numbers))} | {fmt(max(numbers))} |")
    lines += ["", "IPC: instructions/core cycles; CPI: core cycles/instruction. MPKI: misses per 1,000 instructions. "
              "No reference-cycle substitution is used. Percent metrics use the matching reference event.", "",
              "The matching raw CSV, collection status, workload receipt and logs are in each group/repeat directory.", ""]
    (Path(out) / "stat-summary.md").write_text("\n".join(lines))


def source_diff(base, opt, out):
    """Diff the actual first paired snapshots, not mutable working copies."""
    def files(root):
        return {p.relative_to(root).as_posix(): p for p in Path(root).rglob("*")
                if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    a, b = files(base), files(opt)
    changes, chunks = [], []
    for name in sorted(a.keys() | b.keys()):
        left = a[name].read_bytes() if name in a else None
        right = b[name].read_bytes() if name in b else None
        if left == right:
            continue
        changes.append({"path": name, "change": "added" if left is None else "removed" if right is None else "modified",
                        "baseline_sha256": hashlib.sha256(left).hexdigest() if left is not None else None,
                        "optimized_sha256": hashlib.sha256(right).hexdigest() if right is not None else None})
        try:
            if b"\0" in (left or b"") + (right or b""):
                raise UnicodeError
            x, y = (left or b"").decode("utf-8"), (right or b"").decode("utf-8")
        except UnicodeError:
            chunks.append(f"Binary file changed: {name}\n")
        else:
            for line in difflib.unified_diff(x.splitlines(keepends=True), y.splitlines(keepends=True),
                          fromfile="baseline/" + name if left is not None else "/dev/null",
                          tofile="optimized/" + name if right is not None else "/dev/null"):
                chunks.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
    Path(out, "source.diff").write_text("".join(chunks) or "# Source trees are identical.\n")
    Path(out, "source-changes.json").write_text(json.dumps({"baseline_snapshot": str(base),
        "optimized_snapshot": str(opt), "note": "First paired snapshots; comparator checks consistency across rounds.",
        "changes": changes}, indent=2) + "\n")


def probe_status(returncode, diagnostic, events):
    text = diagnostic.lower()
    if returncode == 127 and not events:
        return "tool_missing_or_not_executable"
    if any(s in text for s in ("permission", "access to performance monitoring", "operation not permitted")):
        return "permission_denied"
    if any(s in text for s in ("not supported", "unknown tracepoint", "event syntax error")):
        return "unsupported_event_or_syntax"
    if returncode:
        return "probe_failed"
    if not events:
        return "no_parseable_events"
    if any(e.get("count") is None for e in events.values()):
        return "event_unavailable"
    if any(e["count"] <= 0 for e in events.values()):
        return "zero_on_busy_workload"
    if any(e.get("running_percent") is None for e in events.values()):
        return "running_fraction_unknown"
    if any(e["running_percent"] < 95 for e in events.values()):
        return "insufficient_running_fraction"
    return "count_and_scheduling_sanity_passed"


def jit_perf_version_supported(version):
    """Conservative official-version gate; actual recording must still succeed.

    Permit >6.8 and the explicitly documented 6.7.2+ backport. Do not read
    distro '-3' suffixes as upstream patch versions. Unknown backports require
    a newer known-compatible tool, not a silent override.
    """
    match = re.search(r"\bperf version (\d+)\.(\d+)(?:\.(\d+))?", version)
    if not match:
        return False
    major, minor, patch = (int(x or 0) for x in match.groups())
    return (major, minor) > (6, 8) or ((major, minor) == (6, 7) and patch >= 2)
