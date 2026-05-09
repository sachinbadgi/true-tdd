"""
Graphify Observer Sync Module
Injects deterministic True TDD metrics (surviving mutants, WEAK/VERIFIED statuses)
into the Graphify knowledge graph so the full agentic loop sees enriched nodes.

Strategy:
  - Always READ from the canonical graph.json (never from a previous enriched copy).
    This ensures running graph_sync twice is safe — it never double-enriches.
  - The ``_truetdd_enriched`` sentinel key prevents double-enrichment: if graph.json
    was already enriched (e.g. ``graphify update`` was not re-run), sync_graph skips
    and exits with a warning.
  - Write enriched output to BOTH:
      1. graph_enriched.json  — truetdd-owned backup; useful for debugging
      2. graph.json           — so Graphify tooling, the LLM, and correlator.py
                                all read enriched nodes without extra indirection.

Pipeline order: `graphify update` → `truetdd-sync` (graphify always runs first).
"""

import json
import sys
from pathlib import Path

import click

CANONICAL_GRAPH = Path("graphify-out/graph.json")
ENRICHED_GRAPH = Path("graphify-out/graph_enriched.json")


def sync_graph(graph_path: str | None = None) -> None:
    """Inject truetdd reliability metrics into the Graphify knowledge graph.

    Reads mutation_results.json and loop_feedback.json and fuses the data into
    graph.json (in-place) so the LLM loop and correlator always see enriched nodes.

    Args:
        graph_path: Override the default graph.json path (injectable for testing).
    """
    canonical = Path(graph_path) if graph_path else CANONICAL_GRAPH
    enriched = canonical.parent / "graph_enriched.json"

    if not canonical.exists():
        print("⚠️  No graph.json found — run graphify update first.", file=sys.stderr)
        return

    graph = json.loads(canonical.read_text())

    # Guard: skip if already enriched by a previous truetdd-sync call without
    # an intervening `graphify update` (which would reset the sentinel).
    if graph.get("_truetdd_enriched"):
        print(
            "⚠️  graph.json already contains truetdd enrichments. "
            "Run `graphify update` first to reset the canonical graph before re-enriching.",
            file=sys.stderr,
        )
        return

    # 1. Inject Surviving Mutants per file
    mut_path = Path("mutation_results.json")
    if mut_path.exists():
        muts = json.loads(mut_path.read_text())
        file_counts = muts.get("surviving_mutants_by_file", {})
        for node in graph.get("nodes", []):
            sf = node.get("source_file")
            if sf in file_counts:
                node["surviving_mutants"] = file_counts[sf]

    # 2. Inject Reliability Statuses onto Test Nodes
    fb_path = Path("loop_feedback.json")
    store_path = Path("traceability_store.json")

    if fb_path.exists() and store_path.exists():
        fb = json.loads(fb_path.read_text())
        store = json.loads(store_path.read_text())

        req_statuses = {r: data.get("status") for r, data in fb.get("requirements", {}).items()}

        # Build mapping: test_nodeid -> status (first requirement wins)
        test_statuses: dict = {}
        for test_id, data in store.get("tests", {}).items():
            reqs = data.get("requirement_ids", [])
            if reqs and reqs[0] in req_statuses:
                test_statuses[test_id] = req_statuses[reqs[0]]

        for node in graph.get("nodes", []):
            if node.get("file_type") == "code":
                label = node.get("label", "").replace("()", "")
                sf = node.get("source_file", "")
                test_id = f"{sf}::{label}"
                if test_id in test_statuses:
                    node["truetdd_req_status"] = test_statuses[test_id]

    # Mark as enriched so a second call is detectable and safe
    graph["_truetdd_enriched"] = True
    enriched_json = json.dumps(graph, indent=2)

    # Write backup copy for debugging / idempotency checks
    enriched.parent.mkdir(parents=True, exist_ok=True)
    enriched.write_text(enriched_json)

    # Also update graph.json so all Graphify tooling reads enriched nodes.
    # graphify update will regenerate graph.json from source — truetdd-sync must
    # run AFTER graphify update each cycle to re-apply enrichments.
    canonical.write_text(enriched_json)

    print(
        f"✅ True TDD metrics fused into graph.json (backup: {enriched})",
        file=sys.stderr,
    )


@click.command()
@click.option(
    "--graph",
    "graph_path",
    default=None,
    help="Override path to graph.json (default: graphify-out/graph.json).",
)
def cli(graph_path: str | None) -> None:
    """Fuse truetdd reliability metrics into the Graphify knowledge graph."""
    sync_graph(graph_path=graph_path)


if __name__ == "__main__":
    cli()
