#!/usr/bin/env python3
"""Unprofiled pyperf adapter for exact local benchmark sources.

All workload arguments are explicitly forwarded to pyperf workers. The original
bench_time_func entry point supplies the elapsed time, preserving its original
timer boundaries (including nbody's untimed momentum offset).
"""

import hashlib
from pathlib import Path

import pyperf

from workload import load_benchmark, source_directory, source_tree_hash


def add_cmdline_args(command, args):
    command.extend(("--benchmark", args.benchmark,
                    "--source", str(args.source),
                    "--iterations", str(args.iterations),
                    "--width", str(args.width),
                    "--height", str(args.height)))


def main():
    runner = pyperf.Runner(add_cmdline_args=add_cmdline_args)
    parser = runner.argparser
    parser.add_argument("--benchmark", required=True, choices=("nbody", "raytrace"))
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--width", type=int, default=100)
    parser.add_argument("--height", type=int, default=100)
    args = runner.parse_args()
    if not args.source.is_absolute():
        parser.error("--source must be an absolute path to the exact benchmark source")
    if min(args.iterations, args.width, args.height) <= 0:
        parser.error("--iterations, --width, and --height must be positive")
    if args.benchmark == "raytrace" and min(args.width, args.height) < 2:
        parser.error("raytrace dimensions must be at least 2")
    source = args.source.resolve(strict=True)
    runner.metadata.update({
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_tree_sha256": source_tree_hash(source.parent),
        "workload_benchmark": args.benchmark,
        "workload_iterations": args.iterations,
        "workload_width": args.width,
        "workload_height": args.height,
        "workload_reference": "sun",
        "workload_state_policy": "one imported module per worker; state continues across benchmark calls",
        "measurement_method": "exact source bench_time_func return value; unprofiled pyperf workers",
    })
    with source_directory(source):
        module = load_benchmark(source, args.benchmark)
        if args.benchmark == "nbody":
            runner.bench_time_func("nbody", module.bench_nbody, "sun", args.iterations)
        else:
            runner.bench_time_func("raytrace", module.bench_raytrace, args.width, args.height, None)


if __name__ == "__main__":
    main()
