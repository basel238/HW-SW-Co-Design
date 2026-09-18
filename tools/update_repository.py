#!/usr/bin/env python3
"""Safely update an installed toolkit from an extracted package; dry-run by default.

Preserves benchmark sources, results, configuration and written reports. Only
manifest-listed toolkit files with recognized previous content may be replaced.
Stop running measurements before applying. Does not stage, commit or push.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile

PACKAGE = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    '.gitignore', 'README.md', 'QUICKSTART.md', 'CHANGELOG.md', 'TESTING.md',
    'STAGES_1_3.md', 'UPDATING.md', 'MIGRATION.md', 'ANALYSIS_REVIEW.md',
    'ALTERNATIVE_SCRIPTS_REVIEW.md', 'requirements.txt',
    'requirements-profile.txt', 'requirements-reference.txt', 'requirements-course.txt',
    'script_nbody.sh', 'script_raytrace.sh', 'PACKAGE_SHA256.json',
}
ALLOWED_DIRS = {'tools', 'scripts', 'tests', 'docs', 'licenses', 'vendor'}


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def safe_name(name):
    parts = PurePosixPath(name).parts
    if (not name or name != PurePosixPath(name).as_posix() or
            PurePosixPath(name).is_absolute() or '..' in parts or
            any(part in ('.git', '') for part in parts) or '\\' in name):
        raise ValueError('Unsafe manifest path: ' + repr(name))
    if name not in ROOT_FILES and (len(parts) < 2 or parts[0] not in ALLOWED_DIRS):
        raise ValueError('Protected or unrecognized update path: ' + name)
    return name


def check_path(root, relative):
    """Reject symlinks at every component, including a dangling final link."""
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Symlink in update path: ' + str(current))
        if current.exists() and current != root / relative and not current.is_dir():
            raise ValueError('Non-directory parent in update path: ' + str(current))
    return current


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or 'Git command failed')
    return result.stdout.strip()


def update(package, repo, apply=False):
    package = package.resolve(strict=True)
    repo = repo.resolve(strict=True)
    if package == repo or package in repo.parents or repo in package.parents:
        raise ValueError('Extract the update package outside the target repository')
    if Path(git(repo, 'rev-parse', '--show-toplevel')).resolve() != repo:
        raise ValueError('--repo must be the Git repository root')
    if git(repo, 'status', '--porcelain', '--untracked-files=no'):
        raise ValueError('Tracked changes exist. Commit or save them before updating; no changes made.')
    manifest_path = check_path(package, 'UPDATE_MANIFEST.json')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('schema_version') != 1 or manifest.get('release') != 'v4.2':
        raise ValueError('Unsupported update manifest schema or release')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files:
        raise ValueError('Empty or invalid update manifest')
    gitlinks = []
    for entry in git(repo, 'ls-files', '--stage', '-z').split('\0'):
        if entry:
            metadata, name = entry.split('\t', 1)
            if metadata.split()[0] == '160000':
                gitlinks.append(name)
    changes, unchanged = [], []
    for name, item in sorted(files.items()):
        safe_name(name)
        if not isinstance(item, dict):
            raise ValueError('Invalid manifest entry: ' + name)
        new = item.get('new_sha256')
        old = item.get('old_sha256')
        if not isinstance(old, list) or not all(
                isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value)
                for value in [new, *old]):
            raise ValueError('Invalid manifest hashes: ' + name)
        source = check_path(package, name)
        if not source.is_file() or digest(source) != new:
            raise ValueError('Package file missing or changed: ' + name)
        if any(name == link or name.startswith(link + '/') for link in gitlinks):
            raise ValueError('Update overlaps a Git submodule: ' + name)
        target = check_path(repo, name)
        before = None
        if target.exists():
            if not target.is_file():
                raise ValueError('Update target is not a regular file: ' + name)
            before = digest(target)
            if before == new:
                unchanged.append(name)
                continue
            if before not in old:
                raise ValueError('Modified or unknown file would be overwritten: ' + name)
        changes.append({'path': name, 'before_sha256': before, 'after_sha256': new})
    # Check the archive parent even in dry-run mode to catch unsafe destinations.
    check_path(repo, 'archive')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    archive = Path('archive') / ('update-v4.2-' + stamp)
    check_path(repo, archive)
    plan = {'schema_version': 1, 'release': 'v4.2', 'package': str(package),
            'repository': str(repo), 'base_commit': git(repo, 'rev-parse', 'HEAD'),
            'archive': archive.as_posix(), 'changes': changes, 'unchanged': unchanged,
            'operation': 'Copy toolkit files after backups; no deletion, staging, commit or push',
            'preserved': ['config.json', 'ENVIRONMENT.md', 'src/', 'results/',
                          'reports/', 'hw/', 'prompt.txt', '.venv/', 'existing archive/']}
    if not apply or not changes:
        return plan
    archive_dir = repo / archive
    archive_dir.mkdir(parents=True, exist_ok=False)
    (archive_dir / '.gitignore').write_text('*\n')
    (archive_dir / 'UPDATE.json').write_text(json.dumps(plan, indent=2) + '\n')
    shutil.copy2(manifest_path, archive_dir / 'UPDATE_MANIFEST.json')
    # Preserve every replaced file before the first target write.
    for change in changes:
        if change['before_sha256'] is not None:
            target = check_path(repo, change['path'])
            if digest(target) != change['before_sha256']:
                raise ValueError('Target changed during update: ' + change['path'])
            backup = archive_dir / 'original' / change['path']
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
    for change in changes:
        name = change['path']
        target = check_path(repo, name)
        current = digest(target) if target.is_file() else None
        if current != change['before_sha256']:
            raise ValueError('Target changed during update: ' + name)
        source = check_path(package, name)
        if digest(source) != change['after_sha256']:
            raise ValueError('Package changed during update: ' + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix='.toolkit-update-', dir=target.parent)
        os.close(handle)
        try:
            shutil.copy2(source, temporary)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--json', action='store_true', help='Print the full machine-readable update plan')
    args = parser.parse_args()
    plan = update(PACKAGE, args.repo, args.apply)
    if args.json:
        print(json.dumps(plan, indent=2))
    else:
        print('Repository:', plan['repository'])
        print('Toolkit files to update:', len(plan['changes']), '| already current:', len(plan['unchanged']))
        for change in plan['changes']:
            print(('  replace ' if change['before_sha256'] else '  add     ') + change['path'])
        print('Preserved: configuration, environments, benchmark sources, results, reports and prompt history.')
    if not args.apply:
        print('\nDry-run only. Stop active measurements, then add --apply to install.')
    elif not plan['changes']:
        print('\nToolkit is already up to date; nothing was changed.')
    else:
        print('\nUpdated. Backups:', plan['archive'])
        print('Review from the target repository: git status --short; git diff --stat; git diff')
        print('No files were staged, committed or pushed. Configuration and experiment data were preserved.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        print('No user files are deleted. If applying stopped, inspect git diff and archive/update-v4.2-* before retrying.', file=sys.stderr)
        raise SystemExit(2)
