"""
tests/test_testdata_suggester.py

Unit tests for truetdd.testdata_suggester.

Tests cover:
  - _generate_boundary_cases: boundary case generation heuristics
  - _infer_param_names: parameter name inference
  - _extract_call_from_test: AST extraction from test source
  - suggest_testdata_for_weak_tests: integration (pure function, uses tmp_path for files)
"""

import textwrap

from truetdd.testdata_suggester import (
    _extract_call_from_test,
    _generate_boundary_cases,
    _infer_param_names,
    suggest_testdata_for_weak_tests,
)

# ──────────────────────────────────────────────────────────────────────────────
# _infer_param_names
# ──────────────────────────────────────────────────────────────────────────────


class TestInferParamNames:
    def test_two_args_returns_a_b(self):
        result = _infer_param_names("add", [1, 2])
        assert result == ["a", "b"]

    def test_three_args_returns_a_b_c(self):
        result = _infer_param_names("func", [1, 2, 3])
        assert result == ["a", "b", "c"]

    def test_one_arg_returns_value(self):
        result = _infer_param_names("negate", [5])
        assert result == ["value"]

    def test_zero_args_returns_empty(self):
        result = _infer_param_names("no_args", [])
        assert result == []

    def test_four_args_uses_argN_pattern(self):
        result = _infer_param_names("func", [1, 2, 3, 4])
        assert result == ["arg0", "arg1", "arg2", "arg3"]


# ──────────────────────────────────────────────────────────────────────────────
# _generate_boundary_cases
# ──────────────────────────────────────────────────────────────────────────────


class TestGenerateBoundaryCases:
    def test_generates_baseline_case(self):
        cases = _generate_boundary_cases([2, 3], 5, ["a", "b"])
        baselines = [c for c in cases if c.get("_comment", "").startswith("baseline")]
        assert len(baselines) == 1
        assert baselines[0]["a"] == 2
        assert baselines[0]["b"] == 3
        assert baselines[0]["expected"] == 5

    def test_generates_zero_input_case(self):
        cases = _generate_boundary_cases([2, 3], 5, ["a", "b"])
        zeros = [c for c in cases if c.get("_comment", "").startswith("zero")]
        assert len(zeros) == 1
        assert zeros[0]["a"] == 0
        assert zeros[0]["b"] == 0
        assert zeros[0]["expected"] == "???"

    def test_generates_identity_case_for_two_args(self):
        cases = _generate_boundary_cases([2, 3], 5, ["a", "b"])
        identities = [c for c in cases if "identity" in c.get("_comment", "")]
        assert len(identities) == 1
        assert identities[0]["a"] == 1
        assert identities[0]["b"] == 1

    def test_generates_negative_case(self):
        cases = _generate_boundary_cases([2, 3], 5, ["a", "b"])
        negatives = [c for c in cases if "negative" in c.get("_comment", "")]
        assert len(negatives) == 1
        assert negatives[0]["a"] < 0  # first arg negated

    def test_no_identity_case_for_one_arg(self):
        cases = _generate_boundary_cases([5], 25, ["value"])
        identities = [c for c in cases if "identity" in c.get("_comment", "")]
        assert len(identities) == 0

    def test_missing_baseline_skips_it(self):
        """When args or expected contain None, baseline should be skipped."""
        cases = _generate_boundary_cases([None, 3], None, ["a", "b"])
        baselines = [c for c in cases if c.get("_comment", "").startswith("baseline")]
        assert len(baselines) == 0

    def test_all_cases_have_expected_key(self):
        cases = _generate_boundary_cases([2, 3], 5, ["a", "b"])
        for c in cases:
            assert "expected" in c

    def test_negative_of_zero_arg_uses_minus_one(self):
        """When baseline first arg is 0, negative case should use -1."""
        cases = _generate_boundary_cases([0, 3], 3, ["a", "b"])
        negatives = [c for c in cases if "negative" in c.get("_comment", "")]
        if negatives:
            assert negatives[0]["a"] == -1


# ──────────────────────────────────────────────────────────────────────────────
# _extract_call_from_test
# ──────────────────────────────────────────────────────────────────────────────


class TestExtractCallFromTest:
    def test_extracts_simple_assert(self, tmp_path):
        source = textwrap.dedent("""\
            from calculator import add

            def test_add():
                assert add(2, 3) == 5
        """)
        f = tmp_path / "test_calc.py"
        f.write_text(source)
        result = _extract_call_from_test(f, "test_add")
        assert result is not None
        called, args, expected = result
        assert called == "add"
        assert args == [2, 3]
        assert expected == 5

    def test_extracts_negative_arg(self, tmp_path):
        source = textwrap.dedent("""\
            from calculator import subtract

            def test_sub():
                assert subtract(-1, 2) == -3
        """)
        f = tmp_path / "test_calc.py"
        f.write_text(source)
        result = _extract_call_from_test(f, "test_sub")
        assert result is not None
        _, args, expected = result
        assert args[0] == -1
        assert expected == -3

    def test_returns_none_for_missing_function(self, tmp_path):
        source = textwrap.dedent("""\
            def test_something():
                pass
        """)
        f = tmp_path / "test_calc.py"
        f.write_text(source)
        result = _extract_call_from_test(f, "test_nonexistent")
        assert result is None

    def test_returns_none_for_unreadable_file(self, tmp_path):
        missing = tmp_path / "nonexistent.py"
        result = _extract_call_from_test(missing, "test_add")
        assert result is None


# ──────────────────────────────────────────────────────────────────────────────
# suggest_testdata_for_weak_tests (integration)
# ──────────────────────────────────────────────────────────────────────────────


class TestSuggestTestdata:
    def test_generates_stub_for_weak_data_req(self, tmp_path):
        source = textwrap.dedent("""\
            from calculator import add

            def test_add():
                assert add(2, 3) == 5
        """)
        test_file = tmp_path / "test_calc.py"
        test_file.write_text(source)

        weak_data_reqs = {
            "REQ-101": {
                "status": "WEAK_DATA",
                "tests": [f"{test_file}::test_add"],
            }
        }
        result = suggest_testdata_for_weak_tests(weak_data_reqs, {}, tests_dir=str(tmp_path))
        assert "test_add" in result
        stub = result["test_add"]
        assert "cases" in stub
        assert len(stub["cases"]) > 0

    def test_skips_non_weak_data_reqs(self, tmp_path):
        weak_data_reqs = {
            "REQ-101": {"status": "WEAK", "tests": []},  # not WEAK_DATA
        }
        result = suggest_testdata_for_weak_tests(weak_data_reqs, {}, tests_dir=str(tmp_path))
        assert result == {}

    def test_does_not_duplicate_function_suggestions(self, tmp_path):
        source = textwrap.dedent("""\
            from calculator import add

            def test_add():
                assert add(2, 3) == 5
        """)
        test_file = tmp_path / "test_calc.py"
        test_file.write_text(source)

        # Two requirements, both pointing to the same test function
        weak_data_reqs = {
            "REQ-101": {"status": "WEAK_DATA", "tests": [f"{test_file}::test_add"]},
            "REQ-102": {"status": "WEAK_DATA", "tests": [f"{test_file}::test_add"]},
        }
        result = suggest_testdata_for_weak_tests(weak_data_reqs, {}, tests_dir=str(tmp_path))
        # Should only generate once
        assert list(result.keys()).count("test_add") == 1
