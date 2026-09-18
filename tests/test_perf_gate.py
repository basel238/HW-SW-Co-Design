"""Exercise the actual FIFO protocol, including Linux 5.15's trailing NUL."""

import importlib.util
import json
import os
from pathlib import Path
import select
import tempfile
import threading
import unittest


SPEC = importlib.util.spec_from_file_location(
    "tested_workload", Path(__file__).resolve().parents[1] / "tools" / "workload.py"
)
workload = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workload)


class FakePerf:
    """A FIFO peer; each response is a list of chunks or None for silence."""

    def __init__(self, directory, responses):
        self.control = Path(directory) / "control.fifo"
        self.ack = Path(directory) / "ack.fifo"
        os.mkfifo(self.control)
        os.mkfifo(self.ack)
        # Retain both ends so test startup/teardown never blocks on open().
        self.control_fd = os.open(self.control, os.O_RDWR | os.O_NONBLOCK)
        self.ack_fd = os.open(self.ack, os.O_RDWR | os.O_NONBLOCK)
        self.responses = iter(responses)
        self.commands = []
        self.errors = []
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        buffered = b""
        try:
            while not self.stop.is_set():
                ready, _, _ = select.select([self.control_fd], [], [], 0.02)
                if not ready:
                    continue
                buffered += os.read(self.control_fd, 4096)
                while b"\n" in buffered:
                    command, buffered = buffered.split(b"\n", 1)
                    self.commands.append(command)
                    chunks = next(self.responses, None)
                    if chunks is not None:
                        for chunk in chunks:
                            pending = chunk
                            while pending:
                                _, ready, _ = select.select([], [self.ack_fd], [], 0.2)
                                if not ready:
                                    raise TimeoutError("Fake perf ACK writer stalled")
                                pending = pending[os.write(self.ack_fd, pending):]
                            # Permit fragmented reads and a delayed terminal NUL.
                            self.stop.wait(0.003)
        except BaseException as exc:
            self.errors.append(exc)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=1)
        os.close(self.control_fd)
        os.close(self.ack_fd)
        if self.thread.is_alive():
            raise AssertionError("Fake perf thread did not stop")
        if self.errors:
            raise self.errors[0]


@unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO protocol needs POSIX")
class PerfGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def gate(self, responses, timeout=0.5):
        peer = FakePerf(self.temp.name, responses)
        self.addCleanup(peer.close)
        gate = workload.PerfGate(peer.control, peer.ack, timeout=timeout)
        self.addCleanup(gate.close)
        gate.open()
        return gate, peer

    def test_plain_ack_pair(self):
        gate, peer = self.gate([[b"ack\n"], [b"ack\n"]])
        gate.command("enable")
        self.assertTrue(gate.may_be_enabled)
        self.assertTrue(gate.enable_acknowledged)
        gate.command("disable")
        self.assertFalse(gate.may_be_enabled)
        self.assertTrue(gate.disable_acknowledged)
        self.assertEqual(peer.commands, [b"enable", b"disable"])

    def test_linux_515_ack_pair(self):
        gate, _ = self.gate([[b"ack\n\0"], [b"ack\n\0"]])
        gate.command("enable")
        gate.command("disable")
        self.assertTrue(gate.disable_acknowledged)

    def test_fragmented_ack_and_delayed_nul(self):
        gate, _ = self.gate([
            [b"a", b"c", b"k", b"\n", b"\0"],
            [b"a", b"ck", b"\n", b"\0"],
        ])
        gate.command("enable")
        gate.command("disable")
        self.assertFalse(gate.may_be_enabled)

    def test_buffered_reply_frames(self):
        gate, _ = self.gate([[b"\0ack\n\0ack\n\0"], None])
        gate.command("enable")
        gate.command("disable")
        self.assertTrue(gate.disable_acknowledged)

    def test_malformed_ack_preserves_disable_cleanup(self):
        gate, peer = self.gate([[b"a\0ck\n"], [b"ack\n\0"]])
        with self.assertRaisesRegex(RuntimeError, "Unexpected perf acknowledgement"):
            gate.command("enable")
        self.assertTrue(gate.may_be_enabled)
        self.assertFalse(gate.enable_acknowledged)
        gate.command("disable")
        self.assertFalse(gate.may_be_enabled)
        self.assertEqual(peer.commands, [b"enable", b"disable"])

    def test_oversized_ack_fails_even_if_padding_would_strip(self):
        gate, _ = self.gate([[b"\0" * 4097 + b"ack\n"]])
        with self.assertRaisesRegex(RuntimeError, "oversized"):
            gate.command("enable")
        self.assertFalse(gate.enable_acknowledged)

    def test_missing_ack_is_bounded_and_disable_still_possible(self):
        gate, _ = self.gate([None, [b"ack\n"]], timeout=0.1)
        with self.assertRaisesRegex(TimeoutError, "No acknowledgement"):
            gate.command("enable")
        self.assertTrue(gate.may_be_enabled)
        gate.command("disable")
        self.assertFalse(gate.may_be_enabled)

    def test_no_control_reader_times_out_and_closes(self):
        control = Path(self.temp.name) / "unopened-control"
        ack = Path(self.temp.name) / "unopened-ack"
        os.mkfifo(control)
        os.mkfifo(ack)
        gate = workload.PerfGate(control, ack, timeout=0.05)
        try:
            with self.assertRaisesRegex(TimeoutError, "control FIFO"):
                gate.open()
        finally:
            gate.close()
        self.assertIsNone(gate.control_fd)
        self.assertIsNone(gate.ack_fd)

    def test_full_driver_receipt_with_nul_ack(self):
        peer = FakePerf(self.temp.name, [[b"ack\n\0"], [b"ack\n\0"]])
        self.addCleanup(peer.close)
        source = Path(self.temp.name) / "benchmark.py"
        source.write_text(
            "def bench_nbody(loops, reference, iterations):\n    return 0.125\n",
            encoding="utf-8",
        )
        receipt = Path(self.temp.name) / "receipt.json"
        rc = workload.main([
            "--benchmark", "nbody", "--source", str(source.resolve()),
            "--calls", "3", "--warmups", "2", "--receipt", str(receipt),
            "--control-fifo", str(peer.control), "--ack-fifo", str(peer.ack),
            "--control-timeout", "0.5",
        ])
        result = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(rc, 0)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["completed_calls"], 3)
        self.assertEqual(result["completed_warmups"], 2)
        self.assertEqual(result["reported_benchmark_seconds"], 0.375)
        self.assertTrue(result["enable_acknowledged"])
        self.assertTrue(result["disable_acknowledged"])


class MeasuredWrapperTests(unittest.TestCase):
    def test_returns_durations_and_counts_only_successful_calls(self):
        values = iter([0.1, 0.2, 0.3])
        result = {"completed_calls": 0}
        self.assertEqual(
            workload.run_measured_calls(lambda: next(values), 3, result),
            [0.1, 0.2, 0.3],
        )
        self.assertEqual(result["completed_calls"], 3)

    def test_failed_call_retains_completed_count(self):
        values = iter([0.1])
        result = {"completed_calls": 0}
        with self.assertRaises(StopIteration):
            workload.run_measured_calls(lambda: next(values), 3, result)
        self.assertEqual(result["completed_calls"], 1)


if __name__ == "__main__":
    unittest.main()
