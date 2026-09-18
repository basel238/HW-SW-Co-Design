#!/usr/bin/env python3
"""Compare paired, independently timed source variants with explicit evidence gates.

The bootstrap resamples whole worker means independently for each variant. It
quantifies variation among these workers, not unmeasured environmental bias.
pyperf's comparison is retained as supporting output; its exit status is never
used as evidence of a 7% improvement.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import subprocess
import sys
from pathlib import Path


BOOTSTRAP_REPLICATES = 2000
BOOTSTRAP_SEED = 20260917
MINIMUM_REDUCTION = 0.07
INTERPRETER_KEYS = (
    "real_executable", "executable_sha256", "version", "py_debug", "compiler",
    "cflags", "config_args",
)
TIMING_KEYS = ("processes", "values", "warmups", "loops", "affinity")
MACHINE_KEYS = ("platform", "cpu_model", "cpu_count")
UNCERTAINTY_NOTE = (
    "95% percentile bootstrap intervals use independent resampling of whole "
    "worker means (2,000 replicates per round). They are conditional on the "
    "measured workers and do not include environmental systematic error, "
    "correlated host/VM interference, or drift between runs. A positive lower "
    "bound supports improvement; it does not prove a reduction of at least 7%."
)


class EvidenceError(ValueError):
    """Inputs cannot support a valid comparison."""


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EvidenceError(f"Cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise EvidenceError(f"Expected a JSON object in {path}")
    return data


def require_keys(value: object, keys: tuple, label: str) -> dict:
    if not isinstance(value, dict):
        raise EvidenceError(f"{label} must be an object")
    missing = [key for key in keys if key not in value]
    if missing:
        raise EvidenceError(f"{label} is missing: {', '.join(missing)}")
    return value


def require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        c not in "0123456789abcdef" for c in value.lower()
    ):
        raise EvidenceError(f"{label} must be a SHA-256 hex digest")
    return value.lower()


def positive_int(value: object, label: str, allow_zero: bool = False) -> int:
    if type(value) is not int or value < (0 if allow_zero else 1):
        raise EvidenceError(f"{label} must be {'nonnegative' if allow_zero else 'positive'} integer")
    return value


def provenance_signature(provenance: dict, label: str) -> dict:
    require_keys(provenance, (
        "benchmark", "variant", "source_sha256", "source_tree_sha256", "interpreter",
        "packages", "workload", "timing", "machine", "toolkit_sha256",
    ), label)
    if provenance["benchmark"] not in ("nbody", "raytrace"):
        raise EvidenceError(f"{label}: benchmark must be nbody or raytrace")
    for key in ("source_sha256", "source_tree_sha256", "toolkit_sha256"):
        require_sha(provenance[key], f"{label}.{key}")
    interpreter = require_keys(provenance["interpreter"], INTERPRETER_KEYS, f"{label}.interpreter")
    require_sha(interpreter["executable_sha256"], f"{label}.interpreter.executable_sha256")
    timing = require_keys(provenance["timing"], TIMING_KEYS, f"{label}.timing")
    for key in ("processes", "values", "loops"):
        positive_int(timing[key], f"{label}.timing.{key}")
    positive_int(timing["warmups"], f"{label}.timing.warmups", allow_zero=True)
    if timing["loops"] != 1:
        raise EvidenceError(f"{label}: this fixed-work comparison requires timing.loops=1")
    if timing["processes"] < 2:
        raise EvidenceError(f"{label}: at least two measured workers are required for uncertainty")
    if timing["affinity"] is not None and not isinstance(timing["affinity"], str):
        raise EvidenceError(f"{label}.timing.affinity must be a string or null")
    workload = require_keys(provenance["workload"], (
        "iterations", "width", "height", "reference",
    ), f"{label}.workload")
    for key in ("iterations", "width", "height"):
        positive_int(workload[key], f"{label}.workload.{key}")
    if workload["reference"] != "sun":
        raise EvidenceError(f"{label}: expected the documented nbody reference 'sun'")
    machine = require_keys(provenance["machine"], MACHINE_KEYS, f"{label}.machine")
    packages = provenance["packages"]
    if not isinstance(packages, list) or not all(isinstance(item, str) for item in packages):
        raise EvidenceError(f"{label}.packages must be a list of pip-freeze lines")
    # A venv's executable spelling may differ; its resolved interpreter and hash
    # must still match. Source directories and output paths are not invariants.
    return {
        "benchmark": provenance["benchmark"],
        "interpreter": {key: interpreter[key] for key in INTERPRETER_KEYS},
        "packages": sorted(packages),
        "workload": workload,
        "timing": {key: timing[key] for key in TIMING_KEYS},
        "machine": {key: machine[key] for key in MACHINE_KEYS},
        "toolkit_sha256": provenance["toolkit_sha256"],
    }


def differing_fields(left: object, right: object, prefix: str = "") -> list:
    if isinstance(left, dict) and isinstance(right, dict):
        result = []
        for key in sorted(left.keys() | right.keys()):
            field = f"{prefix}.{key}" if prefix else key
            if key not in left or key not in right:
                result.append(field)
            else:
                result.extend(differing_fields(left[key], right[key], field))
        return result
    return [] if left == right else [prefix]


def validate_observed_source_and_workload(metadata: dict, provenance: dict, label: str) -> None:
    """Bind pyperf's own recorded workload to its external provenance sidecar."""
    expected = {
        "source_sha256": provenance["source_sha256"],
        "source_tree_sha256": provenance["source_tree_sha256"],
        "workload_benchmark": provenance["benchmark"],
        **{f"workload_{key}": provenance["workload"][key]
           for key in ("iterations", "width", "height", "reference")},
    }
    for key, value in expected.items():
        if key not in metadata:
            raise EvidenceError(f"{label}: pyperf metadata lacks required {key}; rerun using timing_runner.py")
        observed = metadata[key]
        if key.endswith("sha256"):
            observed = require_sha(observed, f"{label}.{key}")
            value = value.lower()
        if observed != value:
            raise EvidenceError(f"{label}: pyperf metadata {key} does not match provenance")


def load_run(directory: Path, variant: str) -> dict:
    provenance = read_json(directory / "provenance.json")
    signature = provenance_signature(provenance, str(directory / "provenance.json"))
    if provenance["variant"] != variant:
        raise EvidenceError(f"{directory}: expected variant={variant!r}, got {provenance['variant']!r}")
    raw = read_json(directory / "timing.json")
    benchmarks = raw.get("benchmarks")
    if not isinstance(benchmarks, list) or len(benchmarks) != 1:
        raise EvidenceError(f"{directory}/timing.json must contain exactly one benchmark")
    benchmark = benchmarks[0]
    if not isinstance(benchmark, dict):
        raise EvidenceError(f"{directory}/timing.json contains malformed benchmark data")
    metadata = dict(raw.get("metadata", {}))
    metadata.update(benchmark.get("metadata", {}))
    if metadata.get("name") != provenance["benchmark"]:
        raise EvidenceError(f"{directory}: pyperf benchmark name must exactly equal {provenance['benchmark']!r}")
    if metadata.get("unit", "second") != "second":
        raise EvidenceError(f"{directory}: timing unit must be second")
    measured = []
    for run in benchmark.get("runs", []):
        if not isinstance(run, dict):
            raise EvidenceError(f"{directory}: malformed pyperf run")
        effective_metadata = dict(metadata)
        effective_metadata.update(run.get("metadata", {}))
        validate_observed_source_and_workload(effective_metadata, provenance, str(directory))
        if effective_metadata.get("name") != provenance["benchmark"]:
            raise EvidenceError(f"{directory}: a worker has an unexpected benchmark name")
        if "values" not in run or not run["values"]:
            continue  # Calibration and warmup-only workers are not observations.
        if effective_metadata.get("loops", 1) != 1 or effective_metadata.get("inner_loops", 1) != 1:
            raise EvidenceError(f"{directory}: worker loop normalization differs from fixed-work configuration")
        values = run["values"]
        if not isinstance(values, list) or not all(
            type(value) in (int, float) and math.isfinite(value) and value > 0
            for value in values
        ):
            raise EvidenceError(f"{directory}: timing values must be finite positive seconds")
        if len(values) != provenance["timing"]["values"]:
            raise EvidenceError(f"{directory}: observed values per worker differ from provenance")
        measured.append(values)
    if len(measured) != provenance["timing"]["processes"]:
        raise EvidenceError(f"{directory}: observed {len(measured)} measured workers; expected {provenance['timing']['processes']}")
    flattened = [value for worker in measured for value in worker]
    worker_means = [statistics.mean(worker) for worker in measured]
    return {
        "directory": str(directory.resolve()),
        "provenance": provenance,
        "signature": signature,
        "pyperf_metadata": metadata,
        "worker_means": worker_means,
        "statistics": {
            "mean_seconds": statistics.mean(flattened),
            "sample_sd_seconds": statistics.stdev(flattened) if len(flattened) > 1 else None,
            "median_seconds": statistics.median(flattened),
            "minimum_seconds": min(flattened),
            "maximum_seconds": max(flattened),
            "measured_workers": len(measured),
            "measured_values": len(flattened),
            "worker_means_seconds": worker_means,
        },
    }


def percentile(sorted_values: list, fraction: float) -> float:
    position = (len(sorted_values) - 1) * fraction
    low = math.floor(position)
    high = math.ceil(position)
    return sorted_values[low] + (position - low) * (sorted_values[high] - sorted_values[low])


def bootstrap_interval(baseline: list, optimized: list, seed: int) -> tuple:
    rng = random.Random(seed)
    reductions = []
    for _ in range(BOOTSTRAP_REPLICATES):
        bmean = statistics.mean(rng.choices(baseline, k=len(baseline)))
        omean = statistics.mean(rng.choices(optimized, k=len(optimized)))
        reductions.append(1.0 - omean / bmean)
    reductions.sort()
    return percentile(reductions, 0.025), percentile(reductions, 0.975)


def meets_reduction_target(value: float) -> bool:
    # Avoid rejecting an exact decimal 7% because of binary rounding in 1-ratio.
    return value >= MINIMUM_REDUCTION or math.isclose(
        value, MINIMUM_REDUCTION, rel_tol=0, abs_tol=1e-12
    )


def validate_correctness(report: dict, baseline: list, optimized: list) -> None:
    benchmark = baseline[0]["provenance"]["benchmark"]
    if report.get("benchmark") != benchmark:
        raise EvidenceError("Correctness report is for a different or missing benchmark")
    if report.get("passed") is not True:
        raise EvidenceError("Correctness report does not explicitly record passed=true")
    for variant, runs in (("baseline", baseline), ("optimized", optimized)):
        for source_key in ("source_sha256", "source_tree_sha256"):
            key = f"{variant}_{source_key}"
            expected = require_sha(report.get(key), f"correctness.{key}")
            if any(run["provenance"][source_key].lower() != expected for run in runs):
                raise EvidenceError(f"Correctness report {key} does not match the measured source")
    parameters = report.get("parameters")
    if not isinstance(parameters, dict):
        raise EvidenceError("Correctness report must include tested workload parameters")
    workload = baseline[0]["provenance"]["workload"]
    required = ("iterations",) if benchmark == "nbody" else ("width", "height")
    for key in required:
        if key not in parameters:
            raise EvidenceError(f"Correctness report lacks the tested {key} parameter")
    for key in ("iterations", "width", "height", "reference"):
        if key in parameters and parameters[key] != workload[key]:
            raise EvidenceError(f"Correctness workload parameter {key} differs from the timed workload")


def pyperf_comparison(baseline: dict, optimized: dict, output: Path, index: int) -> dict:
    command = [sys.executable, "-m", "pyperf", "compare_to",
               str(Path(baseline["directory"]) / "timing.json"),
               str(Path(optimized["directory"]) / "timing.json"), "--table"]
    log = output / f"round-{index:02d}-pyperf.txt"
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        return {"command": command, "exit_code": result.returncode, "log": log.name,
                "used_for_gate": False}
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.write_text(str(exc) + "\n", encoding="utf-8")
        return {"command": command, "error": str(exc), "log": log.name, "used_for_gate": False}


def markdown(summary: dict) -> str:
    lines = ["# Benchmark comparison", "", f"**Status: {summary['status']}**", ""]
    if summary.get("error"):
        lines.extend([summary["error"], ""])
    if summary.get("benchmark"):
        lines.extend([f"Benchmark: `{summary['benchmark']}`", ""])
    rounds = summary.get("rounds", [])
    if rounds:
        lines += [
            "| Round | Baseline mean | Optimized mean | Runtime reduction | Bootstrap 95% interval | >=7% point estimate | Lower bound >0 |",
            "|---|---:|---:|---:|---:|---|---|",
        ]
        for entry in rounds:
            low, high = entry["runtime_reduction_ci95"]
            lines.append(
                f"| {entry['round']} | {entry['baseline']['mean_seconds'] * 1000:.3f} ms "
                f"| {entry['optimized']['mean_seconds'] * 1000:.3f} ms "
                f"| {entry['runtime_reduction'] * 100:.3f}% | [{low * 100:.3f}%, {high * 100:.3f}%] "
                f"| {'yes' if entry['meets_7_percent_point_estimate'] else 'no'} "
                f"| {'yes' if entry['positive_ci_lower_bound'] else 'no'} |"
            )
        lines += ["", "The reported percentage is **runtime reduction**, `1 - optimized / baseline`; "
                  "a 7% reduction corresponds to approximately 1.0753x speedup.", ""]
        for entry in rounds:
            lines += [f"## Round {entry['round']} distribution", "",
                      "| Variant | Sample SD | Median | Min | Max | Workers | Values |",
                      "|---|---:|---:|---:|---:|---:|---:|"]
            for variant in ("baseline", "optimized"):
                item = entry[variant]
                lines.append(
                    f"| {variant} | {item['sample_sd_seconds'] * 1000:.3f} ms "
                    f"| {item['median_seconds'] * 1000:.3f} ms "
                    f"| {item['minimum_seconds'] * 1000:.3f} ms "
                    f"| {item['maximum_seconds'] * 1000:.3f} ms "
                    f"| {item['measured_workers']} | {item['measured_values']} |"
                )
            lines += ["", "Worker means are retained in `summary.json`. Calibration and warmup values are excluded.", ""]
    lines += ["## Evidence gate", "",
              "A pass requires matching interpreter/build, packages, workload, timing configuration, machine and toolkit; "
              "source consistency within each variant; a successful correctness report matching entry-point and full source-tree hashes; different source trees; "
              "and, in **every paired round**, at least 7% mean runtime reduction with a strictly positive 95% interval lower bound.", "",
              "This gate does **not** claim that the confidence interval's lower bound is at least 7%. "
              "That stronger condition is separately recorded for each round in `summary.json`.", "",
              UNCERTAINTY_NOTE, "",
              "Each worker contributes a block of timing observations. Sample SD above describes the observed values, "
              "not the uncertainty of the estimated improvement. No outliers are removed.", "",
              "`round-*-pyperf.txt` files contain supporting `pyperf compare_to` output when available. "
              "Its exit code is not used to decide whether the improvement target was met.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="append", type=Path, required=True,
                        help="Baseline result directory; repeat in chronological pair order")
    parser.add_argument("--optimized", action="append", type=Path, required=True,
                        help="Optimized result directory; repeat in the corresponding pair order")
    parser.add_argument("--correctness", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New comparison output directory")
    args = parser.parse_args()
    try:
        args.output.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        parser.error(f"--output must be a new writable directory: {exc}")
    summary = {"status": "invalid evidence", "exit_code": 2,
               "minimum_runtime_reduction": MINIMUM_REDUCTION,
               "bootstrap_replicates": BOOTSTRAP_REPLICATES,
               "bootstrap_seed": BOOTSTRAP_SEED, "uncertainty_note": UNCERTAINTY_NOTE,
               "correctness_report": str(args.correctness.resolve()), "rounds": []}
    try:
        if len(args.baseline) != len(args.optimized):
            raise EvidenceError("Supply the same number of --baseline and --optimized directories")
        all_directories = [path.resolve() for path in args.baseline + args.optimized]
        if len(set(all_directories)) != len(all_directories):
            raise EvidenceError("Each input directory must be a distinct measurement; duplicate directories are not independent rounds")
        baseline = [load_run(path, "baseline") for path in args.baseline]
        optimized = [load_run(path, "optimized") for path in args.optimized]
        reference = baseline[0]["signature"]
        summary["benchmark"] = reference["benchmark"]
        summary["invariants"] = reference
        for run in baseline + optimized:
            differences = differing_fields(reference, run["signature"])
            if differences:
                raise EvidenceError(f"Incompatible provenance in {run['directory']}: {', '.join(differences)}")
        # Compare observed pyperf metadata as an additional check whenever both
        # sides record it. Provenance is still mandatory, even if pyperf omits it.
        observed_keys = ("python_version", "python_implementation", "python_compiler",
                         "python_cflags", "python_config_args", "cpu_model_name", "platform")
        for key in observed_keys:
            observed = [(run["directory"], run["pyperf_metadata"][key])
                        for run in baseline + optimized if key in run["pyperf_metadata"]]
            if observed and any(value != observed[0][1] for _, value in observed[1:]):
                raise EvidenceError(f"Observed pyperf metadata differs across runs: {key}")
        for variant, runs in (("baseline", baseline), ("optimized", optimized)):
            for key in ("source_sha256", "source_tree_sha256"):
                if len({run["provenance"][key].lower() for run in runs}) != 1:
                    raise EvidenceError(f"{variant} {key} changed between rounds")
        correctness = read_json(args.correctness)
        validate_correctness(correctness, baseline, optimized)
        summary["correctness_passed"] = True
        summary["sources_differ"] = baseline[0]["provenance"]["source_tree_sha256"].lower() != optimized[0]["provenance"]["source_tree_sha256"].lower()
        summary["entry_points_differ"] = baseline[0]["provenance"]["source_sha256"].lower() != optimized[0]["provenance"]["source_sha256"].lower()
        summary["sources"] = {variant: {key: runs[0]["provenance"][key]
                                        for key in ("source_sha256", "source_tree_sha256")}
                              for variant, runs in (("baseline", baseline), ("optimized", optimized))}
        for index, (base, opt) in enumerate(zip(baseline, optimized), start=1):
            reduction = 1.0 - opt["statistics"]["mean_seconds"] / base["statistics"]["mean_seconds"]
            low, high = bootstrap_interval(base["worker_means"], opt["worker_means"], BOOTSTRAP_SEED + index)
            summary["rounds"].append({
                "round": index, "baseline_directory": base["directory"],
                "optimized_directory": opt["directory"],
                "baseline": base["statistics"], "optimized": opt["statistics"],
                "runtime_reduction": reduction,
                "speedup": base["statistics"]["mean_seconds"] / opt["statistics"]["mean_seconds"],
                "runtime_reduction_ci95": [low, high],
                "meets_7_percent_point_estimate": meets_reduction_target(reduction),
                "positive_ci_lower_bound": low > 0,
                "ci_lower_bound_at_least_7_percent": meets_reduction_target(low),
                "pyperf_comparison": pyperf_comparison(base, opt, args.output, index),
            })
        passed = summary["sources_differ"] and all(
            entry["meets_7_percent_point_estimate"] and entry["positive_ci_lower_bound"]
            for entry in summary["rounds"]
        )
        summary["gate_passed"] = passed
        summary["status"] = "passes stated evidence gate" if passed else "valid comparison; evidence gate not met"
        summary["exit_code"] = 0 if passed else 3
        if not summary["sources_differ"]:
            summary["error"] = "Baseline and optimized source-tree hashes are identical; timing noise cannot establish a source optimization."
    except (EvidenceError, TypeError, KeyError, AttributeError) as exc:
        summary["error"] = str(exc)
        summary["gate_passed"] = False
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (args.output / "summary.md").write_text(markdown(summary), encoding="utf-8")
    print(f"{summary['status']}: {args.output / 'summary.md'}")
    if summary.get("error"):
        print(summary["error"], file=sys.stderr)
    return summary["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
