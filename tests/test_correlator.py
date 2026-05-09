"""
tests/test_correlator.py

Unit tests for truetdd.correlator — the Discovery Engine.

Tests cover all three signal generators as pure functions:
  - _find_untested_reqs
  - _find_orphaned_functions
  - _find_weak_coverage_gaps

And helper utilities:
  - _tokenize
  - _score
  - _source_fn_nodes
  - _tested_fn_names
  - _reqs_with_tests
  - _weak_reqs
"""

import json

from truetdd.correlator import (
    _find_orphaned_functions,
    _find_untested_reqs,
    _find_weak_coverage_gaps,
    _reqs_with_tests,
    _score,
    _source_fn_nodes,
    _tested_fn_names,
    _tokenize,
    _weak_reqs,
)

# ──────────────────────────────────────────────────────────────────────────────
# _tokenize
# ──────────────────────────────────────────────────────────────────────────────


class TestTokenize:
    def test_basic_word_extraction(self):
        tokens = _tokenize("add two numbers")
        assert "add" in tokens
        assert "two" in tokens

    def test_underscores_treated_as_spaces(self):
        tokens = _tokenize("test_add_positive")
        assert "test" in tokens
        assert "add" in tokens
        assert "positive" in tokens

    def test_synonym_normalization(self):
        tokens = _tokenize("addition of values")
        assert "add" in tokens  # "addition" → "add" via _SYNONYMS

    def test_short_words_excluded(self):
        tokens = _tokenize("a b ab the and")
        # Only words with 3+ chars are included
        assert "the" in tokens
        assert "and" in tokens
        assert "a" not in tokens
        assert "ab" not in tokens

    def test_empty_string_returns_empty_set(self):
        assert _tokenize("") == set()


# ──────────────────────────────────────────────────────────────────────────────
# _score
# ──────────────────────────────────────────────────────────────────────────────


class TestScore:
    def test_identical_text_scores_high(self):
        score = _score("add numbers", "add()")
        assert score > 0.3

    def test_unrelated_text_scores_low(self):
        score = _score("encrypt password", "add()")
        assert score < 0.3

    def test_empty_inputs_score_zero(self):
        assert _score("", "add()") == 0.0
        assert _score("add numbers", "") == 0.0

    def test_score_is_between_zero_and_one(self):
        score = _score("addition function", "add()")
        assert 0.0 <= score <= 1.0


# ──────────────────────────────────────────────────────────────────────────────
# _source_fn_nodes
# ──────────────────────────────────────────────────────────────────────────────


class TestSourceFnNodes:
    def _make_graph(self, nodes):
        return {"nodes": nodes}

    def test_extracts_src_function_nodes(self):
        graph = self._make_graph(
            [
                {"id": "1", "label": "add()", "source_file": "src/calculator.py"},
            ]
        )
        result = _source_fn_nodes(graph)
        assert len(result) == 1
        assert result[0]["label"] == "add()"

    def test_excludes_test_nodes(self):
        graph = self._make_graph(
            [
                {"id": "1", "label": "test_add()", "source_file": "src/calculator.py"},
            ]
        )
        result = _source_fn_nodes(graph)
        assert result == []

    def test_excludes_non_src_nodes(self):
        graph = self._make_graph(
            [
                {"id": "1", "label": "add()", "source_file": "mypackage/calculator.py"},
            ]
        )
        result = _source_fn_nodes(graph)
        # Not in src/ → excluded
        assert result == []

    def test_excludes_nodes_without_parens(self):
        graph = self._make_graph(
            [
                {"id": "1", "label": "calculator", "source_file": "src/calculator.py"},
            ]
        )
        result = _source_fn_nodes(graph)
        assert result == []

    def test_empty_graph_returns_empty(self):
        assert _source_fn_nodes({}) == []


# ──────────────────────────────────────────────────────────────────────────────
# _tested_fn_names
# ──────────────────────────────────────────────────────────────────────────────


class TestTestedFnNames:
    def test_extracts_covered_artifact_basenames(self):
        store = {"tests": {"tests/test_calc.py::test_add": {"covered_artifacts": ["calculator.add"]}}}
        result = _tested_fn_names(store)
        assert "add" in result

    def test_empty_store_returns_empty(self):
        assert _tested_fn_names({"tests": {}}) == set()


# ──────────────────────────────────────────────────────────────────────────────
# _reqs_with_tests
# ──────────────────────────────────────────────────────────────────────────────


class TestReqsWithTests:
    def test_passed_tests_included(self):
        store = {"tests": {"t::a": {"outcome": "passed", "requirement_ids": ["REQ-101"]}}}
        result = _reqs_with_tests(store)
        assert "REQ-101" in result

    def test_failed_tests_excluded(self):
        store = {"tests": {"t::a": {"outcome": "failed", "requirement_ids": ["REQ-101"]}}}
        result = _reqs_with_tests(store)
        assert "REQ-101" not in result

    def test_empty_store_returns_empty(self):
        assert _reqs_with_tests({"tests": {}}) == set()


# ──────────────────────────────────────────────────────────────────────────────
# _weak_reqs
# ──────────────────────────────────────────────────────────────────────────────


class TestWeakReqs:
    def test_returns_weak_reqs_from_feedback(self, tmp_path):
        fb = {
            "requirements": {
                "REQ-101": {"status": "WEAK"},
                "REQ-102": {"status": "VERIFIED"},
                "REQ-103": {"status": "WEAK_DATA"},
            }
        }
        fb_path = tmp_path / "loop_feedback.json"
        fb_path.write_text(json.dumps(fb))
        result = _weak_reqs(str(fb_path))
        assert "REQ-101" in result
        assert "REQ-103" in result
        assert "REQ-102" not in result

    def test_missing_file_returns_empty(self, tmp_path):
        result = _weak_reqs(str(tmp_path / "nonexistent.json"))
        assert result == {}


# ──────────────────────────────────────────────────────────────────────────────
# _find_untested_reqs
# ──────────────────────────────────────────────────────────────────────────────


class TestFindUntestedReqs:
    def _source_node(self, label, file="src/calculator.py"):
        return {"id": "1", "label": label, "file": file, "reliability_score": None, "surviving_mutants": None}

    def test_untested_req_produces_signal(self):
        reqs = {"REQ-101": "add two numbers"}
        tracked = set()  # REQ-101 not tracked
        nodes = [self._source_node("add()")]
        signals = _find_untested_reqs(reqs, tracked, nodes)
        assert len(signals) == 1
        assert signals[0]["signal"] == "UNTESTED_REQ"
        assert signals[0]["req_id"] == "REQ-101"

    def test_tracked_req_excluded(self):
        reqs = {"REQ-101": "add two numbers"}
        tracked = {"REQ-101"}
        nodes = [self._source_node("add()")]
        signals = _find_untested_reqs(reqs, tracked, nodes)
        assert signals == []

    def test_likely_implementations_sorted_by_confidence(self):
        reqs = {"REQ-101": "add two numbers"}
        tracked = set()
        nodes = [
            self._source_node("add()"),
            self._source_node("multiply()"),
        ]
        signals = _find_untested_reqs(reqs, tracked, nodes)
        assert signals[0]["signal"] == "UNTESTED_REQ"
        impls = signals[0]["likely_implementations"]
        if len(impls) > 1:
            assert impls[0]["confidence"] >= impls[1]["confidence"]


# ──────────────────────────────────────────────────────────────────────────────
# _find_orphaned_functions
# ──────────────────────────────────────────────────────────────────────────────


class TestFindOrphanedFunctions:
    def _source_node(self, label, file="src/calculator.py"):
        return {"id": "1", "label": label, "file": file, "reliability_score": None, "surviving_mutants": None}

    def test_uncovered_function_is_orphaned(self, tmp_path):
        # No coverage.json → file is not in covered_fns → orphaned
        nodes = [self._source_node("add()")]
        store = {"tests": {}}
        req_texts = {"REQ-101": "add numbers"}
        signals = _find_orphaned_functions(nodes, store, req_texts)
        assert len(signals) == 1
        assert signals[0]["signal"] == "ORPHANED_FN"

    def test_prd_candidates_included(self, tmp_path):
        nodes = [self._source_node("add()")]
        store = {"tests": {}}
        req_texts = {"REQ-101": "add numbers together"}
        signals = _find_orphaned_functions(nodes, store, req_texts)
        assert signals[0]["prd_candidates"]
        assert signals[0]["prd_candidates"][0]["req_id"] == "REQ-101"

    def test_empty_nodes_returns_empty(self):
        assert _find_orphaned_functions([], {}, {}) == []


# ──────────────────────────────────────────────────────────────────────────────
# _find_weak_coverage_gaps
# ──────────────────────────────────────────────────────────────────────────────


class TestFindWeakCoverageGaps:
    def _source_node(self, label, file="src/calculator.py", rel=0.5, surv=3):
        return {
            "id": "1",
            "label": label,
            "file": file,
            "reliability_score": rel,
            "surviving_mutants": surv,
        }

    def test_weak_req_produces_signal(self):
        weak_reqs = {"REQ-101": {"status": "WEAK", "tests": ["t::test_add"]}}
        nodes = [self._source_node("add()")]
        req_texts = {"REQ-101": "add two numbers"}
        signals = _find_weak_coverage_gaps(weak_reqs, nodes, req_texts)
        assert len(signals) == 1
        assert signals[0]["signal"] == "WEAK_COVERAGE"
        assert signals[0]["req_id"] == "REQ-101"

    def test_implementing_fn_includes_reliability(self):
        weak_reqs = {"REQ-101": {"status": "WEAK_DATA", "tests": []}}
        nodes = [self._source_node("add()", rel=0.75, surv=2)]
        req_texts = {"REQ-101": "add numbers"}
        signals = _find_weak_coverage_gaps(weak_reqs, nodes, req_texts)
        if signals:
            fn = signals[0]["implementing_fns"][0]
            assert fn["reliability_score"] == 0.75
            assert fn["surviving_mutants"] == 2

    def test_no_match_produces_no_signal(self):
        weak_reqs = {"REQ-101": {"status": "WEAK", "tests": []}}
        nodes = [self._source_node("encrypt()")]
        req_texts = {"REQ-101": "add numbers"}
        signals = _find_weak_coverage_gaps(weak_reqs, nodes, req_texts)
        assert signals == []

    def test_empty_weak_reqs_returns_empty(self):
        assert _find_weak_coverage_gaps({}, [], {}) == []
