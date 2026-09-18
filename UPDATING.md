# Update your local repository, GitHub and VM

Use this for your existing v4/v4.1 repository. Do not rerun the original layout migration. Extract `project-repo-v4.2.zip` **beside** `HW-SW-Co-Design`, not inside it. The commands below assume those two directories share a parent, as in your earlier terminal session.

## 1. Review and install on your Mac

Stop any measurement before updating its working copy. Start in the extracted `project-repo-v4.2` directory:

```bash
git -C ../HW-SW-Co-Design status --short
python3 tools/update_repository.py --repo ../HW-SW-Co-Design
python3 tools/update_repository.py --repo ../HW-SW-Co-Design --apply
```

The first Python command is a dry run. The second applies that same validated update. Python 3.10+ is supported. It replaces only manifest-listed toolkit files whose existing contents match a recognized package version. It preserves `config.json`, `ENVIRONMENT.md`, `src/`, `results/`, `reports/`, `hw/`, your environments and `prompt.txt`. Replaced files are copied into `archive/update-v4.2-...` first. It neither commits nor pushes.

If it reports tracked changes, review/commit your existing work first. If it reports an unknown or modified file, do not force-copy over it: compare that file with the package and merge deliberately. An unrelated orphan FlameGraph gitlink is not touched; only a submodule that overlaps an update path blocks the update. All preflight checks complete before replacement begins; a rare interruption during writes can leave a partial update, with backups and a manifest in the archive.

## 2. Review, commit and push to GitHub

From the extracted package directory, switch to your repository:

```bash
cd ../HW-SW-Co-Design
git status --short
git diff --stat
git diff
git branch --show-current
git remote -v
```

Then stage only the toolkit update and commit it:

```bash
git add -- scripts tools tests docs README.md QUICKSTART.md STAGES_1_3.md UPDATING.md CHANGELOG.md TESTING.md requirements-course.txt script_nbody.sh script_raytrace.sh .gitignore PACKAGE_SHA256.json
git diff --cached --stat
git commit -m "Fix perf ACK handling and simplify stages 1-3 profiling"
git push -u origin HEAD
```

`git push -u origin HEAD` pushes the current branch. If you are on `main`, this updates GitHub's main branch. If you are on another branch, view that branch on GitHub and merge it through your usual process before expecting main to change. No force push is needed. The updater's archive is a local backup excluded by its own ignore file; result recordings are not staged by these commands.

## 3. Pull on the VM

In the existing VM repository, check the working tree and branch:

```bash
cd ~/HW-SW-Co-Design
git status --short
git branch --show-current
git fetch origin
```

Use your actual VM repository location if it is not `~/HW-SW-Co-Design`. If the change was pushed to main and the VM is already on main:

```bash
git pull --ff-only origin main
bash scripts/00_setup.sh
bash scripts/13_course_stages.sh
```

If the VM is on another branch, switch to the intended branch first, after saving any tracked changes. If you pushed a feature branch, pull that same branch instead of main. `git pull --ff-only origin main` **does not switch branches**. If fast-forward is refused, inspect the divergent commits; do not use reset/force commands to discard VM work.

Setup now requires one debug `.venv` (`Py_DEBUG=1`) for all measurements and defaults to `python3-dbg`. If the VM still has a release `.venv`, setup refuses it without modifying dependencies. Follow **QUICKSTART.md** to move the old environment aside and create the debug one, then rerun the course command. The old `.venv-guide`, benchmark edits and results remain untouched. Never copy a Mac virtual environment to Linux. Collect fresh debug baselines and candidates; historical release timings cannot support new comparisons. The main command prints the new run README path. Old failed runs remain historical evidence; this update does not reclassify them as successful.

## 4. Share results for analysis

Open only the new run's README, the two benchmark READMEs and their graphs first. To send the complete run, run this **on the VM**, replacing the example run name with the printed directory name:

```bash
bash scripts/14_export_results.sh --run run-2026-09-18_150000-abcd --output ../profiling-evidence.zip
```

Choose a new output filename if that archive already exists. The export includes the readable files, the raw evidence ZIP and supporting toolkit files, even when Git ignores them. You can then copy that one ZIP off the VM with your normal file-transfer method and attach it for analysis. A GitHub source download alone is not a complete recording archive.

To commit the small, readable results separately, first review their contents, then stage the specific run directory. `.gitignore` keeps `evidence.zip` out of normal Git. Preserve that ZIP independently before deleting or replacing the VM.
