import json
import sqlite3
from pathlib import Path
from typing import List, Dict


def load_survivors_from_db(db_path: str) -> List[Dict]:
    """Read surviving mutants from mutmut's SQLite cache."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, filename, line_number FROM mutant WHERE status='survived'"
    ).fetchall()
    conn.close()
    return [{"mutant_id": r[0], "filename": r[1], "line": r[2]} for r in rows]


def build_weak_test_map(survivors: List[Dict], coverage: Dict) -> Dict:
    """
    For each survivor, find which test functions covered that line.
    A test covering a mutated line but not killing the mutant = weak test.
    """
    weak_map = {}
    for s in survivors:
        file_key = s["filename"].lstrip("./")
        contexts = (
            coverage.get("files", {})
            .get(file_key, {})
            .get("contexts", {})
            .get(str(s["line"]), [])
        )
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


def run(mutmut_db: str, coverage_json: str, store_path: str, output: str):
    survivors = load_survivors_from_db(mutmut_db)
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
    parser.add_argument("--mutmut-db", default=".mutmut-cache/cache")
    parser.add_argument("--coverage", default="coverage.json")
    parser.add_argument("--store", default="traceability_store.json")
    parser.add_argument("--output", default="mutation_results.json")
    args = parser.parse_args()
    run(args.mutmut_db, args.coverage, args.store, args.output)
