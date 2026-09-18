"""Small analysis view plus a verified archive of complete measurement evidence."""
import hashlib
import io
import json
from pathlib import Path
import pstats
import shutil
import stat
import statistics
import zipfile


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def stage_path(record):
    return Path(record['path']) if record.get('path') else None


def copy_artifact(record, name, dest):
    source = stage_path(record)
    if record.get('available') and source and (source / name).is_file():
        shutil.copy2(source / name, dest)
        return True
    return False


def short_log(record):
    if record.get('error'):
        return str(record['error'])[:1000]
    source = stage_path(record)
    if not source:
        return record.get('reason', 'No capture was produced.')
    for name in ('reference-status.json', 'pyspy-status.json'):
        reason = read_json(source / name).get('unavailable_reason')
        if reason:
            return reason[:1000]
    pieces = []
    for path in sorted(source.rglob('*.stderr.txt')):
        with path.open(errors='replace') as stream:
            value = stream.read(1500).strip()
        if value:
            pieces.append(path.relative_to(source).as_posix() + ': ' + value)
        if len(pieces) == 2:
            break
    return '\n'.join(pieces) or 'Inspect the saved status and logs in evidence.zip.'


def number(value):
    return 'unavailable' if value is None else f'{value:.5g}'


def counters_text(record):
    source = stage_path(record)
    runs = read_json(source / 'stat-summary.json').get('runs', []) if source else []
    if not runs:
        return ['Counters: ' + record.get('reason', 'unavailable; see the evidence logs'), '']
    metrics = ('ipc', 'cpi', 'branch_miss_percent', 'generic_cache_miss_percent',
               'l1_miss_percent', 'branch_mpki', 'generic_cache_mpki', 'l1_load_mpki')
    lines = ['| Metric | Median | Min–max | Usable / attempted |', '|---|---:|---:|---:|']
    for key in metrics:
        attempted = [r for r in runs if key in r]
        if not attempted:
            continue
        values = [r[key] for r in attempted if r[key] is not None]
        lines.append(f'| {key} | {number(statistics.median(values)) if values else "unavailable"} | '
                     f'{number(min(values)) + "–" + number(max(values)) if values else "—"} | {len(values)}/{len(attempted)} |')
    lines += ['', '| Event | Median per benchmark call | Unit | Usable / attempted |', '|---|---:|---|---:|']
    events = {}
    for run in runs:
        for name, item in run.get('events', {}).items():
            # Show one matched group for each event; do not pool MPKI passes.
            if run['group'].endswith('mpki'):
                continue
            events.setdefault(name, []).append(item)
    for name, items in sorted(events.items()):
        values = [i['per_benchmark_call'] for i in items if i.get('per_benchmark_call') is not None]
        lines.append(f'| {name} | {number(statistics.median(values)) if values else "unavailable"} | '
                     f'{items[0].get("unit") or "count"} | {len(values)}/{len(items)} |')
    lines += ['', 'Descriptive medians/ranges, not confidence intervals. Each ratio uses simultaneous events from its own pass. '
              'Per-call means one configured simulation or one rendered frame. A zero cycles counter makes IPC/CPI unavailable. '
              'Generic cache misses do not establish DRAM traffic or a memory bottleneck. Full repeat validity and running fractions are archived.', '']
    return lines


def benchmark_view(out, bench, record):
    dest = out / bench
    dest.mkdir()
    lines = ['# ' + bench + ' — baseline evidence', '',
             'Read this file, then open the graphs. All raw data and full reports are in `../evidence.zip`.', '',
             '## Timing', '']
    if copy_artifact(record.get('timing', {}), 'timing.json', dest / 'timing.json'):
        import pyperf
        suite = pyperf.BenchmarkSuite.load(str(dest / 'timing.json'))
        for name in suite.get_benchmark_names():
            values = suite.get_benchmark(name).get_values()
            lines += [f'Unprofiled debug runtime: **{statistics.mean(values)*1000:.3f} ms per call**; '
                      f'SD {statistics.stdev(values)*1000:.3f} ms across {len(values)} recorded values.' if len(values) > 1
                      else f'Unprofiled debug runtime: {values[0]*1000:.3f} ms; only one value.', '']
        source = stage_path(record['timing'])
        warning_file = source / 'check.stdout.txt'
        if warning_file.is_file() and warning_file.read_text().strip():
            lines += ['pyperf stability check:', '', '```text', warning_file.read_text()[:2500].strip(), '```', '']
        lines += ['This SD describes spread, not a confidence interval. Values within a worker are correlated. '
                  'Use `timing.json` for analysis; do not use profiled runtime or whole-command elapsed time.', '']
    else:
        lines += ['Timing unavailable. ' + short_log(record.get('timing', {})), '']
    native = record.get('native', {})
    lines += ['## Required perf profile', '']
    if copy_artifact(native, 'native.svg', dest / 'perf.svg'):
        lines += ['[Open perf.svg](perf.svg). Built from perf record → perf script → FlameGraph. '
                  'Widths are sampled cpu-clock event-period weights in nanoseconds, not call counts. '
                  'Horizontal position is not a timeline; tall stacks are call depth.', '',
                  'Stack health: **' + str(native.get('stack_health', 'review required')) + '**. '
                  + '; '.join(native.get('stack_warnings', [])), '',
                  'Check ancestry, unknown frames, truncation and sample loss before interpreting callers. '
                  'A large CPython evaluator share is expected for interpreted code and does not identify a specific Python line.', '']
        source = stage_path(native)
        report = source / 'native-self.txt'
        if report.is_file():
            lines += ['Native Self table (first 35 lines; full table archived):', '', '```text',
                      '\n'.join(report.read_text(errors='replace').splitlines()[:35]), '```', '']
    else:
        lines += ['**Missing required perf evidence.** ' + short_log(native), '']
    sample = record.get('python_sampling', {})
    lines += ['## Supplementary Python view', '']
    if copy_artifact(sample, 'python-measured.svg', dest / 'python.svg'):
        stats = read_json(stage_path(sample) / 'pyspy-status.json')
        lines += ['[Open python.svg](python.svg). py-spy samples selected by the exact measured-call wrapper; '
                  'startup/warmup stacks are excluded. This does not replace perf.svg.', '',
                  f'Measured samples: {stats.get("measured_sample_count")}; excluded samples: {stats.get("excluded_sample_count")}. '
                  + (stats.get('warning') or stats.get('sample_count_warning') or ''), '']
    else:
        lines += ['Python sampling: ' + sample.get('reason', short_log(sample)), '']
    source = stage_path(record.get('python_calls', {}))
    if record.get('python_calls', {}).get('available') and source and (source / 'python.pstats').is_file():
        stream = io.StringIO()
        stats = pstats.Stats(str(source / 'python.pstats'), stream=stream).strip_dirs()
        stats.sort_stats('tottime').print_stats(12)
        stats.sort_stats('cumtime').print_stats(12)
        lines += ['cProfile: top 12 by self time, then cumulative time. Instrumentation changes costs; '
                  'use this to locate Python operations, not to estimate unprofiled speedup.', '',
                  '```text', stream.getvalue().strip(), '```', '']
    lines += ['## Counters', ''] + counters_text(record.get('counters', {}))
    lines += ['## Interpretation to finish', '',
              '- Review the source explanation in `docs/stage1-' + bench + '.md` (also archived).',
              '- Identify hot functions from this run and explain their algorithms/data structures.',
              '- Separate observed cost from a proposed cause; no FPU-bound or memory-bound claim follows from a function name alone.',
              '- Use fresh unprofiled debug timings for both variants in any later optimization comparison. This run implements no optimization.', '']
    (dest / 'README.md').write_text('\n'.join(lines))


def write_view(out, status):
    for bench, record in status['benchmarks'].items():
        benchmark_view(out, bench, record)
    copy_artifact(status.get('framework_reference', {}), 'pyperformance.json', out / 'framework.json')
    lines = ['# Start here — stages 1–3', '',
             '**Required collection: ' + ('complete' if status['automated_collection_complete'] else 'INCOMPLETE') + '.** '
             'Written interpretation and human stack review remain required.', '',
             'Guide collection: **' + ('complete' if status['literal_guide_collection_complete'] else 'incomplete') + '**. '
             'All measurements use debug Python (Py_DEBUG=1).', '',
             '| Open | Purpose |', '|---|---|']
    for bench in status['benchmarks']:
        lines.append(f'| [{bench}/README.md]({bench}/README.md) | Timing, top functions, counter validity, graphs and interpretation tasks |')
    lines += ['| [summary.json](summary.json) | Machine-readable status of every attempted stage |',
              '| framework.json, if present | Genuine debug pyperformance reference |',
              '| evidence.zip | Full recordings, logs, commands, source snapshots and toolkit, with checksums |', '',
              'Only files from this new run are compacted. Previous results are untouched. '
              'To inspect raw evidence, extract evidence.zip into this run directory; it restores `details/`. '
              'Original absolute paths remain in provenance to document the measurement machine.', '',
              '## Missing evidence and next actions', '']
    for name in status.get('required_missing', []):
        item = status.get('actions', {}).get(name, {})
        lines += ['- **' + name + '**: ' + short_log(item).replace('\n', ' ')[:1500]]
    if not status.get('required_missing'):
        lines += ['No required collection failures in the selected mode.']
    lines += ['', 'If perf failed: check the archived gate-probe logs first. Missing perf or permission errors require fixing the VM setup; '
              'do not change interpreter or silently substitute a py-spy graph. Zero hardware cycles may be a virtual-PMU limitation; '
              'the software-clock perf graph can still work.', '', '## Supplementary limitations', '']
    lines += ['- ' + name for name in status.get('optional_warnings', [])] or ['None reported.']
    lines += ['', '## Work needed for submission', ''] + ['- ' + item for item in status['manual_tasks']]
    lines += ['', 'No benchmark optimization is applied. No previous results are merged into this run.', '']
    (out / 'README.md').write_text('\n'.join(lines))


def archive_evidence(out, keep_details=False):
    """Remove generated details only after every ZIP member passes hash checks."""
    out = Path(out).resolve()
    details = out / 'details'
    if details.is_symlink() or not details.is_dir():
        raise ValueError('Expected a real details directory in this new run')
    files = []
    for path in sorted(details.rglob('*')):
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError('Refusing to compact non-regular evidence: ' + str(path))
        files.append(path)
    manifest = {'schema_version': 1, 'files': {}, 'note': 'Extract into the run folder to restore details/.'}
    archive_path = out / 'evidence.zip'
    with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
        for path in files:
            name = path.relative_to(out).as_posix()
            before = path.stat()
            digest = hashlib.sha256()
            size = 0
            with path.open('rb') as source, archive.open(name, 'w', force_zip64=True) as target:
                for block in iter(lambda: source.read(1024*1024), b''):
                    target.write(block)
                    digest.update(block)
                    size += len(block)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                raise ValueError('Evidence changed during compaction; details retained')
            manifest['files'][name] = {'sha256': digest.hexdigest(), 'bytes': size}
        archive.writestr('EVIDENCE-MANIFEST.json', json.dumps(manifest, indent=2) + '\n')
    with zipfile.ZipFile(archive_path) as archive:
        for name, item in manifest['files'].items():
            digest = hashlib.sha256()
            with archive.open(name) as stream:
                for block in iter(lambda: stream.read(1024*1024), b''):
                    digest.update(block)
            if digest.hexdigest() != item['sha256']:
                raise ValueError('Archive verification failed; details retained')
    # Check originals again before deleting generated expanded data.
    for path in files:
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024*1024), b''):
                digest.update(block)
        if digest.hexdigest() != manifest['files'][path.relative_to(out).as_posix()]['sha256']:
            raise ValueError('Evidence changed after compaction; details retained')
    if not keep_details:
        shutil.rmtree(details)
    return {'archive': 'evidence.zip', 'verified_files': len(files), 'details_retained': keep_details}


def portable_status(value, out):
    if isinstance(value, dict):
        return {key: portable_status(item, out) for key, item in value.items()}
    if isinstance(value, list):
        return [portable_status(item, out) for item in value]
    if isinstance(value, str) and value.startswith(str(out) + '/'):
        return Path(value).relative_to(out).as_posix()
    return value
