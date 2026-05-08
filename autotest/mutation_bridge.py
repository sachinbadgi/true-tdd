import json
from pathlib import Path
from typing import List, Dict


def load_survivors_from_meta(meta_dir: str = "mutants") -> List[Dict]:
    """Read surviving mutants from mutmut 3.x .meta files."""
    survivors = []
    base_path = Path(meta_dir)
    
    if not base_path.exists():
        return survivors

    for meta_file in base_path.rglob("*.meta"):
        # The mutated filename can be derived from the meta file path
        # e.g. mutants/src/calculator.py.meta -> src/calculator.py
        rel_path = meta_file.relative_to(base_path)
        original_filename = str(rel_path)[:-5] # remove .meta

        with open(meta_file) as f:
            meta = json.load(f)
            
        exit_codes = meta.get("exit_code_by_key", {})
        for mutant_key, exit_code in exit_codes.items():
            # In mutmut 3, exit_code == 0 means the mutant SURVIVED (test passed)
            # exit_code > 0 (usually 1) means the mutant was KILLED (test failed)
            if exit_code == 0:
                survivors.append({
                    "mutant_id": mutant_key,
                    "filename": original_filename,
                    "line": 0 # Mutmut 3 abstracts away line numbers in meta files, so we map by file/function
                })
    return survivors


def build_weak_test_map(survivors: List[Dict], coverage: Dict) -> Dict:
    """
    For each survivor, find which test functions covered the mutated file.
    A test covering a mutated file but not killing the mutant = weak test.
    Note: Due to mutmut 3's AST-based approach, line numbers are abstracted,
    so we flag tests that cover the file containing the survivor.
    """
    weak_map = {}
    
    # Pre-compute which tests touch which files
    tests_by_file = {}
    for file_key, file_data in coverage.get("files", {}).items():
        tests_touching_file = set()
        for contexts in file_data.get("contexts", {}).values():
            tests_touching_file.update(contexts)
        tests_by_file[file_key] = tests_touching_file

    for s in survivors:
        file_key = s["filename"].lstrip("./")
        contexts = tests_by_file.get(file_key, [])
        
        for test_name in contexts:
            if test_name not in weak_map:
                weak_map[test_name] = {"surviving_mutants": 0, "mutant_ids": []}
            weak_map[test_name]["surviving_mutants"] += 1
            weak_map[test_name]["mutant_ids"].append(s["mutant_id"])
            
    return weak_map


def merge_into_traceability(
    scores: Dict, store_path: str = "traceability_store.json"
):
    """Merge weak test metadata back into the main traceability store."""
    p = Path(store_path)
    store = json.loads(p.read_text())
    for test_name, data in scores.items():
        if test_name in store["tests"]:
            store["tests"][test_name]["surviving_mutants_count"] = data[
                "surviving_mutants_count"
            ]
            store["tests"][test_name]["is_weak"] = data["is_weak"]
    p.write_text(json.dumps(store, indent=2))


def run(meta_dir: str, coverage_json: str, store_path: str, output: str):
    survivors = load_survivors_from_meta(meta_dir)
    with open(coverage_json) as f:
        coverage = json.load(f)
        
    weak_map = build_weak_test_map(survivors, coverage)
    scores = {
        k: {
            "surviving_mutants_count": v["surviving_mutants"],
            "is_weak": v["surviving_mutants"] > 0,
        }
        for k, v in weak_map.items()
    }
    merge_into_traceability(scores, store_path)
    result = {"total_surviving_mutants": len(survivors), "weak_tests": scores}
    
    with open(output, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Survivors: {len(survivors)} | Weak tests: {len(scores)}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--meta-dir", default="mutants", help="Directory containing mutmut 3 .meta files")
    parser.add_argument("--coverage", default="coverage.json")
    parser.add_argument("--store", default="traceability_store.json")
    parser.add_argument("--output", default="mutation_results.json")
    args = parser.parse_args()
    run(args.meta_dir, args.coverage, args.store, args.output)
