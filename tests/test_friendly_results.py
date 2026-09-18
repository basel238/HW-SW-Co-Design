"""Verify evidence preservation and fail-closed course status, without real perf."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import friendly_results as f
import course_stages as course
import pipeline as p


class CompactEvidenceTests(unittest.TestCase):
    def test_lossless_compaction_and_retained_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root/'old-run'
            old.mkdir()
            (old/'keep.txt').write_text('historical data')
            out = root/'new-run'
            raw = out/'details'/'native'
            raw.mkdir(parents=True)
            payload = b'PERF\x00\xff' * 10000
            (raw/'perf.data').write_bytes(payload)
            result = f.archive_evidence(out)
            self.assertEqual(result['verified_files'], 1)
            self.assertFalse((out/'details').exists())
            self.assertEqual((old/'keep.txt').read_text(), 'historical data')
            with zipfile.ZipFile(out/'evidence.zip') as archive:
                self.assertEqual(archive.read('details/native/perf.data'), payload)
                self.assertIn('details/native/perf.data', json.loads(archive.read('EVIDENCE-MANIFEST.json'))['files'])

    def test_collision_or_nonregular_file_retains_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            details = out/'details'
            details.mkdir()
            (details/'keep').write_text('raw data')
            (out/'evidence.zip').write_bytes(b'old archive')
            with self.assertRaises(FileExistsError):
                f.archive_evidence(out)
            self.assertTrue((details/'keep').exists())
            (out/'evidence.zip').unlink()
            (details/'link').symlink_to(details/'keep')
            with self.assertRaises(ValueError):
                f.archive_evidence(out)
            self.assertTrue((details/'keep').exists())

    def test_keep_details_and_portable_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out/'details').mkdir()
            (out/'details'/'receipt.json').write_text('{}')
            f.archive_evidence(out, keep_details=True)
            self.assertTrue((out/'details'/'receipt.json').exists())
            self.assertEqual(f.portable_status({'path': str(out/'details'/'receipt.json')}, out),
                             {'path': 'details/receipt.json'})

    def test_failed_perf_cannot_be_replaced_by_python_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out/'details').mkdir()
            fixture = out/'details'/'fixture'
            fixture.mkdir()
            (fixture/'python.svg').write_text('<svg/>')
            args = argparse.Namespace(benchmark='nbody',
                                      skip_python_sampling=True, skip_optional_counters=True)
            with patch.object(p, 'RUN_ROOT', out/'details'), \
                 patch.object(p, 'gate_probe', return_value=(fixture, False)), \
                 patch.object(course, 'run_reference', return_value=(fixture, True)), \
                 patch.object(p, 'timing', return_value=fixture), \
                 patch.object(p, 'python_profile', return_value=fixture), \
                 patch.object(p, 'native') as native:
                status = course.collect_stages(p.config(), args, out)
            native.assert_not_called()
            self.assertFalse(status['automated_collection_complete'])
            self.assertIn('nbody debug perf profile', status['required_missing'])
            self.assertFalse(status['coursework_complete'])


if __name__ == '__main__':
    unittest.main()
