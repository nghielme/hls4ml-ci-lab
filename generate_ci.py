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


def render_environment_file(repo_root: str, project_dir: str, experiment: str, branch: str, hls4ml_url: Optional[str] = None) -> Optional[str]:
    """Render a per-experiment environment file with the selected branch and HLS4ML URL."""
    exp_dir = Path(repo_root) / project_dir
    exp_env = exp_dir / "environment.yml"
    template_env = Path(repo_root) / "experiments" / "template" / "environment.yml"

    if exp_env.exists():
        source = exp_env
    elif template_env.exists():
        source = template_env
    else:
        return None

    try:
        template = source.read_text()
    except OSError:
        return None

    rendered = template.replace("{BRANCH}", branch).replace("{TARGET_EXPERIMENT}", experiment)
    if hls4ml_url:
        rendered = rendered.replace("{HLS4ML_URL}", hls4ml_url)
    else:
        # Default to the standard hls4ml repository if not specified
        rendered = rendered.replace("{HLS4ML_URL}", "https://github.com/fastmachinelearning/hls4ml.git")
    
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
    hls4ml_urls: Dict[str, str],
) -> Dict:
    """Generate GitLab CI configuration for the provided experiments.
    
    Args:
        repo_root: Root directory of the repository
        experiments: List of experiment names
        branches: Dictionary mapping experiment names to branch names
        image_path: Container image path (optional)
        image_tag: Container image tag (optional)
        hls4ml_urls: Dictionary mapping experiment names to hls4ml repository URLs
    """
    if not experiments:
        print("No experiments found under 'experiments/'. Nothing to generate.")
        return {}

    ci: Dict = {}

    # Include templates.yml
    ci["include"] = [{"local": "templates.yml"}]

    # Define stages
    ci["stages"] = ["generate", "synthetise", "analyse"]

    synthetise_job_names: List[str] = []

    # Jobs per experiment
    for exp in experiments:
        project_dir = f"experiments/{exp}"
        generate_job_name = f"generate_{exp}"
        syn_job_name = f"synthetise_{exp}"

        # Get branch for this experiment, default to 'main'
        branch = branches.get(exp, "main")
        # Get hls4ml_url for this experiment, default to official repo
        hls4ml_url = hls4ml_urls.get(exp, "https://github.com/fastmachinelearning/hls4ml.git")
        env_file = render_environment_file(repo_root, project_dir, exp, branch, hls4ml_url)

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


def parse_branches(branch_arg: Optional[str]) -> tuple[Dict[str, str], Dict[str, str]]:
    """Parse branch specification from command-line argument.
    
    Accepts format:
    - "experiment1:url1@branch1,experiment2:url2@branch2" (per-experiment mapping with URLs)
    
    Args:
        branch_arg: Branch specification string
    
    Returns:
        Tuple of (branches_dict, urls_dict) mapping experiment names to branch names and URLs
    """
    branches: Dict[str, str] = {}
    urls: Dict[str, str] = {}
    
    if not branch_arg:
        return branches, urls
    
    # Must be comma-separated list of experiment:url@branch pairs
    if ',' not in branch_arg and ':' not in branch_arg:
        print(f"Error: --branches must use format 'exp:url@branch'. Got: {branch_arg}", file=sys.stderr)
        sys.exit(1)
    
    # Parse experiment:url@branch pairs
    for pair in branch_arg.split(','):
        pair = pair.strip()
        if ':' not in pair:
            print(f"Error: each branch specification must be in format 'exp:url@branch'. Got: {pair}", file=sys.stderr)
            sys.exit(1)
        
        exp, value = pair.split(':', 1)
        exp = exp.strip()
        # Must contain @ (url@branch format)
        if '@' not in value:
            print(f"Error: per-experiment branches must include URL in format 'exp:url@branch'. Got: {exp}:{value}", file=sys.stderr)
            sys.exit(1)
        
        url, branch = value.rsplit('@', 1)
        branches[exp] = branch.strip()
        urls[exp] = url.strip()
    
    return branches, urls


def normalize_branch_spec(spec: Any) -> Dict[str, str]:
    """Normalize branches specification from CLI/config formats (legacy, URLs not supported)."""
    if spec is None:
        return {}
    if isinstance(spec, str):
        # Legacy format - just parse branches, URLs will default
        branches, _ = parse_branches(spec)
        return branches
    if isinstance(spec, dict):
        return {str(k): str(v) for k, v in spec.items()}
    if isinstance(spec, list):
        normalized: Dict[str, str] = {}
        for entry in spec:
            normalized.update(normalize_branch_spec(entry))
        return normalized
    print(f"Warning: unsupported branches specification '{spec}'.", file=sys.stderr)
    return {}


def parse_branch_and_url(value: str) -> tuple[str, str]:
    """Parse "branch, url" or just "branch" from a string.
    
    Returns:
        Tuple of (branch, url). URL defaults to official repo if not provided.
    """
    parts = [p.strip() for p in value.split(',', 1)]
    branch = parts[0]
    url = parts[1] if len(parts) > 1 else "https://github.com/fastmachinelearning/hls4ml.git"
    return branch, url


def normalize_branches_with_urls(spec: Any) -> tuple[Dict[str, str], Dict[str, str]]:
    """Normalize branches specification that may include URLs.
    
    Accepts:
    - None: returns empty dicts
    - dict: mapping of experiment -> "branch" or "branch, url"
    
    Returns:
        Tuple of (branches_dict, urls_dict)
    """
    if spec is None:
        return {}, {}
    if isinstance(spec, dict):
        branches: Dict[str, str] = {}
        urls: Dict[str, str] = {}
        for exp, value in spec.items():
            branch, url = parse_branch_and_url(str(value))
            branches[str(exp)] = branch
            urls[str(exp)] = url
        return branches, urls
    print(f"Warning: unsupported branches specification '{spec}'.", file=sys.stderr)
    return {}, {}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate GitLab CI configuration from experiments"
    )
    parser.add_argument(
        "--branches",
        type=str,
        help="Branch specification: 'exp1:url1@branch1,exp2:url2@branch2' for per-experiment branches with URLs"
    )
    parser.add_argument(
        "--image",
        type=str,
        help="Container image name or path (without tag) to pass to CI variables",
    )
    parser.add_argument(
        "--tag",
        type=str,
        help="Container image tag for the runner machine",
    )
    parser.add_argument(
        "--hls4ml-url",
        type=str,
        help="URL of the hls4ml repository for all experiments (defaults to https://github.com/fastmachinelearning/hls4ml.git). "
             "Use parameters file for per-experiment URLs.",
    )
    parser.add_argument(
        "--parameters",
        type=str,
        help="Path to a YAML parameters file (defaults to parameters.yml if present; see parameters-example.yml for format)",
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
    # Parse branches (which may include URLs in "branch, url" format)
    branch_spec_from_file, url_spec_from_file = normalize_branches_with_urls(param_data.get("branches"))
    image_value = param_data.get("image")
    tag_value = param_data.get("tag")
    
    # Handle CLI overrides
    branch_spec = branch_spec_from_file.copy()
    url_spec = url_spec_from_file.copy()
    
    if args.branches:
        # CLI branches format: "exp1:url1@branch1,exp2:url2@branch2" or "exp1:branch1,exp2:branch2"
        branch_spec_cli, url_spec_cli = parse_branches(args.branches)
        branch_spec = branch_spec_cli
        url_spec = url_spec_cli
    if args.image is not None:
        image_value = args.image
    if args.tag is not None:
        tag_value = args.tag
    if args.hls4ml_url is not None:
        # CLI --hls4ml-url overrides all experiment URLs
        url_spec = {exp: args.hls4ml_url for exp in branch_spec.keys()}
    
    # Prepare experiment directories and ensure all have branch/URL specs
    experiments = prepare_experiment_dirs(repo_root, branch_spec)
    if not branch_spec:
        # If no branches specified, default all to main with official repo
        branch_spec = {exp: "main" for exp in experiments}
    # Ensure URLs exist for all experiments
    for exp in experiments:
        if exp not in url_spec:
            url_spec[exp] = "https://github.com/fastmachinelearning/hls4ml.git"
    
    ci = generate_gitlab_ci(
        repo_root, experiments, branch_spec,
        str(image_value) if image_value is not None else None,
        str(tag_value) if tag_value is not None else None,
        url_spec,
    )
    if not ci:
        # Still write a minimal stages section so pipeline is valid but empty
        ci = {"stages": ["generate", "synthetise", "analyse"]}

    write_yaml(ci, output_path)
    print(f"Generated {output_path}")


if __name__ == "__main__":
    main()



