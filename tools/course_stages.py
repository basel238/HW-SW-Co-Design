#!/usr/bin/env python3
"""Collect first-three-stage evidence; native perf is required, py-spy supplementary."""
import argparse
import contextlib
import json
from pathlib import Path
import shutil
import sys

import pipeline as p
from course_reference import run_guide_reference, run_reference, selected_benchmarks
from friendly_results import write_view, archive_evidence, portable_status


NATIVE_FILES = ("perf.data", "native-self.txt", "native-callgraph.txt", "native-stacks.txt",
                "native.folded", "native.svg", "stack-health.json", "collection.json", "provenance.json")


def native_evidence(path):
    """Validate artifact presence, never equate an SVG with sound unwinding."""
    missing = [name for name in NATIVE_FILES if not (path / name).is_file() or (path / name).stat().st_size == 0]
    if missing:
        return {"available": False, "missing_files": missing, "human_stack_review": "pending"}
    try:
        health = json.loads((path / "stack-health.json").read_text())
        collection = json.loads((path / "collection.json").read_text())
        svg = (path / "native.svg").read_text()
        ok = collection.get("available") is True and "<svg" in svg and health.get("folded", {}).get("total_period_weight", 0) > 0
        return {"available": ok, "missing_files": [], "stack_health": health.get("status"),
                "stack_warnings": health.get("reasons", []), "human_stack_review": "pending",
                "flame_graph_source": "perf record -> perf script -> stackcollapse-perf.pl -> flamegraph.pl"}
    except (OSError, ValueError, TypeError) as exc:
        return {"available": False, "error": str(exc), "human_stack_review": "pending"}


def collect_stages(c, args, out):
    benches = selected_benchmarks(args.benchmark)
    status = {"schema_version": 1, "benchmarks": {}, "required_missing": [], "optional_warnings": [],
              "release_only": args.release_only, "automated_collection_complete": False,
              "coursework_complete": False, "manual_review": "pending",
              "scope": "Stages 1-3 baseline only: code understanding, runtime and profiling/bottleneck evidence. No optimization.",
              "guide_interpretation": "Default includes separately labelled python3-dbg evidence; release-only explicitly defers that guide requirement.",
              "manual_tasks": ["Review both stage-1 explanations and cite the selected frozen sources.",
                               "Record the actual VM/host settings in ENVIRONMENT.md.",
                               "Inspect native graphs, self tables, sample loss and stack-health warnings.",
                               "Write benchmark-specific bottleneck conclusions using the new evidence; distinguish hypotheses from measured causes."]}

    def collect(name, function, required=True):
        print("Collecting:", name, flush=True)
        before = set(p.RUN_ROOT.iterdir())
        try:
            with (out / "details" / "progress.log").open("a") as log, contextlib.redirect_stdout(log):
                result = function()
            path, ok = result if isinstance(result, tuple) else (result, True)
            record = {"path": str(path), "available": bool(ok)}
        except (OSError, ValueError, RuntimeError) as exc:
            created = [path for path in set(p.RUN_ROOT.iterdir()) - before if path.is_dir()]
            record = {"path": str(created[0]) if len(created) == 1 else None,
                      "available": False, "error": str(exc)}
        if not record["available"]:
            status["required_missing" if required else "optional_warnings"].append(name)
        # Retain incremental results if a later command is interrupted.
        status.setdefault("actions", {})[name] = record
        p.dump(out / "details" / "course-summary.json", status)
        print("  " + ("done" if record["available"] else "unavailable — saved diagnostics"), flush=True)
        return record

    status["gate_probe"] = collect("perf enable/disable smoke test", lambda: p.gate_probe(c))
    status["framework_reference"] = collect("release pyperformance framework reference",
                                           lambda: run_reference(c, args.benchmark))
    for bench in benches:
        record = {}
        status["benchmarks"][bench] = record
        doc = p.ROOT / "docs" / ("stage1-" + bench + ".md")
        record["source_review"] = {"path": str(doc), "available": doc.is_file(), "review": "human review pending"}
        if doc.is_file():
            record["source_review"]["sha256"] = p.digest(doc)
        else:
            status["required_missing"].append(bench + " source-understanding document")
        record["timing"] = collect(bench + " release timing", lambda b=bench: p.timing(b, "baseline", c))
        # Required native work is attempted independently of every supplementary
        # sampler/counter stage. A py-spy SVG cannot satisfy this requirement.
        if status["gate_probe"]["available"]:
            record["native"] = collect(bench + " release perf profile", lambda b=bench: p.native(b, "baseline", c))
        else:
            record["native"] = {"available": False, "skipped": True, "reason": "Perf gate probe failed; repair it before a long recording."}
            status["required_missing"].append(bench + " release perf profile")
            status.setdefault("actions", {})[bench + " release perf profile"] = record["native"]
        if record["native"].get("path"):
            evidence = native_evidence(Path(record["native"]["path"]))
            record["native"].update(evidence)
            if not evidence["available"] and bench + " release perf profile" not in status["required_missing"]:
                status["required_missing"].append(bench + " release perf profile")
        record["python_calls"] = collect(bench + " cProfile (supplementary)", lambda b=bench: p.python_profile(b, "baseline", c), False)
        if not args.skip_python_sampling and c["pyspy"]["enabled"]:
            record["python_sampling"] = collect(bench + " py-spy (supplementary)", lambda b=bench: p.pyspy_profile(b, "baseline", c), False)
        else:
            record["python_sampling"] = {"available": False, "skipped": True, "reason": "Explicitly disabled supplementary sampling."}
        if not args.skip_optional_counters and status["gate_probe"]["available"]:
            record["counters"] = collect(bench + " hardware/software counters (supplementary)", lambda b=bench: p.stat(b, "baseline", c), False)
        else:
            record["counters"] = {"available": False, "skipped": True,
                                   "reason": "Explicitly skipped or gate probe failed. IPC/top-down are not substituted."}
    if not args.release_only and status["gate_probe"]["available"]:
        status["guide_debug_reference"] = collect("separate guide python3-dbg reference",
                                                  lambda: run_guide_reference(c, args.benchmark))
    elif not args.release_only:
        status["guide_debug_reference"] = {"available": False, "skipped": True,
                                           "reason": "Perf gate probe failed; guide collection deferred until repaired."}
        status["required_missing"].append("separate guide python3-dbg reference")
        status.setdefault("actions", {})["separate guide python3-dbg reference"] = status["guide_debug_reference"]
    else:
        status["guide_debug_reference"] = {"available": False, "explicitly_deferred": True,
                                            "reason": "--release-only chosen; this is not full literal guide compliance."}
    status["automated_collection_complete"] = not status["required_missing"]
    status["literal_guide_collection_complete"] = status["automated_collection_complete"] and not args.release_only
    # A machine cannot certify the student's interpretation or stack ancestry.
    status["coursework_complete"] = False
    return status


def run(c, args):
    out = p.new_run("run")
    details = out / "details"
    details.mkdir()
    previous = p.RUN_ROOT
    p.RUN_ROOT = details
    try:
        toolkit = details / "toolkit"
        toolkit.mkdir()
        for name in ("tools", "scripts", "docs", "vendor", "licenses"):
            shutil.copytree(p.ROOT / name, toolkit / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for name in ("SOURCES.json", "ENVIRONMENT.md", "requirements.txt", "requirements-course.txt", "requirements-profile.txt"):
            shutil.copy2(p.ROOT / name, toolkit / name)
        p.dump(toolkit / "config.json", c)
        try:
            status = collect_stages(c, args, out)
        except KeyboardInterrupt:
            checkpoint = details / "course-summary.json"
            status = json.loads(checkpoint.read_text()) if checkpoint.is_file() else {
                "benchmarks": {}, "required_missing": [], "optional_warnings": [], "manual_tasks": []}
            status["required_missing"].append("run interrupted")
            status.update(automated_collection_complete=False, literal_guide_collection_complete=False,
                          coursework_complete=False, interrupted=True)
        p.dump(details / "course-summary.json", status)
        write_view(out, status)
        print("Packing and verifying raw evidence…", flush=True)
        status["evidence"] = archive_evidence(out, keep_details=args.keep_details)
        p.dump(out / "summary.json", portable_status(status, out))
    finally:
        p.RUN_ROOT = previous
    print("Open:", out / "README.md", flush=True)
    print("Required collection:", "complete" if status["automated_collection_complete"] else "INCOMPLETE",
          "; interpretation still needs review.", flush=True)
    return 0 if status["automated_collection_complete"] else 3



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", choices=p.BENCHMARKS, help="Default: collect both benchmarks")
    parser.add_argument("--release-only", action="store_true", help="Explicitly defer literal guide python3-dbg reference; not full guide compliance")
    parser.add_argument("--skip-optional-counters", action="store_true", help="Skip supplementary PMU stat passes; native perf remains required")
    parser.add_argument("--skip-python-sampling", action="store_true", help="Skip supplementary py-spy; native perf remains required")
    parser.add_argument("--keep-details", action="store_true", help="Keep expanded raw evidence as well as the verified evidence ZIP")
    args = parser.parse_args()
    p.preflight()
    return run(p.config(), args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        raise SystemExit(2)
