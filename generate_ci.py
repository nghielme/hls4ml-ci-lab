#!/usr/bin/env python3
import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml  # type: ignore
except Exception:
    print("PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def find_experiments(experiments_root: str) -> List[str]:
    """Return a sorted list of experiment directory names under experiments_root.

    An experiment is any directory directly under experiments_root that contains files.
    """
    if not os.path.isdir(experiments_root):
        return []
    experiments = []
    for entry in os.listdir(experiments_root):
        full_path = os.path.join(experiments_root, entry)
        if os.path.isdir(full_path):
            # consider as experiment if it contains any file (e.g. user_code.py)
            try:
                contains_file = any(os.path.isfile(os.path.join(full_path, f)) for f in os.listdir(full_path))
            except PermissionError:
                contains_file = False
            if contains_file:
                experiments.append(entry)
    return sorted(experiments)


def load_parameters_file(path: Optional[str], warn_if_missing: bool = True) -> Dict[str, Any]:
    """Load parameters from a YAML file (returns empty dict on failure)."""
    if not path:
        return {}
    file_path = Path(path)
    if not file_path.is_file():
        if warn_if_missing:
            print(f"Warning: parameters file '{path}' not found; ignoring.", file=sys.stderr)
        return {}
    try:
        with open(file_path, "r") as f:
            data = yaml.safe_load(f) or {}
    except Exception as exc:  # pragma: no cover - best effort warning
        print(f"Warning: failed to load parameters file '{path}': {exc}", file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        print(f"Warning: parameters file '{path}' must define a YAML mapping.", file=sys.stderr)
        return {}
    return data


def make_generate_job(
    exp_name: str,
    project_dir: str,
    branch: str,
    env_file: Optional[str],
    image_path: Optional[str],
    image_tag: Optional[str],
) -> Dict:
    variables: Dict[str, str] = {
        "PROJECT_DIR": project_dir,
        "TARGET_EXPERIMENT": exp_name,
        "BRANCH": branch,
    }
    if env_file:
        variables["ENV_FILE"] = env_file
    if image_path:
        variables["IMAGE"] = image_path
    if image_tag:
        variables["TAG"] = image_tag

    job: Dict = {
        "extends": ".generate-template",
        "stage": "generate",
        "variables": variables,
    }
    return job


def make_synthetise_job(
    exp_name: str,
    project_dir: str,
    branch: str,
    env_file: Optional[str],
    image_path: Optional[str],
    image_tag: Optional[str],
) -> Dict:
    variables: Dict[str, str] = {
        "PROJECT_DIR": project_dir,
        "TARGET_EXPERIMENT": exp_name,
        "BRANCH": branch,
    }
    if env_file:
        variables["ENV_FILE"] = env_file
    if image_path:
        variables["IMAGE"] = image_path
    if image_tag:
        variables["TAG"] = image_tag

    job: Dict = {
        "extends": ".synthetise-template",
        "stage": "synthetise",
        "variables": variables,
    }
    return job


def render_environment_file(repo_root: str, project_dir: str, experiment: str, branch: str) -> Optional[str]:
    """Render a per-experiment environment file with the selected branch."""
    exp_dir = Path(repo_root) / project_dir
    exp_env = exp_dir / "environment.yml"
    common_env = Path(repo_root) / "common" / "environment.yml"

    if exp_env.exists():
        source = exp_env
    elif common_env.exists():
        source = common_env
    else:
        return None

    try:
        template = source.read_text()
    except OSError:
        return None

    rendered = template.replace("{BRANCH}", branch).replace("{TARGET_EXPERIMENT}", experiment)
    dest = exp_dir / "environment.rendered.yml"

    try:
        dest.write_text(rendered)
    except OSError:
        return None

    return os.path.relpath(dest, repo_root)


def prepare_experiment_dirs(repo_root: str, branches: Dict[str, str]) -> List[str]:
    """Ensure experiment directories exist, cloning from experiments/template if needed."""
    experiments_root = Path(repo_root) / "experiments"
    template_dir = experiments_root / "template"

    # If explicit branches provided, ensure corresponding directories
    if branches:
        experiment_names: List[str] = []
        template_missing = not template_dir.is_dir()

        for exp in branches.keys():
            if exp == "template":
                continue

            target_dir = experiments_root / exp
            if target_dir.exists():
                experiment_names.append(exp)
                continue

            if template_missing:
                print(
                    f"Warning: experiments/template missing; cannot clone experiment '{exp}'",
                    file=sys.stderr,
                )
                continue

            shutil.copytree(template_dir, target_dir)
            experiment_names.append(exp)

        return experiment_names

    # No explicit branches: return existing experiments (excluding template)
    return [
        exp
        for exp in find_experiments(str(experiments_root))
        if exp != "template"
    ]


def make_analyse_job(
    synthetise_jobs: List[str],
    experiments: List[str],
    image_path: Optional[str],
    image_tag: Optional[str],
) -> Dict:
    # Make analyse depend on all synthetise jobs and download their artifacts
    needs = [{"job": j, "artifacts": True} for j in synthetise_jobs]
    job: Dict = {
        "extends": ".analyse-template",
        "stage": "analyse",
        "needs": needs if needs else None,
        "dependencies": synthetise_jobs if synthetise_jobs else None,
        "variables": {
            # Provide experiment list for plotting scripts if needed
            "EXPERIMENTS": " ".join(experiments),
        },
    }
    if image_path:
        job["variables"]["IMAGE"] = image_path
    if image_tag:
        job["variables"]["TAG"] = image_tag
    return job


def generate_gitlab_ci(
    repo_root: str,
    experiments: List[str],
    branches: Dict[str, str],
    image_path: Optional[str],
    image_tag: Optional[str],
) -> Dict:
    """Generate GitLab CI configuration for the provided experiments."""
    if not experiments:
        print("No experiments found under 'experiments/'. Nothing to generate.")
        return {}

    ci: Dict = {}

    # Define stages
    ci["stages"] = ["generate", "synthetise", "analyse"]

    synthetise_job_names: List[str] = []

    # Jobs per experiment
    for exp in experiments:
        project_dir = f"experiments/{exp}"
        generate_job_name = f"generate:{exp}"
        syn_job_name = f"synthetise:{exp}"

        # Get branch for this experiment, default to 'main'
        branch = branches.get(exp, "main")
        env_file = render_environment_file(repo_root, project_dir, exp, branch)

        ci[generate_job_name] = make_generate_job(
            exp, project_dir, branch, env_file, image_path, image_tag
        )
        ci[syn_job_name] = make_synthetise_job(
            exp, project_dir, branch, env_file, image_path, image_tag
        )

        synthetise_job_names.append(syn_job_name)

    # Single analyse job waiting all synthetise jobs
    analyse_job = make_analyse_job(
        synthetise_job_names, experiments, image_path, image_tag
    )
    # Clean None fields for YAML cleanliness
    if analyse_job.get("needs") is None:
        analyse_job.pop("needs")
    if analyse_job.get("dependencies") is None:
        analyse_job.pop("dependencies")
    ci["analyse"] = analyse_job

    return ci


def write_yaml(data: Dict, path: str) -> None:
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def parse_branches(branch_arg: Optional[str]) -> Dict[str, str]:
    """Parse branch specification from command-line argument.
    
    Accepts formats:
    - "experiment1:branch1,experiment2:branch2" (per-experiment mapping)
    - "branch_name" (single branch for all experiments)
    
    Args:
        branch_arg: Branch specification string
    
    Returns:
        Dictionary mapping experiment names to branch names
    """
    branches: Dict[str, str] = {}
    
    if not branch_arg:
        return branches
    
    # Check if it's a comma-separated list of experiment:branch pairs
    if ',' in branch_arg or ':' in branch_arg:
        # Try to parse as experiment:branch pairs
        for pair in branch_arg.split(','):
            pair = pair.strip()
            if ':' in pair:
                exp, branch = pair.split(':', 1)
                branches[exp.strip()] = branch.strip()
            else:
                # If no colon, treat as single branch for all
                return {}  # Will be handled below
    else:
        # Single branch name - will be applied to all experiments
        return {"*": branch_arg.strip()}
    
    return branches


def normalize_branch_spec(spec: Any) -> Dict[str, str]:
    """Normalize branches specification from CLI/config formats."""
    if spec is None:
        return {}
    if isinstance(spec, str):
        return parse_branches(spec)
    if isinstance(spec, dict):
        return {str(k): str(v) for k, v in spec.items()}
    if isinstance(spec, list):
        normalized: Dict[str, str] = {}
        for entry in spec:
            normalized.update(normalize_branch_spec(entry))
        return normalized
    print(f"Warning: unsupported branches specification '{spec}'.", file=sys.stderr)
    return {}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate GitLab CI configuration from experiments"
    )
    parser.add_argument(
        "--branches",
        type=str,
        help="Branch specification: 'branch_name' for all experiments, "
             "or 'exp1:branch1,exp2:branch2' for per-experiment branches"
    )
    parser.add_argument(
        "--image",
        type=str,
        help="Container image name or path (without tag) to pass to CI variables",
    )
    parser.add_argument(
        "--tag",
        type=str,
        help="Container image tag. Combined with --image to form image:tag",
    )
    parser.add_argument(
        "--parameters",
        type=str,
        help="Path to a YAML parameters file (defaults to parameters.yml if present)",
    )
    args = parser.parse_args()
    
    repo_root = os.path.abspath(os.path.dirname(__file__))
    output_path = os.path.join(repo_root, ".gitlab-ci.yml")
    experiments_root = os.path.join(repo_root, "experiments")
    
    # Load parameters file (CLI takes precedence over file)
    param_path: Optional[str] = None
    warn_missing_params = False
    if args.parameters:
        param_path = args.parameters
        warn_missing_params = True
    else:
        default_parameters = Path(repo_root) / "parameters.yml"
        if default_parameters.is_file():
            param_path = str(default_parameters)
    param_data = load_parameters_file(param_path, warn_missing_params)
    
    # Parameters precedence: config file -> CLI overrides
    branch_spec = normalize_branch_spec(param_data.get("branches"))
    image_value = param_data.get("image")
    tag_value = param_data.get("tag")
    
    if args.branches:
        branch_spec = parse_branches(args.branches)
    if args.image is not None:
        image_value = args.image
    if args.tag is not None:
        tag_value = args.tag
    
    # If a default branch was specified, we need to get the list of experiments first
    if "*" in branch_spec:
        experiments = [
            exp for exp in find_experiments(experiments_root) if exp != "template"
        ]
        default_branch = branch_spec["*"]
        branch_spec = {exp: default_branch for exp in experiments}
    else:
        experiments = prepare_experiment_dirs(repo_root, branch_spec)
        if not branch_spec:
            branch_spec = {exp: "main" for exp in experiments}
    
    ci = generate_gitlab_ci(
        repo_root, experiments, branch_spec,
        str(image_value) if image_value is not None else None,
        str(tag_value) if tag_value is not None else None,
    )
    if not ci:
        # Still write a minimal stages section so pipeline is valid but empty
        ci = {"stages": ["generate", "synthetise", "analyse"]}

    write_yaml(ci, output_path)
    print(f"Generated {output_path}")


if __name__ == "__main__":
    main()



