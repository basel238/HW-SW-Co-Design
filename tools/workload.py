#!/usr/bin/env python3
"""Execute fixed useful work without pyperformance environment/worker management.

This is a counter/profiler workload driver, not a replacement for an unprofiled
pyperf timing experiment. Imports, warmups, and receipts are outside the gated
region. The region still includes the small driver loop, function-call boundary,
and timer overhead; FIFO acknowledgements add a small boundary cost to perf data.
"""

import argparse
import contextlib
import cProfile
import errno
import hashlib
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import pstats
import select
import signal
import stat
import sys
import time
import types
import uuid


def source_tree_hash(path):
    """Hash source, sibling helpers, and data with the pipeline's canonical order."""
    path = Path(path)
    digest = hashlib.sha256()
    for candidate in sorted(path.rglob("*")):
        if candidate.is_file() and "__pycache__" not in candidate.parts and candidate.suffix != ".pyc":
            digest.update(candidate.relative_to(path).as_posix().encode() + b"\0")
            digest.update(candidate.read_bytes() + b"\0")
    return digest.hexdigest()


@contextlib.contextmanager
def source_directory(source):
    """Allow ordinary sibling imports, including imports during a benchmark call."""
    old_path = sys.path[:]
    sys.path.insert(0, str(Path(source).resolve().parent))
    try:
        yield
    finally:
        sys.path[:] = old_path


def load_benchmark(source, benchmark):
    """Import the exact file into a fresh module and validate its public entry point.

    Unique package names also allow relative sibling imports. Absolute sibling
    import names obey Python's normal module cache; independent processes should
    be used when baseline and optimized trees contain different sibling modules.
    """
    source = Path(source).resolve(strict=True)
    if not source.is_file():
        raise ValueError(f"Not a source file: {source}")
    package_name = "_measurement_" + uuid.uuid4().hex
    package = types.ModuleType(package_name)
    package.__path__ = [str(source.parent)]
    sys.modules[package_name] = package
    module_name = package_name + ".run_benchmark"
    spec = importlib.util.spec_from_file_location(module_name, source)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load Python source: {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        with source_directory(source):
            spec.loader.exec_module(module)
        entry_name = "bench_" + benchmark
        entry = getattr(module, entry_name, None)
        if not callable(entry):
            raise ValueError(f"Unsupported benchmark API: missing callable {entry_name}")
        arguments = (1, "sun", 1) if benchmark == "nbody" else (1, 1, 1, None)
        try:
            inspect.signature(entry).bind(*arguments)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Unsupported benchmark API for {entry_name}: {exc}") from exc
        return module
    except BaseException:
        for name in list(sys.modules):
            if name == package_name or name.startswith(package_name + "."):
                del sys.modules[name]
        raise


def make_call(module, benchmark, iterations=20000, width=100, height=100, filename=None):
    """Return a zero-argument call performing exactly one public benchmark loop."""
    if benchmark == "nbody":
        return lambda: module.bench_nbody(1, "sun", iterations)
    if benchmark == "raytrace":
        return lambda: module.bench_raytrace(1, width, height, filename)
    raise ValueError(f"Unsupported benchmark: {benchmark}")


class PerfGate:
    """perf --control=fifo:CTL,ACK client with bounded open/write/read operations."""

    def __init__(self, control, ack, timeout=20.0):
        self.control_path = Path(control)
        self.ack_path = Path(ack)
        self.timeout = timeout
        self.control_fd = None
        self.ack_fd = None
        self.may_be_enabled = False
        self.enable_acknowledged = False
        self.disable_acknowledged = False
        self.buffer = b""

    def open(self):
        for path in (self.control_path, self.ack_path):
            if not stat.S_ISFIFO(path.stat().st_mode):
                raise ValueError(f"Expected an existing FIFO: {path}")
        # Open the ACK reader first: perf may open its ACK writer synchronously.
        self.ack_fd = os.open(self.ack_path, os.O_RDONLY | os.O_NONBLOCK)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self.control_fd = os.open(self.control_path, os.O_WRONLY | os.O_NONBLOCK)
                break
            except OSError as exc:
                if exc.errno != errno.ENXIO:
                    raise
                if time.monotonic() >= deadline:
                    raise TimeoutError("perf did not open the control FIFO for reading") from exc
                time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))

    def command(self, command):
        if self.control_fd is None or self.ack_fd is None:
            raise RuntimeError("PerfGate is not open")
        deadline = time.monotonic() + self.timeout
        message = (command + "\n").encode("ascii")
        while message:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Timed out writing perf {command}")
            _, writable, _ = select.select([], [self.control_fd], [], remaining)
            if not writable:
                raise TimeoutError(f"Timed out writing perf {command}")
            try:
                written = os.write(self.control_fd, message)
                message = message[written:]
            except BlockingIOError:
                continue
        if command == "enable":
            self.may_be_enabled = True
        while b"\n" not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"No acknowledgement for perf {command}")
            ready, _, _ = select.select([self.ack_fd], [], [], remaining)
            if not ready:
                raise TimeoutError(f"No acknowledgement for perf {command}")
            try:
                chunk = os.read(self.ack_fd, 4096)
            except BlockingIOError:
                continue
            if not chunk:
                # FIFO has no writer yet, or perf exited. Neither may hang us.
                time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
                continue
            self.buffer += chunk
            if len(self.buffer) > 4096:
                raise RuntimeError("Unexpected oversized perf acknowledgement")
        line, self.buffer = self.buffer.split(b"\n", 1)
        # Linux perf 5.15 writes sizeof("ack\n"), including the terminating
        # NUL. It can arrive with this line or at the beginning of the next
        # read. Consume boundary padding only: embedded NULs, other replies,
        # unbounded padding, and missing replies must still fail closed.
        if line.strip(b"\x00 \t\r") != b"ack":
            raise RuntimeError(f"Unexpected perf acknowledgement: {line!r}")
        if command == "enable":
            self.enable_acknowledged = True
        if command == "disable":
            self.may_be_enabled = False
            self.disable_acknowledged = True

    def close(self):
        for name in ("control_fd", "ack_fd"):
            fd = getattr(self, name)
            if fd is not None:
                os.close(fd)
                setattr(self, name, None)


def reserve_file(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("x", encoding="utf-8")


def _signal_interrupt(signum, _frame):
    raise KeyboardInterrupt(f"Received signal {signum}")


def run_measured_calls(call, calls, result):
    """Stable sampling marker enclosing only the measured benchmark calls.

    Profilers can select this function in this exact source file to exclude
    imports and warmups without depending on changing source line numbers.
    A call that raises is not counted as completed.
    """
    durations = []
    for _ in range(calls):
        durations.append(call())
        result["completed_calls"] += 1
    return durations


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", required=True, choices=("nbody", "raytrace"))
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--calls", required=True, type=int)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--width", type=int, default=100)
    parser.add_argument("--height", type=int, default=100)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--control-fifo", type=Path)
    parser.add_argument("--ack-fifo", type=Path)
    parser.add_argument("--control-timeout", type=float, default=20.0)
    parser.add_argument("--cprofile", type=Path, help="Separate diagnostic .pstats output; also writes PATH.txt")
    args = parser.parse_args(argv)
    try:
        receipt_handle = reserve_file(args.receipt)
    except OSError as exc:
        print(f"Cannot reserve receipt (existing files are preserved): {exc}", file=sys.stderr)
        return 2
    result = {
        "status": "error", "benchmark": args.benchmark, "source": str(args.source),
        "calls": args.calls, "completed_calls": 0, "warmups": args.warmups,
        "completed_warmups": 0, "loops_per_call": 1,
        "parameters": ({"iterations": args.iterations, "reference": "sun"}
                       if args.benchmark == "nbody" else {"width": args.width, "height": args.height}),
        "wall_seconds": None, "process_cpu_seconds": None,
        "reported_benchmark_seconds": None, "roi_gated": bool(args.control_fifo),
        "enable_acknowledged": False, "disable_acknowledged": False,
        "cprofile": str(args.cprofile) if args.cprofile else None,
        "nbody_state_policy": "one imported module; state continues across warmups and measured calls; bench_nbody offsets momentum on every call",
        "measurement_scope": "fixed benchmark calls plus driver loop/timer overhead; imports and warmups excluded from gated counters; FIFO boundary cost remains",
        "errors": [],
    }
    gate = None
    profile = None
    profile_reserved = False
    profile_text_handle = None
    signal_handlers = {}
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal_handlers[sig] = signal.signal(sig, _signal_interrupt)
        if not args.source.is_absolute():
            raise ValueError("--source must be an absolute path to the exact benchmark source")
        if args.calls <= 0 or args.warmups < 0:
            raise ValueError("--calls must be positive and --warmups must be nonnegative")
        if min(args.iterations, args.width, args.height) <= 0:
            raise ValueError("--iterations, --width, and --height must be positive")
        if not math.isfinite(args.control_timeout) or args.control_timeout <= 0:
            raise ValueError("--control-timeout must be finite and positive")
        if bool(args.control_fifo) != bool(args.ack_fifo):
            raise ValueError("Specify both --control-fifo and --ack-fifo, or neither")
        if args.cprofile and args.control_fifo:
            raise ValueError("Run cProfile separately from perf; instrumentation changes the counter/profile workload")
        result["source"] = str(args.source.resolve(strict=True))
        result["source_sha256"] = hashlib.sha256(args.source.read_bytes()).hexdigest()
        result["source_tree_sha256"] = source_tree_hash(args.source.parent)
        result["interpreter"] = sys.executable
        result["python_version"] = sys.version
        result["pid"] = os.getpid()
        if args.cprofile:
            with reserve_file(args.cprofile):
                pass
            profile_reserved = True
            profile_text_handle = reserve_file(Path(str(args.cprofile) + ".txt"))
            profile = cProfile.Profile()
        with source_directory(args.source):
            module = load_benchmark(args.source, args.benchmark)
            call = make_call(module, args.benchmark, args.iterations, args.width, args.height)
            for _ in range(args.warmups):
                call()
                result["completed_warmups"] += 1
            if args.control_fifo:
                gate = PerfGate(args.control_fifo, args.ack_fifo, args.control_timeout)
                gate.open()
                gate.command("enable")
            start_wall = time.perf_counter()
            start_cpu = time.process_time()
            try:
                if profile:
                    profile.enable()
                durations = run_measured_calls(call, args.calls, result)
            finally:
                if profile:
                    profile.disable()
                result["process_cpu_seconds"] = time.process_time() - start_cpu
                result["wall_seconds"] = time.perf_counter() - start_wall
                if gate and gate.may_be_enabled:
                    gate.command("disable")
            if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in durations):
                raise ValueError("Unsupported benchmark API: bench function must return a finite nonnegative elapsed time")
            result["reported_benchmark_seconds"] = sum(durations)
        result["status"] = "ok"
    except BaseException as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        if gate:
            try:
                if gate.may_be_enabled:
                    gate.command("disable")
            except BaseException as exc:
                result["errors"].append(f"Counter disable cleanup: {type(exc).__name__}: {exc}")
            finally:
                result["enable_acknowledged"] = gate.enable_acknowledged
                result["disable_acknowledged"] = gate.disable_acknowledged
                gate.close()
        if profile:
            try:
                profile.dump_stats(str(args.cprofile))
                stats = pstats.Stats(profile, stream=profile_text_handle)
                profile_text_handle.write("Separate instrumented diagnostic: do not compare these times with unprofiled timings.\n\nCUMULATIVE TIME\n")
                stats.sort_stats("cumulative").print_stats(80)
                profile_text_handle.write("\nSELF TIME\n")
                stats.sort_stats("tottime").print_stats(80)
                profile_text_handle.flush()
            except BaseException as exc:
                result["errors"].append(f"cProfile output: {type(exc).__name__}: {exc}")
        elif profile_reserved:
            args.cprofile.unlink(missing_ok=True)
        if profile_text_handle:
            profile_text_handle.close()
        if result["errors"]:
            result["status"] = "error"
        for sig, handler in signal_handlers.items():
            signal.signal(sig, handler)
        with receipt_handle:
            json.dump(result, receipt_handle, indent=2, allow_nan=False)
            receipt_handle.write("\n")
    if result["status"] != "ok":
        print("; ".join(result["errors"]), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
