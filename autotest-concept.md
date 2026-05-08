# Python Reliability Shield — Concept & Build Plan

A developer-facing test quality framework that maps domain rules to executable
code and validates them using semantic tracing, fuzz testing, and mutation testing.

**Audience:** developers. **Mode:** fast feedback during development.  
**Based on:** existing infrastructure in `astroq-v2/backend`.

---

## Tech Stack

| Role | Tool | Status |
|---|---|---|
| Rule extraction | `RuleExtractor` (AST parser on `lk_pattern_constants.py`) | ✅ Built |
| Semantic tracing | `GraphTracer` (thread-local context manager) | ✅ Built |
| Graph indexing | `GraphIndex` (loads Graphify's local `graph.json`) | ✅ Built |
| Synthetic fuzzing | `ConstraintAwareFuzzer` (mocked chart data) | ✅ Built |
| Physical fuzzing | `PhysicalChartFuzzer` (real ephemeris charts) | ✅ Built |
| Coverage analysis | `CoverageAnalyzer` (JSON report, per-domain stats) | ✅ Built |
| Forensic audit | `SystemAuditOrchestrator` (public figures SQLite DB) | ✅ Built |
| Persistence | SQLite (`.mutmut-cache`, `public_figures.db`, `config.db`) | ✅ In use |
| Mutation engine | `mutmut` | 🔲 Not yet wired |
| REQ-ID tagging | `pytest.mark.requirement` on existing test suite | 🔲 Not yet applied |
| Code coverage bridge | `coverage.py` with `--cov-context=test` | 🔲 Not yet wired |
| Reliability report | `reliability_report.py` (unified CLI output) | 🔲 Not yet built |

**No Neo4j.** Graphify's output is a local `graph.json` file queried via
`GraphIndex` (Python dict lookup). All persistence is SQLite or JSON on disk.

---

## 1. What Already Exists

### 1.1 Semantic Rule Coverage (the core loop)

The following pipeline is **already implemented and running**:

```
lk_pattern_constants.py
       │
       ▼
  RuleExtractor          ← AST-parses VARSHPHAL_TIMING_TRIGGERS + EVENT_DOMAIN_CATALOGUE
       │ produces coverage_map.json (89 ExtractedRules)
       ▼
  ConstraintAwareFuzzer  ← generates synthetic ChartData satisfying each rule's constraints
       │ or
  PhysicalChartFuzzer    ← searches real ephemeris dates satisfying constraints
       │
       ▼
  VarshphalTimingEngine  ← executes with GraphTracer active as context manager
       │ emits trace_hit(node_id) calls
       ▼
  CoverageAnalyzer       ← logs rule_id → node_hit → domain stats
       │
       ▼
  latest_regression_report.md (89 rules, 79.78% coverage as of 2026-05-04)
```

**Current result:** 71/89 rules verified, 18 failing.

### 1.2 GraphTracer — the instrumentation layer

`astroq/lk_prediction/tracer.py` — thread-local context manager. Any engine
function decorated with `trace_hit(node_id)` registers a hit when a tracer is
active. This is the existing equivalent of a "semantic coverage marker".

```python
# Usage already in place:
from astroq.lk_prediction.tracer import trace_hit

def evaluate_varshphal_triggers(self, context, domain):
    trace_hit("lk_prediction_varshphal_timing_engine_...")  # already instrumented
    ...
```

### 1.3 SystemAuditOrchestrator — forensic audit against real people

`tests/graphify_test/system_orchestrator.py` runs two audits in one:

1. **Rule audit** — synthetic/physical fuzzing against all 89 extracted rules
2. **Forensic audit** — real public figures from `public_figures.db` (SQLite),
   checking if the engine correctly identifies life events at the right age

### 1.4 conftest.py — shared fixtures

`tests/lk_prediction/conftest.py` provides `SAMPLE_NATAL_CHART`,
`SAMPLE_ANNUAL_CHART`, and pytest fixtures for all lk_prediction tests.
No external services. Pure Python dicts.

---

## 2. What Still Needs Building

### 2.1 REQ-ID Tagging on Existing Tests

The existing ~60 pytest test files have no `@pytest.mark.requirement` tags.
Adding them creates the traceability link between tests and domain rules.

**Convention:** use rule IDs from `coverage_map.json` as the requirement IDs.

```python
# Before (existing)
def test_varshphal_marriage_saturn():
    ...

# After (tagged)
@pytest.mark.requirement("Annual Saturn in House 1")
@pytest.mark.requirement("Annual Venus or Mercury in 2 or 7")
def test_varshphal_marriage_saturn():
    ...
```

Register markers in `pyproject.toml` (or `setup.cfg` if used):

```toml
[tool.pytest.ini_options]
markers = [
    "requirement: rule_id this test validates",
]
```

**Note:** `rule_id` values come directly from `RuleExtractor` output in
`coverage_map.json`. The link is: `test → rule_id → node_id → engine function`.

### 2.2 Mutmut Wiring

Add `mutmut` to the development toolchain. It runs against `astroq/lk_prediction/`
and validates that the existing tests actually catch assertion failures.

**`mutmut_config.py`** (project root):

```python
# mutmut_config.py

def pre_mutation(context):
    """
    Verified context properties (mutmut ≥ 2.x):
      context.filename             — file being mutated
      context.current_source_line  — source line (string)
      context.skip                 — set True to skip this mutation
      context.config.test_command  — override test command per mutation

    NOT supported: custom mutation injection (next_mutation does not exist).
    Mutmut generates its own operator mutations; injection requires a fork.
    """
    # Skip low-value targets
    if any(skip in context.current_source_line for skip in [
        "logger.", "print(", "# pragma", "__repr__", "__str__"
    ]):
        context.skip = True
        return

    # Route engine mutations to their focused tests (speed optimisation)
    if "varshphal_timing_engine" in context.filename:
        context.config.test_command = (
            "pytest tests/lk_prediction/test_varshphal_timing.py "
            "tests/lk_prediction/test_advanced_grammar_fidelity.py -x"
        )
    elif "rules_engine" in context.filename:
        context.config.test_command = "pytest tests/lk_prediction/test_rules_engine.py -x"
    elif "strength_engine" in context.filename:
        context.config.test_command = "pytest tests/lk_prediction/test_strength_engine.py -x"
```

**Run sequence:**

```bash
# Step 1: generate per-test coverage data (also scopes mutation to covered lines)
pytest --cov=astroq --cov-context=test --cov-report=json

# Step 2: run mutmut (reads .coverage to skip uncovered lines)
mutmut run --paths-to-mutate astroq/lk_prediction/

# Step 3: view survivors
mutmut results
```

**CI trigger strategy:**

| Trigger | Scope | Rationale |
|---|---|---|
| PR push | Changed files only: `--paths-to-mutate $(git diff --name-only origin/main)` | Fast, targeted |
| Nightly | Full `astroq/lk_prediction/` | Ground-truth score |
| Pre-release | Full + reliability report | Release gate |

Do **not** run full mutmut as a pre-commit hook — too expensive.

### 2.3 Mutation Bridge — surviving mutants → weak tests

mutmut has no native kill matrix. Use `coverage.py` dynamic contexts as a proxy.

**`mutation_bridge.py`** (project root):

```python
"""
Joins mutmut's surviving mutants with coverage.py's per-test context data
to identify which tests are weak (cover a mutated line but don't kill the mutant).

Output: mutation_results.json — machine-readable, feeds reliability_report.py
"""
import sqlite3
import json
from pathlib import Path

def load_survivors():
    """Read surviving mutants from mutmut's SQLite cache."""
    cache = Path(".mutmut-cache") / "cache"
    if not cache.exists():
        return []
    conn = sqlite3.connect(cache)
    rows = conn.execute(
        "SELECT id, filename, line_number FROM mutant WHERE status='survived'"
    ).fetchall()
    conn.close()
    return [{"mutant_id": r[0], "filename": r[1], "line": r[2]} for r in rows]

def load_coverage_contexts():
    """Read per-test line coverage from coverage.json."""
    with open("coverage.json") as f:
        return json.load(f)

def build_weak_test_map(survivors, coverage):
    """
    For each survivor, find which test functions covered that line.
    A test covering a mutated line but not killing the mutant = weak test.
    """
    weak_map = {}  # test_name -> {"surviving_mutants": count, "mutant_ids": []}

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

def compute_mutation_scores(weak_map, coverage):
    """
    mutation_score per test = killed / total mutants on covered lines
    Approximation: assumes any line covered could be mutated.
    """
    results = {}
    for test_name, data in weak_map.items():
        surviving = data["surviving_mutants"]
        # Use surviving count as lower bound for "at risk" classification
        results[test_name] = {
            "surviving_mutants_count": surviving,
            "mutant_ids": data["mutant_ids"],
            # Score cannot be computed exactly without total killed count per test;
            # flag as weak if any survivors on covered lines
            "is_weak": surviving > 0,
        }
    return results

if __name__ == "__main__":
    survivors = load_survivors()
    coverage = load_coverage_contexts()
    weak_map = build_weak_test_map(survivors, coverage)
    scores = compute_mutation_scores(weak_map, coverage)

    output = {
        "total_surviving_mutants": len(survivors),
        "weak_tests_count": len(scores),
        "weak_tests": scores,
    }
    with open("mutation_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"Survivors: {len(survivors)}, Weak tests identified: {len(scores)}")
```

**Caveat:** `coverage line ≠ assertion`. A test covering a mutated line but
asserting only on unrelated output will still appear weak. Manual review of
survivors via `mutmut show <id>` is needed for confirmed kills.

### 2.4 Traceability Bridge — test results → JSON store

Rather than pushing to Neo4j, write a conftest plugin that appends test
results + requirement markers to a **local JSON file** after each run.
This file is the "traceability database" and can be queried in Python.

**`conftest_bridge.py`** — placed at project root as `conftest.py` or imported:

```python
# Add to tests/lk_prediction/conftest.py (or a root conftest.py)
import json
import os
import pytest
from pathlib import Path

TRACEABILITY_FILE = Path("traceability_store.json")

def _load_store():
    if TRACEABILITY_FILE.exists():
        with open(TRACEABILITY_FILE) as f:
            return json.load(f)
    return {"tests": {}}

def _save_store(store):
    with open(TRACEABILITY_FILE, "w") as f:
        json.dump(store, f, indent=2)

def pytest_runtest_logreport(report):
    if report.when != "call":
        return

    req_ids = [
        mark.args[0]
        for mark in report.item.iter_markers("requirement")
    ]
    if not req_ids:
        return  # only track tagged tests

    store = _load_store()
    store["tests"][report.nodeid] = {
        "outcome": report.outcome,      # "passed" / "failed" / "error"
        "duration": report.duration,
        "requirement_ids": req_ids,
        # mutation_score written later by mutation_bridge.py
        "surviving_mutants_count": 0,
        "mutation_score": None,
    }
    _save_store(store)
```

After `mutation_bridge.py` runs, merge its output into `traceability_store.json`:

```python
# In mutation_bridge.py, add at the end:
def merge_into_traceability(scores, traceability_path="traceability_store.json"):
    with open(traceability_path) as f:
        store = json.load(f)
    for test_name, data in scores.items():
        if test_name in store["tests"]:
            store["tests"][test_name]["surviving_mutants_count"] = data["surviving_mutants_count"]
            store["tests"][test_name]["is_weak"] = data["is_weak"]
    with open(traceability_path, "w") as f:
        json.dump(store, f, indent=2)
```

### 2.5 Coverage.py Role

Coverage.py serves two jobs:

1. **Mutation scope filter**: `mutate_only_covered_lines = true` in
   `pyproject.toml` ensures mutmut ignores dead code.

2. **Kill matrix proxy**: `--cov-context=test` records which test function
   ran each source line — the raw material for `mutation_bridge.py`.

```toml
# pyproject.toml additions
[tool.mutmut]
mutate_only_covered_lines = true

[tool.coverage.run]
dynamic_context = "test_function"
source = ["astroq"]
```

Coverage % alone is a secondary metric in the report. The real signal is:

| Coverage | Mutation score | Meaning |
|---|---|---|
| Low | Any | Code paths not exercised at all |
| High | Low | Tests exercise code but don't assert outcomes — worst case |
| High | High | Strong tests |

### 2.6 Reliability Report

Queries `traceability_store.json` + `coverage_map.json` + `mutation_results.json`
in pure Python. No external database.

**`reliability_report.py`**:

```python
"""
Reliability Report — pure Python, no external services.
Reads: traceability_store.json, coverage_map.json, mutation_results.json (optional)

Reliability Score = VERIFIED rules / total rules × 100

Rule status:
  VERIFIED  — ≥1 passing test tagged to this rule AND no surviving mutants on covered lines
  WEAK      — ≥1 passing test BUT surviving mutants detected
  FAILING   — ≥1 test tagged but outcome != "passed"
  UNTESTED  — no test tagged to this rule at all
"""
import json
from pathlib import Path

def load(path, default=None):
    p = Path(path)
    if not p.exists():
        return default if default is not None else {}
    with open(p) as f:
        return json.load(f)

def run_report():
    rules      = load("tests/graphify_test/coverage_map.json", default=[])
    store      = load("traceability_store.json", default={"tests": {}})
    mutations  = load("mutation_results.json", default={"weak_tests": {}})

    tests = store["tests"]
    weak_tests = mutations.get("weak_tests", {})

    # Build rule → test mapping
    rule_to_tests = {r["rule_id"]: [] for r in rules}
    for test_id, data in tests.items():
        for req_id in data.get("requirement_ids", []):
            if req_id in rule_to_tests:
                rule_to_tests[req_id].append((test_id, data))

    results = []
    for rule in rules:
        rid = rule["rule_id"]
        domain = rule.get("domain", "unknown")
        mapped = rule_to_tests.get(rid, [])

        if not mapped:
            status = "UNTESTED"
        elif any(d["outcome"] != "passed" for _, d in mapped):
            status = "FAILING"
        elif any(tid in weak_tests for tid, _ in mapped):
            status = "WEAK"
        else:
            status = "VERIFIED"

        results.append({
            "rule_id": rid,
            "domain": domain,
            "status": status,
            "test_count": len(mapped),
        })

    total     = len(results)
    verified  = sum(1 for r in results if r["status"] == "VERIFIED")
    weak      = sum(1 for r in results if r["status"] == "WEAK")
    failing   = sum(1 for r in results if r["status"] == "FAILING")
    untested  = sum(1 for r in results if r["status"] == "UNTESTED")
    score     = round(verified / total * 100, 1) if total else 0

    icons = {"VERIFIED": "✅", "WEAK": "⚠️", "FAILING": "🔴", "UNTESTED": "❌"}

    print(f"\n{'='*62}")
    print(f"  Reliability Score: {score}% ({verified}/{total} VERIFIED)")
    print(f"  Weak: {weak}  |  Failing: {failing}  |  Untested: {untested}")
    print(f"{'='*62}\n")

    # Group by domain
    by_domain = {}
    for r in results:
        by_domain.setdefault(r["domain"], []).append(r)

    for domain, domain_rules in sorted(by_domain.items()):
        v = sum(1 for r in domain_rules if r["status"] == "VERIFIED")
        t = len(domain_rules)
        print(f"  [{domain}] {v}/{t} verified")
        for r in domain_rules:
            if r["status"] != "VERIFIED":
                print(f"    {icons[r['status']]} {r['rule_id']}")

    print()

if __name__ == "__main__":
    run_report()
```

---

## 3. Reliability Score Definition

```
Rule status per rule_id:
  VERIFIED  — ≥1 test tagged, all passing, zero surviving mutants on covered lines
  WEAK      — ≥1 test tagged, passing, but ≥1 surviving mutant on covered lines
  FAILING   — ≥1 test tagged but test outcome is "failed" or "error"
  UNTESTED  — no test in the suite carries @pytest.mark.requirement("<rule_id>")

Reliability Score (%) = VERIFIED count / total rules × 100
```

**Release gate thresholds (suggested defaults):**

| Status | Green | Yellow | Red |
|---|---|---|---|
| Reliability Score | ≥ 90% | ≥ 75% | < 75% |
| UNTESTED rules | 0 | ≤ 5% | > 5% |
| FAILING rules | 0 | 0 | any |

---

## 4. Full Pipeline Execution Order

```bash
# 1. Extract rules from pattern constants
python -m tests.graphify_test.rule_extractor
#    → tests/graphify_test/coverage_map.json

# 2. Run semantic audit (existing, already working)
python tests/graphify_test/run_full_audit.py
#    → tests/graphify_test/full_audit_report.json
#    → tests/graphify_test/latest_regression_report.md

# 3. Run pytest with coverage + REQ-ID tracing
pytest --cov=astroq --cov-context=test --cov-report=json
#    → coverage.json, traceability_store.json

# 4. Run mutmut (scoped to changed files on PR, full on nightly)
mutmut run --paths-to-mutate astroq/lk_prediction/
#    → .mutmut-cache/cache (SQLite)

# 5. Bridge mutation results to traceability store
python mutation_bridge.py
#    → mutation_results.json, updates traceability_store.json

# 6. Generate reliability report
python reliability_report.py
```

---

## 5. Build Roadmap — Execution Order

| Step | Task | Status |
|---|---|---|
| ✅ | `RuleExtractor` + `coverage_map.json` (89 rules) | Done |
| ✅ | `GraphTracer` instrumented in engine | Done |
| ✅ | `ConstraintAwareFuzzer` + `PhysicalChartFuzzer` | Done |
| ✅ | `CoverageAnalyzer` + domain breakdown | Done |
| ✅ | `SystemAuditOrchestrator` (rule + forensic audit) | Done |
| ✅ | `conftest.py` fixtures (sample charts, model defaults) | Done |
| 🔲 | Add `@pytest.mark.requirement` tags to existing ~60 test files | Next |
| 🔲 | Add `conftest_bridge.py` to write `traceability_store.json` | Next |
| 🔲 | Wire `mutmut` + `mutmut_config.py` | Next |
| 🔲 | Write `mutation_bridge.py` | Next |
| 🔲 | Add `pyproject.toml` entries for mutmut + coverage | Next |
| 🔲 | Write `reliability_report.py` | Final |
| 🔲 | Define CI pipeline steps + release gate thresholds | Final |

---

## 6. Dependency List (additions only — existing venv already has pytest etc.)

```bash
pip install mutmut coverage pytest-cov
```

Everything else (`pytest`, `sqlalchemy`, `faker` equivalents) is already in
the project venv.

---

## 7. Comparison to Original Concept

| Original concept | Reality / Decision |
|---|---|
| Neo4j graph database | **Dropped** — `GraphIndex` reads Graphify's local `graph.json` |
| Cypher queries | **Replaced** — Python dict lookups + `reliability_report.py` |
| `conftest.py` → Neo4j driver | **Replaced** — writes to `traceability_store.json` (local file) |
| `graphify --neo4j-push` | **Already done** — `graphify-out/graph.json` exists |
| `context.next_mutation` | **Does not exist** — mutmut's hook is filter-only |
| "Data-Aware Mutations" via mutmut | **Separated** — `ConstraintAwareFuzzer` does data mutations; mutmut does code mutations |
| PRD headers as REQ-IDs | **Replaced** — rule IDs come from `RuleExtractor` parsing `lk_pattern_constants.py` |

---

## 8. Data-Aware Mutation Testing

Autotest is "data-aware": it can externalize and inject richer test data values during
mutmut runs to improve mutation kill rates, without permanently modifying test files.

**Design doc:** `docs/plans/2026-05-09-data-aware-design.md`

### 8.1 Implemented: Sidecar YAML + File Rewriter (C1 + Approach A)

A `testdata.yaml` sidecar file (co-located with tests) declares named case sets.
Before a mutmut run, `autotest-inject prepare` rewrites test files with
`@pytest.mark.parametrize` injected from the YAML, then restores originals after.

```
tests/
├── test_calculator.py       ← original (active during normal dev)
├── testdata.yaml            ← case sets declared here
└── .autotest_backup/        ← originals preserved during mutmut run
    └── test_calculator.py.bak
```

The sidecar is matched to tests by function name automatically, or explicitly via
`@pytest.mark.testdata("set_name")` on the test (C2 optional override). The marker
produces an `EXTRACTED` confidence edge in the Graphify graph — stronger than the
`INFERRED` proximity edge that would result from co-location alone.

**New reliability status:** `WEAK_DATA` — test passes but has no sidecar cases declared,
meaning it was only validated against the single hardcoded input. Data coverage gap.

**New files:**
- `autotest/data_injector.py` — rewriter + `autotest-inject` CLI
- `example/tests/testdata.yaml` — example sidecar demonstrating the schema

**Graphify traceability:** Graphify's semantic extractor reads `testdata.yaml` naturally.
Re-running `/graphify` after adding a sidecar adds testdata nodes and edges to the graph
with zero changes to Graphify itself.

### 8.2 Future Feature: Data Registry / Catalog (not yet built)

Declare test data sets in a **central registry file** rather than per-directory sidecars.
Cases would be keyed by requirement ID (`REQ-201`) rather than test function name,
enabling cross-test data sharing at the requirements level. autotest would generate or
parameterize pytest cases from the registry automatically during any pytest invocation,
not just mutmut runs.

### 8.3 Future Feature: Mutation-Aware Data Advisor (not yet built)

After a mutant survives, analyze *why* the test data was insufficient. The advisor would
compare the mutated operator (e.g. `+` → `-`) against the input values in the sidecar
to determine if any existing case would have exposed the fault. If not, it generates
targeted boundary values (zero, symmetric, identity, large magnitude) and appends them
to `testdata.yaml` as suggestions. Output: annotated YAML diff showing which cases to
add and which mutants they would kill.