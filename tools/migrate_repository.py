#!/usr/bin/env python3
"""Archive legacy files and install this complete package in an existing Git repo.

Default is a read-only plan. --apply creates a branch, preserves old files,
installs the package, stages exact files, and creates a local commit. Never pushes.
Run this from an extracted package OUTSIDE the target repository.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

PACKAGE = Path(__file__).resolve().parents[1]


def git(repo, *args, check=True):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    repo = args.repo.resolve(strict=True)
    if Path(git(repo, 'rev-parse', '--show-toplevel')).resolve() != repo:
        raise ValueError('--repo must name the repository root')
    if PACKAGE == repo or repo in PACKAGE.parents or PACKAGE in repo.parents:
        raise ValueError('Extract the migration package outside the target repository')
    if git(repo, 'status', '--porcelain', '--untracked-files=all'):
        raise ValueError('Working tree must be clean, including untracked files. Commit or save your current work first.')
    manifest = json.loads((PACKAGE/'PACKAGE_SHA256.json').read_text())
    for name, expected in manifest.items():
        p = PACKAGE/name
        if p.is_symlink() or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise ValueError('Package file missing or changed: ' + name)
    if any(Path(name).is_absolute() or '..' in Path(name).parts or '.git' in Path(name).parts for name in manifest):
        raise ValueError('Invalid package manifest paths')
    payload = sorted([*manifest, 'PACKAGE_SHA256.json'])
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    archive = Path('archive')/('before-v4-' + stamp)
    branch = 'chore/measurement-layout-' + stamp
    roots = {Path(name).parts[0] for name in payload}
    roots.update(('run_scripts', 'FlameGraph'))
    for pattern in ('*_base.json', '*_opt.json', '*.svg', 'perfstat_*.txt',
                    'report_nbody.txt', 'report_raytrace.txt', 'perf.data*', 'out.perf', 'out.folded'):
        roots.update(p.name for p in repo.glob(pattern))
    moves = sorted(name for name in roots if (repo/name).exists() or (repo/name).is_symlink())
    if (repo/archive).exists():
        raise ValueError('Archive destination already exists; retry after one second')
    gitlinks = []
    for entry in git(repo, 'ls-files', '--stage', '-z').split('\0'):
        if not entry:
            continue
        metadata, name = entry.split('\t', 1)
        mode, commit, stage = metadata.split()
        if mode == '160000':
            gitlinks.append({'path': name, 'commit': commit, 'stage': stage})
    bundled_commit = json.loads((PACKAGE/'vendor/FlameGraph/PROVENANCE.json').read_text())['commit']
    supported_orphan = (gitlinks == [{'path': 'FlameGraph', 'commit': bundled_commit, 'stage': '0'}]
                        and not (repo/'.gitmodules').exists()
                        and not git(repo, 'ls-files', '--', '.gitmodules'))
    if gitlinks and not supported_orphan:
        raise ValueError('Unreviewed submodule configuration. Only the confirmed orphan FlameGraph pointer matching the bundled commit is supported; no changes made.')
    plan = {'package': str(PACKAGE), 'repository': str(repo), 'branch': branch,
            'archive': str(archive), 'archive_paths': moves, 'install_files': payload,
            'base_commit': git(repo, 'rev-parse', 'HEAD'),
            'archived_gitlinks': gitlinks,
            'gitlink_handling': 'Record original path/commit in MIGRATION.json; preserve local directory if present; use bundled ordinary files in vendor/FlameGraph. Previous pointer remains in Git history.',
            'operation': 'archive, install at root, stage, local commit; no push'}
    print(json.dumps(plan, indent=2))
    if not args.apply:
        print('\nPlan only. Add --apply to execute this migration.')
        return
    ignored_before = [p for p in git(repo, 'ls-files', '--others', '--ignored', '--exclude-standard', '-z').split('\0') if p]
    # Validate author/committer identity before changing files or branches.
    git(repo, 'var', 'GIT_AUTHOR_IDENT')
    git(repo, 'var', 'GIT_COMMITTER_IDENT')
    git(repo, 'switch', '-c', branch)
    (repo/archive).mkdir(parents=True)
    # This confirmed orphan has no .gitmodules mapping, so git mv cannot
    # reliably relocate it as a registered submodule. Remove only its index
    # entry; the following move preserves any local directory, including .git.
    for link in gitlinks:
        git(repo, 'update-index', '--force-remove', '--', link['path'])
    # Prevent previously ignored/untracked archive contents becoming accidental additions.
    for name in moves:
        tracked = git(repo, 'ls-files', '-z', '--', name)
        tracked_names = [x for x in tracked.split('\0') if x]
        dest = archive/'original'/name
        (repo/dest.parent).mkdir(parents=True, exist_ok=True)
        if tracked_names:
            git(repo, 'mv', '--', name, str(dest))
        else:
            shutil.move(str(repo/name), str(repo/dest))
    for name in payload:
        target = repo/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PACKAGE/name, target)
    archive_ignore = repo/archive/'.gitignore'
    archive_ignore.write_text('*\n')
    migration_record = repo/archive/'MIGRATION.json'
    migration_record.write_text(json.dumps(plan, indent=2)+'\n')
    # Replacing .gitignore must not expose existing local environments/caches
    # as new files to commit. Preserve exact surviving paths locally, without
    # importing broad old rules that might hide new experiment evidence.
    survivors = [name for name in ignored_before if (repo/name).exists() and
                 not any(name == moved or name.startswith(moved + '/') for moved in moves)]
    if survivors:
        exclude = Path(git(repo, 'rev-parse', '--git-path', 'info/exclude'))
        if not exclude.is_absolute():
            exclude = repo/exclude
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open('a') as stream:
            stream.write('\n# Preserve existing local ignored files after measurement-layout migration\n')
            for name in survivors:
                if '\n' in name or '\r' in name:
                    continue
                escaped = ''.join('\\'+ch if ch in '\\*?[] ' else ch for ch in name)
                stream.write('/'+escaped+'\n')
    # git mv already staged tracked historical artifacts. Force only known
    # payload and these two administrative files, never the entire archive.
    for name in payload + [str(archive/'.gitignore'), str(archive/'MIGRATION.json')]:
        git(repo, 'add', '-f', '--', name)
    git(repo, 'commit', '-m', 'Archive legacy profiling files and install reproducible measurement layout')
    print('\nMigration committed locally:', git(repo, 'rev-parse', '--short', 'HEAD'))
    print('Branch:', branch)
    print('Review:', 'git show --stat HEAD')
    print('When ready to publish:', 'git push -u origin ' + branch)
    print('Archive:', archive)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        print('No files are deleted by this migration. If an operation stopped after branch creation, inspect git status and the archive before retrying.', file=sys.stderr)
        raise SystemExit(2)
