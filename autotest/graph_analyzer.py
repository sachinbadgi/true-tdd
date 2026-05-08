import json
from pathlib import Path
from typing import Dict, List, Set, Tuple

def load_graph(graph_path: str) -> dict:
    p = Path(graph_path)
    if not p.exists():
        return {"nodes": [], "links": []}
    with open(p) as f:
        return json.load(f)

def _clean_label(label: str) -> str:
    return label.replace("()", "").lower()

def analyze_traceability(graph_data: dict, source_dir: str = "src", test_dir: str = "test") -> dict:
    """
    Parses graph.json to establish structural traceability:
    1. Which test nodes call which source nodes.
    2. Which source nodes are orphaned (0 incoming calls from tests).
    3. Which test nodes are 'God Tests' (calls > 5 source nodes).
    """
    nodes_by_id = {n["id"]: n for n in graph_data.get("nodes", [])}
    links = graph_data.get("links", [])
    
    # Identify test nodes and source nodes
    test_nodes = {}
    source_nodes = {}
    
    for node_id, node in nodes_by_id.items():
        if node.get("file_type") != "code":
            continue
            
        file_path = node.get("source_file", "")
        # Ignore mutmut generated folders and pycache
        if "mutants/" in file_path or "__pycache__" in file_path:
            continue
            
        if "test" in file_path or "tests/" in file_path:
            test_nodes[node_id] = node
        elif source_dir in file_path:
            # Skip module-level structural nodes that aren't specific functions
            if node.get("label", "").endswith(".py"):
                continue
            source_nodes[node_id] = node
            
    # Map edges: source_id -> target_id for 'calls'
    test_to_source_calls = {tid: set() for tid in test_nodes}
    source_to_test_callers = {sid: set() for sid in source_nodes}
    
    for link in links:
        if link.get("relation") == "calls":
            src = link["source"]
            tgt = link["target"]
            
            # If a test node calls a source node
            if src in test_nodes and tgt in source_nodes:
                test_to_source_calls[src].add(tgt)
                source_to_test_callers[tgt].add(src)
                
    # Fallback heuristic: If graphify missed implicit import calls, infer them by name conventions
    for tid, tnode in test_nodes.items():
        t_label = _clean_label(tnode.get("norm_label", tnode.get("label", "")))
        if not t_label.startswith("test_"):
            continue
        
        for sid, snode in source_nodes.items():
            s_label = _clean_label(snode.get("norm_label", snode.get("label", "")))
            # e.g., if "test_add_positive" contains "add"
            # We want to make sure it's an exact word match to avoid false positives
            parts = t_label.split("_")
            if s_label in parts:
                test_to_source_calls[tid].add(sid)
                source_to_test_callers[sid].add(tid)
                
    # 1. Orphaned Functions (Code Artifacts with no incoming test calls)
    orphaned_functions = []
    for sid, callers in source_to_test_callers.items():
        if len(callers) == 0:
            orphaned_functions.append(nodes_by_id[sid])
            
    # 2. God Tests (Tests calling many distinct source functions)
    god_tests = []
    for tid, callees in test_to_source_calls.items():
        if len(callees) > 5:
            god_tests.append(nodes_by_id[tid])
            
    # 3. Mappings for the 3-tier matrix
    test_to_source_map = {}
    for tid, callees in test_to_source_calls.items():
        node_label = test_nodes[tid].get("norm_label", test_nodes[tid].get("label", tid))
        clean_label = node_label.replace("()", "")
        test_to_source_map[clean_label] = [
            nodes_by_id[c].get("norm_label", nodes_by_id[c].get("label", c)) 
            for c in callees
        ]
        
    return {
        "orphaned_functions": orphaned_functions,
        "god_tests": god_tests,
        "test_to_source_map": test_to_source_map,
        "source_to_test_callers": source_to_test_callers
    }
