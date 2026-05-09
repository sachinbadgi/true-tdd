"""
truetdd/summary_report.py
--------------------------
Generates a deterministic, human-readable improvement report after a full
truetdd pipeline run.

Reads (all optional, degrades gracefully):
  - coverage.json            pytest-cov output  (line/branch/statement coverage)
  - mutation_results.json    mutation_bridge output (mutant counts)
  - traceability_store.json  conftest_plugin + mutation_bridge output
  - loop_feedback.json       truetdd-report --json-out output (scores per REQ)
  - prd.md                   requirements source (for descriptions)

Produces:
  - stdout: formatted report with metrics dashboard + per-REQ table
  - --md-out FILE: Markdown file (the artifact report)
  - --json-out FILE: machine-readable summary JSON

Usage:
  truetdd-summary \\
    --prd prd.md \\
    --coverage coverage.json \\
    --mutation mutation_results.json \\
    --store traceability_store.json \\
    --feedback loop_feedback.json \\
    --md-out reliability_report.md \\
    --json-out summary.json
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, TypeVar

import click

from truetdd import __version__ as _truetdd_version
from truetdd.prd_parser import parse_prd_file

# ---------------------------------------------------------------------------
# Loaders — each returns {} / [] on missing file, never raises
# ---------------------------------------------------------------------------

_T = TypeVar("_T")


def _load(path: str | None, default: _T) -> _T:
    if not path:
        return default
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text())  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError):
        return default


def load_coverage(path: Optional[str]) -> Dict:
    """Return parsed coverage.json, or empty dict."""
    return _load(path, {})


def load_mutation(path: Optional[str]) -> Dict:
    """Return parsed mutation_results.json, or empty dict."""
    return _load(path, {})


def load_store(path: Optional[str]) -> Dict:
    """Return parsed traceability_store.json, or {tests:{}}."""
    return _load(path, {"tests": {}})


def load_feedback(path: Optional[str]) -> Dict:
    """Return parsed loop_feedback.json (truetdd-report --json-out), or {}."""
    return _load(path, {})


# ---------------------------------------------------------------------------
# Coverage metrics extraction
# ---------------------------------------------------------------------------


def extract_coverage_metrics(cov: Dict) -> Dict:
    """Pull top-level and per-file coverage numbers from coverage.json."""
    if not cov:
        return {}

    totals = cov.get("totals", {})
    files = cov.get("files", {})

    # Per-file function → test mapping from dynamic contexts
    per_function = {}
    for filepath, fdata in files.items():
        for fn_name, fn_data in fdata.get("functions", {}).items():
            if not fn_name:
                continue
            # Collect which tests executed this function's lines
            executing_tests: set = set()
            for line_no in fn_data.get("executed_lines", []):
                ctx = fdata.get("contexts", {}).get(str(line_no), [])
                executing_tests.update(ctx)
            per_function[f"{filepath}::{fn_name}"] = {
                "stmts": fn_data["summary"]["num_statements"],
                "covered": fn_data["summary"]["covered_lines"],
                "pct": fn_data["summary"]["percent_covered"],
                "executed_by": sorted(executing_tests),
            }

    return {
        "line_pct": totals.get("percent_covered", 0.0),
        "covered_lines": totals.get("covered_lines", 0),
        "total_lines": totals.get("num_statements", 0),
        "missing_lines": totals.get("missing_lines", 0),
        "per_file": {
            fp: {
                "stmts": fd["summary"]["num_statements"],
                "covered": fd["summary"]["covered_lines"],
                "pct": fd["summary"]["percent_covered"],
                "missing": fd["summary"]["missing_lines"],
            }
            for fp, fd in files.items()
        },
        "per_function": per_function,
    }


# ---------------------------------------------------------------------------
# Mutation metrics extraction
# ---------------------------------------------------------------------------


def extract_mutation_metrics(mut: Dict) -> Dict:
    """Pull survivor counts from mutation_results.json."""
    if not mut:
        return {}
    survivors = mut.get("total_surviving_mutants", 0)
    weak_tests = mut.get("weak_tests", {})
    total_weak = len(weak_tests)
    return {
        "survivors": survivors,
        "weak_test_count": total_weak,
        "weak_tests": list(weak_tests.keys()),
    }


# ---------------------------------------------------------------------------
# Traceability store metrics
# ---------------------------------------------------------------------------


def extract_store_metrics(store: Dict) -> Dict:
    """Count tests, outcomes, testdata declarations from traceability_store."""
    tests = store.get("tests", {})
    total = len(tests)
    passed = sum(1 for t in tests.values() if t.get("outcome") == "passed")
    failed = sum(1 for t in tests.values() if t.get("outcome") != "passed")
    with_testdata = sum(1 for t in tests.values() if t.get("testdata"))
    weak = sum(1 for t in tests.values() if t.get("is_weak"))
    return {
        "total_tests": total,
        "passed": passed,
        "failed": failed,
        "with_testdata": with_testdata,
        "weak": weak,
    }


# ---------------------------------------------------------------------------
# Requirement status from loop_feedback.json
# ---------------------------------------------------------------------------


def extract_req_metrics(feedback: Dict, requirements: List[Dict]) -> Dict:
    """
    Extract requirements from loop_feedback.json (from truetdd-report --json-out).
    Falls back to PRD requirements if feedback is missing.
    """
    results = {}
    fb_reqs = feedback.get("requirements", {})

    if fb_reqs:
        for rid, fb in fb_reqs.items():
            results[rid] = {
                "description": fb.get("description", ""),
                "status": fb.get("status", "UNTESTED"),
                "tests": fb.get("tests", []),
                "covered_artifacts": fb.get("covered_artifacts", []),
            }
    else:
        for r in requirements:
            results[r["id"]] = {
                "description": r["description"],
                "status": "UNTESTED",
                "tests": [],
                "covered_artifacts": [],
            }

    return {
        "score": feedback.get("score", 0.0),
        "passed": feedback.get("passed", False),
        "threshold": feedback.get("threshold", 100.0),
        "requirements": results,
        "orphaned_functions": feedback.get("orphaned_functions", []),
        "god_tests": feedback.get("god_tests", []),
    }


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

STATUS_ICONS = {
    "VERIFIED": "✅",
    "WEAK": "⚠️ ",
    "WEAK_DATA": "📊",
    "FAILING": "🔴",
    "UNTESTED": "❌",
}

STATUS_ORDER = ["FAILING", "UNTESTED", "WEAK", "WEAK_DATA", "VERIFIED"]


def _bar(pct: float, width: int = 20) -> str:
    filled = int(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _score_color_label(score: float) -> str:
    if score >= 90:
        return "🟢 RELEASE-READY"
    elif score >= 75:
        return "🟡 REVIEW BEFORE RELEASE"
    elif score >= 60:
        return "🟠 SIGNIFICANT GAPS"
    else:
        return "🔴 BLOCKED"


def format_report(
    project: str,
    prd_path: str,
    cov_metrics: Dict,
    mut_metrics: Dict,
    store_metrics: Dict,
    req_metrics: Dict,
    run_date: str,
) -> str:
    """Render the full Markdown report."""
    score = req_metrics.get("score", 0.0)
    threshold = req_metrics.get("threshold", 100.0)
    gate = "✅ PASS" if req_metrics.get("passed") else f"❌ FAIL (threshold: {threshold}%)"

    reqs = req_metrics.get("requirements", {})
    verified = sum(1 for r in reqs.values() if r["status"] == "VERIFIED")
    weak = sum(1 for r in reqs.values() if r["status"] == "WEAK")
    weak_data = sum(1 for r in reqs.values() if r["status"] == "WEAK_DATA")
    failing = sum(1 for r in reqs.values() if r["status"] == "FAILING")
    untested = sum(1 for r in reqs.values() if r["status"] == "UNTESTED")
    total_reqs = len(reqs)
    orphaned = len(req_metrics.get("orphaned_functions", []))

    # Coverage vars
    if cov_metrics:
        cov_pct = f"{cov_metrics.get('line_pct', 0.0):>5.1f}%"
        cov_lines = f"{cov_metrics.get('covered_lines', 0):>4} / {cov_metrics.get('total_lines', 0):<4}"
        cov_miss = f"{cov_metrics.get('missing_lines', 0):>4}"
    else:
        cov_pct = "N/A"
        cov_lines = "N/A"
        cov_miss = "N/A"

    mut_surv = f"{mut_metrics.get('survivors', 0):>4}" if mut_metrics else "N/A"
    mut_weak = f"{mut_metrics.get('weak_test_count', 0):>4}" if mut_metrics else "N/A"

    parts = [
        f"""# truetdd Reliability Report

**Project:** {project}
**PRD:** `{prd_path}`
**Generated:** {run_date}
**Framework:** truetdd v{_truetdd_version}

---

## Combined Metrics Dashboard

```
┌{"─" * 67}┐
│  METRIC                        VALUE          SOURCE             │
├{"─" * 67}┤
│  Tests passing                 {store_metrics.get("passed", 0):>4} / {store_metrics.get("total_tests", 0):<4}    pytest             │
│  Line coverage                 {cov_pct:<14} pytest-cov         │
│  Statements covered            {cov_lines:<14} coverage.json      │
│  Missing statements            {cov_miss:<14} coverage.json      │
├{"─" * 67}┤
│  Surviving mutants             {mut_surv:<14} mutmut             │
│  Weak tests (cover+no-kill)    {mut_weak:<14} mutation_bridge    │
├{"─" * 67}┤
│  Requirements tracked          {total_reqs:>4} / {total_reqs:<4}    prd.md + tags      │
│  Requirements VERIFIED         {verified:>4}            truetdd-report    │
│  Requirements WEAK             {weak:>4}            truetdd-report    │
│  Requirements WEAK_DATA        {weak_data:>4}            truetdd-report    │
│  Requirements FAILING          {failing:>4}            truetdd-report    │
│  Requirements UNTESTED         {untested:>4}            truetdd-report    │
│  Orphaned functions            {orphaned:>4}            graphify graph     │
├{"─" * 67}┤
│  Tests with testdata.yaml      {store_metrics.get("with_testdata", 0):>4} / {store_metrics.get("total_tests", 0):<4}    testdata.yaml      │
├{"─" * 67}┤
│  Reliability Score             {score:>5.1f}%          truetdd-report    │
│  Gate result                   {gate:<30}│
└{"─" * 67}┘
```

---
"""
    ]

    if cov_metrics and cov_metrics.get("per_file"):
        cov_details = [f"""## Code Coverage Detail\n\n```\nName{" " * 32}Stmts   Miss  Cover\n{"─" * 55}"""]
        for fp, fd in cov_metrics["per_file"].items():
            name = fp if len(fp) <= 35 else "…" + fp[-34:]
            cov_details.append(f"{name:<36}{fd['stmts']:>5}  {fd['missing']:>5}  {fd['pct']:>5.0f}%")

        pct = cov_metrics.get("line_pct", 0.0)
        covered = cov_metrics.get("covered_lines", 0)
        total = cov_metrics.get("total_lines", 0)
        cov_details.append(f"{'─' * 55}\n{'TOTAL':<36}{total:>5}  {total - covered:>5}  {pct:>5.0f}%\n```\n")
        cov_details.append(
            "> **Coverage ≠ Reliability.** A test that executes a line but asserts only `result is not None` achieves 100% line coverage but will NOT kill arithmetic mutants. Only the reliability score measures assertion strength.\n\n---\n"
        )
        parts.append("\n".join(cov_details))

    bar = _bar(score)
    label = _score_color_label(score)
    parts.append(f"""## Reliability Score

```
  {bar}  {score:.1f}%
  {label}
```

{"=" * 70}
  Reliability Score: {score}% ({verified}/{total_reqs} VERIFIED)
{"=" * 70}

## Requirement Status
""")

    sorted_reqs = sorted(reqs.items(), key=lambda x: STATUS_ORDER.index(x[1]["status"]))
    for rid, data in sorted_reqs:
        status = data["status"]
        icon = STATUS_ICONS.get(status, "?")
        desc = data["description"]
        tests = data.get("tests", [])
        artifacts = data.get("covered_artifacts", [])

        req_part = [f"### {icon} {rid}: {status}\n**{desc}**  "]
        if tests:
            test_labels = ", ".join(f"`{t.split('::')[-1]}`" for t in tests)
            req_part.append(f"Tests: {test_labels}")
        if artifacts:
            artifact_labels = ", ".join(f"`{art}`" for art in artifacts)
            req_part.append(f"Artifacts: {artifact_labels}")

        if status == "WEAK":
            req_part.append(
                "> ⚠️ Assertion gap — mutants survived on covered lines. Strengthen assertions or add testdata.yaml boundary cases."
            )
        elif status == "WEAK_DATA":
            req_part.append(
                "> 📊 Data coverage gap — tests pass and no mutants survived, but no `testdata.yaml` cases declared. Declare boundary cases to confirm mutation-kill rate."
            )
        elif status == "FAILING":
            req_part.append("> 🔴 Test is failing — fix source code or test before proceeding.")
        elif status == "UNTESTED":
            req_part.append(
                f'> ❌ No test tagged to this requirement. Add `@pytest.mark.requirement("{rid}")` to a test.'
            )

        parts.append("\n".join(req_part) + "\n")

    orphaned_fns = req_metrics.get("orphaned_functions", [])
    if orphaned_fns:
        orph_part = [
            "---\n\n## Untraceable Code Artifacts\n\n> 👻 These functions exist in the call graph but no test structurally calls them via a traced requirement edge. They count against the reliability score.\n"
        ]
        for fn in orphaned_fns:
            orph_part.append(f"- 👻 `{fn}`")
        parts.append("\n".join(orph_part) + "\n")

    god_tests = req_metrics.get("god_tests", [])
    if god_tests:
        god_part = ["---\n\n## Structural Warnings\n"]
        for gt in god_tests:
            god_part.append(f"- ⚡ **God Test:** `{gt}` calls too many source functions — consider splitting.")
        parts.append("\n".join(god_part) + "\n")

    if mut_metrics and mut_metrics.get("weak_tests"):
        mut_part = [
            "---\n\n## Weak Tests (Mutation Survivors)\n\nThe following tests cover mutated lines but did not kill all mutants:\n"
        ]
        for t in mut_metrics["weak_tests"]:
            mut_part.append(f"- `{t.split('::')[-1]}` — add stronger assertions or `testdata.yaml` boundary cases")
        parts.append("\n".join(mut_part) + "\n")

    actions = []
    if failing > 0:
        actions.append(f"🔴 **Fix {failing} FAILING requirement(s)** — tests are broken, blocking all other work")
    if untested > 0:
        actions.append(f"❌ **Tag {untested} UNTESTED requirement(s)** — add `@pytest.mark.requirement` to tests")
    if weak > 0:
        actions.append(
            f"⚠️  **Strengthen {weak} WEAK requirement(s)** — mutants survived, add discriminating assertions"
        )
    if weak_data > 0:
        actions.append(f"📊 **Declare testdata.yaml for {weak_data} WEAK_DATA requirement(s)** — run `truetdd-inject`")
    if orphaned > 0:
        actions.append(
            f"👻 **Trace {orphaned} orphaned function(s)** — write tests that call them via tagged requirements"
        )
    if not actions:
        actions.append("✅ **All requirements VERIFIED** — safe to commit and release")

    act_part = ["---\n\n## Recommended Actions\n"]
    for i, act in enumerate(actions, 1):
        act_part.append(f"{i}. {act}")

    act_part.append(
        f"\n---\n\n*Generated by `truetdd-summary` — truetdd v{_truetdd_version}*  \n*Run `truetdd-report` for the live gate check.*"
    )
    parts.append("\n".join(act_part))

    return "\n".join(parts)


def format_json_summary(
    cov_metrics: Dict,
    mut_metrics: Dict,
    store_metrics: Dict,
    req_metrics: Dict,
    run_date: str,
) -> Dict:
    """Produce a machine-readable summary dict."""
    reqs = req_metrics.get("requirements", {})
    status_counts: Dict[str, int] = {}
    for r in reqs.values():
        s = r["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    return {
        "generated_at": run_date,
        "coverage": {
            "line_pct": cov_metrics.get("line_pct"),
            "covered_lines": cov_metrics.get("covered_lines"),
            "total_lines": cov_metrics.get("total_lines"),
            "missing_lines": cov_metrics.get("missing_lines"),
        }
        if cov_metrics
        else None,
        "mutation": {
            "survivors": mut_metrics.get("survivors"),
            "weak_test_count": mut_metrics.get("weak_test_count"),
        }
        if mut_metrics
        else None,
        "reliability": {
            "score": req_metrics.get("score"),
            "passed": req_metrics.get("passed"),
            "threshold": req_metrics.get("threshold"),
            "status_counts": status_counts,
            "orphaned_functions": req_metrics.get("orphaned_functions", []),
            "god_tests": req_metrics.get("god_tests", []),
        },
        "requirements": req_metrics.get("requirements", {}),
    }


# ---------------------------------------------------------------------------
# Phase progression (before → during → after)
# ---------------------------------------------------------------------------


def format_phase_progression(phases: List[Dict]) -> str:
    """Render a human-readable narrative progression across pipeline phases."""
    if not phases:
        return ""

    STAGE_META = {
        0: {
            "icon": "🔵",
            "what": "Plain pytest + line coverage",
            "reveals": "How many lines of code are executed by the tests.",
            "blind_spot": "Does NOT check whether assertions are correct or complete.",
        },
        1: {
            "icon": "🟡",
            "what": "Requirement traceability tags added",
            "reveals": "Which test validates which requirement from the PRD.",
            "blind_spot": "Still no check on assertion strength — just mapping.",
        },
        2: {
            "icon": "🟠",
            "what": "Mutation testing (mutmut)",
            "reveals": "Which test assertions are strong enough to catch logic bugs.",
            "blind_spot": "Surviving mutants = real gaps where wrong code would pass tests.",
        },
        3: {
            "icon": "🔴",
            "what": "Reliability gate (truetdd-report)",
            "reveals": "End-to-end requirement verification score against the PRD.",
            "blind_spot": "WEAK_DATA = tests pass but boundary cases aren't declared yet.",
        },
    }

    parts = [
        "## What truetdd Found — Stage by Stage\n",
        "> truetdd runs 4 cumulative stages. Each one reveals something the previous stage missed.",
        "> Line coverage stays 100% throughout — proving coverage alone is not enough.\n",
    ]

    for i, p in enumerate(phases):
        meta = STAGE_META.get(i, {})
        icon = meta.get("icon", "⚪")
        what = meta.get("what", p.get("name", ""))
        reveals = meta.get("reveals", "")
        blind = meta.get("blind_spot", "")

        cov = p.get("line_pct")
        tests = p.get("tests_passing")
        survivors = p.get("survivors")
        score = p.get("reliability_score")
        verified = p.get("verified", 0) or 0
        weak = (p.get("weak", 0) or 0) + (p.get("weak_data", 0) or 0)
        failing = p.get("failing", 0) or 0

        phase_part = [
            f"### {icon} Stage {i + 1}: {p.get('name', what)}\n**What this stage does:** {what}\n**What it reveals:** {reveals}\n"
        ]

        if tests is not None:
            phase_part.append(f"- ✅ {tests} tests passing")
        if cov is not None:
            phase_part.append(f"- 📊 {cov:.0f}% line coverage")
        if survivors is not None:
            if survivors == 0:
                phase_part.append("- 🎉 0 mutants survived")
            else:
                phase_part.append(f"- 🙁 {survivors} mutant(s) survived — tests missed logic changes")
        if score is not None:
            if score >= 100:
                phase_part.append(f"- ✅ Reliability: {score:.0f}% — all requirements VERIFIED")
            elif score > 0:
                phase_part.append(f"- ⚠️  Reliability: {score:.0f}% — partially verified")
            else:
                phase_part.append(f"- ❌ Reliability: {score:.0f}% — no requirements fully verified yet")
        if verified:
            phase_part.append(f"- ✅ {verified} requirement(s) VERIFIED")
        if weak:
            phase_part.append(f"- 📊 {weak} requirement(s) need boundary case declarations")
        if failing:
            phase_part.append(f"- ❌ {failing} requirement(s) FAILING")

        parts.append("\n".join(phase_part) + "\n")

        if blind and (survivors is not None or score is not None):
            parts.append(f"> ⚠️  **Gap found:** {blind}\n")

        parts.append("---\n")

    first = phases[0] if phases else {}
    last = phases[-1] if phases else {}
    f_cov = first.get("line_pct")
    l_score = last.get("reliability_score")
    l_survivors = last.get("survivors")

    summary_part = ["### 📋 What This Means\n"]
    if f_cov is not None:
        summary_part.append(
            f"- **Line coverage was {f_cov:.0f}% from the very start** — and stayed there. Coverage tells you code was *executed*, not that it was *correctly tested*."
        )
    if l_survivors is not None and l_survivors > 0:
        summary_part.append(
            f"- **{l_survivors} mutant(s) survived** — logic changes that no test caught. These are real test gaps, not false positives."
        )
    if l_score is not None and l_score < 100:
        req_gap = (last.get("weak", 0) or 0) + (last.get("weak_data", 0) or 0)
        summary_part.append(
            f"- **Reliability is {l_score:.0f}%** because {req_gap} requirement(s) lack boundary case declarations in `testdata.yaml`. Run `truetdd-inject` to fix this."
        )
    elif l_score is not None and l_score >= 100:
        summary_part.append("- **Reliability is 100%** — all requirements are verified with strong assertions.")

    parts.append("\n".join(summary_part) + "\n")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option("--prd", required=True, help="Path to Markdown PRD file")
@click.option("--coverage", "coverage_path", default=None, help="Path to coverage.json (pytest-cov output)")
@click.option("--mutation", "mutation_path", default=None, help="Path to mutation_results.json")
@click.option("--store", "store_path", default="traceability_store.json", help="Path to traceability_store.json")
@click.option(
    "--feedback", "feedback_path", default=None, help="Path to loop_feedback.json (truetdd-report --json-out)"
)
@click.option(
    "--phases", "phases_path", default=None, help="Path to phases.json with per-phase snapshots for progression table"
)
@click.option("--project", default=".", help="Project name or path label for the report header")
@click.option("--md-out", "md_out", default=None, help="Write Markdown report to this file")
@click.option("--json-out", "json_out", default=None, help="Write JSON summary to this file")
def cli(prd, coverage_path, mutation_path, store_path, feedback_path, phases_path, project, md_out, json_out):
    """Generate a deterministic reliability improvement report from truetdd artifacts."""
    run_date = datetime.now().strftime("%Y-%m-%d %H:%M")

    requirements = parse_prd_file(prd)
    cov = load_coverage(coverage_path)
    mut = load_mutation(mutation_path)
    store = load_store(store_path)
    feedback = load_feedback(feedback_path)
    phases = _load(phases_path, [])

    cov_metrics = extract_coverage_metrics(cov)
    mut_metrics = extract_mutation_metrics(mut)
    store_metrics = extract_store_metrics(store)
    req_metrics = extract_req_metrics(feedback, requirements)

    project_label = project if project != "." else Path(prd).parent.name or "project"
    report_md = format_report(
        project=project_label,
        prd_path=prd,
        cov_metrics=cov_metrics,
        mut_metrics=mut_metrics,
        store_metrics=store_metrics,
        req_metrics=req_metrics,
        run_date=run_date,
    )

    if phases:
        progression = format_phase_progression(phases)
        report_md = report_md.replace(
            "\n---\n\n## Combined Metrics",
            f"\n---\n\n{progression}\n---\n\n## Combined Metrics",
            1,
        )

    print(report_md)

    if md_out:
        Path(md_out).write_text(report_md)
        print(f"\n📄 Markdown report written to {md_out}", file=sys.stderr)

    if json_out:
        summary = format_json_summary(cov_metrics, mut_metrics, store_metrics, req_metrics, run_date)
        if phases:
            summary["phases"] = phases
        Path(json_out).write_text(json.dumps(summary, indent=2))
        print(f"📊 JSON summary written to {json_out}", file=sys.stderr)

    if not req_metrics.get("passed", True) and feedback_path:
        sys.exit(1)


if __name__ == "__main__":
    cli()
