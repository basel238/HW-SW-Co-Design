"""Real workload/FIFO/renderer integration with a synthetic perf executable.

Run with the package's .venv/bin/python -m unittest discover -s tests -v.
The benchmark code, ACK exchange, source hashes, folding, and SVG generation
actually run. Counts and native samples are fabricated fixtures: these tests do
not validate hardware counters, PMU virtualization, or real stack unwinding.
"""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pipeline as p


SYNTHETIC_PERF = r'''#!/usr/bin/env python3
"""TEST FIXTURE ONLY. Real workload/FIFO exchange, fabricated PMU data."""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time

args = sys.argv[1:]
mode = os.environ.get("TEST_SYNTHETIC_PERF_MODE", "valid")
def option(name):
    return args[args.index(name) + 1]

if args == ["--version"] or args == ["version", "--build-options"]:
    print("perf version 5.15.0 SYNTHETIC TEST FIXTURE, NOT HARDWARE")
    if "--build-options" in args:
        print("dwarf: [ on ] SYNTHETIC TEST FIXTURE")
    raise SystemExit(0)

if args[0] == "buildid-list":
    print("0000000000000000000000000000000000000000 /synthetic/libpython.so")
    raise SystemExit(0)

if args[0] in ("stat", "record"):
    output = Path(option("-o"))
    output.parent.mkdir(parents=True, exist_ok=True)
    control, ack = option("--control").removeprefix("fifo:").split(",")
    control_fd = os.open(control, os.O_RDWR | os.O_NONBLOCK)
    ack_fd = os.open(ack, os.O_RDWR | os.O_NONBLOCK)
    child = subprocess.Popen(args[args.index("--") + 1:])
    buffered = b""
    commands = []
    deadline = time.monotonic() + 10
    while child.poll() is None:
        if time.monotonic() > deadline:
            child.kill()
            child.wait()
            raise SystemExit(124)
        ready, _, _ = select.select([control_fd], [], [], 0.01)
        if ready:
            buffered += os.read(control_fd, 4096)
            while b"\n" in buffered:
                line, buffered = buffered.split(b"\n", 1)
                commands.append(line.decode("ascii"))
                # The real Linux 5.15 framing bug included the C string's NUL.
                reply = b"ack\n\0"
                if mode == "malformed_ack" and line == b"enable":
                    reply = b"a\0ck\n\0"
                os.write(ack_fd, reply)
    os.close(control_fd)
    os.close(ack_fd)
    (output.parent / "synthetic-handshake.json").write_text(json.dumps({
        "commands": commands, "child_exit": child.returncode,
        "synthetic_perf_data": True, "ack_format": "ack newline NUL",
    }))
    if child.returncode:
        raise SystemExit(child.returncode)
    if args[0] == "record":
        output.write_text("SYNTHETIC PERF.DATA: samples are test fixtures\n")
        raise SystemExit(0)
    counts = {
        "task-clock": 12.5, "context-switches": 2, "cpu-migrations": 0,
        "minor-faults": 4, "major-faults": 0,
        "cycles:u": 0 if mode == "zero_cycles" else 1000000,
        "instructions:u": 2000000, "branches:u": 100000,
        "branch-misses:u": 2000, "cache-references:u": 20000,
        "cache-misses:u": 200, "L1-dcache-loads:u": 100000,
        "L1-dcache-load-misses:u": 1000,
    }
    rows = ["# SYNTHETIC COUNTS, NOT A HARDWARE MEASUREMENT"]
    for event in option("-e").strip("{}").split(","):
        unit = "msec" if event == "task-clock" else ""
        rows.append(f"{counts[event]};{unit};{event};10000000;100.00")
    output.write_text("\n".join(rows) + "\n")
    raise SystemExit(0)

if args[0] == "report":
    print("# SYNTHETIC NATIVE SAMPLE FIXTURE, NOT HARDWARE")
    print("# Total Lost Samples: 0\n# Samples: 3 of event 'cpu-clock:u'")
    print("# Event count (approx.): 6000000")
    if "--header-only" not in args:
        print("  66.67% python libpython.so [.] _PyEval_EvalFrameDefault")
        print("  33.33% python libpython.so [.] PyFloat_FromDouble")
    raise SystemExit(0)

if args[0] == "script":
    for index, leaf in enumerate(("_PyEval_EvalFrameDefault",) * 2 + ("PyFloat_FromDouble",)):
        print(f"python 123 1.00{index + 1}000: 2000000 cpu-clock:u:")
        print(f"        7f000001 {leaf}+0x1 (/usr/lib/libpython.so)")
        print("        7f000002 PyEval_EvalCode+0x2 (/usr/lib/libpython.so)")
        print("        7f000003 Py_RunMain+0x3 (/usr/lib/libpython.so)\n")
    raise SystemExit(0)

print("Unsupported synthetic perf command:", args, file=sys.stderr)
raise SystemExit(2)
'''


@unittest.skipUnless(hasattr(os, "mkfifo") and shutil.which("perl"),
                     "Requires POSIX FIFOs and Perl for the actual renderer")
@unittest.skipUnless(importlib.util.find_spec("pyperf"),
                     "Run with .venv/bin/python; unchanged benchmarks import pyperf")
class PerfPipelineIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        package = Path(__file__).resolve().parents[1]
        shutil.copytree(package, self.root, ignore=shutil.ignore_patterns(
            ".venv", ".venv-guide", ".course-cache", "results", "__pycache__", ".git", "exports"
        ))
        self.settings = json.loads((self.root / "config.json").read_text())
        self.settings["nbody"].update(iterations=2000, profile_calls=2, profile_warmups=1)
        self.settings.update(stat_repeats=1, affinity=None, command_timeout_seconds=15)
        binary_directory = Path(self.temp.name) / "bin"
        binary_directory.mkdir()
        binary = binary_directory / "perf"
        binary.write_text(SYNTHETIC_PERF)
        binary.chmod(0o755)
        for patcher in (
            patch.object(p, "ROOT", self.root),
            patch.object(p, "TOOLS", self.root / "tools"),
            patch.object(p, "PY", sys.executable),
            patch.dict(os.environ, {
                "PATH": str(binary_directory) + os.pathsep + os.environ.get("PATH", ""),
                "TEST_SYNTHETIC_PERF_MODE": "valid",
            }),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def assert_complete_receipt(self, directory):
        receipt = json.loads((directory / "workload.json").read_text())
        self.assertEqual(receipt["status"], "ok")
        self.assertEqual(receipt["completed_calls"], 2)
        self.assertEqual(receipt["completed_warmups"], 1)
        self.assertTrue(receipt["enable_acknowledged"])
        self.assertTrue(receipt["disable_acknowledged"])
        self.assertTrue(json.loads((directory / "collection.json").read_text())["available"])
        exchange = json.loads((directory / "synthetic-handshake.json").read_text())
        self.assertEqual(exchange["commands"], ["enable", "disable"])
        self.assertEqual(exchange["child_exit"], 0)
        self.assertFalse((directory / "control.fifo").exists())
        self.assertFalse((directory / "ack.fifo").exists())

    def test_gate_probe_accepts_real_workload_and_nul_framing(self):
        directory, passed = p.gate_probe(self.settings)
        self.assertTrue(passed)
        for kind in ("stat", "record"):
            self.assert_complete_receipt(directory / kind)
        self.assertTrue(json.loads((directory / "gate-probe.json").read_text())["passed"])

    def test_stat_and_native_complete_the_output_chain(self):
        stat_directory, stat_ok = p.stat("nbody", "baseline", self.settings)
        self.assertTrue(stat_ok)
        summary = json.loads((stat_directory / "stat-summary.json").read_text())
        self.assertTrue(summary["all_collection_completed"])
        self.assertTrue(summary["all_requested_events_usable"])
        self.assertTrue(summary["ipc_available"])
        ipc = json.loads((stat_directory / "ipc-1" / "metrics.json").read_text())
        self.assertEqual(ipc["ipc"], 2.0)  # Fixture arithmetic, not observed IPC.
        self.assertEqual(ipc["cpi"], 0.5)
        self.assert_complete_receipt(stat_directory / "ipc-1")
        native_directory, native_ok = p.native("nbody", "baseline", self.settings)
        self.assertTrue(native_ok)
        self.assert_complete_receipt(native_directory)
        for name in ("perf.data", "native-self.txt", "native-callgraph.txt", "native-stacks.txt",
                     "native.folded", "native.svg", "stack-health.json"):
            self.assertGreater((native_directory / name).stat().st_size, 0, name)
        self.assertIn("<svg", (native_directory / "native.svg").read_text())
        self.assertIn("PyFloat_FromDouble", (native_directory / "native.folded").read_text())
        health = json.loads((native_directory / "stack-health.json").read_text())
        self.assertEqual(health["folded"]["total_period_weight"], 6000000)
        self.assertEqual(health["weight_unit"], "nanoseconds_of_event_period")

    def test_malformed_handshake_fails_before_graph_generation(self):
        with patch.dict(os.environ, {"TEST_SYNTHETIC_PERF_MODE": "malformed_ack"}):
            probe, probe_ok = p.gate_probe(self.settings)
            directory, native_ok = p.native("nbody", "baseline", self.settings)
        self.assertFalse(probe_ok)
        self.assertFalse(native_ok)
        self.assertFalse((directory / "native.svg").exists())
        self.assertFalse((directory / "stacks.command.json").exists())
        receipt = json.loads((directory / "workload.json").read_text())
        self.assertEqual(receipt["status"], "error")
        self.assertEqual(receipt["completed_calls"], 0)
        self.assertFalse(receipt["enable_acknowledged"])
        self.assertTrue(receipt["disable_acknowledged"])
        self.assertFalse(json.loads((directory / "collection.json").read_text())["available"])
        self.assertFalse(json.loads((probe / "gate-probe.json").read_text())["passed"])

    def test_zero_cycles_keeps_completed_collection_but_no_ipc(self):
        with patch.dict(os.environ, {"TEST_SYNTHETIC_PERF_MODE": "zero_cycles"}):
            directory, ok = p.stat("nbody", "baseline", self.settings)
        self.assertFalse(ok)
        summary = json.loads((directory / "stat-summary.json").read_text())
        self.assertTrue(summary["all_collection_completed"])
        self.assertFalse(summary["ipc_available"])
        ipc = json.loads((directory / "ipc-1" / "metrics.json").read_text())
        self.assertIsNone(ipc["ipc"])
        self.assertIsNone(ipc["cpi"])
        self.assertEqual(ipc["events"]["cycles:u"]["status"], "invalid_zero_for_active_workload")
        self.assert_complete_receipt(directory / "ipc-1")


if __name__ == "__main__":
    unittest.main()
