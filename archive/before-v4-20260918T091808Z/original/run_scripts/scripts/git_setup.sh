#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -d "$ROOT/.git" ]]; then
    git -C "$ROOT" init
fi
echo "Repository initialized. README and .gitignore were preserved."
echo "Set repository-local identity if needed, review files, then commit."
echo "This script does not stage files, change global settings, or publish."
