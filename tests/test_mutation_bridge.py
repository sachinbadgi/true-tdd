import json
import sqlite3
import pytest
from autotest.mutation_bridge import (
    load_survivors_from_db,
    build_weak_test_map,
    merge_into_traceability,
)


def _make_mutmut_db(path):
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE mutant (id INTEGER, filename TEXT, line_number INTEGER, status TEXT)"
    )
    conn.execute("INSERT INTO mutant VALUES (1, 'src/calc.py', 10, 'survived')")
    conn.execute("INSERT INTO mutant VALUES (2, 'src/calc.py', 20, 'killed')")
    conn.commit()
    conn.close()


def test_loads_only_survivors(tmp_path):
    db = tmp_path / "cache"
    _make_mutmut_db(db)
    survivors = load_survivors_from_db(str(db))
    assert len(survivors) == 1
    assert survivors[0]["line"] == 10


def test_maps_survivors_to_tests():
    survivors = [{"mutant_id": 1, "filename": "src/calc.py", "line": 10}]
    coverage = {
        "files": {
            "src/calc.py": {"contexts": {"10": ["tests/test_calc.py::test_add"]}}
        }
    }
    weak_map = build_weak_test_map(survivors, coverage)
    assert "tests/test_calc.py::test_add" in weak_map
    assert weak_map["tests/test_calc.py::test_add"]["surviving_mutants"] == 1


def test_merge_updates_traceability(tmp_path):
    store_path = tmp_path / "store.json"
    store = {
        "tests": {
            "tests/test_calc.py::test_add": {
                "outcome": "passed",
                "requirement_ids": ["REQ-101"],
                "surviving_mutants_count": 0,
                "is_weak": False,
            }
        }
    }
    store_path.write_text(json.dumps(store))
    scores = {
        "tests/test_calc.py::test_add": {"surviving_mutants_count": 2, "is_weak": True}
    }
    merge_into_traceability(scores, str(store_path))
    updated = json.loads(store_path.read_text())
    assert updated["tests"]["tests/test_calc.py::test_add"]["is_weak"] is True
    assert updated["tests"]["tests/test_calc.py::test_add"]["surviving_mutants_count"] == 2
