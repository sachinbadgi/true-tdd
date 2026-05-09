import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

import click

from truetdd.graph_analyzer import analyze_traceability, load_graph
from truetdd.prd_parser import parse_prd_file
from truetdd.testdata_suggester import suggest_testdata_for_weak_tests

logger = logging.getLogger(__name__)


def compute_reliability(requirements: List[Dict], store: Dict, graph_analysis: Optional[Dict] = None) -> Dict:
    tests = store.get("tests", {})
    req_to_tests: Dict[str, List[Dict]] = {r["id"]: [] for r in requirements}

    # 1. Map REQ -> Test
    for test_id, data in tests.items():
        for rid in data.get("requirement_ids", []):
            if rid in req_to_tests:
                # Store nodeid along with the data
                test_data = data.copy()
                test_data["nodeid"] = test_id
                req_to_tests[rid].append(test_data)

    results = {}
    test_to_source = graph_analysis.get("test_to_source_map", {}) if graph_analysis else {}

    # 2. Evaluate REQ status
    for req in requirements:
        rid = req["id"]
        mapped = req_to_tests.get(rid, [])

        covered_artifacts = (
            list({artifact for t in mapped for artifact in test_to_source.get(t["nodeid"].split("::")[-1], [])})
            if graph_analysis
            else []
        )

        if not mapped:
            status = "UNTESTED"
        elif any(d["outcome"] != "passed" for d in mapped):
            status = "FAILING"
        elif any(d.get("is_weak") for d in mapped):
            status = "WEAK"
        elif all(not d.get("testdata") for d in mapped):
            # All tests pass and no mutants survived, but none have testdata.yaml cases
            # declared — data coverage gap (not assertion gap)
            status = "WEAK_DATA"
        else:
            status = "VERIFIED"

        results[rid] = {
            "status": status,
            "description": req["description"],
            "test_count": len(mapped),
            "covered_artifacts": covered_artifacts,
            "tests": [t["nodeid"] for t in mapped],
        }
    return results


@click.command()
@click.option("--prd", required=True, help="Path to Markdown PRD file")
@click.option("--store", default="traceability_store.json", help="Path to traceability store")
@click.option("--graph", default=None, help="Path to Graphify graph.json for structural analysis")
@click.option("--threshold", default=90.0, help="Minimum reliability % to pass")
@click.option("--json-out", default=None, help="Path to output machine-readable validation matrix JSON")
@click.option(
    "--tests-dir",
    "tests_dir",
    default="tests",
    show_default=True,
    help="Path to the test directory (used for testdata stub generation)",
)
def cli(prd, store, graph, threshold, json_out, tests_dir):
    requirements = parse_prd_file(prd)
    store_data = json.loads(Path(store).read_text()) if Path(store).exists() else {"tests": {}}

    graph_analysis = None
    if graph and Path(graph).exists():
        graph_data = load_graph(graph)
        graph_analysis = analyze_traceability(graph_data)

    results = compute_reliability(requirements, store_data, graph_analysis)

    orphaned_funcs = graph_analysis.get("orphaned_functions", []) if graph_analysis else []
    god_tests = graph_analysis.get("god_tests", []) if graph_analysis else []

    # Reliability score denominator includes orphaned functions (untraceable code penalty)
    total_items = len(results) + len(orphaned_funcs)
    verified_reqs = sum(1 for r in results.values() if r["status"] == "VERIFIED")

    score = round(verified_reqs / total_items * 100, 1) if total_items else 0

    icons = {
        "VERIFIED": "✅",
        "WEAK": "⚠️",
        "WEAK_DATA": "📊",
        "FAILING": "🔴",
        "UNTESTED": "❌",
        "UNTRACEABLE": "👻",
        "GOD_TEST": "⚡",
    }
    print(f"\n{'=' * 70}")
    print(f"  Reliability Score: {score}% ({verified_reqs}/{total_items} items VERIFIED)")
    print(f"{'=' * 70}")

    # Print Requirements
    for rid, data in results.items():
        if data["status"] != "VERIFIED":
            print(f"  {icons[data['status']]} {rid}: {data['status']} — {data['description']}")
            if graph_analysis and data["status"] == "WEAK":
                print(
                    f"     └─ Semantic Gap: {', '.join(data['tests'])} tests are weak on {', '.join(data['covered_artifacts']) or 'unknown artifacts'}"
                )
            if data["status"] == "WEAK_DATA":
                print(f"     └─ Data Gap: no testdata.yaml cases declared for {', '.join(data['tests'])}")

    # Print Structural Gaps
    if graph_analysis:
        if orphaned_funcs:
            print("\n  Untraceable Code Artifacts (Penalty applied):")
            for fn in orphaned_funcs:
                print(f"  {icons['UNTRACEABLE']} {fn['label']} in {fn['source_file']}")

        if god_tests:
            print("\n  Structural Warnings:")
            for gt in god_tests:
                print(f"  {icons['GOD_TEST']} God Test Detected: {gt['label']} calls too many source functions.")

    print()

    if json_out:
        # Generate deterministic testdata stubs for WEAK_DATA requirements
        # so the LLM loop can fix them without reasoning — just fill ??? values
        weak_data = {rid: d for rid, d in results.items() if d["status"] == "WEAK_DATA"}
        suggested_testdata = {}
        if weak_data:
            try:
                suggested_testdata = suggest_testdata_for_weak_tests(weak_data, store_data, tests_dir=tests_dir)
            except Exception as e:
                logger.debug("testdata suggestion failed (best-effort, report unaffected): %s", e)

        out_payload = {
            "score": score,
            "threshold": threshold,
            "passed": score >= threshold,
            "requirements": results,
            "orphaned_functions": [fn["label"] for fn in orphaned_funcs],
            "god_tests": [gt["label"] for gt in god_tests],
            "suggested_testdata": suggested_testdata,
        }
        Path(json_out).write_text(json.dumps(out_payload, indent=2))
        print(f"Validation matrix written to {json_out}")

    if score < threshold:
        print(f"FAIL: score {score}% is below threshold {threshold}%")
        sys.exit(1)


if __name__ == "__main__":
    cli()
