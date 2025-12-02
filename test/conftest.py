"""Pytest configuration and shared fixtures."""
import tempfile
import shutil
from pathlib import Path
import pytest


@pytest.fixture
def temp_repo():
    """Create a temporary repository structure for testing."""
    # Get the actual repository root (parent of test directory)
    actual_repo_root = Path(__file__).parent.parent
    
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        
        # Copy template directory from actual repo
        actual_template = actual_repo_root / "experiments" / "template"
        temp_template = repo_root / "experiments" / "template"
        shutil.copytree(actual_template, temp_template)
        
        # Copy common directory if it exists (needed for run.py imports)
        actual_common = actual_repo_root / "common"
        temp_common = repo_root / "common"
        if actual_common.exists():
            shutil.copytree(actual_common, temp_common)
        else:
            temp_common.mkdir()
            (temp_common / "__init__.py").write_text("")
            (temp_common / "script.py").write_text("def main(stage: str, experiment_name: str):\n    pass\n")
        
        # Create a test experiment
        (repo_root / "experiments" / "baseline").mkdir()
        baseline_env = repo_root / "experiments" / "baseline" / "environment.yml"
        baseline_env.write_text("""name: {TARGET_EXPERIMENT}
channels:
  - miniforge
dependencies:
  - python=3.10
  - pip:
    - git+{HLS4ML_URL}@{BRANCH}
""")
        
        yield repo_root

