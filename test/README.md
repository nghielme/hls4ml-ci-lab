# Test Suite

This directory contains pytest tests for the `hls4ml-ci-lab` functionality.

## Running Tests

```bash
# Run all tests
python3 -m pytest test/

# Run with verbose output
python3 -m pytest test/ -v

# Run a specific test class
python3 -m pytest test/test_generate_ci.py::TestParseBranches -v

# Run a specific test
python3 -m pytest test/test_generate_ci.py::TestParseBranches::test_parse_branches_valid_format -v

# Run with coverage
python3 -m pytest test/ --cov=generate_ci --cov-report=html
```

## Test Coverage

The test suite covers:

1. **Branch Parsing** (`TestParseBranches`)
   - Valid `exp:url@branch` format parsing
   - Error handling for invalid formats
   - Empty input handling

2. **Parameters File Parsing** (`TestParseBranchAndUrl`, `TestNormalizeBranchesWithUrls`)
   - Parsing `branch, url` format from YAML
   - Default URL handling
   - Whitespace normalization

3. **Environment File Rendering** (`TestRenderEnvironmentFile`)
   - Template variable substitution (`{TARGET_EXPERIMENT}`, `{BRANCH}`, `{HLS4ML_URL}`)
   - Fallback to template when experiment file missing
   - Default URL substitution

4. **Experiment Directory Preparation** (`TestPrepareExperimentDirs`)
   - Creating experiments from template
   - Excluding template directory
   - Preserving existing experiments

5. **CI Generation** (`TestGenerateGitlabCi`)
   - Basic CI job generation
   - Multiple experiments
   - Variable injection (IMAGE, TAG, BRANCH, etc.)
   - Analyse job dependencies

6. **Parameters File Loading** (`TestLoadParametersFile`)
   - Valid YAML parsing
   - Missing file handling
   - Empty file handling

7. **Integration Tests** (`TestIntegration`)
   - Full workflow from parameters file to CI generation
   - End-to-end verification

---

## Requirements

- `pytest`

Install with:
```bash
pip install pytest
```

# Test Suite Overview

This document provides a high-level overview of why each test category exists and what it validates.

## Test Categories

### 1. **TestParseBranches** - CLI Input Validation
**Why it exists:** Users provide branch specifications via `--branches` CLI argument. This must be parsed correctly and reject invalid formats.

**What it tests:** 
- Validates the `exp:url@branch` format parsing (the only supported CLI format)
- Ensures proper error handling for malformed input (missing `@` or `:`)
- Handles edge cases (empty input, single experiment)

**Value:** Prevents runtime errors from bad user input and ensures the CLI interface is strict and predictable.

---

### 2. **TestParseBranchAndUrl** - Parameters File Format Parsing
**Why it exists:** The parameters YAML file uses a different format (`branch, url`) than the CLI. This needs separate parsing logic.

**What it tests:**
- Parses the comma-separated `branch, url` format from YAML
- Applies default URL when only branch is specified
- Handles whitespace variations

**Value:** Ensures the parameters file format works correctly and is user-friendly (allows optional URL).

---

### 3. **TestNormalizeBranchesWithUrls** - Configuration Normalization
**Why it exists:** Branch specifications can come from CLI or YAML file in different formats. They need to be normalized into a consistent internal representation.

**What it tests:**
- Converts YAML dict format into separate branch/URL dictionaries
- Applies default URLs when missing
- Handles empty/missing configurations gracefully

**Value:** Ensures the system can work with different input formats and always has consistent data internally.

---

### 4. **TestRenderEnvironmentFile** - Template Variable Substitution
**Why it exists:** Environment files contain placeholders (`{TARGET_EXPERIMENT}`, `{BRANCH}`, `{HLS4ML_URL}`) that must be replaced with actual values before use.

**What it tests:**
- Substitutes all template variables correctly
- Falls back to template file when experiment-specific file is missing
- Uses default URL when not provided
- Handles missing files gracefully

**Value:** Critical for environment reproducibility - ensures each experiment gets the correct hls4ml branch/URL in its conda environment.

---

### 5. **TestPrepareExperimentDirs** - Experiment Auto-Creation
**Why it exists:** Users can specify experiment names in `--branches` that don't exist yet. The system should auto-create them from the template.

**What it tests:**
- Creates new experiment directories by cloning from template
- Excludes the template directory itself from experiment lists
- Preserves existing experiments (doesn't overwrite user customizations)

**Value:** Enables workflow where users just specify experiment names and the system sets them up automatically, while protecting user modifications.

---

### 6. **TestGenerateGitlabCi** - CI Configuration Generation
**Why it exists:** The core functionality - generating valid GitLab CI YAML with correct job structure, variables, and dependencies.

**What it tests:**
- Creates proper CI structure (stages, jobs, extends templates)
- Injects all required variables (IMAGE, TAG, BRANCH, PROJECT_DIR, etc.) into jobs
- Sets up correct job dependencies (analyse waits for all synthetise jobs)
- Handles edge cases (no experiments, multiple experiments)

**Value:** Ensures the generated `.gitlab-ci.yml` will actually work in GitLab CI/CD - jobs have the right variables, dependencies are correct, and the pipeline structure is valid.

---

### 7. **TestLoadParametersFile** - Configuration File Loading
**Why it exists:** Users can provide configuration via YAML file instead of CLI arguments. This must be loaded and parsed correctly.

**What it tests:**
- Parses valid YAML files correctly
- Handles missing files gracefully (returns empty dict, doesn't crash)
- Handles empty/malformed files gracefully

**Value:** Makes the system robust - works whether or not a parameters file exists, and doesn't crash on bad files.

---

### 8. **TestIntegration** - End-to-End Workflow
**Why it exists:** Individual functions might work in isolation but fail when used together. Integration tests verify the complete workflow.

**What it tests:**
- Full pipeline: parameters file → normalization → directory prep → environment rendering → CI generation
- Verifies that all pieces work together correctly
- Ensures data flows correctly between functions (e.g., experiments are created before CI jobs reference them)

**Value:** Catches integration bugs that unit tests miss - ensures the system works for real-world usage scenarios.

---

## Test Philosophy

The test suite follows these principles:

1. **Input Validation First:** Tests for CLI and file parsing ensure bad input is caught early
2. **Core Functionality:** CI generation is the main feature - it's thoroughly tested
3. **User Experience:** Tests for auto-creation and fallbacks ensure the system is user-friendly
4. **Robustness:** Edge cases (missing files, empty inputs) are tested to prevent crashes
5. **Integration:** End-to-end tests verify the complete workflow works

The tests use temporary directories to avoid modifying the actual repository, and copy real template files to ensure tests reflect actual behavior.

