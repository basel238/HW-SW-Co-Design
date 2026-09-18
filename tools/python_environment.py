"""Shared interpreter policy for setup, measurement launchers and workers."""
import platform
import sys
import sysconfig


def require_debug_python():
    if sys.version_info < (3, 10) or platform.python_implementation() != "CPython":
        raise RuntimeError("Measurements require debug CPython 3.10 or newer.")
    if not sysconfig.get_config_var("Py_DEBUG"):
        raise RuntimeError(
            "Measurements require debug Python (Py_DEBUG=1). Run scripts/00_setup.sh "
            "with python3-dbg or PYTHON_BIN=/path/to/debug/python. "
            "If .venv uses release Python, move it aside first; see QUICKSTART.md."
        )
    if sys.flags.optimize:
        raise RuntimeError("Use debug Python without -O/-OO or PYTHONOPTIMIZE.")


if __name__ == "__main__":
    try:
        require_debug_python()
    except RuntimeError as exc:
        print("ERROR:", exc, file=sys.stderr)
        raise SystemExit(2)
    print("Debug interpreter:", sys.executable, sys.version.split()[0], "(Py_DEBUG=1)")
