"""
truetdd/correlator.py — Semantic Discovery Engine (v2)

Produces discovery_suggestions.json with THREE classes of signals
for the Superpowers LLM loop:

1. UNTESTED_REQ  — PRD requirement has no test at all
2. ORPHANED_FN   — source function exists but no test calls it
   (independent of PRD — the LLM decides if a PRD entry is needed)
3. WEAK_COVERAGE — requirement is WEAK/WEAK_DATA but graph shows
   the implementing function has reachable code paths not exercised

The LLM reads this file, reasons about semantic meaning, and acts:
  - Write TDD test for an ORPHANED_FN
  - Add a PRD entry for genuinely new behaviour
  - Strengthen a WEAK test by adding boundary cases for uncovered paths
"""

from __future__ import annotations

import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List

import click

from truetdd.prd_parser import parse_prd_file

# ── Semantic confidence thresholds ───────────────────────────────────────────

#: Minimum similarity score to suggest a source function as implementing an untested PRD requirement.
#: Set slightly higher than ORPHAN_MATCH_THRESHOLD because the signal is more actionable:
#: we are directly prescribing test authorship.
_UNTESTED_REQ_THRESHOLD: float = 0.35

#: Minimum similarity score to cross-correlate an orphaned function against a PRD requirement.
#: Looser than the untested-req threshold — the LLM makes the final semantic judgement.
_ORPHAN_MATCH_THRESHOLD: float = 0.3

#: Minimum similarity score to suggest a source function as implementing a WEAK/WEAK_DATA requirement.
_WEAK_COVERAGE_THRESHOLD: float = 0.3

# ── Graph helpers ─────────────────────────────────────────────────────────────


def _load_graph(path: str = "graphify-out/graph.json") -> dict:
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else {}


def _load_store(path: str = "traceability_store.json") -> dict:
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else {}


def _load_prd(prd_path: str) -> Dict[str, str]:
    p = Path(prd_path)
    if not p.exists():
        return {}
    return {r["id"]: r["description"] for r in parse_prd_file(prd_path)}


# ── Semantic scoring ─────────────────────────────────────────────────────────

_SYNONYMS = {
    "addition": "add",
    "sum": "add",
    "plus": "add",
    "subtraction": "subtract",
    "difference": "subtract",
    "minus": "subtract",
    "multiplication": "multiply",
    "product": "multiply",
    "times": "multiply",
    "division": "divide",
    "quotient": "divide",
    "exponent": "power",
    "exponentiation": "power",
    "raise": "power",
    "clamp": "constrain",
    "bound": "clamp",
    "limit": "clamp",
    "clip": "clamp",
    "constrain": "clamp",
}


def _tokenize(text: str) -> set:
    text = text.lower().replace("_", " ").replace("()", "")
    words = set(re.findall(r"\b[a-z]{3,}\b", text))
    return {_SYNONYMS.get(w, w) for w in words}


def _score(req_text: str, node_label: str) -> float:
    req_tok = _tokenize(req_text)
    node_tok = _tokenize(node_label)
    if not req_tok or not node_tok:
        return 0.0
    overlap = len(req_tok & node_tok)
    token_score = overlap / max(len(node_tok), 1)
    seq_score = SequenceMatcher(None, req_text.lower(), node_label.lower()).ratio()
    return round(max(token_score, seq_score), 3)


# ── Source node extraction ───────────────────────────────────────────────────


def _source_fn_nodes(graph: dict) -> List[dict]:
    """All function nodes in src/ files (not test files)."""
    nodes = []
    for node in graph.get("nodes", []):
        label = node.get("label", "")
        src = node.get("source_file", "")
        if "test_" not in label and "src/" in src and "()" in label:
            nodes.append(
                {
                    "id": node.get("id"),
                    "label": label,
                    "file": src,
                    "reliability_score": node.get("reliability_score"),
                    "surviving_mutants": node.get("surviving_mutants"),
                }
            )
    return nodes


def _tested_fn_names(store: dict) -> set:
    """
    Set of source function names that have at least one test calling them.
    Derived from the traceability store's covered artifacts or test call graph.
    """
    covered = set()
    for test_data in store.get("tests", {}).items():
        # test_data is (nodeid, data_dict)
        for artifact in test_data[1].get("covered_artifacts", []):
            covered.add(artifact.split(".")[-1])  # e.g. "calculator.add" → "add"
    return covered


def _reqs_with_tests(store: dict) -> set:
    """Set of req IDs that have at least one passing test."""
    tracked = set()
    for data in store.get("tests", {}).values():
        if data.get("outcome") == "passed":
            tracked.update(data.get("requirement_ids", []))
    return tracked


def _weak_reqs(loop_feedback_path: str = "loop_feedback.json") -> Dict[str, dict]:
    """Load WEAK and WEAK_DATA requirements from last pipeline run."""
    p = Path(loop_feedback_path)
    if not p.exists():
        return {}
    fb = json.loads(p.read_text())
    return {rid: d for rid, d in fb.get("requirements", {}).items() if d.get("status") in ("WEAK", "WEAK_DATA")}


# ── Three signal generators ──────────────────────────────────────────────────


def _find_untested_reqs(
    req_texts: Dict[str, str],
    tracked_reqs: set,
    source_nodes: List[dict],
) -> List[dict]:
    """Signal 1: PRD requirement with no test → find likely implementing function."""
    results = []
    untested = {rid: txt for rid, txt in req_texts.items() if rid not in tracked_reqs}
    for req_id, text in untested.items():
        matches = []
        for node in source_nodes:
            s = _score(text, node["label"])
            if s > _UNTESTED_REQ_THRESHOLD:
                matches.append({"fn": node["label"], "file": node["file"], "confidence": s})
        results.append(
            {
                "signal": "UNTESTED_REQ",
                "req_id": req_id,
                "req_text": text,
                "likely_implementations": sorted(matches, key=lambda x: -x["confidence"])[:3],
                "llm_action": (
                    f"Write a @pytest.mark.requirement('{req_id}') test that calls the "
                    f"most likely function. Add boundary cases to testdata.yaml."
                ),
            }
        )
    return results


def _find_orphaned_functions(
    source_nodes: List[dict],
    store: dict,
    req_texts: Dict[str, str],
) -> List[dict]:
    """
    Signal 2: Source function exists but has no test coverage.
    Even if it has a PRD requirement, if coverage.json shows 0 tests hitting it,
    it is 'functionally orphaned'.
    Cross-correlates with every PRD requirement to suggest the best match.
    """
    # Which function labels appear in coverage data?
    covered_fns = set()
    cov_path = Path("coverage.json")
    if cov_path.exists():
        cov = json.loads(cov_path.read_text())
        for fname, fdata in cov.get("files", {}).items():
            # covered functions: executed_lines > 0 in this file
            if fdata.get("summary", {}).get("covered_lines", 0) > 0:
                covered_fns.add(Path(fname).name)  # e.g. "calculator.py"

    # Also check traceability store for which functions have tests

    results = []
    for node in source_nodes:
        fn_name = node["label"].replace("()", "")
        src_file = Path(node["file"]).name

        # Heuristic: if the source file has 0 coverage, the function is orphaned
        file_covered = src_file in covered_fns

        # Check if fn_name appears in any test's covered artifacts
        fn_has_test = any(
            fn_name in test_data.get("covered_artifacts", []) or fn_name in test_data.get("requirement_ids", [])
            for test_data in store.get("tests", {}).values()
        )

        if not file_covered and not fn_has_test:
            # Correlate against all PRD requirements to find best match
            best_matches: List[Dict[str, Any]] = []
            for req_id, req_text in req_texts.items():
                s = _score(req_text, node["label"])
                if s > _ORPHAN_MATCH_THRESHOLD:
                    best_matches.append({"req_id": req_id, "req_text": req_text, "confidence": s})
            best_matches.sort(key=lambda x: x["confidence"], reverse=True)

            results.append(
                {
                    "signal": "ORPHANED_FN",
                    "fn": node["label"],
                    "file": node["file"],
                    "prd_candidates": best_matches[:3],
                    "llm_action": (
                        f"Function '{node['label']}' in {node['file']} has no test. "
                        f"Check if it maps to an existing PRD requirement (see prd_candidates). "
                        f"If yes, write a tagged test. If no, add a new PRD entry first."
                    ),
                }
            )
    return results


def _find_weak_coverage_gaps(
    weak_reqs: Dict[str, dict],
    source_nodes: List[dict],
    req_texts: Dict[str, str],
) -> List[dict]:
    """
    Signal 3: Requirements that are WEAK or WEAK_DATA.
    The graph shows which source functions are covered — report
    the implementing function and its mutation/reliability score
    so the LLM can decide if more boundary cases are needed.
    """
    results = []
    for req_id, req_data in weak_reqs.items():
        req_text = req_texts.get(req_id, "")
        # Find the source function most likely implementing this requirement
        matches = []
        for node in source_nodes:
            s = _score(req_text, node["label"])
            if s > _WEAK_COVERAGE_THRESHOLD:
                matches.append(
                    {
                        "fn": node["label"],
                        "file": node["file"],
                        "confidence": s,
                        "reliability_score": node.get("reliability_score"),
                        "surviving_mutants": node.get("surviving_mutants"),
                    }
                )
        matches.sort(key=lambda x: -x["confidence"])
        if matches:
            results.append(
                {
                    "signal": "WEAK_COVERAGE",
                    "req_id": req_id,
                    "status": req_data.get("status"),
                    "req_text": req_text,
                    "tests": req_data.get("tests", []),
                    "implementing_fns": matches[:2],
                    "llm_action": (
                        f"REQ {req_id} is {req_data.get('status')}. "
                        f"Add boundary cases to testdata.yaml for the implementing function. "
                        f"Focus on: zero inputs, negative inputs, boundary-touching values."
                    ),
                }
            )
    return results


# ── Main entry point ─────────────────────────────────────────────────────────


def generate_suggestions(
    prd_path: str,
    graph_path: str = "graphify-out/graph.json",
    store_path: str = "traceability_store.json",
    feedback_path: str = "loop_feedback.json",
    output_path: str = "discovery_suggestions.json",
) -> None:
    """Run all three signal generators and write discovery_suggestions.json.

    Args:
        prd_path: Path to the Markdown PRD file.
        graph_path: Path to graphify graph.json (injectable for testing).
        store_path: Path to traceability_store.json (injectable for testing).
        feedback_path: Path to loop_feedback.json (injectable for testing).
        output_path: Destination path for discovery_suggestions.json.
    """
    graph = _load_graph(graph_path)
    store = _load_store(store_path)
    req_texts = _load_prd(prd_path)
    weak_reqs = _weak_reqs(feedback_path)

    if not graph or not req_texts:
        print("Missing required artifacts for correlation.", file=sys.stderr)
        return

    source_nodes = _source_fn_nodes(graph)
    tracked_reqs = _reqs_with_tests(store)

    # Run all three signal generators
    untested_req_signals = _find_untested_reqs(req_texts, tracked_reqs, source_nodes)
    orphaned_fn_signals = _find_orphaned_functions(source_nodes, store, req_texts)
    weak_coverage_signals = _find_weak_coverage_gaps(weak_reqs, source_nodes, req_texts)

    all_signals = untested_req_signals + orphaned_fn_signals + weak_coverage_signals
    total = len(all_signals)

    # Score-sort so LLM sees highest-confidence items first
    def _signal_priority(s: dict) -> float:
        candidates = s.get("likely_implementations", []) or s.get("prd_candidates", []) or s.get("implementing_fns", [])
        return candidates[0]["confidence"] if candidates else 0.0

    all_signals.sort(key=_signal_priority, reverse=True)

    output = {
        "_summary": {
            "total_signals": total,
            "untested_reqs": len(untested_req_signals),
            "orphaned_fns": len(orphaned_fn_signals),
            "weak_coverage": len(weak_coverage_signals),
            "loop_complete": total == 0,
        },
        "signals": all_signals,
    }

    out_path = Path(output_path)
    out_path.write_text(json.dumps(output, indent=2))

    if total:
        print(
            f"💡 Discovery Engine found {total} signal(s): "
            f"{len(untested_req_signals)} untested reqs, "
            f"{len(orphaned_fn_signals)} orphaned functions, "
            f"{len(weak_coverage_signals)} weak coverage gaps.",
            file=sys.stderr,
        )
    else:
        print(
            "✅ Discovery Engine: No gaps found. Loop may terminate.",
            file=sys.stderr,
        )


@click.command()
@click.option("--prd", required=True, help="Path to Markdown PRD file")
@click.option("--graph", default="graphify-out/graph.json", show_default=True, help="Path to graphify graph.json")
@click.option("--store", default="traceability_store.json", show_default=True, help="Path to traceability_store.json")
@click.option("--feedback", default="loop_feedback.json", show_default=True, help="Path to loop_feedback.json")
@click.option("--output", default="discovery_suggestions.json", show_default=True, help="Output path for suggestions")
def cli(prd: str, graph: str, store: str, feedback: str, output: str) -> None:
    """Run the Discovery Engine and write discovery_suggestions.json."""
    generate_suggestions(prd, graph_path=graph, store_path=store, feedback_path=feedback, output_path=output)


if __name__ == "__main__":
    cli()
