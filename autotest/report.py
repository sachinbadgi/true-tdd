import json
import sys
import click
from pathlib import Path
from typing import List, Dict
from autotest.prd_parser import parse_prd_file


def compute_reliability(requirements: List[Dict], store: Dict) -> Dict:
    tests = store.get("tests", {})
    req_to_tests = {r["id"]: [] for r in requirements}
    for test_id, data in tests.items():
        for rid in data.get("requirement_ids", []):
            if rid in req_to_tests:
                req_to_tests[rid].append(data)

    results = {}
    for req in requirements:
        rid = req["id"]
        mapped = req_to_tests.get(rid, [])
        if not mapped:
            status = "UNTESTED"
        elif any(d["outcome"] != "passed" for d in mapped):
            status = "FAILING"
        elif any(d.get("is_weak") for d in mapped):
            status = "WEAK"
        else:
            status = "VERIFIED"
        results[rid] = {
            "status": status,
            "description": req["description"],
            "test_count": len(mapped),
        }
    return results


@click.command()
@click.option("--prd", required=True, help="Path to Markdown PRD file")
@click.option(
    "--store", default="traceability_store.json", help="Path to traceability store"
)
@click.option("--threshold", default=90.0, help="Minimum reliability % to pass")
def cli(prd, store, threshold):
    requirements = parse_prd_file(prd)
    store_data = (
        json.loads(Path(store).read_text())
        if Path(store).exists()
        else {"tests": {}}
    )
    results = compute_reliability(requirements, store_data)

    total = len(results)
    verified = sum(1 for r in results.values() if r["status"] == "VERIFIED")
    score = round(verified / total * 100, 1) if total else 0

    icons = {"VERIFIED": "✅", "WEAK": "⚠️", "FAILING": "🔴", "UNTESTED": "❌"}
    print(f"\n{'='*60}")
    print(f"  Reliability Score: {score}% ({verified}/{total} VERIFIED)")
    print(f"{'='*60}")
    for rid, data in results.items():
        if data["status"] != "VERIFIED":
            print(f"  {icons[data['status']]} {rid}: {data['status']} — {data['description']}")
    print()

    if score < threshold:
        print(f"FAIL: score {score}% is below threshold {threshold}%")
        sys.exit(1)


if __name__ == "__main__":
    cli()
