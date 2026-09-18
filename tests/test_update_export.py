"""Safe package updates and complete evidence export; no PMU required."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import export_results
import update_repository


def digest(data):
    return hashlib.sha256(data).hexdigest()


class ToolkitUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.package = self.root / 'package'
        for path in (self.repo, self.package):
            (path / 'tools').mkdir(parents=True)
        self.git('init', '-q')
        (self.repo / 'tools' / 'workload.py').write_bytes(b'old\n')
        (self.package / 'tools' / 'workload.py').write_bytes(b'new\n')
        (self.package / 'tools' / 'new.py').write_bytes(b'new helper\n')
        (self.repo / 'config.json').write_text('{"my_setting":42}\n')
        (self.repo / 'prompt.txt').write_text('my prompts\n')
        (self.repo / '.gitignore').write_text('results/\n.venv/\n')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture')
        self.manifest = {'schema_version': 1, 'release': 'v4.2', 'files': {
            'tools/workload.py': {'new_sha256': digest(b'new\n'), 'old_sha256': [digest(b'old\n')]},
            'tools/new.py': {'new_sha256': digest(b'new helper\n'), 'old_sha256': []}}}
        self.write_manifest()

    def git(self, *args):
        result = subprocess.run(['git', '-C', str(self.repo), *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def write_manifest(self):
        (self.package / 'UPDATE_MANIFEST.json').write_text(json.dumps(self.manifest))

    def test_dry_run_changes_nothing(self):
        result = update_repository.update(self.package, self.repo)
        self.assertEqual(len(result['changes']), 2)
        self.assertEqual((self.repo / 'tools/workload.py').read_bytes(), b'old\n')
        self.assertFalse((self.repo / 'archive').exists())
        self.assertFalse((self.repo / 'tools/new.py').exists())

    def test_update_backs_up_and_preserves_data_without_git_operations(self):
        (self.repo / 'results/run/source').mkdir(parents=True)
        (self.repo / 'results/run/source/run_benchmark.py').write_text('historical source\n')
        result = update_repository.update(self.package, self.repo, apply=True)
        self.assertEqual((self.repo / 'tools/workload.py').read_bytes(), b'new\n')
        self.assertEqual((self.repo / result['archive'] / 'original/tools/workload.py').read_bytes(), b'old\n')
        self.assertEqual((self.repo / 'config.json').read_text(), '{"my_setting":42}\n')
        self.assertEqual((self.repo / 'prompt.txt').read_text(), 'my prompts\n')
        self.assertEqual((self.repo / 'results/run/source/run_benchmark.py').read_text(), 'historical source\n')
        self.assertEqual(self.git('diff', '--cached', '--name-only'), '')
        self.assertEqual(self.git('rev-list', '--count', 'HEAD').strip(), '1')

    def test_tracked_changes_refused(self):
        (self.repo / 'tools/workload.py').write_text('my uncommitted edit\n')
        with self.assertRaisesRegex(ValueError, 'Tracked changes'):
            update_repository.update(self.package, self.repo, apply=True)
        self.assertFalse((self.repo / 'archive').exists())

    def test_committed_unknown_content_refused(self):
        (self.repo / 'tools/workload.py').write_text('my committed edit\n')
        self.git('add', 'tools/workload.py')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'custom')
        with self.assertRaisesRegex(ValueError, 'Modified or unknown'):
            update_repository.update(self.package, self.repo, apply=True)
        self.assertFalse((self.repo / 'archive').exists())

    def test_untracked_collision_refused(self):
        (self.repo / 'tools/new.py').write_text('my own tool\n')
        with self.assertRaisesRegex(ValueError, 'Modified or unknown'):
            update_repository.update(self.package, self.repo, apply=True)
        self.assertFalse((self.repo / 'archive').exists())

    def test_protected_manifest_path_refused(self):
        self.manifest['files']['config.json'] = {'new_sha256': digest(b'{}'), 'old_sha256': []}
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'Protected'):
            update_repository.update(self.package, self.repo, apply=True)

    def test_symlink_collision_and_archive_refused(self):
        (self.repo / 'tools/new.py').symlink_to(self.package / 'tools/new.py')
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            update_repository.update(self.package, self.repo, apply=True)
        (self.repo / 'tools/new.py').unlink()
        (self.repo / 'archive').symlink_to(self.root)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            update_repository.update(self.package, self.repo, apply=True)

    def test_tampered_package_refused(self):
        (self.package / 'tools/workload.py').write_text('changed after manifest\n')
        with self.assertRaisesRegex(ValueError, 'Package file missing or changed'):
            update_repository.update(self.package, self.repo, apply=True)


class EvidenceExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.run = self.repo / 'results/run-native'
        (self.run / 'source').mkdir(parents=True)
        (self.run / 'source/run_benchmark.py').write_bytes(b'original benchmark\n')
        (self.run / 'provenance.json').write_text(json.dumps({
            'source_sha256': digest(b'original benchmark\n'),
            'source_path': '/old-vm/repo/results/run-native/source/run_benchmark.py'}))
        (self.run / 'perf-record.command.json').write_text('{}')
        (self.run / 'perf.data').write_bytes(b'PERF\x00\xffbinary')
        (self.run / 'cprofile.command.json').write_text('{}')
        (self.run / 'python.pstats').write_bytes(b'PSTATS\x00binary')
        (self.repo / '.gitignore').write_text('results/**/perf.data\nresults/**/source/\n*.pstats\n')
        (self.repo / 'config.json').write_text('{}')
        self.output = self.root / 'evidence.zip'

    def test_export_contains_ignored_evidence_and_exact_checksums(self):
        result = export_results.export(self.repo, self.output, all_runs=True)
        self.assertEqual(result['gaps'], [])
        with zipfile.ZipFile(self.output) as archive:
            for name, item in result['files'].items():
                data = archive.read(name)
                self.assertEqual(digest(data), item['sha256'])
                self.assertEqual(len(data), item['bytes'])
            self.assertEqual(archive.read('results/run-native/perf.data'), b'PERF\x00\xffbinary')
            self.assertIn('results/run-native/python.pstats', archive.namelist())
            self.assertIn('results/run-native/source/run_benchmark.py', archive.namelist())

    def test_gaps_are_reported_without_reconstructing_evidence(self):
        (self.run / 'source/run_benchmark.py').unlink()
        (self.run / 'perf.data').unlink()
        (self.run / 'python.pstats').unlink()
        result = export_results.export(self.repo, self.output, selected=['run-native'])
        self.assertEqual(len(result['gaps']), 3)
        self.assertFalse((self.run / 'source/run_benchmark.py').exists())
        with zipfile.ZipFile(self.output) as archive:
            self.assertNotIn('results/run-native/perf.data', archive.namelist())

    def test_symlinks_and_fifos_skipped(self):
        (self.run / 'outside-link').symlink_to(self.root)
        os.mkfifo(self.run / 'ack.fifo')
        result = export_results.export(self.repo, self.output, all_runs=True)
        self.assertEqual(len(result['skipped']), 2)
        with zipfile.ZipFile(self.output) as archive:
            self.assertNotIn('results/run-native/ack.fifo', archive.namelist())
            self.assertNotIn('results/run-native/outside-link', archive.namelist())

    def test_output_collision_and_inside_repo_refused(self):
        with self.assertRaisesRegex(ValueError, 'outside the repository'):
            export_results.export(self.repo, self.repo / 'evidence.zip', all_runs=True)
        self.output.write_bytes(b'preserve existing')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            export_results.export(self.repo, self.output, all_runs=True)
        self.assertEqual(self.output.read_bytes(), b'preserve existing')

    def test_run_escape_refused(self):
        with self.assertRaisesRegex(ValueError, 'direct, non-symlink child'):
            export_results.export(self.repo, self.output, selected=['../'])


if __name__ == '__main__':
    unittest.main()
