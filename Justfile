# Justfile for crhelper
# Run `just` to see available recipes.

default:
    @just --list

# Run the test suite on the host Python (fast iteration).
test:
    uv run pytest -q

# Run the test suite with coverage report.
test-cov:
    uv run pytest --cov=crhelper --cov-report=term-missing

# Lint + type-check (ruff + mypy). Same checks as the CI lint job.
lint:
    uv run ruff check
    uv run mypy crhelper/

# Auto-fix the ruff issues that have safe fixes.
lint-fix:
    uv run ruff check --fix

# Refresh uv.lock after pyproject.toml changes.
lock:
    uv lock

# Run the CI matrix locally via `act` (Linux containers).
# Requires `act` (https://nektosact.com): brew install act
# Runs amd64 + arm64 in parallel; within each arch the 4 Python versions
# run in parallel as defined in .github/workflows/ci.yml.
# Each invocation gets its own action-cache path to avoid races.
test-matrix: _check-act
    #!/usr/bin/env bash
    set -uo pipefail
    echo "Running amd64 and arm64 jobs in parallel via act..."
    act -j test --container-architecture linux/amd64 --matrix runner:ubuntu-24.04 \
        --action-cache-path /tmp/act-cache-amd64 &
    pids=("$!")
    act -j test --container-architecture linux/arm64 --matrix runner:ubuntu-24.04-arm \
        --action-cache-path /tmp/act-cache-arm64 &
    pids+=("$!")
    failed=0
    for pid in "${pids[@]}"; do
      wait "$pid" || failed=1
    done
    exit "$failed"

# Run only the amd64 jobs (4 Python versions in parallel).
test-matrix-amd64: _check-act
    act -j test --container-architecture linux/amd64 --matrix runner:ubuntu-24.04

# Run only the arm64 jobs (4 Python versions in parallel; native on Apple Silicon).
test-matrix-arm64: _check-act
    act -j test --container-architecture linux/arm64 --matrix runner:ubuntu-24.04-arm

# Build sdist and wheel into ./dist
build:
    uv build

# Inspect wheel contents (sanity check that py.typed and *.pyi are bundled).
build-inspect: build
    @echo "--- wheel contents ---"
    @unzip -l dist/*.whl
    @echo "--- sdist contents ---"
    @tar -tzf dist/*.tar.gz

# Remove build artifacts and caches.
clean:
    rm -rf dist build *.egg-info .pytest_cache .coverage coverage.xml .mypy_cache
    find . -type d -name __pycache__ -exec rm -rf {} +

_check-act:
    @command -v act >/dev/null || { echo 'error: act not installed. Install with: brew install act'; exit 1; }
