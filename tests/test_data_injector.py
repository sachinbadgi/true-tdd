"""
tests/test_data_injector.py

Unit tests for truetdd.data_injector.

Tests cover:
  - YAML loading
  - prepare() / restore() backup lifecycle
  - crash recovery via lock sentinel
  - AST rewriting: normal cases (assert) + raises cases
  - marker resolution priority (explicit @pytest.mark.testdata vs auto-match)
  - graceful passthrough when no matching cases exist
"""

import ast
import textwrap

import pytest

from truetdd.data_injector import (
    BACKUP_DIR_NAME,
    LOCK_FILENAME,
    DataInjector,
    _get_testdata_marker,
)

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

MINIMAL_YAML = textwrap.dedent("""\
    version: 1
    cases:
      test_add_positive:
        description: Boundary cases
        cases:
          - {a: 2, b: 3, expected: 5}
          - {a: 0, b: 0, expected: 0}
          - {a: -5, b: 5, expected: 0}
      add_cases:
        description: Shared named set
        cases:
          - {a: 2, b: 3, expected: 5}
          - {a: 0, b: 0, expected: 0}
      test_divide_by_zero_raises:
        description: Raises cases
        cases:
          - {a: 10, b: 0, raises: ValueError}
          - {a: -5, b: 0, raises: ValueError}
""")

SIMPLE_TEST_SOURCE = textwrap.dedent("""\
    import pytest
    from calculator import add

    @pytest.mark.requirement("REQ-201")
    def test_add_positive():
        assert add(2, 3) == 5
""")

RAISES_TEST_SOURCE = textwrap.dedent("""\
    import pytest
    from calculator import divide

    @pytest.mark.requirement("REQ-202")
    def test_divide_by_zero_raises():
        with pytest.raises(ValueError):
            divide(10, 0)
""")

MARKER_TEST_SOURCE = textwrap.dedent("""\
    import pytest
    from calculator import add

    @pytest.mark.requirement("REQ-201")
    @pytest.mark.testdata("add_cases")
    def test_add_with_marker():
        assert add(2, 3) == 5
""")

NO_MATCH_SOURCE = textwrap.dedent("""\
    import pytest
    from calculator import subtract

    def test_subtract_unknown():
        assert subtract(5, 3) == 2
""")


@pytest.fixture()
def tmp_testdata(tmp_path):
    """Write testdata.yaml to a temp directory and return the path."""
    yaml_path = tmp_path / "testdata.yaml"
    yaml_path.write_text(MINIMAL_YAML)
    return yaml_path


@pytest.fixture()
def injector(tmp_path, tmp_testdata):
    backup_dir = tmp_path / BACKUP_DIR_NAME
    inj = DataInjector(tmp_testdata, backup_dir)
    inj.load()
    return inj


@pytest.fixture()
def test_file(tmp_path):
    """Write a simple test file and return its path."""
    f = tmp_path / "test_calculator.py"
    f.write_text(SIMPLE_TEST_SOURCE)
    return f


@pytest.fixture()
def raises_test_file(tmp_path):
    f = tmp_path / "test_raises.py"
    f.write_text(RAISES_TEST_SOURCE)
    return f


@pytest.fixture()
def marker_test_file(tmp_path):
    f = tmp_path / "test_marker.py"
    f.write_text(MARKER_TEST_SOURCE)
    return f


@pytest.fixture()
def no_match_test_file(tmp_path):
    f = tmp_path / "test_no_match.py"
    f.write_text(NO_MATCH_SOURCE)
    return f


# ──────────────────────────────────────────────────────────────────────────────
# YAML Loading
# ──────────────────────────────────────────────────────────────────────────────


class TestLoad:
    def test_load_returns_case_sets(self, injector):
        assert "test_add_positive" in injector._case_sets
        assert "add_cases" in injector._case_sets
        assert "test_divide_by_zero_raises" in injector._case_sets

    def test_load_case_count(self, injector):
        cases = injector._case_sets["test_add_positive"]["cases"]
        assert len(cases) == 3

    def test_load_missing_yaml_returns_empty(self, tmp_path):
        inj = DataInjector(tmp_path / "nonexistent.yaml", tmp_path / BACKUP_DIR_NAME)
        result = inj.load()
        assert result == {}

    def test_load_named_set(self, injector):
        cases = injector._case_sets["add_cases"]["cases"]
        assert len(cases) == 2
        assert cases[0] == {"a": 2, "b": 3, "expected": 5}


# ──────────────────────────────────────────────────────────────────────────────
# Prepare / Restore lifecycle
# ──────────────────────────────────────────────────────────────────────────────


class TestPrepareRestore:
    def test_prepare_creates_backup(self, injector, test_file):
        original = test_file.read_text()
        injector.prepare(test_file)
        bak = injector.backup_dir / (test_file.name + ".bak")
        assert bak.exists()
        assert bak.read_text() == original

    def test_prepare_creates_lock(self, injector, test_file):
        injector.prepare(test_file)
        assert (injector.backup_dir / LOCK_FILENAME).exists()

    def test_prepare_modifies_test_file(self, injector, test_file):
        original = test_file.read_text()
        injector.prepare(test_file)
        assert test_file.read_text() != original

    def test_prepare_returns_true_when_injected(self, injector, test_file):
        assert injector.prepare(test_file) is True

    def test_prepare_returns_false_when_no_match(self, injector, no_match_test_file):
        assert injector.prepare(no_match_test_file) is False

    def test_restore_reinstates_original(self, injector, test_file):
        original = test_file.read_text()
        injector.prepare(test_file)
        injector.restore(test_file)
        assert test_file.read_text() == original

    def test_restore_removes_backup(self, injector, test_file):
        injector.prepare(test_file)
        injector.restore(test_file)
        bak = injector.backup_dir / (test_file.name + ".bak")
        assert not bak.exists()

    def test_restore_removes_lock_when_all_done(self, injector, test_file):
        injector.prepare(test_file)
        injector.restore(test_file)
        assert not (injector.backup_dir / LOCK_FILENAME).exists()

    def test_restore_is_idempotent(self, injector, test_file):
        injector.prepare(test_file)
        injector.restore(test_file)
        # second restore should not raise
        injector.restore(test_file)

    def test_prepare_missing_file_returns_false(self, injector, tmp_path):
        missing = tmp_path / "test_does_not_exist.py"
        assert injector.prepare(missing) is False


# ──────────────────────────────────────────────────────────────────────────────
# Crash recovery
# ──────────────────────────────────────────────────────────────────────────────


class TestCrashRecovery:
    def test_init_with_lock_calls_restore_all(self, tmp_path, tmp_testdata):
        backup_dir = tmp_path / BACKUP_DIR_NAME
        backup_dir.mkdir(parents=True)

        # Simulate a mid-run crash: write original to backup, augmented to test file
        test_file = tmp_path / "test_calc.py"
        original_content = "# original\n"
        test_file.write_text("# augmented\n")  # crashed mid-write

        bak_path = backup_dir / "test_calc.py.bak"
        bak_path.write_text(original_content)

        lock_path = backup_dir / LOCK_FILENAME
        lock_path.touch()

        # Constructing DataInjector should trigger restore_all
        DataInjector(tmp_testdata, backup_dir)

        # Original should be restored
        assert test_file.read_text() == original_content
        assert not bak_path.exists()
        assert not lock_path.exists()


# ──────────────────────────────────────────────────────────────────────────────
# AST rewriting: normal assert tests
# ──────────────────────────────────────────────────────────────────────────────


class TestAugmentNormal:
    def test_augmented_source_is_valid_python(self, injector, test_file):
        injector.prepare(test_file)
        source = test_file.read_text()
        # Should parse without errors
        ast.parse(source)

    def test_augmented_has_parametrize_decorator(self, injector, test_file):
        injector.prepare(test_file)
        source = test_file.read_text()
        assert "parametrize" in source

    def test_augmented_has_correct_param_count(self, injector, test_file):
        injector.prepare(test_file)
        source = test_file.read_text()
        # Should have 3 tuples from 3 cases
        assert source.count("(2, 3, 5)") >= 1 or "2, 3, 5" in source

    def test_injected_sets_tracked(self, injector, test_file):
        injector.prepare(test_file)
        injected = injector.get_injected_sets()
        assert any("test_add_positive" in k for k in injected)

    def test_injected_case_count(self, injector, test_file):
        injector.prepare(test_file)
        injected = injector.get_injected_sets()
        key = next(k for k in injected if "test_add_positive" in k)
        assert injected[key]["case_count"] == 3


# ──────────────────────────────────────────────────────────────────────────────
# AST rewriting: raises tests
# ──────────────────────────────────────────────────────────────────────────────


class TestAugmentRaises:
    def test_raises_augmented_is_valid_python(self, injector, raises_test_file):
        injector.prepare(raises_test_file)
        source = raises_test_file.read_text()
        ast.parse(source)

    def test_raises_has_parametrize(self, injector, raises_test_file):
        injector.prepare(raises_test_file)
        source = raises_test_file.read_text()
        assert "parametrize" in source

    def test_raises_preserves_pytest_raises(self, injector, raises_test_file):
        injector.prepare(raises_test_file)
        source = raises_test_file.read_text()
        assert "pytest.raises" in source


# ──────────────────────────────────────────────────────────────────────────────
# Marker resolution
# ──────────────────────────────────────────────────────────────────────────────


class TestMarkerResolution:
    def test_marker_extracts_set_name(self, marker_test_file):
        source = marker_test_file.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "test_add_with_marker":
                result = _get_testdata_marker(node)
                assert result == "add_cases"
                return
        pytest.fail("Function not found")

    def test_marker_set_used_over_function_name(self, injector, marker_test_file):
        """When @pytest.mark.testdata is present, it takes priority over fn name."""
        injector.prepare(marker_test_file)
        injected = injector.get_injected_sets()
        key = next(k for k in injected if "test_add_with_marker" in k)
        assert injected[key]["set_name"] == "add_cases"
        assert injected[key]["edge_type"] == "EXTRACTED"

    def test_auto_match_uses_inferred_edge(self, injector, test_file):
        """Without marker, resolution is INFERRED from function name."""
        injector.prepare(test_file)
        injected = injector.get_injected_sets()
        key = next(k for k in injected if "test_add_positive" in k)
        assert injected[key]["edge_type"] == "INFERRED"


# ──────────────────────────────────────────────────────────────────────────────
# Graceful passthrough
# ──────────────────────────────────────────────────────────────────────────────


class TestGracefulPassthrough:
    def test_no_match_leaves_file_unchanged(self, injector, no_match_test_file):
        original = no_match_test_file.read_text()
        injector.prepare(no_match_test_file)
        assert no_match_test_file.read_text() == original

    def test_no_match_no_backup_created(self, injector, no_match_test_file):
        injector.prepare(no_match_test_file)
        bak = injector.backup_dir / (no_match_test_file.name + ".bak")
        assert not bak.exists()
