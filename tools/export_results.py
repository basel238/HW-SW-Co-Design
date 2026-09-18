#!/usr/bin/env python3
"""Export complete local evidence, including Git-ignored perf.data and sources.

Run on the measurement VM. No evidence is reconstructed from current sources.
The checksum manifest records missing evidence and skipped links/special files.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
METADATA_FILES = ('config.json', 'ENVIRONMENT.md', 'SOURCES.json', 'PACKAGE_SHA256.json',
                  'UPDATE_MANIFEST.json', 'requirements.txt', 'requirements-profile.txt',
                  'requirements-course.txt', 'README.md', 'STAGES_1_3.md', 'CHANGELOG.md',
                  'script_nbody.sh', 'script_raytrace.sh')
METADATA_DIRS = ('tools', 'scripts', 'tests', 'docs', 'vendor', 'licenses')
SKIP_DIRS = {'.git', '.venv', 'venv', '__pycache__', 'node_modules'}


def sha256(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def within(path, root):
    return path == root or root in path.parents


def regular_files(root, path, skipped):
    """Do not follow links or open FIFO/device files, even inside result trees."""
    mode = path.lstat().st_mode
    relative = path.relative_to(root).as_posix()
    if stat.S_ISLNK(mode):
        skipped.append({'path': relative, 'reason': 'symlink'})
    elif stat.S_ISREG(mode):
        yield path
    elif stat.S_ISDIR(mode):
        if path.name in SKIP_DIRS:
            skipped.append({'path': relative, 'reason': 'environment or cache directory'})
            return
        for child in sorted(path.iterdir()):
            yield from regular_files(root, child, skipped)
    else:
        skipped.append({'path': relative, 'reason': 'non-regular file (FIFO, socket or device)'})


def evidence_gaps(root, runs, included):
    gaps = []
    def missing(path, reason):
        name = path.relative_to(root).as_posix()
        if name not in included:
            gaps.append({'path': name, 'reason': reason})
    for run in runs:
        provenance = run / 'provenance.json'
        if provenance.is_file() and not provenance.is_symlink():
            try:
                data = json.loads(provenance.read_text())
            except (ValueError, UnicodeError) as exc:
                gaps.append({'path': provenance.relative_to(root).as_posix(),
                             'reason': 'Invalid provenance JSON: ' + str(exc)})
            else:
                snapshot = run / 'source' / 'run_benchmark.py'
                if data.get('source_sha256') or data.get('source_path'):
                    missing(snapshot, 'Frozen benchmark source absent; not reconstructed from current src/')
                    if snapshot.relative_to(root).as_posix() in included and data.get('source_sha256'):
                        if sha256(snapshot) != data['source_sha256']:
                            gaps.append({'path': snapshot.relative_to(root).as_posix(),
                                         'reason': 'Source snapshot hash differs from recorded provenance'})
        # Logs are enough to establish that a recording/profile was attempted.
        if any((run / name).exists() for name in ('perf-record.command.json', 'perf-record.stderr.txt', 'native.svg')):
            missing(run / 'perf.data', 'Native recording was attempted but raw perf.data is absent')
        if any((run / name).exists() for name in ('cprofile.command.json', 'cprofile.stdout.txt', 'python-self.txt')):
            missing(run / 'python.pstats', 'cProfile run was attempted but binary python.pstats is absent')
    return gaps


def export(root, output, selected=(), all_runs=False):
    root = root.resolve(strict=True)
    results = root / 'results'
    if results.is_symlink() or not results.is_dir():
        raise ValueError('Expected a real results/ directory in --repo')
    output = output.absolute()
    if output.is_symlink() or output.exists():
        raise ValueError('Output already exists; choose a new archive filename')
    if not output.parent.is_dir():
        raise ValueError('Output parent directory does not exist')
    output = output.parent.resolve(strict=True) / output.name
    if within(output, root):
        raise ValueError('Write the export outside the repository, e.g. ../profiling-evidence.zip')
    if all_runs == bool(selected):
        raise ValueError('Select either --all or one or more --run arguments')
    candidates = sorted(results.iterdir()) if all_runs else [Path(name) for name in selected]
    runs = []
    for candidate in candidates:
        if not candidate.parts or '..' in candidate.parts:
            raise ValueError('Run must be a direct, non-symlink child of results/: ' + str(candidate))
        if not candidate.is_absolute():
            candidate = root / candidate if candidate.parts[0] == 'results' else results / candidate
        # Only immediate run directories are accepted; never dereference aliases.
        if candidate.resolve().parent != results.resolve() or candidate.is_symlink():
            raise ValueError('Run must be a direct, non-symlink child of results/: ' + str(candidate))
        if not candidate.is_dir():
            if all_runs:
                continue
            raise ValueError('Run directory not found: ' + str(candidate))
        if candidate.name not in SKIP_DIRS:
            runs.append(candidate.resolve())
    runs = sorted(set(runs))
    if not runs:
        raise ValueError('No result run directories selected')
    skipped = []
    files = {}
    paths = [*runs]
    paths += [root / name for name in METADATA_FILES + METADATA_DIRS if (root / name).exists() or (root / name).is_symlink()]
    for path in paths:
        for file in regular_files(root, path, skipped):
            files[file.relative_to(root).as_posix()] = file
    included = set(files)
    manifest = {'schema_version': 1, 'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'selected_runs': [run.relative_to(root).as_posix() for run in runs],
                'files': {}, 'skipped': skipped, 'gaps': evidence_gaps(root, runs, included),
                'note': 'Current toolkit/configuration are supplied for reference. Per-run provenance and snapshots describe historical measurements; nothing was reconstructed.',
                'git': {}}
    for label, args in [('commit', ['rev-parse', 'HEAD']), ('status', ['status', '--porcelain', '--untracked-files=no'])]:
        try:
            result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True, timeout=10)
            manifest['git'][label] = result.stdout.strip() if result.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            manifest['git'][label] = None
    # Exclusive mode avoids overwriting an archive. On failure the partial ZIP is
    # intentionally retained for inspection, and the caller receives an error.
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for name, path in sorted(files.items()):
            before = path.lstat()
            if not stat.S_ISREG(before.st_mode):
                raise ValueError('Evidence changed type during export: ' + name)
            value = hashlib.sha256()
            count = 0
            info = zipfile.ZipInfo.from_file(path, name)
            info.compress_type = zipfile.ZIP_DEFLATED
            with path.open('rb') as source, archive.open(info, 'w', force_zip64=True) as target:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    target.write(block)
                    value.update(block)
                    count += len(block)
            after = path.lstat()
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                raise ValueError('Evidence changed while exporting: ' + name + '. Stop measurements and retry with a new output name.')
            manifest['files'][name] = {'sha256': value.hexdigest(), 'bytes': count}
        archive.writestr('EXPORT-MANIFEST.json', json.dumps(manifest, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--all', action='store_true', help='Include all direct result run directories')
    group.add_argument('--run', action='append', default=[], help='Run directory name, repeat to select several')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = export(args.repo, args.output, args.run, args.all)
    print('Exported', len(manifest['files']), 'files to', args.output.resolve())
    print('SHA256:', sha256(args.output))
    print('Evidence gaps:', len(manifest['gaps']), '| skipped unsafe/cache entries:', len(manifest['skipped']))
    for gap in manifest['gaps']:
        print('GAP:', gap['path'] + ':', gap['reason'])
    print('Inspect EXPORT-MANIFEST.json in the archive. Export success does not certify measurement validity.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        print('ERROR:', exc, file=sys.stderr)
        print('No source evidence was modified. A failed export may leave a partial archive; use a new output filename when retrying.', file=sys.stderr)
        raise SystemExit(2)
