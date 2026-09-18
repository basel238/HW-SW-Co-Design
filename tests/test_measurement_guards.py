"""Run with .venv/bin/python -m unittest discover -s tests -v.

Synthetic observations test software decisions, never hardware accuracy.
"""
import copy
import json
import shutil
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import pipeline as p
from measurement_extras import source_diff, probe_status, jit_perf_version_supported


def events(cycles=1000, instructions=2000, misses=0, running=100):
    return {name + ":u": {"count": value, "raw_count": str(value), "unit": "",
                          "counter_runtime": 10000, "running_percent": running}
            for name, value in (("cycles", cycles), ("instructions", instructions), ("cache-misses", misses))}


class MeasurementGuards(unittest.TestCase):
    def test_zero_cycles_never_become_ipc(self):
        result = p.stat_metrics(events(cycles=0), ("instructions", "cycles", "ipc", 1), True)
        self.assertIsNone(result["ipc"])
        self.assertIsNone(result["cpi"])

    def test_mpki_can_exist_when_cycles_do_not(self):
        result = p.stat_metrics(events(cycles=0, misses=4), ("cache-misses", "instructions", "generic_cache_mpki", 1000), True)
        self.assertEqual(result["generic_cache_mpki"], 2)

    def test_zero_misses_are_legitimate(self):
        result = p.stat_metrics(events(), ("cache-misses", "instructions", "generic_cache_mpki", 1000), True)
        self.assertEqual(result["generic_cache_mpki"], 0)

    def test_invalid_instruction_denominator(self):
        for count in (0, None):
            result = p.stat_metrics(events(instructions=count), ("cache-misses", "instructions", "generic_cache_mpki", 1000), True)
            self.assertIsNone(result["generic_cache_mpki"])

    def test_multiplexed_or_failed_collection_is_not_accepted(self):
        for running, collected in ((50, True), (None, True), (100, False)):
            result = p.stat_metrics(events(running=running), ("instructions", "cycles", "ipc", 1), collected)
            self.assertIsNone(result["ipc"])

    def test_reference_cycle_metric_has_distinct_name(self):
        data = events()
        data['ref-cycles:u'] = data.pop('cycles:u')
        result = p.stat_metrics(data, ("instructions", "ref-cycles", "instructions_per_reference_cycle", 1), True)
        self.assertEqual(result['instructions_per_reference_cycle'], 2)
        self.assertNotIn('ipc', result)

    def test_probe_categories(self):
        self.assertEqual(probe_status(127, 'No such file', {}), 'tool_missing_or_not_executable')
        self.assertEqual(probe_status(255, 'No permission to enable cycles', {}), 'permission_denied')
        self.assertEqual(probe_status(0, '', events(cycles=0)), 'zero_on_busy_workload')
        self.assertEqual(probe_status(0, '', events(misses=1, running=50)), 'insufficient_running_fraction')
        self.assertEqual(probe_status(0, '', events(misses=1)), 'count_and_scheduling_sanity_passed')

    def test_jit_version_does_not_misread_distro_suffix(self):
        for value in ('perf version 5.15.0', 'perf version 6.7-3', 'perf version 6.8', 'unknown'):
            self.assertFalse(jit_perf_version_supported(value), value)
        for value in ('perf version 6.7.2', 'perf version 6.9.0', 'perf version 7.0'):
            self.assertTrue(jit_perf_version_supported(value), value)

    def test_even_rounds_enforced(self):
        original = json.loads((p.ROOT / 'config.json').read_text())
        with tempfile.TemporaryDirectory() as folder, patch.object(p, 'ROOT', Path(folder)):
            for count in (1, 3, 5):
                settings = copy.deepcopy(original)
                settings['compare_rounds'] = count
                (Path(folder) / 'config.json').write_text(json.dumps(settings))
                with self.assertRaises(ValueError):
                    p.config()
            original['compare_rounds'] = 4
            (Path(folder) / 'config.json').write_text(json.dumps(original))
            self.assertEqual(p.config()['compare_rounds'], 4)

    def test_whole_tree_diff_includes_helpers_and_binary_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); a = root/'a'; b = root/'b'; a.mkdir(); b.mkdir()
            for d in (a,b): (d/'run_benchmark.py').write_text('unchanged\n')
            (a/'helper.py').write_text('old'); (b/'helper.py').write_text('new')
            (a/'removed.py').write_text('gone\n'); (b/'added.py').write_text('new\n')
            (b/'data.bin').write_bytes(b'\x00\xff')
            source_diff(a, b, root)
            result = json.loads((root/'source-changes.json').read_text())
            self.assertEqual({x['path'] for x in result['changes']}, {'helper.py','removed.py','added.py','data.bin'})
            text = (root/'source.diff').read_text()
            self.assertIn('Binary file changed: data.bin', text)
            self.assertIn('No newline at end of file', text)

    @unittest.skipUnless(shutil.which('perl'), 'Perl required for real SVG generation')
    def test_pyspy_output_path_with_explicit_synthetic_samples(self):
        # Only sampler observations are synthetic; the bundled renderer actually runs.
        package = p.ROOT
        settings = json.loads((package / 'config.json').read_text())
        real_command = p.command
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'project'
            shutil.copytree(package, root, ignore=shutil.ignore_patterns('.venv','.venv-guide','.course-cache','results','__pycache__','.git'))
            binary = root / 'synthetic-py-spy'
            binary.write_text('TEST FIXTURE ONLY\n')
            def simulate(argv, directory, name, *args, **kwargs):
                directory = Path(directory)
                if str(argv[0]) == str(binary):
                    if '--version' in argv:
                        (directory / 'pyspy-version.stdout.txt').write_text('py-spy 0.4.2\n')
                    else:
                        self.assertEqual(argv[argv.index('--format')+1], 'raw')
                        raw = Path(argv[argv.index('--output')+1])
                        raw.write_text('module;run_measured_calls (' + str((root/'tools/workload.py').resolve()) + ':200);advance (fixture.py:1) 600\nmodule;offset (fixture.py:2) 400\n')
                        source = directory/'source/run_benchmark.py'
                        receipt = dict(status='ok', benchmark='nbody', calls=settings['nbody']['profile_calls'],
                                       completed_calls=settings['nbody']['profile_calls'], warmups=1, completed_warmups=1,
                                       source_sha256=p.digest(source), source_tree_sha256=p.tree_hash(source.parent))
                        (directory / 'workload.json').write_text(json.dumps(receipt))
                        (directory / 'pyspy.stdout.txt').write_text('Wrote raw flamegraph data. Samples: 1000 Errors: 0\n')
                        (directory / 'pyspy.stderr.txt').write_text('')
                    return 0
                return real_command(argv, directory, name, *args, **kwargs)
            with patch.object(p, 'ROOT', root), patch.object(p, 'TOOLS', root/'tools'), \
                 patch.object(p, 'require_debug_python'), \
                 patch.object(p, 'pyspy_executable', return_value=binary), patch.object(p, 'command', simulate):
                out, ok = p.pyspy_profile('nbody','baseline',settings)
            self.assertTrue(ok)
            status = json.loads((out/'pyspy-status.json').read_text())
            self.assertEqual(status['sample_count'], 1000)
            self.assertIn('NOT perf-gated', status['scope'])
            self.assertIn('<svg', (out/'python-sampled.svg').read_text())
            self.assertIn('samples', (out/'python-sampled.svg').read_text())
            self.assertEqual(status['measured_sample_count'], 600)
            self.assertIn('<svg', (out/'python-measured.svg').read_text())


if __name__ == '__main__':
    unittest.main()
