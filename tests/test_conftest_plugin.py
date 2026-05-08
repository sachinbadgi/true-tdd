import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from autotest.conftest_plugin import TraceabilityPlugin


def _make_item_and_call(nodeid, outcome, req_ids, duration=0.1):
    # Mock the item (which holds markers and nodeid)
    item = MagicMock()
    item.nodeid = nodeid
    marker_mocks = [MagicMock(args=(rid,)) for rid in req_ids]
    item.iter_markers.return_value = iter(marker_mocks)
    
    # Mock the report
    report = MagicMock()
    report.when = "call"
    report.nodeid = nodeid
    report.outcome = outcome
    report.duration = duration
    
    # Mock the outcome object that yield returns
    outcome_mock = MagicMock()
    outcome_mock.get_result.return_value = report
    
    return item, outcome_mock


def _run_hook(plugin, item, outcome_mock):
    gen = plugin.pytest_runtest_makereport(item, None)
    next(gen)
    try:
        gen.send(outcome_mock)
    except StopIteration:
        pass


def test_writes_passed_test(tmp_path):
    store_path = tmp_path / "store.json"
    plugin = TraceabilityPlugin(store_path=str(store_path))
    item, outcome_mock = _make_item_and_call("tests/test_foo.py::test_bar", "passed", ["REQ-101"])
    _run_hook(plugin, item, outcome_mock)
    
    data = json.loads(store_path.read_text())
    assert "tests/test_foo.py::test_bar" in data["tests"]
    assert data["tests"]["tests/test_foo.py::test_bar"]["outcome"] == "passed"
    assert "REQ-101" in data["tests"]["tests/test_foo.py::test_bar"]["requirement_ids"]


def test_skips_untagged_tests(tmp_path):
    store_path = tmp_path / "store.json"
    plugin = TraceabilityPlugin(store_path=str(store_path))
    item, outcome_mock = _make_item_and_call("tests/test_foo.py::test_untagged", "passed", [])
    _run_hook(plugin, item, outcome_mock)
    assert not store_path.exists()


def test_appends_multiple_tests(tmp_path):
    store_path = tmp_path / "store.json"
    plugin = TraceabilityPlugin(store_path=str(store_path))
    
    item1, out1 = _make_item_and_call("t::a", "passed", ["REQ-101"])
    _run_hook(plugin, item1, out1)
    
    item2, out2 = _make_item_and_call("t::b", "failed", ["REQ-102"])
    _run_hook(plugin, item2, out2)
    
    data = json.loads(store_path.read_text())
    assert len(data["tests"]) == 2


def test_stores_outcome_and_duration(tmp_path):
    store_path = tmp_path / "store.json"
    plugin = TraceabilityPlugin(store_path=str(store_path))
    
    item, outcome_mock = _make_item_and_call("t::a", "failed", ["REQ-101"], duration=0.42)
    _run_hook(plugin, item, outcome_mock)
    
    data = json.loads(store_path.read_text())
    entry = data["tests"]["t::a"]
    assert entry["outcome"] == "failed"
    assert entry["duration"] == pytest.approx(0.42)


def test_defaults_weak_flags_to_false(tmp_path):
    store_path = tmp_path / "store.json"
    plugin = TraceabilityPlugin(store_path=str(store_path))
    
    item, outcome_mock = _make_item_and_call("t::a", "passed", ["REQ-101"])
    _run_hook(plugin, item, outcome_mock)
    
    data = json.loads(store_path.read_text())
    entry = data["tests"]["t::a"]
    assert entry["is_weak"] is False
    assert entry["surviving_mutants_count"] == 0
