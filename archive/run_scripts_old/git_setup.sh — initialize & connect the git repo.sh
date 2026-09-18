#!/usr/bin/env bash
# =============================================================================
# GIT — Initialize the project repo, make the first commit, connect to remote
# HW/SW Co-design (00460882)
# -----------------------------------------------------------------------------
# Sets up version control for your project so you can track progress and files.
# Run this ONCE from the top of your project folder.
#
# Usage:   bash git_setup.sh
# =============================================================================
set -euo pipefail

# ---- 1. Tell git who you are (only needed the first time on a machine) ------
read -rp "Your name for git commits: "  GIT_NAME
read -rp "Your email for git commits: " GIT_EMAIL
git config --global user.name  "${GIT_NAME}"
git config --global user.email "${GIT_EMAIL}"
git config --global init.defaultBranch main

# ---- 2. Initialize the repository -------------------------------------------
git init

# ---- 3. Create a .gitignore so we DON'T commit junk / big files -------------
cat > .gitignore <<'EOF'
# Python
venv/
__pycache__/
*.pyc

# perf raw data (large, machine-specific - keep the readable reports instead)
perf.data
perf.data.old
out.perf
out.folded

# tools we clone, not author
FlameGraph/

# OS noise
.DS_Store
EOF

# ---- 4. Create a starter README describing the repo layout ------------------
cat > README.md <<'EOF'
# HW/SW Co-design Project (00460882) — pyperformance Optimization

Optimizing two pure-Python `pyperformance` benchmarks (**nbody**, **raytrace**),
profiling them with `perf` + flame graphs, and proposing a hardware accelerator.

## Repository layout
| Path | Contents |
|------|----------|
| `scripts/` | Phase scripts (setup, baseline, perf stat, record+flame, compare) |
| `report_nbody.txt` / `report_raytrace.txt` | perf report output + written analysis |
| `script_nbody.sh` / `script_raytrace.sh` | End-to-end run scripts per benchmark |
| `*.svg` | Flame graphs |
| `*_base.json` / `*_opt.json` | pyperf results (before / after) |
| `hw/` | Verilog/SystemVerilog accelerator + block diagram |
| `prompt.txt` | AI-tool prompts used |

## How to reproduce
```bash
bash scripts/00_setup.sh                 # once
source venv/bin/activate                 # each new shell
bash scripts/01_baseline.sh   nbody
bash scripts/02_perf_stat.sh  nbody
bash scripts/03_perf_record_flame.sh nbody
# ... edit the benchmark code ...
bash scripts/04_optimize_compare.sh nbody
```
EOF

# ---- 5. First commit --------------------------------------------------------
git add .
git commit -m "chore: initial project scaffold (scripts, README, .gitignore)"

echo ""
echo "  Local repo created with your first commit."
echo ""
echo "  NEXT - connect it to a remote (GitHub / course GitLab):"
echo "    1) Create an EMPTY repo on the website (no README/…gitignore)."
echo "    2) Copy its URL, then run:"
echo "         git remote add origin <REPO_URL>"
echo "         git push -u origin main"
echo ""
echo "  After that, your daily loop is:"
echo "         git add <files>          # or: git add -A"
echo "         git commit -m \"message\"  # save a checkpoint"
echo "         git push                  # upload to the remote"
