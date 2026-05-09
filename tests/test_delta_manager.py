"""
tests/test_delta_manager.py

Unit tests for truetdd.delta_manager.generate_delta().

Tests cover:
  - No manifest → early exit (no delta file written)
  - Changed files detected and written to delta.txt
  - Unchanged files produce empty delta
  - Test files and infrastructure files excluded from delta
  - Last manifest updated on each run
"""

import json
from pathlib import Path
from typing import Optional

from truetdd.delta_manager import generate_delta


def _setup_manifest(tmp_path: Path, current: dict, last: Optional[dict] = None):
    """Helper to write manifest files and return paths."""
    manifest = tmp_path / "manifest.json"
    last_manifest = tmp_path / "last_manifest.json"
    delta = tmp_path / "delta.txt"
    manifest.write_text(json.dumps(current))
    if last is not None:
        last_manifest.write_text(json.dumps(last))
    return str(manifest), str(last_manifest), str(delta)


class TestNoDelta:
    def test_no_manifest_does_not_write_delta(self, tmp_path):
        """If no graphify manifest exists, generate_delta() exits early — no file written."""
        delta = tmp_path / "delta.txt"
        generate_delta(
            manifest_path=str(tmp_path / "nonexistent.json"),
            last_manifest_path=str(tmp_path / "last.json"),
            delta_out=str(delta),
        )
        assert not delta.exists()

    def test_no_changes_writes_empty_delta(self, tmp_path):
        """If no files changed since last run, delta.txt should be empty."""
        manifest_data = {"src/calculator.py": {"hash": "abc123"}}
        mf, last_m, df = _setup_manifest(tmp_path, manifest_data, manifest_data)
        generate_delta(manifest_path=mf, last_manifest_path=last_m, delta_out=df)
        assert Path(df).read_text().strip() == ""


class TestDeltaDetection:
    def test_new_file_is_detected(self, tmp_path):
        """A file present in current manifest but not in last is flagged as changed."""
        mf, last_m, df = _setup_manifest(tmp_path, {"src/calculator.py": {"hash": "abc123"}})
        generate_delta(manifest_path=mf, last_manifest_path=last_m, delta_out=df)
        delta = Path(df).read_text().splitlines()
        assert "src/calculator.py" in delta

    def test_hash_change_detected(self, tmp_path):
        """A file whose hash changed between runs is flagged."""
        mf, last_m, df = _setup_manifest(
            tmp_path,
            {"src/calculator.py": {"hash": "new_hash"}},
            {"src/calculator.py": {"hash": "old_hash"}},
        )
        generate_delta(manifest_path=mf, last_manifest_path=last_m, delta_out=df)
        assert "src/calculator.py" in Path(df).read_text().splitlines()

    def test_test_files_excluded(self, tmp_path):
        """Test files should never appear in the mutation delta."""
        mf, last_m, df = _setup_manifest(
            tmp_path,
            {
                "src/calculator.py": {"hash": "abc"},
                "tests/test_calculator.py": {"hash": "def"},
            },
        )
        generate_delta(manifest_path=mf, last_manifest_path=last_m, delta_out=df)
        delta = Path(df).read_text().splitlines()
        assert "src/calculator.py" in delta
        assert "tests/test_calculator.py" not in delta

    def test_non_py_files_excluded(self, tmp_path):
        """Only .py files should appear in the delta."""
        mf, last_m, df = _setup_manifest(
            tmp_path,
            {
                "src/calculator.py": {"hash": "abc"},
                "src/README.md": {"hash": "def"},
            },
        )
        generate_delta(manifest_path=mf, last_manifest_path=last_m, delta_out=df)
        assert "src/README.md" not in Path(df).read_text().splitlines()

    def test_conftest_excluded(self, tmp_path):
        """conftest.py is infrastructure — should not be mutated."""
        mf, last_m, df = _setup_manifest(tmp_path, {"tests/conftest.py": {"hash": "abc"}})
        generate_delta(manifest_path=mf, last_manifest_path=last_m, delta_out=df)
        dp = Path(df)
        if dp.exists():
            assert "conftest.py" not in dp.read_text()

    def test_unchanged_file_not_in_delta(self, tmp_path):
        """Unchanged file (same hash) must not appear in delta."""
        same = {"hash": "stable"}
        mf, last_m, df = _setup_manifest(tmp_path, {"src/stable.py": same}, {"src/stable.py": same})
        generate_delta(manifest_path=mf, last_manifest_path=last_m, delta_out=df)
        assert "src/stable.py" not in Path(df).read_text()


class TestManifestUpdate:
    def test_last_manifest_written_after_run(self, tmp_path):
        """generate_delta() should persist the current manifest as the 'last' for the next run."""
        current = {"src/calculator.py": {"hash": "abc123"}}
        mf, last_m, df = _setup_manifest(tmp_path, current)
        generate_delta(manifest_path=mf, last_manifest_path=last_m, delta_out=df)
        assert Path(last_m).exists()
        assert json.loads(Path(last_m).read_text()) == current
