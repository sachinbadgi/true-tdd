import json

from truetdd.mutation_bridge import (
    build_weak_test_map,
    load_survivors_from_meta,
    merge_into_traceability,
)


def _make_mutmut_meta(path, mutants):
    meta = {
        "exit_code_by_key": {},
        "durations_by_key": {},
        "estimated_durations_by_key": {},
        "type_check_error_by_key": {},
    }
    for mutant_id, exit_code in mutants.items():
        meta["exit_code_by_key"][mutant_id] = exit_code

    path.parent.mkdir(parents=True, exist_ok=True)
    import json

    path.write_text(json.dumps(meta))


def test_loads_only_survivors(tmp_path):
    # mutmut 3 uses exit_code 0 for survived, >0 for killed
    meta_dir = tmp_path / "mutants"
    meta_file = meta_dir / "src" / "calc.py.meta"
    _make_mutmut_meta(
        meta_file,
        {
            "calc.x_add__mutmut_1": 0,  # survived
            "calc.x_add__mutmut_2": 1,  # killed
        },
    )

    survivors = load_survivors_from_meta(str(meta_dir))
    assert len(survivors) == 1
    assert survivors[0]["mutant_id"] == "calc.x_add__mutmut_1"
    assert survivors[0]["filename"] == "src/calc.py"


def test_maps_survivors_to_tests():
    survivors = [{"mutant_id": "calc.x_add__mutmut_1", "filename": "src/calc.py", "line": 0}]
    coverage = {"files": {"src/calc.py": {"contexts": {"10": ["tests/test_calc.py::test_add"]}}}}
    weak_map = build_weak_test_map(survivors, coverage)
    assert "tests/test_calc.py::test_add" in weak_map
    assert weak_map["tests/test_calc.py::test_add"]["surviving_mutants"] == 1
    assert "calc.x_add__mutmut_1" in weak_map["tests/test_calc.py::test_add"]["mutant_ids"]


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
    scores = {"tests/test_calc.py::test_add": {"surviving_mutants_count": 2, "is_weak": True}}
    merge_into_traceability(scores, str(store_path))
    updated = json.loads(store_path.read_text())
    assert updated["tests"]["tests/test_calc.py::test_add"]["is_weak"] is True
    assert updated["tests"]["tests/test_calc.py::test_add"]["surviving_mutants_count"] == 2
