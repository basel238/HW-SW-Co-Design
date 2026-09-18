# Move an existing repository to the new layout

Extract this complete package **outside** your Git checkout. You do not need to manually rename files, remove old results or copy scripts first. Run with Python 3.10+ on the machine containing your checkout; setup/measurements themselves run inside the Ubuntu VM.

From the extracted package directory:

```bash
python3 tools/migrate_repository.py --repo /absolute/path/to/your/repository
python3 tools/migrate_repository.py --repo /absolute/path/to/your/repository --apply
```

The first command prints a plan. The second:

1. Requires a clean working tree and configured Git author/committer identity.
2. Creates a new `chore/measurement-layout-<UTC timestamp>` branch.
3. Moves old `run_scripts/`, old root `FlameGraph/`, root benchmark JSON/SVG/perf outputs and colliding package paths into `archive/before-v4-<timestamp>/original/`. The old README and .gitignore are preserved there too.
4. Installs the complete new package at the repository root.
5. Stages the new package and tracked archive moves, then creates one local commit.

Existing ignored files inside moved directories remain archived locally, but are not newly committed. Already tracked raw perf files remain tracked in their new archive locations. This operation does not purge their existing Git history or shrink the repository. Unknown nonconflicting root files are preserved. Registered or unreviewed submodules are refused for manual review. The confirmed orphan root FlameGraph gitlink at commit 41fee1f99f9276008b7cd112fca19dc3ea84ac32, without .gitmodules, is supported: its path and commit are recorded in the committed MIGRATION.json, its local directory is archived if present, and the old gitlink remains in Git history. The replacement uses ordinary pinned files under vendor/FlameGraph/. Archived local clone contents are not newly added to Git.

Previously ignored local files that remain outside the moved paths keep exact local exclusions in Git's info/exclude, so replacing .gitignore does not suddenly stage your existing environment/cache files. These local rules are not pushed.

It does not push, merge, rewrite history, or delete old contents. If the working tree is dirty, commit or otherwise preserve your current work and rerun; do not use a destructive reset merely to pass this check. If Git identity is missing, configure your own `user.name` and `user.email` locally in the repository.

After migration, run from your checkout:

```bash
git show --stat HEAD
git status
# When you are ready to publish the new branch:
git push -u origin HEAD
```

Open a pull request to your normal default branch. After reviewing/merging, keep `archive/` as historical evidence. The new measurement folders do not contain results until you run the new workflow.

## New repository layout

| Path | Contents |
|---|---|
| scripts/ | Phase runners, setup, diagnostics and comparisons |
| tools/ | Complete Python measurement, validation and migration helpers |
| src/baseline/ | Verified original nbody/raytrace source |
| src/optimized/ | Candidate source copies; initially unchanged |
| results/ | New timestamped measurement runs |
| reports/ | Authored report templates to complete from new evidence |
| hw/ | Hardware implementation location; currently a README only |
| vendor/FlameGraph/ | Pinned plotting tools |
| archive/before-v4-.../original/ | Preserved previous scripts, documents and results |
| script_nbody.sh, script_raytrace.sh | Per-benchmark entry points |
| README.md, QUICKSTART.md, ENVIRONMENT.md | Instructions and machine configuration record |

The new README intentionally puts generated output in results/ and written reports in reports/. It no longer advertises flat root outputs or describes raw perf dumps as completed written analysis.

Inside the Ubuntu VM, from the reorganized repository root:

```bash
bash scripts/00_setup.sh
bash script_nbody.sh
bash script_raytrace.sh
```

Read QUICKSTART.md for optional-stage exit codes, candidate editing and optimization comparisons. Do not run the old git_setup.sh; the existing repository and remote are retained.
