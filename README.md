# `hls4ml` CI Lab

Utilities and structure to run multiple `hls4ml` experiments in a consistent
way both locally and in GitLab CI.

---

## Repository layout

- `experiments/<name>/`
  - `run.py`: entry point executed for each pipeline stage (`generate`,
    `synthetise`, `analyse`).
  - `pre_script.py` / `post_script.py`: custom hooks executed before/after
    the shared logic in `common/script.py`.
  - `environment.yml`: conda/pip requirements for the experiment. If missing,
    `experiments/template/environment.yml` is used.
- `common/`
  - `script.py`: shared experiment logic (imported by every `run.py`).
  - `environment.yml`: default environment used when an experiment does not
    define its own environment file.
- `template.yml`: reusable GitLab CI templates consumed by generated jobs.
- `generate_ci.py`: script that scans `experiments/` and writes a complete
  `.gitlab-ci.yml`.

---

## Experiment lifecycle

1. **Stage selection**
   - CI (or local runs) invoke `python3 run.py --stage <stage>`.
   - `run.py` forwards the stage to `pre_script`, `common/script`, and
     `post_script` in that order.

2. **Environment setup**
   - Each experiment provides `environment.yml`. When `.gitlab-ci.yml` is
     generated, the file is rendered to `environment.rendered.yml` with
     `{BRANCH}` and `{TARGET_EXPERIMENT}` substituted.
   - If an experiment does not ship `environment.yml`, the generator falls
     back to `experiments/template/environment.yml`.
   - During the `generate` stage the pipeline sources Miniforge, creates a conda
     env named after the experiment (e.g. `baseline`), archives it as
     `<experiment>-conda-env.tar.gz`, and caches both the archive and any
     downloaded data.
   - Subsequent stages restore the cached archive, extract it into
     `/opt/conda/envs`, and `conda activate <experiment>` before running the
     experiment code, so the environment is created exactly once.

3. **Hooks**
   - Both hooks are optional. For apples-to-apples comparisons just leave the
     files empty (or omit them) so only the shared logic runs.
   - `pre_script.py` is there for experiments that need extra preparation
     before `common/script.py` (e.g. fetching data, patching configs, checking
     out ancillary repos).
   - `post_script.py` can gather artifacts, upload plots, or run bespoke clean
     up once the shared logic finishes.

---

## Generating `.gitlab-ci.yml`

Use `generate_ci.py` to materialize the pipeline. Provide branch information
per experiment (or a single default branch), and optionally the container image
and runner tag that should run the jobs:

```bash
# Different branches and URLs per experiment (format: exp:url@branch)
python3 generate_ci.py --branches "baseline:https://github.com/fastmachinelearning/hls4ml.git@main,experiment:https://github.com/custom/hls4ml-fork.git@feature-123" --image registry.example.com/hls4ml --tag 2024.11

# Using a parameters file
python3 generate_ci.py --parameters parameters.yml
```

When you pass `exp:url@branch` pairs the script clones `experiments/template`
into `experiments/<exp>/` (if it does not already exist) before generating CI.
This lets you create whole experiment suites just by naming them on the command
line.

The resulting `.gitlab-ci.yml` contains, for each experiment:

- `generate:<experiment>` job
- `synthetise:<experiment>` job
- A shared `analyse` job that depends on every synthetise job

Each job gets the following variables:

- `PROJECT_DIR`: path to the experiment (e.g. `experiments/baseline`)
- `TARGET_EXPERIMENT`: experiment name (e.g. `baseline`)
- `BRANCH`: branch name passed via `--branches`
- `ENV_FILE`: path to the rendered environment file (if available)
- `IMAGE`: container image string supplied via CLI/parameters file
- `TAG`: runner tag supplied via CLI/parameters file (to select GitLab runners)

The `environment.yml` files support template variables:
- `{TARGET_EXPERIMENT}`: replaced with the experiment name
- `{BRANCH}`: replaced with the hls4ml branch name
- `{HLS4ML_URL}`: replaced with the hls4ml repository URL for that experiment (defaults to `https://github.com/fastmachinelearning/hls4ml.git` if not specified per-experiment)

Regenerate `.gitlab-ci.yml` whenever you add/remove experiments or change
branch mappings.

---

## Adding a new experiment

Recommended workflow:

1. Keep `experiments/template/` up to date with the baseline structure you want.
2. Create or update `parameters.yml` (see below) with the experiments you want,
   or run `python3 generate_ci.py --branches newexp:https://github.com/fastmachinelearning/hls4ml.git@my-branch`
   to clone the template into `experiments/newexp/`, render its environment file, and update
   `.gitlab-ci.yml`.
3. Customize `experiments/newexp/` as needed (configs, hooks, etc.) and rerun
   the generator.
4. Commit the new experiment directory along with the regenerated CI file.

Manual creation still works (just make the directory yourself); in that case
use the parameters file or specify branches in the `exp:url@branch` format.

---

## Local testing

```bash
cd experiments/<name>
python3 run.py --stage generate
python3 run.py --stage synthetise
python3 run.py --stage analyse
```

Ensure the required dependencies from `environment.yml` are available in your
local Python environment (the CI pipeline installs them automatically).

---

## Parameters file

You can store all generator options in `parameters.yml` (auto-detected if
present) or pass a custom path via `--parameters path/to/file.yml`.

```yaml
# parameters.yml
branches:
  baseline: main, https://github.com/fastmachinelearning/hls4ml.git
  experiment: feature-123, https://github.com/custom/hls4ml-fork.git
image: registry.example.com/hls4ml
tag: gpu-runner
```

Each experiment can specify both the branch and the hls4ml repository URL in the format `branch, url`. If the URL is omitted, it defaults to the official repository (`https://github.com/fastmachinelearning/hls4ml.git`). You can also use `--hls4ml-url <url>` to set a single URL for all experiments (overrides the parameters file).

CLI flags always override the file (e.g. `--image` to temporarily change the
container, `--branches` to generate a different experiment set).

---

## Troubleshooting

- **Missing environment file**: the CI generator will fall back to
  `experiments/template/environment.yml`. If neither file exists, the pipeline prints a
  warning before running the stage.
- **Branch not checked out**: specify the desired branch via `--branches` when
  running `generate_ci.py`. For a single default branch, pass just the branch
  name. For mixed branches, use `exp:url@branch` format to specify both the repository URL and branch.
- **New experiments not in CI**: rerun `generate_ci.py` whenever you add or
  remove experiment directories.

