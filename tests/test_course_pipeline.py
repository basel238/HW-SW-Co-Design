"""Whole-course output integration with clearly synthetic sampler/framework data.

Actual benchmark timings, cProfile, workload drivers, FIFO acknowledgements and
FlameGraph rendering run. The perf samples/counters and framework-reference
fixture are synthetic, so these tests are software checks, not course evidence.
Actual pyperformance CLI integration is separately exercised with --smoke.
"""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import sysconfig
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import course_stages
import pipeline as p
from test_perf_pipeline import SYNTHETIC_PERF


@unittest.skipUnless(hasattr(os, "mkfifo") and shutil.which("perl"),
                     "Requires POSIX FIFO exchanges and the real Perl renderer")
@unittest.skipUnless(importlib.util.find_spec("pyperf"),
                     "Run with .venv/bin/python for actual timing and cProfile")
@unittest.skipUnless(sysconfig.get_config_var("Py_DEBUG"), "Actual measurements require debug Python")
class CoursePipelineIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        package = Path(__file__).resolve().parents[1]
        shutil.copytree(package, self.root, ignore=shutil.ignore_patterns(
            ".course-cache", ".venv*", "venv*", "results", "__pycache__", ".git", "exports"
        ))
        self.settings = json.loads((self.root / "config.json").read_text())
        self.settings["timing"].update(processes=1, values=2, warmups=1, loops=1)
        self.settings["nbody"].update(iterations=2000, profile_calls=2, profile_warmups=1)
        self.settings["raytrace"].update(width=24, height=24, profile_calls=2, profile_warmups=1)
        self.settings.update(stat_repeats=1, affinity=None, command_timeout_seconds=30)
        self.args = types.SimpleNamespace(
            benchmark=None, skip_python_sampling=True,
            skip_optional_counters=True, keep_details=False,
        )
        binary_directory = Path(self.temp.name) / "bin"
        binary_directory.mkdir()
        binary = binary_directory / "perf"
        binary.write_text(SYNTHETIC_PERF)
        binary.chmod(0o755)
        for patcher in (
            patch.object(p, "ROOT", self.root),
            patch.object(p, "TOOLS", self.root / "tools"),
            patch.object(p, "PY", sys.executable),
            patch.object(p, "RUN_ROOT", None),
            patch.object(course_stages, "run_reference", self.synthetic_framework_reference),
            patch.dict(os.environ, {
                "PATH": str(binary_directory) + os.pathsep + os.environ.get("PATH", ""),
                "TEST_SYNTHETIC_PERF_MODE": "valid",
            }),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def synthetic_framework_reference(settings, benchmark=None):
        out = p.new_run("debug-pyperformance-reference")
        # This fixture is intentionally marked, never mistaken for real timing.
        p.dump(out / "pyperformance.json", {
            "synthetic_fixture_only": True,
            "note": "Actual pyperformance CLI is smoke-tested separately.",
        })
        p.dump(out / "reference-status.json", {
            "available": True, "synthetic_fixture_only": True,
            "smoke_only": False, "unavailable_reason": None,
        })
        return out, True

    def only_run(self):
        outputs = list((self.root / "results").iterdir())
        self.assertEqual(len(outputs), 1, outputs)
        self.assertTrue(outputs[0].is_dir())
        return outputs[0]

    def test_one_compact_run_preserves_evidence_and_compliance_boundaries(self):
        rc = course_stages.run(self.settings, self.args)
        self.assertEqual(rc, 0)
        self.assertIsNone(p.RUN_ROOT)
        out = self.only_run()
        self.assertFalse((out / "details").exists())
        for name in ("README.md", "summary.json", "framework.json", "evidence.zip"):
            self.assertGreater((out / name).stat().st_size, 0, name)
        summary = json.loads((out / "summary.json").read_text())
        self.assertTrue(summary["automated_collection_complete"])
        self.assertTrue(summary["literal_guide_collection_complete"])
        self.assertEqual(summary["interpreter_kind"], "debug")
        self.assertNotIn("guide_debug_reference", summary)
        self.assertNotIn("release_only", summary)
        self.assertFalse(summary["coursework_complete"])
        self.assertEqual(summary["manual_review"], "pending")
        self.assertEqual(summary["required_missing"], [])
        self.assertFalse(summary["evidence"]["details_retained"])
        self.assertGreater(summary["evidence"]["verified_files"], 0)
        overview = (out / "README.md").read_text()
        self.assertIn("Required collection: complete", overview)
        self.assertIn("Guide collection: **complete**", overview)
        self.assertNotIn("Traceback", overview)
        with zipfile.ZipFile(out / "evidence.zip") as archive:
            names = set(archive.namelist())
            self.assertIn("EVIDENCE-MANIFEST.json", names)
            manifest = json.loads(archive.read("EVIDENCE-MANIFEST.json"))
            for bench in ("nbody", "raytrace"):
                visible = out / bench
                for name in ("README.md", "timing.json", "perf.svg"):
                    self.assertGreater((visible / name).stat().st_size, 0, bench + "/" + name)
                report = (visible / "README.md").read_text()
                self.assertIn("Unprofiled debug runtime", report)
                self.assertNotIn("guide-perf.svg", report)
                self.assertFalse((visible / "guide-perf.svg").exists())
                self.assertIn("cProfile: top 12", report)
                self.assertNotIn("Traceback", report)
                self.assertIn("<svg", (visible / "perf.svg").read_text())
                native = f"details/{bench}-baseline-native/"
                for suffix in ("perf.data", "workload.json", "source/run_benchmark.py", "native.folded"):
                    self.assertIn(native + suffix, names)
                    self.assertIn(native + suffix, manifest["files"])
                receipt = json.loads(archive.read(native + "workload.json"))
                self.assertEqual(receipt["status"], "ok")
                self.assertTrue(receipt["enable_acknowledged"])
                self.assertTrue(receipt["disable_acknowledged"])
                self.assertEqual(receipt["completed_calls"], 2)
                self.assertTrue(summary["benchmarks"][bench]["native"]["path"].startswith("details/"))

    def test_failed_gate_still_produces_compact_readable_failure_report(self):
        self.args.benchmark = "nbody"

        def failed_probe(settings):
            out = p.new_run("perf-gate-probe")
            p.dump(out / "gate-probe.json", {"passed": False, "synthetic_fixture_only": True})
            return out, False

        with patch.object(p, "gate_probe", failed_probe), patch.object(p, "native") as native:
            rc = course_stages.run(self.settings, self.args)
        self.assertEqual(rc, 3)
        native.assert_not_called()
        out = self.only_run()
        self.assertFalse((out / "details").exists())
        self.assertTrue((out / "evidence.zip").is_file())
        self.assertFalse((out / "nbody" / "perf.svg").exists())
        summary = json.loads((out / "summary.json").read_text())
        self.assertFalse(summary["automated_collection_complete"])
        self.assertIn("nbody debug perf profile", summary["required_missing"])
        self.assertIn("Missing required perf evidence", (out / "nbody" / "README.md").read_text())
        self.assertIn("INCOMPLETE", (out / "README.md").read_text())


if __name__ == "__main__":
    unittest.main()
