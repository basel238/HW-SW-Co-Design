#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3-dbg}"
if [[ -e "$ROOT/.venv" || -L "$ROOT/.venv" ]]; then
    [[ -x "$ROOT/.venv/bin/python" ]] || {
        echo "Existing .venv has no usable Python. Move it aside, then rerun setup; see QUICKSTART.md." >&2
        exit 2
    }
else
    command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
        echo "Debug Python not found: $PYTHON_BIN. Install python3-dbg and matching python3-venv support," >&2
        echo "or set PYTHON_BIN=/path/to/debug/python. Release Python is not supported for measurements." >&2
        exit 2
    }
    "$PYTHON_BIN" "$ROOT/tools/python_environment.py"
    "$PYTHON_BIN" -m venv "$ROOT/.venv"
fi
"$ROOT/.venv/bin/python" "$ROOT/tools/python_environment.py"
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/requirements.txt"
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/requirements-course.txt"
if [[ "${INSTALL_PYSPY:-1}" == 1 ]]; then
    if ! "$ROOT/.venv/bin/python" -m pip install -r "$ROOT/requirements-profile.txt"; then
        echo "Optional py-spy installation failed; timing, cProfile and perf remain usable." >&2
        echo "The sampling stage will report unavailable until requirements-profile.txt is installed." >&2
    fi
fi
"$ROOT/.venv/bin/python" "$ROOT/tools/pipeline.py" preflight
if ! command -v perf >/dev/null 2>&1; then
    echo "perf is missing. On Ubuntu install the matching linux-tools package."
    echo 'Example: sudo apt install linux-tools-common "linux-tools-$(uname -r)"'
fi
echo "Setup complete. All measurements use debug .venv/bin/python automatically."
echo "Review config.json and record your QEMU launch command in ENVIRONMENT.md."
echo "Run bash scripts/13_course_stages.sh to collect the first-three-stage evidence for both benchmarks."
