import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from autotest.conftest_plugin import TraceabilityPlugin


def _make_report(nodeid, outcome, req_ids, duration=0.1):
    report = MagicMock()
    report.when = "call"
    report.nodeid = nodeid
    report.outcome = outcome
    report.duration = duration
    marker_mocks = [MagicMock(args=(rid,)) for rid in req_ids]
    report.item = MagicMock()
    report.item.iter_markers.return_value = iter(marker_mocks)
    return report


def test_writes_passed_test(tmp_path):
    store_path = tmp_path / "store.json"
    plugin = TraceabilityPlugin(store_path=str(store_path))
    plugin.pytest_runtest_logreport(
        _make_report("tests/test_foo.py::test_bar", "passed", ["REQ-101"])
    )
    data = json.loads(store_path.read_text())
    assert "tests/test_foo.py::test_bar" in data["tests"]
    assert data["tests"]["tests/test_foo.py::test_bar"]["outcome"] == "passed"
    assert "REQ-101" in data["tests"]["tests/test_foo.py::test_bar"]["requirement_ids"]


def test_skips_untagged_tests(tmp_path):
    store_path = tmp_path / "store.json"
    plugin = TraceabilityPlugin(store_path=str(store_path))
    plugin.pytest_runtest_logreport(
        _make_report("tests/test_foo.py::test_untagged", "passed", [])
    )
    assert not store_path.exists()


def test_appends_multiple_tests(tmp_path):
    store_path = tmp_path / "store.json"
    plugin = TraceabilityPlugin(store_path=str(store_path))
    plugin.pytest_runtest_logreport(_make_report("t::a", "passed", ["REQ-101"]))
    plugin.pytest_runtest_logreport(_make_report("t::b", "failed", ["REQ-102"]))
    data = json.loads(store_path.read_text())
    assert len(data["tests"]) == 2


def test_stores_outcome_and_duration(tmp_path):
    store_path = tmp_path / "store.json"
    plugin = TraceabilityPlugin(store_path=str(store_path))
    plugin.pytest_runtest_logreport(
        _make_report("t::a", "failed", ["REQ-101"], duration=0.42)
    )
    data = json.loads(store_path.read_text())
    entry = data["tests"]["t::a"]
    assert entry["outcome"] == "failed"
    assert entry["duration"] == pytest.approx(0.42)


def test_defaults_weak_flags_to_false(tmp_path):
    store_path = tmp_path / "store.json"
    plugin = TraceabilityPlugin(store_path=str(store_path))
    plugin.pytest_runtest_logreport(_make_report("t::a", "passed", ["REQ-101"]))
    data = json.loads(store_path.read_text())
    entry = data["tests"]["t::a"]
    assert entry["is_weak"] is False
    assert entry["surviving_mutants_count"] == 0
