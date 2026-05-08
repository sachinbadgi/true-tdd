import pytest
from autotest.graph_analyzer import analyze_traceability

def test_analyze_traceability_identifies_orphans_and_god_tests():
    mock_graph = {
        "nodes": [
            {"id": "test_t1", "label": "test_add()", "file_type": "code", "source_file": "tests/test_calc.py", "norm_label": "test_add()"},
            {"id": "test_t2", "label": "test_god()", "file_type": "code", "source_file": "tests/test_calc.py", "norm_label": "test_god()"},
            {"id": "src_s1", "label": "add()", "file_type": "code", "source_file": "src/calc.py", "norm_label": "add()"},
            {"id": "src_s2", "label": "multiply()", "file_type": "code", "source_file": "src/calc.py", "norm_label": "multiply()"},
            {"id": "src_s3", "label": "f1()", "file_type": "code", "source_file": "src/calc.py", "norm_label": "f1()"},
            {"id": "src_s4", "label": "f2()", "file_type": "code", "source_file": "src/calc.py", "norm_label": "f2()"},
            {"id": "src_s5", "label": "f3()", "file_type": "code", "source_file": "src/calc.py", "norm_label": "f3()"},
            {"id": "src_s6", "label": "f4()", "file_type": "code", "source_file": "src/calc.py", "norm_label": "f4()"},
            {"id": "src_s7", "label": "f5()", "file_type": "code", "source_file": "src/calc.py", "norm_label": "f5()"},
            {"id": "src_s8", "label": "f6()", "file_type": "code", "source_file": "src/calc.py", "norm_label": "f6()"},
        ],
        "links": [
            {"source": "test_t1", "target": "src_s1", "relation": "calls"},
            {"source": "test_t2", "target": "src_s3", "relation": "calls"},
            {"source": "test_t2", "target": "src_s4", "relation": "calls"},
            {"source": "test_t2", "target": "src_s5", "relation": "calls"},
            {"source": "test_t2", "target": "src_s6", "relation": "calls"},
            {"source": "test_t2", "target": "src_s7", "relation": "calls"},
            {"source": "test_t2", "target": "src_s8", "relation": "calls"},
        ]
    }
    
    result = analyze_traceability(mock_graph)
    
    # Orphans: s2 (multiply)
    orphans = [n["id"] for n in result["orphaned_functions"]]
    assert "src_s2" in orphans
    assert "src_s1" not in orphans
    
    # God tests: t2 (test_god) has 6 calls
    gods = [n["id"] for n in result["god_tests"]]
    assert "test_t2" in gods
    assert "test_t1" not in gods
    
    # Test to Source Map
    assert "test_add" in result["test_to_source_map"]
    assert "add()" in result["test_to_source_map"]["test_add"]
