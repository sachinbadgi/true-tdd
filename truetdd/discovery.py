"""
truetdd/discovery.py

Auto-discovery for Python source and test files.
Outputs bash variable assignments (SRC_FILES, TEST_FILES) to decouple
run_pipeline.sh from hardcoded src/ and tests/ folders.

A file is considered a test if:
- It matches test_*.py or *_test.py
- OR it contains 'import pytest' or 'from pytest import'
All other .py files are considered source files.

Usage:
  eval $(python -m truetdd.discovery)
"""

from pathlib import Path


def is_test_file(path: Path) -> bool:
    if not path.name.endswith(".py"):
        return False

    # Naming convention
    if path.name.startswith("test_") or path.name.endswith("_test.py"):
        return True

    # Content inspection
    try:
        content = path.read_text(encoding="utf-8")
        if any(
            marker in content
            for marker in ["import pytest", "from pytest import", "import unittest", "from unittest import"]
        ):
            return True
    except Exception:
        pass

    return False


def discover(root_dir: str = "."):
    src_files = []
    test_files = []

    root_path = Path(root_dir)
    # Ignore hidden directories like .venv, .git, etc.
    for p in root_path.rglob("*.py"):
        # Exclude hidden directories, cache dirs, and build artifacts
        if any(part.startswith(".") for part in p.parts):
            continue
        if "__pycache__" in p.parts:
            continue

        if is_test_file(p):
            test_files.append(str(p))
        else:
            src_files.append(str(p))

    return src_files, test_files


if __name__ == "__main__":
    src_files, test_files = discover()

    # Print as bash variable assignments so `eval` can parse it.
    src_csv = ",".join(src_files)
    test_csv = ",".join(test_files)

    print(f'SRC_FILES="{src_csv}"')
    print(f'TEST_FILES="{test_csv}"')
