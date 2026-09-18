#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
    "$PYTHON_BIN" -m venv "$ROOT/.venv"
fi
"$ROOT/.venv/bin/python" - <<'PY'
import sys, sysconfig
if sys.version_info < (3, 10):
    raise SystemExit("Use Python 3.10 or newer. Preserve your old version for continuity.")
if sysconfig.get_config_var("Py_DEBUG"):
    raise SystemExit("Use a release interpreter for this experiment.")
print("Selected interpreter:", sys.executable, sys.version)
PY
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/requirements.txt"
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
echo "Setup complete. Scripts use .venv/bin/python automatically."
echo "Review config.json and record your QEMU launch command in ENVIRONMENT.md."
