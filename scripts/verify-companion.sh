#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

python3 -W error::ResourceWarning -m unittest -v companion.test_runtime
python3 -m compileall -q companion
uvx ruff check companion
uvx pip-audit --strict --path companion
bash -n start.sh
git diff --check
