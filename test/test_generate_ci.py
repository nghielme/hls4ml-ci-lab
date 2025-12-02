"""Tests for generate_ci.py functionality."""
import tempfile
import shutil
from pathlib import Path
import pytest

# Add parent directory to path to import generate_ci
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from generate_ci import (
    parse_branches,
    normalize_branches_with_urls,
    parse_branch_and_url,
    render_environment_file,
    prepare_experiment_dirs,
    generate_gitlab_ci,
    load_parameters_file,
)


class TestParseBranches:
    """Test branch parsing functionality."""
    
    def test_parse_branches_valid_format(self):
        """Test parsing valid exp:url@branch format."""
        branches, urls = parse_branches(
            "exp1:https://github.com/test/repo.git@main,exp2:https://github.com/test/repo2.git@feature"
        )
        assert branches == {"exp1": "main", "exp2": "feature"}
        assert urls == {
            "exp1": "https://github.com/test/repo.git",
            "exp2": "https://github.com/test/repo2.git"
        }
    
    def test_parse_branches_empty(self):
        """Test parsing empty string."""
        branches, urls = parse_branches(None)
        assert branches == {}
        assert urls == {}
    
    def test_parse_branches_single_experiment(self):
        """Test parsing single experiment."""
        branches, urls = parse_branches("exp1:https://github.com/test/repo.git@main")
        assert branches == {"exp1": "main"}
        assert urls == {"exp1": "https://github.com/test/repo.git"}
    
    def test_parse_branches_invalid_no_at(self):
        """Test that format without @ raises error."""
        with pytest.raises(SystemExit):
            parse_branches("exp1:main")
    
    def test_parse_branches_invalid_no_colon(self):
        """Test that format without colon raises error."""
        with pytest.raises(SystemExit):
            parse_branches("main")


class TestParseBranchAndUrl:
    """Test parsing branch and URL from parameters file format."""
    
    def test_parse_branch_and_url_with_url(self):
        """Test parsing 'branch, url' format."""
        branch, url = parse_branch_and_url("main, https://github.com/test/repo.git")
        assert branch == "main"
        assert url == "https://github.com/test/repo.git"
    
    def test_parse_branch_and_url_without_url(self):
        """Test parsing just branch (defaults URL)."""
        branch, url = parse_branch_and_url("main")
        assert branch == "main"
        assert url == "https://github.com/fastmachinelearning/hls4ml.git"
    
    def test_parse_branch_and_url_whitespace(self):
        """Test parsing with extra whitespace."""
        branch, url = parse_branch_and_url("  main  ,  https://github.com/test/repo.git  ")
        assert branch == "main"
        assert url == "https://github.com/test/repo.git"


class TestNormalizeBranchesWithUrls:
    """Test normalizing branches from parameters file."""
    
    def test_normalize_branches_with_urls_dict(self):
        """Test normalizing dict format from parameters file."""
        spec = {
            "baseline": "main, https://github.com/test/repo.git",
            "experiment": "feature-123, https://github.com/test/repo2.git"
        }
        branches, urls = normalize_branches_with_urls(spec)
        assert branches == {"baseline": "main", "experiment": "feature-123"}
        assert urls == {
            "baseline": "https://github.com/test/repo.git",
            "experiment": "https://github.com/test/repo2.git"
        }
    
    def test_normalize_branches_with_urls_no_url(self):
        """Test normalizing without URL (defaults)."""
        spec = {
            "baseline": "main",
            "experiment": "feature-123"
        }
        branches, urls = normalize_branches_with_urls(spec)
        assert branches == {"baseline": "main", "experiment": "feature-123"}
        assert urls == {
            "baseline": "https://github.com/fastmachinelearning/hls4ml.git",
            "experiment": "https://github.com/fastmachinelearning/hls4ml.git"
        }
    
    def test_normalize_branches_with_urls_none(self):
        """Test normalizing None."""
        branches, urls = normalize_branches_with_urls(None)
        assert branches == {}
        assert urls == {}


class TestRenderEnvironmentFile:
    """Test environment file rendering."""
    
    def test_render_environment_file_experiment_specific(self, temp_repo):
        """Test rendering experiment-specific environment file."""
        result = render_environment_file(
            str(temp_repo),
            "experiments/baseline",
            "baseline",
            "main",
            "https://github.com/test/repo.git"
        )
        assert result is not None
        
        rendered_path = temp_repo / "experiments" / "baseline" / "environment.rendered.yml"
        assert rendered_path.exists()
        
        content = rendered_path.read_text()
        assert "{TARGET_EXPERIMENT}" not in content
        assert "{BRANCH}" not in content
        assert "{HLS4ML_URL}" not in content
        assert "baseline" in content
        assert "main" in content
        assert "https://github.com/test/repo.git" in content
    
    def test_render_environment_file_fallback_to_template(self, temp_repo):
        """Test falling back to template when experiment file doesn't exist."""
        # Remove experiment-specific file
        (temp_repo / "experiments" / "baseline" / "environment.yml").unlink()
        
        result = render_environment_file(
            str(temp_repo),
            "experiments/baseline",
            "baseline",
            "main",
            "https://github.com/test/repo.git"
        )
        assert result is not None
        
        rendered_path = temp_repo / "experiments" / "baseline" / "environment.rendered.yml"
        assert rendered_path.exists()
    
    def test_render_environment_file_no_file(self, temp_repo):
        """Test when no environment file exists."""
        # Remove both files
        (temp_repo / "experiments" / "baseline" / "environment.yml").unlink()
        (temp_repo / "experiments" / "template" / "environment.yml").unlink()
        
        result = render_environment_file(
            str(temp_repo),
            "experiments/baseline",
            "baseline",
            "main",
            "https://github.com/test/repo.git"
        )
        assert result is None
    
    def test_render_environment_file_default_url(self, temp_repo):
        """Test rendering with default URL when not provided."""
        result = render_environment_file(
            str(temp_repo),
            "experiments/baseline",
            "baseline",
            "main",
            None
        )
        assert result is not None
        
        rendered_path = temp_repo / "experiments" / "baseline" / "environment.rendered.yml"
        content = rendered_path.read_text()
        assert "https://github.com/fastmachinelearning/hls4ml.git" in content


class TestPrepareExperimentDirs:
    """Test experiment directory preparation."""
    
    def test_prepare_experiment_dirs_creates_from_template(self, temp_repo):
        """Test that new experiments are created from template."""
        branches = {
            "newexp": "main",
            "anotherexp": "feature"
        }
        
        experiments = prepare_experiment_dirs(str(temp_repo), branches)
        
        assert "newexp" in experiments
        assert "anotherexp" in experiments
        assert (temp_repo / "experiments" / "newexp").exists()
        assert (temp_repo / "experiments" / "anotherexp").exists()
        assert (temp_repo / "experiments" / "newexp" / "run.py").exists()
        assert (temp_repo / "experiments" / "newexp" / "environment.yml").exists()
    
    def test_prepare_experiment_dirs_excludes_template(self, temp_repo):
        """Test that template directory is excluded."""
        branches = {
            "template": "main",  # Should be ignored
            "baseline": "main"
        }
        
        experiments = prepare_experiment_dirs(str(temp_repo), branches)
        
        assert "template" not in experiments
        assert "baseline" in experiments
    
    def test_prepare_experiment_dirs_preserves_existing(self, temp_repo):
        """Test that existing experiments are preserved."""
        # Create existing experiment
        existing = temp_repo / "experiments" / "existing"
        existing.mkdir()
        (existing / "run.py").write_text("# existing")
        
        branches = {"existing": "main"}
        experiments = prepare_experiment_dirs(str(temp_repo), branches)
        
        assert "existing" in experiments
        # Should not overwrite existing files
        assert (existing / "run.py").read_text() == "# existing"


class TestGenerateGitlabCi:
    """Test GitLab CI generation."""
    
    def test_generate_gitlab_ci_basic(self, temp_repo):
        """Test basic CI generation."""
        experiments = ["baseline"]
        branches = {"baseline": "main"}
        urls = {"baseline": "https://github.com/fastmachinelearning/hls4ml.git"}
        
        ci = generate_gitlab_ci(
            str(temp_repo),
            experiments,
            branches,
            "registry.example.com/hls4ml",
            "gpu-runner",
            urls
        )
        
        assert "stages" in ci
        assert ci["stages"] == ["generate", "synthetise", "analyse"]
        assert "generate:baseline" in ci
        assert "synthetise:baseline" in ci
        assert "analyse" in ci
        
        # Check variables
        gen_job = ci["generate:baseline"]
        assert gen_job["variables"]["PROJECT_DIR"] == "experiments/baseline"
        assert gen_job["variables"]["TARGET_EXPERIMENT"] == "baseline"
        assert gen_job["variables"]["BRANCH"] == "main"
        assert gen_job["variables"]["IMAGE"] == "registry.example.com/hls4ml"
        assert gen_job["variables"]["TAG"] == "gpu-runner"
    
    def test_generate_gitlab_ci_multiple_experiments(self, temp_repo):
        """Test CI generation with multiple experiments."""
        # Create additional experiments
        for exp in ["exp1", "exp2"]:
            (temp_repo / "experiments" / exp).mkdir()
        
        experiments = ["baseline", "exp1", "exp2"]
        branches = {
            "baseline": "main",
            "exp1": "feature1",
            "exp2": "feature2"
        }
        urls = {
            "baseline": "https://github.com/fastmachinelearning/hls4ml.git",
            "exp1": "https://github.com/test/repo1.git",
            "exp2": "https://github.com/test/repo2.git"
        }
        
        ci = generate_gitlab_ci(
            str(temp_repo),
            experiments,
            branches,
            None,
            None,
            urls
        )
        
        assert "generate:baseline" in ci
        assert "generate:exp1" in ci
        assert "generate:exp2" in ci
        assert "synthetise:baseline" in ci
        assert "synthetise:exp1" in ci
        assert "synthetise:exp2" in ci
        
        # Check analyse job dependencies
        analyse_job = ci["analyse"]
        assert "needs" in analyse_job
        assert len(analyse_job["needs"]) == 3
    
    def test_generate_gitlab_ci_no_experiments(self, temp_repo):
        """Test CI generation with no experiments."""
        ci = generate_gitlab_ci(
            str(temp_repo),
            [],
            {},
            None,
            None,
            {}
        )
        assert ci == {}


class TestLoadParametersFile:
    """Test parameters file loading."""
    
    def test_load_parameters_file_valid(self, temp_repo):
        """Test loading valid parameters file."""
        params_file = temp_repo / "parameters.yml"
        params_file.write_text("""branches:
  baseline: main, https://github.com/fastmachinelearning/hls4ml.git
  experiment: feature-123, https://github.com/custom/repo.git
image: registry.example.com/hls4ml
tag: gpu-runner
""")
        
        data = load_parameters_file(str(params_file), False)
        assert "branches" in data
        assert "image" in data
        assert "tag" in data
        assert data["image"] == "registry.example.com/hls4ml"
        assert data["tag"] == "gpu-runner"
    
    def test_load_parameters_file_missing(self, temp_repo):
        """Test loading non-existent parameters file."""
        data = load_parameters_file(str(temp_repo / "nonexistent.yml"), False)
        assert data == {}
    
    def test_load_parameters_file_empty(self, temp_repo):
        """Test loading empty parameters file."""
        params_file = temp_repo / "parameters.yml"
        params_file.write_text("")
        
        data = load_parameters_file(str(params_file), False)
        assert data == {}


class TestIntegration:
    """Integration tests for full workflow."""
    
    def test_full_workflow_with_parameters_file(self, temp_repo):
        """Test full workflow using parameters file."""
        # Create parameters file
        params_file = temp_repo / "parameters.yml"
        params_file.write_text("""branches:
  baseline: main, https://github.com/fastmachinelearning/hls4ml.git
  newexp: feature-123, https://github.com/custom/repo.git
image: registry.example.com/hls4ml
tag: gpu-runner
""")
        
        # Load and normalize
        param_data = load_parameters_file(str(params_file), False)
        branch_spec, url_spec = normalize_branches_with_urls(param_data.get("branches"))
        
        # Prepare experiments
        experiments = prepare_experiment_dirs(str(temp_repo), branch_spec)
        
        # Generate CI
        ci = generate_gitlab_ci(
            str(temp_repo),
            experiments,
            branch_spec,
            param_data.get("image"),
            param_data.get("tag"),
            url_spec
        )
        
        # Verify structure
        assert "generate:baseline" in ci
        assert "generate:newexp" in ci
        assert ci["generate:baseline"]["variables"]["BRANCH"] == "main"
        assert ci["generate:newexp"]["variables"]["BRANCH"] == "feature-123"
        
        # Verify rendered environment files exist
        assert (temp_repo / "experiments" / "baseline" / "environment.rendered.yml").exists()
        assert (temp_repo / "experiments" / "newexp" / "environment.rendered.yml").exists()

