#!/usr/bin/env python3
"""Finite regression oracle for the supported nbody/raytrace benchmark APIs.

Each variant executes in a fresh interpreter, preventing global state and sibling
module caches from leaking between baseline and optimized implementations. Passing
these finite cases is useful evidence, not proof of equivalence for every input.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

from workload import load_benchmark, make_call, source_directory, source_tree_hash


REL_TOL = 1e-10
ABS_TOL = 1e-12


def body_snapshot(module):
    bodies = getattr(module, "BODIES", None)
    if not isinstance(bodies, dict) or not bodies or "sun" not in bodies:
        raise ValueError("Unsupported nbody state API: expected nonempty BODIES dict containing sun")
    result = {}
    for name, body in bodies.items():
        if not isinstance(name, str) or not isinstance(body, (list, tuple)) or len(body) != 3:
            raise ValueError("Unsupported BODIES entry: expected name -> (position, velocity, mass)")
        position, velocity, mass = body
        if not isinstance(position, (list, tuple)) or not isinstance(velocity, (list, tuple)):
            raise ValueError(f"Unsupported position/velocity representation for {name}")
        if len(position) != 3 or len(velocity) != 3:
            raise ValueError(f"Expected three position and three velocity coordinates for {name}")
        values = list(position) + list(velocity) + [mass]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise ValueError(f"Nonfinite or unsupported numeric state in body {name}")
        result[name] = {"position": list(position), "velocity": list(velocity), "mass": mass}
    return result


def compare_states(baseline, optimized, location="state"):
    """Compare all fields, reporting structural errors and every numeric mismatch."""
    differences = []
    if isinstance(baseline, dict):
        if not isinstance(optimized, dict):
            return [{"path": location, "error": "state types differ"}]
        if set(baseline) != set(optimized):
            differences.append({"path": location, "error": "keys differ",
                                "baseline_keys": sorted(baseline), "optimized_keys": sorted(optimized)})
        for key in sorted(set(baseline) & set(optimized)):
            differences.extend(compare_states(baseline[key], optimized[key], location + "." + key))
    elif isinstance(baseline, list):
        if not isinstance(optimized, list) or len(baseline) != len(optimized):
            return [{"path": location, "error": "array types or lengths differ"}]
        for index, (left, right) in enumerate(zip(baseline, optimized)):
            differences.extend(compare_states(left, right, f"{location}[{index}]"))
    elif (not isinstance(optimized, (int, float)) or not math.isfinite(optimized)
          or not math.isclose(baseline, optimized, rel_tol=REL_TOL, abs_tol=ABS_TOL)):
        differences.append({"path": location, "baseline": baseline, "optimized": optimized,
                            "absolute_difference": abs(baseline - optimized) if isinstance(optimized, (int, float)) else None})
    return differences


def collect_variant(args):
    """Hidden child mode: one clean process, one source module, one state history."""
    output = {"status": "error", "source": str(args.source), "errors": []}
    try:
        output["source_sha256"] = hashlib.sha256(args.source.read_bytes()).hexdigest()
        output["source_tree_sha256"] = source_tree_hash(args.source.parent)
        with source_directory(args.source):
            module = load_benchmark(args.source, args.benchmark)
            if args.benchmark == "nbody":
                output["states"] = [body_snapshot(module)]
                call = make_call(module, "nbody", args.iterations)
                for _ in range(3):
                    call()
                    output["states"].append(body_snapshot(module))
            else:
                ppm = args.worker_output.with_suffix(".ppm")
                if ppm.exists():
                    raise FileExistsError(f"Refusing to overwrite image: {ppm}")
                make_call(module, "raytrace", width=args.width, height=args.height, filename=str(ppm))()
                data = ppm.read_bytes()
                if not data:
                    raise ValueError("Renderer produced an empty PPM")
                output.update(ppm=str(ppm), ppm_bytes=len(data), ppm_sha256=hashlib.sha256(data).hexdigest())
        output["status"] = "ok"
    except BaseException as exc:
        output["errors"].append(f"{type(exc).__name__}: {exc}")
    with args.worker_output.open("x", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2, allow_nan=False)
        handle.write("\n")
    return 0 if output["status"] == "ok" else 1


def run_variant(args, label, source):
    output_path = args.output / (label + "-state.json")
    command = [sys.executable, str(Path(__file__).resolve()), "--worker",
               "--benchmark", args.benchmark, "--source", str(source.resolve()),
               "--iterations", str(args.iterations), "--width", str(args.width),
               "--height", str(args.height), "--worker-output", str(output_path)]
    with (args.output / (label + ".stdout.txt")).open("x") as stdout, (args.output / (label + ".stderr.txt")).open("x") as stderr:
        try:
            process = subprocess.run(command, stdout=stdout, stderr=stderr,
                                     timeout=args.timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"{label} correctness workload exceeded {args.timeout}s") from exc
    if not output_path.is_file():
        raise RuntimeError(f"{label} worker exited {process.returncode} without a result; inspect {label}.stderr.txt")
    result = json.loads(output_path.read_text())
    if process.returncode or result.get("status") != "ok":
        raise RuntimeError(f"{label} correctness worker failed: {result.get('errors', [])}")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", required=True, choices=("nbody", "raytrace"))
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--optimized", type=Path)
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--width", type=int, default=100)
    parser.add_argument("--height", type=int, default=100)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=float, default=300.0, help="Maximum seconds per isolated variant")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--source", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-output", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        if args.source is None or args.worker_output is None:
            parser.error("Internal worker requires --source and --worker-output")
        return collect_variant(args)
    if args.baseline is None or args.optimized is None or args.output is None:
        parser.error("--baseline, --optimized, and --output are required")
    args.output = args.output.resolve()
    try:
        args.output.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        print(f"Cannot create new correctness output directory: {exc}", file=sys.stderr)
        return 2
    result = {
        "passed": False, "benchmark": args.benchmark,
        "baseline": str(args.baseline.resolve()), "optimized": str(args.optimized.resolve()),
        "oracle_limit": "Finite regression check only, not proof of equivalence for all inputs or benchmark variants.",
        "parameters": ({"iterations": args.iterations, "reference": "sun", "consecutive_calls": 3,
                        "loops_per_call": 1} if args.benchmark == "nbody" else {"width": args.width, "height": args.height, "loops": 1}),
        "comparison": ("all initial state and all state after each of three consecutive public benchmark calls"
                       if args.benchmark == "nbody" else "exact bytes of PPM output from the normal bench_raytrace entry point"),
        "tolerances": {"relative": REL_TOL, "absolute": ABS_TOL} if args.benchmark == "nbody" else {"mode": "exact; no tolerance"},
        "differences": [], "errors": [],
    }
    try:
        if min(args.iterations, args.width, args.height) <= 0:
            raise ValueError("--iterations, --width, and --height must be positive")
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise ValueError("--timeout must be finite and positive")
        baseline = run_variant(args, "baseline", args.baseline)
        optimized = run_variant(args, "optimized", args.optimized)
        result["baseline_source_sha256"] = baseline["source_sha256"]
        result["optimized_source_sha256"] = optimized["source_sha256"]
        result["baseline_source_tree_sha256"] = baseline["source_tree_sha256"]
        result["optimized_source_tree_sha256"] = optimized["source_tree_sha256"]
        if args.benchmark == "nbody":
            result["differences"] = compare_states(baseline["states"], optimized["states"], "states")
        else:
            left = Path(baseline["ppm"]).read_bytes()
            right = Path(optimized["ppm"]).read_bytes()
            result["images"] = {"baseline": baseline, "optimized": optimized}
            if left != right:
                first_difference = next((i for i, (a, b) in enumerate(zip(left, right)) if a != b), min(len(left), len(right)))
                result["differences"] = [{"error": "PPM bytes differ", "baseline_bytes": len(left),
                                          "optimized_bytes": len(right), "first_different_byte": first_difference}]
        result["passed"] = not result["differences"]
    except BaseException as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
    with (args.output / "correctness.json").open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    if not result["passed"]:
        print("Correctness check failed; inspect " + str(args.output / "correctness.json"), file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
