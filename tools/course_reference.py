#!/usr/bin/env python3
"""Real pyperformance references using the shared debug Python environment."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import sys

import pipeline as p


def selected_benchmarks(benchmark=None):
    return (benchmark,) if benchmark else p.BENCHMARKS


def smoke_settings(c):
    """Separate small, accurately recorded diagnostics from course workloads."""
    c = json.loads(json.dumps(c))
    c["timing"].update(processes=1, values=1, warmups=0, loops=1)
    c["nbody"].update(iterations=2000, profile_calls=2, profile_warmups=1)
    c["raytrace"].update(width=24, height=24, profile_calls=2, profile_warmups=1)
    return c


def build_manifest(out, c, benchmarks, smoke=False):
    """Keep upstream source snapshots intact; place explicit metadata beside them."""
    entries = []
    sources = {}
    for bench in benchmarks:
        dest = out / bench
        dest.mkdir()
        source = p.snapshot(bench, "baseline", dest, c)
        sources[bench] = {"path": str(source), "sha256": p.digest(source),
                          "tree_sha256": p.tree_hash(source.parent)}
        options = ["--loops=1", "--processes=" + str(1 if smoke else c["timing"]["processes"]),
                   "--values=" + str(1 if smoke else c["timing"]["values"]),
                   "--warmups=" + str(0 if smoke else c["timing"]["warmups"])]
        if bench == "nbody":
            options += ["--iterations=" + str(c[bench]["iterations"])]
        else:
            options += ["--width=" + str(c[bench]["width"]), "--height=" + str(c[bench]["height"])]
        # json.dumps produces valid TOML basic strings/arrays, including paths with spaces.
        metadata = (
            '[project]\nname = "pyperformance_bm_' + bench + '"\n'
            'version = "1.14.0"\nrequires-python = ">=3.10"\n'
            'dependencies = ["pyperf==2.10.0"]\n\n'
            '[tool.pyperformance]\nname = ' + json.dumps(bench) + '\n'
            'runscript = "source/run_benchmark.py"\n'
            'extra_opts = ' + json.dumps(options) + '\n')
        (dest / "pyproject.toml").write_text(metadata)
        (dest / "requirements.txt").write_text("pyperf==2.10.0\n")
        # pyperformance 1.14 resolves ordinary metafile entries against cwd,
        # not the manifest's directory. Runs use the separate cache as cwd.
        metafile = str((dest / "pyproject.toml").resolve())
        if any(character in metafile for character in ("\t", "\r", "\n", "#")):
            raise ValueError("The framework manifest requires a repository path without tabs, newlines, or '#'.")
        entries.append(bench + "\t" + metafile)
    manifest = out / "benchmarks.manifest"
    manifest.write_text("[benchmarks]\nname\tmetafile\n" + "\n".join(entries) + "\n")
    return manifest, sources


def run_reference(c, benchmark=None, smoke=False):
    """Return (output_directory, valid_reference); smoke is never course evidence."""
    p.require_debug_python()
    if smoke:
        c = smoke_settings(c)
    benchmarks = selected_benchmarks(benchmark)
    out = p.new_run("debug-pyperformance-reference")
    status = {"available": False, "smoke_only": smoke, "benchmarks": list(benchmarks),
              "framework": "pyperformance", "required_framework_version": "1.14.0",
              "interpreter_kind": "debug",
              "interpreter": p.interpreter(), "unavailable_reason": None,
              "measurement_scope": "pyperformance's benchmark timers; no perf wrapper around the harness",
              "use": "Framework reference only; use controlled debug timing for optimization comparisons."}
    try:
        if importlib.metadata.version("pyperformance") != "1.14.0":
            raise RuntimeError("Run scripts/00_setup.sh to install pinned requirements-course.txt.")
        if importlib.metadata.version("pyperf") != "2.10.0":
            raise RuntimeError("The reference launcher requires pyperf==2.10.0.")
        manifest, sources = build_manifest(out, c, benchmarks, smoke)
        status["sources"] = sources
        # The pinned framework chooses a cache key from interpreter identity and
        # dependency compatibility. Use that very key for its genuine CLI prep.
        from pyperformance.run import get_run_id
        cache = p.ROOT / ".course-cache"
        cache.mkdir(exist_ok=True)
        venv = cache / "venv" / get_run_id(p.PY).name
        base = [p.PY, "-m", "pyperformance"]
        common = ["--manifest", str(manifest), "--benchmarks", ",".join(benchmarks)]
        # pyperformance restricts subprocess environments to HOME/PATH unless
        # explicitly told otherwise. Preserve configured package transport,
        # including proxies or an offline wheelhouse, without Python flags.
        transport_names = (
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
            "http_proxy", "https_proxy", "all_proxy", "no_proxy",
            "PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "PIP_TRUSTED_HOST",
            "PIP_CERT", "PIP_CLIENT_CERT", "PIP_CONFIG_FILE", "PIP_FIND_LINKS",
            "PIP_NO_INDEX", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE",
        )
        inherited = [name for name in transport_names if name in os.environ]
        if inherited:
            common += ["--inherit-environ", ",".join(inherited)]
        status["inherited_dependency_environment_names"] = inherited
        if not (venv / "bin" / "python").is_file():
            p.require(p.command(base + ["venv", "create", "--venv", str(venv)] + common,
                                out, "prepare-environment", c["command_timeout_seconds"], cwd=cache),
                      "pyperformance environment preparation failed")
        else:
            p.require(p.command(base + ["venv", "show", "--venv", str(venv)],
                                out, "prepare-environment", 60, cwd=cache),
                      "pyperformance cache inspection failed")
        # Reject a stale/wrong cache before any benchmark is launched.
        status["worker_environment"] = str(venv)
        p.require(p.command([str(venv / "bin/python"), "-c",
                             "import hashlib,json,sys,sysconfig,importlib.metadata as m; from pathlib import Path; "
                             "print(json.dumps({'executable':sys.executable,'version':sys.version,"
                             "'executable_sha256':hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),"
                             "'py_debug':bool(sysconfig.get_config_var('Py_DEBUG')),"
                             "'packages':sorted(d.metadata['Name']+'=='+d.version for d in m.distributions())}))"],
                            out, "worker-environment", 30), "Worker environment capture failed")
        worker = json.loads((out / "worker-environment.stdout.txt").read_text())
        if worker["py_debug"] is not True:
            raise RuntimeError("Framework worker must use debug Python (Py_DEBUG=1).")
        if worker["executable_sha256"] != status["interpreter"]["executable_sha256"]:
            raise RuntimeError("Framework worker executable differs from the requested interpreter.")
        if "pyperf==2.10.0" not in worker["packages"]:
            raise RuntimeError("Framework worker did not use pinned pyperf==2.10.0.")
        status["worker_metadata"] = worker
        result = out / "pyperformance.json"
        argv = base + ["run"] + common + ["--python", p.PY, "--output", str(result),
                                         "--timeout", str(c["command_timeout_seconds"])]
        if c["affinity"] is not None:
            argv += ["--affinity", str(c["affinity"])]
        p.require(p.command(argv, out, "pyperformance-run", c["command_timeout_seconds"], cwd=cache),
                  "pyperformance framework reference failed")
        import pyperf
        suite = pyperf.BenchmarkSuite.load(str(result))
        if set(suite.get_benchmark_names()) != set(benchmarks):
            raise RuntimeError("Framework output has missing or unexpected benchmarks.")
        for bench in benchmarks:
            measured = suite.get_benchmark(bench)
            if measured.get_metadata().get("performance_version") != "1.14.0":
                raise RuntimeError("Output does not identify pinned pyperformance 1.14.0.")
            if not measured.get_values() or any(value <= 0 for value in measured.get_values()):
                raise RuntimeError("Framework output contains no positive timing values.")
            if p.tree_hash(Path(sources[bench]["path"]).parent) != sources[bench]["tree_sha256"]:
                raise RuntimeError("Frozen benchmark source changed during reference measurement.")
        for action in ("metadata", "check", "stats"):
            p.command([p.PY, "-m", "pyperf", action, str(result)], out, action, 60)
        status["available"] = True
    except (OSError, ValueError, RuntimeError, importlib.metadata.PackageNotFoundError) as exc:
        status["unavailable_reason"] = str(exc)
    p.dump(out / "reference-status.json", status)
    text = ["# pyperformance framework reference", "", status["use"], "",
            "Interpreter: " + status["interpreter_kind"] + ".", "",
            "A successful capture includes the actual `python -m pyperformance run` command and output using a custom manifest.",
            "Each manifest entry names its frozen local source and explicit version; upstream source files are unchanged.",
            "Environment creation/package checks are outside all perf recording and outside benchmark inner timers.",
            "The framework may recheck dependencies before worker launch. Never use its harness wall time as benchmark time.", "",
            "Status: " + ("captured" if status["available"] else "missing/failed"),
            "Reason: " + (status["unavailable_reason"] or "none"),
            "Smoke only: " + str(smoke) + ". Smoke output is not reportable course timing evidence.", ""]
    (out / "README.md").write_text("\n".join(text))
    return out, status["available"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", choices=p.BENCHMARKS, help="Default: both benchmarks")
    parser.add_argument("--smoke", action="store_true", help="One framework value only; not course timing evidence")
    args = parser.parse_args()
    c = p.config()
    p.preflight()
    _, ok = run_reference(c, args.benchmark, args.smoke)
    return 0 if ok else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        raise SystemExit(2)
