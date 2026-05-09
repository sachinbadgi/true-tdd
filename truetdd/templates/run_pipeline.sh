#!/usr/bin/env bash
# ============================================================
# truetdd full pipeline — Calculator project
#
# Usage:  cd /path/to/calculator && bash run_pipeline.sh
#
# Outputs:
#   reliability_report.md  — full report with phase progression
#   summary.json           — structured JSON
#   phases.json            — per-phase metrics for the report
# ============================================================
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
PY="$VENV_PYTHON"

if [[ ! -x "$PY" ]]; then
  echo "❌  No .venv — create one:"
  echo "    /path/to/python3.11 -m venv .venv && .venv/bin/pip install /path/to/truetdd"
  exit 1
fi

echo "✅  Python : $($PY --version)"
echo "✅  Project: $SCRIPT_DIR"
cd "$SCRIPT_DIR"

# sitecustomize.py patches multiprocessing.set_start_method → idempotent
export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"

# ── 0. Clean ──────────────────────────────────────────────────
echo ""
echo "=== 0. Cleaning ==="
find . -path ./.venv -prune -o -type d -name __pycache__ -print | xargs rm -rf 2>/dev/null || true
rm -f coverage.json traceability_store.json mutation_results.json \
      loop_feedback.json reliability_report.md summary.json phases.json pytest_results.json
echo "[]" > phases.json

# ── Helper: add a phase snapshot via Python ───────────────────
add_phase() {
  local name="$1"
  "$PY" - "$name" <<'PYEOF'
import json, pathlib, sys

name = sys.argv[1]

# Read coverage
line_pct = None
cov_path = pathlib.Path("coverage.json")
if cov_path.exists():
    t = json.loads(cov_path.read_text()).get("totals", {})
    covered = t.get("covered_lines", 0)
    total = covered + t.get("missing_lines", 0)
    line_pct = round(100 * covered / total, 1) if total else None

# Read test count
tests_passing = None
pr_path = pathlib.Path("pytest_results.json")
if pr_path.exists():
    tests_passing = json.loads(pr_path.read_text()).get("passed")

# Read mutation results
survivors = None
mut_path = pathlib.Path("mutation_results.json")
if mut_path.exists():
    survivors = json.loads(mut_path.read_text()).get("total_surviving_mutants")

# Read reliability from feedback
reliability_score = None
verified = weak = weak_data = untested = failing = 0
fb_path = pathlib.Path("loop_feedback.json")
if fb_path.exists():
    fb = json.loads(fb_path.read_text())
    reliability_score = fb.get("score")
    reqs = fb.get("requirements", {})
    for r in reqs.values():
        s = r.get("status", "UNTESTED")
        if s == "VERIFIED": verified += 1
        elif s == "WEAK": weak += 1
        elif s == "WEAK_DATA": weak_data += 1
        elif s == "FAILING": failing += 1
        else: untested += 1


phases_path = pathlib.Path("phases.json")
phases = json.loads(phases_path.read_text())
phases.append({
    "name": name,
    "line_pct": line_pct,
    "tests_passing": tests_passing,
    "survivors": survivors,
    "reliability_score": reliability_score,
    "verified": verified,
    "weak": weak,
    "weak_data": weak_data,
    "untested": untested,
    "failing": failing,
})
phases_path.write_text(json.dumps(phases, indent=2))
print(f"   📸 Phase snapshot: {name}")
PYEOF
}

# ── Run pytest and capture pass count ─────────────────────────
run_pytest() {
  local extra_args="$*"
  # Run pytest with JSON report for test counts
  "$PY" -m pytest \
    --cov=src \
    --cov-report=json:coverage.json \
    --cov-report=term-missing \
    -q $extra_args 2>&1 | tee /tmp/pytest_out.txt

  # Extract pass count from output
  "$PY" -c "
import re, json, pathlib
txt = open('/tmp/pytest_out.txt').read()
m = re.search(r'(\d+) passed', txt)
passed = int(m.group(1)) if m else None
pathlib.Path('pytest_results.json').write_text(json.dumps({'passed': passed}))
" 2>/dev/null || true
}

# ── 1. Baseline: pytest + coverage (no REQ tracking context) ─
echo ""
echo "=== 1. Baseline — plain pytest + coverage ==="
run_pytest --cov-context=test
add_phase "1. Baseline (pytest only)"

# ── 2. With requirement tagging ───────────────────────────────
echo ""
echo "=== 2. REQ-tagged + traceability ==="
# Re-run so traceability_store.json gets populated
run_pytest --cov-context=test
add_phase "2. REQ-tagged (traceability)"

# ── 2b. Graphify Delta Manager (Targeted Scoping) ────────────────
echo ""
echo "=== 2b. Graphify Delta Manager ==="
if command -v graphify &> /dev/null; then
  echo "Extracting AST and checking for file changes..."
  graphify update . >/dev/null 2>&1 || true
  "$PY" -m truetdd.delta_manager || true
else
  echo "⚠️ Graphify not found in PATH. Targeted mutations disabled."
fi

# ── 3. Mutation testing (mutmut) ────────────────────────────────
echo ""
echo "=== 3. Mutation testing ==="

if [[ -f truetdd_delta.txt ]]; then
  if [ -s truetdd_delta.txt ]; then
    DELTA_FILES=$(tr '\n' ' ' < truetdd_delta.txt)
    echo "⚡ Targeting mutations only on changed files: $DELTA_FILES"
    mutmut run --paths-to-mutate $DELTA_FILES > /dev/null 2>&1 || true
  else
    echo "⚡ No source files changed since last run. Skipping mutmut."
  fi
else
  echo "Running full mutation suite..."
  mutmut run > /dev/null 2>&1 || true
fi

echo "=== 3b. mutation_bridge (reading results) ==="
"$PY" -m truetdd.mutation_bridge \
  --cache .mutmut-cache \
  --meta-dir mutants \
  --coverage coverage.json \
  --store traceability_store.json \
  --output mutation_results.json \
  --testdata tests/testdata.yaml

add_phase "3. + Mutation testing"

# ── 4. truetdd-report ────────────────────────────────────────
echo ""
echo "=== 4. truetdd-report (reliability gate) ==="
"$PY" -m truetdd.report \
  --prd prd.md \
  --store traceability_store.json \
  --threshold 100 \
  --json-out loop_feedback.json || true

add_phase "4. + truetdd-report"

# ── 5. Final summary with phase progression ───────────────────
echo ""
echo "=== 5. truetdd-summary ==="
"$PY" -m truetdd.summary_report \
  --prd prd.md \
  --coverage coverage.json \
  --mutation mutation_results.json \
  --store traceability_store.json \
  --feedback loop_feedback.json \
  --phases phases.json \
  --project "Calculator" \
  --md-out reliability_report.md \
  --json-out summary.json || true

# ── 6. Graphify Knowledge Base Sync & Discovery ─────────────────
echo ""
echo "=== 6. Graphify Knowledge Base & Discovery ==="
if command -v graphify &> /dev/null; then
  echo "Updating structural graph..."
  graphify update . >/dev/null 2>&1 || true
  "$PY" -m truetdd.graph_sync || true
  "$PY" -m truetdd.correlator --prd prd.md || true
else
  echo "⚠️ Graphify not found in PATH. Skipping knowledge base sync."
fi

echo ""
echo "=================================================="
echo "📄  reliability_report.md"
echo "📊  summary.json"
echo "📸  phases.json"
echo "🧠  graphify-out/graph.json (Enriched)"
if [[ -f discovery_suggestions.json ]]; then
  echo "💡  discovery_suggestions.json (Shadow code found)"
fi
echo "=================================================="

