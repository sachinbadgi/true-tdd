# Python Reliability Shield — Implementation Plan

> **For Antigravity:** REQUIRED SUB-SKILL: Load executing-plans to implement this plan task-by-task.

**Goal:** Build a standalone, reusable Python framework that maps PRD requirements to tests, runs mutation testing, and produces a reliability score — usable on any Python project.

**Architecture:** A pip-installable package (`autotest`) providing a pytest plugin, a CLI, and a set of scripts. It reads a Markdown PRD (REQ-ID tagged headers), traces which tests cover which requirements, pipes results through mutmut, and outputs a JSON-backed reliability report. No external services — everything is local files (JSON + SQLite).

**Tech Stack:** Python 3.10+, pytest, mutmut, coverage.py, pytest-cov, click (CLI)

---

## Project Layout Convention

```
/Users/sachinbadgi/Documents/autotest/
├── autotest/                  ← the library
│   ├── __init__.py
│   ├── prd_parser.py          ← extract REQ-IDs from Markdown
│   ├── conftest_plugin.py     ← pytest plugin: writes traceability_store.json
│   ├── mutation_bridge.py     ← joins mutmut survivors + coverage contexts
│   └── report.py              ← CLI: reliability_report
├── tests/
│   └── test_*.py
├── pyproject.toml
├── README.md
└── example/                   ← demo project to validate the framework end-to-end
    ├── prd.md
    ├── src/calculator.py
    └── tests/test_calculator.py
```

---

## Task 1: Project Scaffold + pyproject.toml

**Files:**
- Create: `autotest/__init__.py`
- Create: `pyproject.toml`

**Step 1: Write test that imports the package**

```python
# tests/test_import.py
def test_package_imports():
    import autotest
    assert autotest.__version__ == "0.1.0"
```

**Step 2: Run — verify it fails**

```bash
cd /Users/sachinbadgi/Documents/autotest
pytest tests/test_import.py -v
```
Expected: `ModuleNotFoundError: No module named 'autotest'`

**Step 3: Create scaffold**

```python
# autotest/__init__.py
__version__ = "0.1.0"
```

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "autotest"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["pytest", "coverage", "pytest-cov", "mutmut", "click"]

[tool.pytest.ini_options]
markers = ["requirement: REQ-ID this test validates"]

[tool.mutmut]
mutate_only_covered_lines = true

[tool.coverage.run]
dynamic_context = "test_function"
```

**Step 4: Install + run**

```bash
pip install -e .
pytest tests/test_import.py -v
```
Expected: `PASSED`

**Step 5: Commit**

```bash
git init
git add autotest/ tests/ pyproject.toml
git commit -m "feat: scaffold autotest package"
```

---

## Task 2: PRD Parser

**Files:**
- Create: `autotest/prd_parser.py`
- Test: `tests/test_prd_parser.py`

The parser reads a Markdown file and returns a list of `{"id": "REQ-101", "description": "..."}` dicts. Only headers matching `##+ REQ-\d+:` are extracted.

**Step 1: Write failing tests**

```python
# tests/test_prd_parser.py
import textwrap
from autotest.prd_parser import parse_requirements

PRD = textwrap.dedent("""
    # My Product

    ## REQ-101: User must register with a valid email
    Some body text.

    ### REQ-102: System rejects users under 18

    ## Not a requirement — no REQ prefix
""")

def test_extracts_req_ids():
    reqs = parse_requirements(PRD)
    ids = [r["id"] for r in reqs]
    assert "REQ-101" in ids
    assert "REQ-102" in ids

def test_excludes_non_tagged_headers():
    reqs = parse_requirements(PRD)
    ids = [r["id"] for r in reqs]
    assert len(ids) == 2

def test_captures_description():
    reqs = parse_requirements(PRD)
    r = next(r for r in reqs if r["id"] == "REQ-101")
    assert "valid email" in r["description"]

def test_empty_prd_returns_empty_list():
    assert parse_requirements("# Title\n\n## No requirements here") == []
```

**Step 2: Run — verify all fail**

```bash
pytest tests/test_prd_parser.py -v
```
Expected: 4 × `FAILED` with `ImportError`

**Step 3: Implement**

```python
# autotest/prd_parser.py
import re
from typing import List, Dict

REQ_PATTERN = re.compile(r'^#{1,6}\s+(REQ-\d+):\s*(.+)$', re.MULTILINE)

def parse_requirements(markdown: str) -> List[Dict[str, str]]:
    return [
        {"id": m.group(1), "description": m.group(2).strip()}
        for m in REQ_PATTERN.finditer(markdown)
    ]

def parse_prd_file(path: str) -> List[Dict[str, str]]:
    with open(path) as f:
        return parse_requirements(f.read())
```

**Step 4: Run — verify all pass**

```bash
pytest tests/test_prd_parser.py -v
```
Expected: 4 × `PASSED`

**Step 5: Commit**

```bash
git add autotest/prd_parser.py tests/test_prd_parser.py
git commit -m "feat: prd_parser extracts REQ-ID tagged headers from markdown"
```

---

## Task 3: Pytest Conftest Plugin (Traceability Writer)

**Files:**
- Create: `autotest/conftest_plugin.py`
- Test: `tests/test_conftest_plugin.py`

The plugin hooks into pytest's `pytest_runtest_logreport` and appends test results + requirement markers to `traceability_store.json` on disk.

**Step 1: Write failing tests**

```python
# tests/test_conftest_plugin.py
import json, pytest
from pathlib import Path
from unittest.mock import MagicMock
from autotest.conftest_plugin import TraceabilityPlugin

def _make_report(nodeid, outcome, req_ids, duration=0.1):
    report = MagicMock()
    report.when = "call"
    report.nodeid = nodeid
    report.outcome = outcome
    report.duration = duration
    marker_mocks = [MagicMock(args=(rid,)) for rid in req_ids]
    report.item = MagicMock()
    report.item.iter_markers.return_value = iter(marker_mocks)
    return report

def test_writes_passed_test(tmp_path):
    store_path = tmp_path / "store.json"
    plugin = TraceabilityPlugin(store_path=str(store_path))
    plugin.pytest_runtest_logreport(_make_report("tests/test_foo.py::test_bar", "passed", ["REQ-101"]))
    data = json.loads(store_path.read_text())
    assert "tests/test_foo.py::test_bar" in data["tests"]
    assert data["tests"]["tests/test_foo.py::test_bar"]["outcome"] == "passed"
    assert "REQ-101" in data["tests"]["tests/test_foo.py::test_bar"]["requirement_ids"]

def test_skips_untagged_tests(tmp_path):
    store_path = tmp_path / "store.json"
    plugin = TraceabilityPlugin(store_path=str(store_path))
    plugin.pytest_runtest_logreport(_make_report("tests/test_foo.py::test_untagged", "passed", []))
    assert not store_path.exists()

def test_appends_multiple_tests(tmp_path):
    store_path = tmp_path / "store.json"
    plugin = TraceabilityPlugin(store_path=str(store_path))
    plugin.pytest_runtest_logreport(_make_report("t::a", "passed", ["REQ-101"]))
    plugin.pytest_runtest_logreport(_make_report("t::b", "failed", ["REQ-102"]))
    data = json.loads(store_path.read_text())
    assert len(data["tests"]) == 2
```

**Step 2: Run — verify all fail**

```bash
pytest tests/test_conftest_plugin.py -v
```
Expected: 3 × `FAILED`

**Step 3: Implement**

```python
# autotest/conftest_plugin.py
import json
from pathlib import Path

class TraceabilityPlugin:
    def __init__(self, store_path: str = "traceability_store.json"):
        self.store_path = Path(store_path)

    def _load(self):
        if self.store_path.exists():
            return json.loads(self.store_path.read_text())
        return {"tests": {}}

    def _save(self, data):
        self.store_path.write_text(json.dumps(data, indent=2))

    def pytest_runtest_logreport(self, report):
        if report.when != "call":
            return
        req_ids = [m.args[0] for m in report.item.iter_markers("requirement")]
        if not req_ids:
            return
        store = self._load()
        store["tests"][report.nodeid] = {
            "outcome": report.outcome,
            "duration": report.duration,
            "requirement_ids": req_ids,
            "surviving_mutants_count": 0,
            "is_weak": False,
        }
        self._save(store)
```

**Step 4: Run — verify all pass**

```bash
pytest tests/test_conftest_plugin.py -v
```
Expected: 3 × `PASSED`

**Step 5: Commit**

```bash
git add autotest/conftest_plugin.py tests/test_conftest_plugin.py
git commit -m "feat: conftest_plugin writes traceability_store.json after each tagged test"
```

---

## Task 4: Mutation Bridge

**Files:**
- Create: `autotest/mutation_bridge.py`
- Test: `tests/test_mutation_bridge.py`

Reads `.mutmut-cache/cache` (SQLite, mutmut's output) and `coverage.json` (coverage.py `--cov-context=test` output), joins them, and writes `mutation_results.json`. Also merges weak-test data back into `traceability_store.json`.

**Step 1: Write failing tests**

```python
# tests/test_mutation_bridge.py
import json, sqlite3, pytest
from autotest.mutation_bridge import (
    load_survivors_from_db,
    build_weak_test_map,
    merge_into_traceability,
)

def _make_mutmut_db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE mutant (id INTEGER, filename TEXT, line_number INTEGER, status TEXT)")
    conn.execute("INSERT INTO mutant VALUES (1, 'src/calc.py', 10, 'survived')")
    conn.execute("INSERT INTO mutant VALUES (2, 'src/calc.py', 20, 'killed')")
    conn.commit()
    conn.close()

def test_loads_only_survivors(tmp_path):
    db = tmp_path / "cache"
    _make_mutmut_db(db)
    survivors = load_survivors_from_db(str(db))
    assert len(survivors) == 1
    assert survivors[0]["line"] == 10

def test_maps_survivors_to_tests():
    survivors = [{"mutant_id": 1, "filename": "src/calc.py", "line": 10}]
    coverage = {
        "files": {
            "src/calc.py": {
                "contexts": {"10": ["tests/test_calc.py::test_add"]}
            }
        }
    }
    weak_map = build_weak_test_map(survivors, coverage)
    assert "tests/test_calc.py::test_add" in weak_map
    assert weak_map["tests/test_calc.py::test_add"]["surviving_mutants"] == 1

def test_merge_updates_traceability(tmp_path):
    store_path = tmp_path / "store.json"
    store = {"tests": {"tests/test_calc.py::test_add": {
        "outcome": "passed", "requirement_ids": ["REQ-101"],
        "surviving_mutants_count": 0, "is_weak": False
    }}}
    store_path.write_text(json.dumps(store))
    scores = {"tests/test_calc.py::test_add": {"surviving_mutants_count": 2, "is_weak": True}}
    merge_into_traceability(scores, str(store_path))
    updated = json.loads(store_path.read_text())
    assert updated["tests"]["tests/test_calc.py::test_add"]["is_weak"] is True
    assert updated["tests"]["tests/test_calc.py::test_add"]["surviving_mutants_count"] == 2
```

**Step 2: Run — verify all fail**

```bash
pytest tests/test_mutation_bridge.py -v
```
Expected: 3 × `FAILED`

**Step 3: Implement**

```python
# autotest/mutation_bridge.py
import json, sqlite3
from pathlib import Path
from typing import List, Dict

def load_survivors_from_db(db_path: str) -> List[Dict]:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, filename, line_number FROM mutant WHERE status='survived'"
    ).fetchall()
    conn.close()
    return [{"mutant_id": r[0], "filename": r[1], "line": r[2]} for r in rows]

def build_weak_test_map(survivors: List[Dict], coverage: Dict) -> Dict:
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

def merge_into_traceability(scores: Dict, store_path: str = "traceability_store.json"):
    p = Path(store_path)
    store = json.loads(p.read_text())
    for test_name, data in scores.items():
        if test_name in store["tests"]:
            store["tests"][test_name]["surviving_mutants_count"] = data["surviving_mutants_count"]
            store["tests"][test_name]["is_weak"] = data["is_weak"]
    p.write_text(json.dumps(store, indent=2))

def run(mutmut_db: str, coverage_json: str, store_path: str, output: str):
    survivors = load_survivors_from_db(mutmut_db)
    with open(coverage_json) as f:
        coverage = json.load(f)
    weak_map = build_weak_test_map(survivors, coverage)
    scores = {
        k: {"surviving_mutants_count": v["surviving_mutants"], "is_weak": v["surviving_mutants"] > 0}
        for k, v in weak_map.items()
    }
    merge_into_traceability(scores, store_path)
    result = {"total_surviving_mutants": len(survivors), "weak_tests": scores}
    with open(output, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Survivors: {len(survivors)} | Weak tests: {len(scores)}")
```

**Step 4: Run — verify all pass**

```bash
pytest tests/test_mutation_bridge.py -v
```
Expected: 3 × `PASSED`

**Step 5: Commit**

```bash
git add autotest/mutation_bridge.py tests/test_mutation_bridge.py
git commit -m "feat: mutation_bridge joins mutmut survivors with coverage contexts"
```

---

## Task 5: Reliability Report CLI

**Files:**
- Create: `autotest/report.py`
- Test: `tests/test_report.py`

Reads `traceability_store.json` + requirements list (from prd_parser), classifies each requirement as VERIFIED / WEAK / FAILING / UNTESTED, prints summary, returns exit code 1 if score < threshold.

**Step 1: Write failing tests**

```python
# tests/test_report.py
import json
from autotest.report import compute_reliability

REQUIREMENTS = [
    {"id": "REQ-101", "description": "valid email"},
    {"id": "REQ-102", "description": "age check"},
    {"id": "REQ-103", "description": "untested feature"},
]

def _store(tests_dict):
    return {"tests": tests_dict}

def test_verified_when_passing_and_not_weak():
    store = _store({"t::a": {
        "outcome": "passed", "requirement_ids": ["REQ-101"],
        "is_weak": False, "surviving_mutants_count": 0
    }})
    results = compute_reliability(REQUIREMENTS, store)
    assert results["REQ-101"]["status"] == "VERIFIED"

def test_weak_when_surviving_mutants():
    store = _store({"t::a": {
        "outcome": "passed", "requirement_ids": ["REQ-102"],
        "is_weak": True, "surviving_mutants_count": 2
    }})
    results = compute_reliability(REQUIREMENTS, store)
    assert results["REQ-102"]["status"] == "WEAK"

def test_failing_when_test_failed():
    store = _store({"t::a": {
        "outcome": "failed", "requirement_ids": ["REQ-101"],
        "is_weak": False, "surviving_mutants_count": 0
    }})
    results = compute_reliability(REQUIREMENTS, store)
    assert results["REQ-101"]["status"] == "FAILING"

def test_untested_when_no_test_tagged():
    store = _store({})
    results = compute_reliability(REQUIREMENTS, store)
    assert results["REQ-103"]["status"] == "UNTESTED"

def test_score_is_verified_over_total():
    store = _store({"t::a": {
        "outcome": "passed", "requirement_ids": ["REQ-101"],
        "is_weak": False, "surviving_mutants_count": 0
    }})
    results = compute_reliability(REQUIREMENTS, store)
    verified = sum(1 for r in results.values() if r["status"] == "VERIFIED")
    assert verified == 1
    assert len(results) == 3
```

**Step 2: Run — verify all fail**

```bash
pytest tests/test_report.py -v
```
Expected: 5 × `FAILED`

**Step 3: Implement**

```python
# autotest/report.py
import json, sys, click
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
        results[rid] = {"status": status, "description": req["description"], "test_count": len(mapped)}
    return results

@click.command()
@click.option("--prd", required=True, help="Path to Markdown PRD file")
@click.option("--store", default="traceability_store.json", help="Path to traceability store")
@click.option("--threshold", default=90.0, help="Minimum reliability % to pass")
def cli(prd, store, threshold):
    requirements = parse_prd_file(prd)
    store_data = json.loads(Path(store).read_text()) if Path(store).exists() else {"tests": {}}
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
```

Add CLI entrypoint to `pyproject.toml`:

```toml
[project.scripts]
autotest-report = "autotest.report:cli"
```

**Step 4: Run — verify all pass**

```bash
pytest tests/test_report.py -v
```
Expected: 5 × `PASSED`

**Step 5: Commit**

```bash
git add autotest/report.py tests/test_report.py pyproject.toml
git commit -m "feat: reliability report CLI with VERIFIED/WEAK/FAILING/UNTESTED scoring"
```

---

## Task 6: Example Project (End-to-End Validation)

**Files:**
- Create: `example/prd.md`
- Create: `example/src/calculator.py`
- Create: `example/tests/conftest.py`
- Create: `example/tests/test_calculator.py`

This validates the full pipeline works on a real (simple) project.

**Step 1: Create the example**

```markdown
<!-- example/prd.md -->
# Calculator PRD

## REQ-201: Addition must return the correct sum of two integers
## REQ-202: Division by zero must raise ValueError
## REQ-203: Multiplication must return the correct product
```

```python
# example/src/calculator.py
def add(a: int, b: int) -> int:
    return a + b

def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

def multiply(a: int, b: int) -> int:
    return a * b
```

```python
# example/tests/conftest.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Register the traceability plugin
from autotest.conftest_plugin import TraceabilityPlugin
import pytest

@pytest.fixture(autouse=True, scope="session")
def _traceability_plugin(request):
    plugin = TraceabilityPlugin(store_path="example/traceability_store.json")
    request.config.pluginmanager.register(plugin)
```

```python
# example/tests/test_calculator.py
import pytest
from calculator import add, divide, multiply

@pytest.mark.requirement("REQ-201")
def test_add_positive():
    assert add(2, 3) == 5

@pytest.mark.requirement("REQ-201")
def test_add_negative():
    assert add(-1, 1) == 0

@pytest.mark.requirement("REQ-202")
def test_divide_by_zero_raises():
    with pytest.raises(ValueError):
        divide(10, 0)

# REQ-203 intentionally left untagged to demonstrate UNTESTED status
```

**Step 2: Run the full pipeline**

```bash
# From project root
cd example

# 1. Run tests with coverage
pytest tests/ --cov=src --cov-context=test --cov-report=json -v
# Expected: 3 PASSED, coverage.json written

# 2. Run mutmut
mutmut run --paths-to-mutate src/
# Expected: some mutants killed, some survived

# 3. Run mutation bridge
python -m autotest.mutation_bridge \
  --mutmut-db .mutmut-cache/cache \
  --coverage coverage.json \
  --store traceability_store.json \
  --output mutation_results.json

# 4. Run reliability report
autotest-report --prd prd.md --store traceability_store.json --threshold 60
```

Expected output:
```
============================================================
  Reliability Score: 66.7% (2/3 VERIFIED)
============================================================
  ❌ REQ-203: UNTESTED — Multiplication must return the correct product
```

**Step 3: Commit**

```bash
git add example/
git commit -m "feat: add end-to-end example project validating full pipeline"
```

---

## Task 7: mutmut_config.py Template + README

**Files:**
- Create: `autotest/templates/mutmut_config.py`
- Create: `README.md`

**Step 1: Create the reusable config template**

```python
# autotest/templates/mutmut_config.py
"""
Copy this file to your project root as mutmut_config.py.
Customise the skip rules and test command routing for your codebase.

Verified context properties (mutmut ≥ 2.x):
  context.filename              — path of file being mutated
  context.current_source_line   — source line text
  context.skip                  — set True to skip this mutation
  context.config.test_command   — override test command for this mutant
"""

def pre_mutation(context):
    # Skip low-signal lines
    if any(s in context.current_source_line for s in [
        "logger.", "print(", "# pragma", "__repr__", "__str__", "logging."
    ]):
        context.skip = True
        return

    # Optional: route mutations to focused test files for speed
    # if "your_module" in context.filename:
    #     context.config.test_command = "pytest tests/test_your_module.py -x"
```

**Step 2: Write README**

````markdown
# autotest — Python Reliability Shield

Maps PRD requirements to tests, detects weak assertions via mutation testing,
produces a reliability score. Works on any Python project.

## Install

```bash
pip install -e /path/to/autotest
```

## Usage

### 1. Tag your PRD

```markdown
## REQ-101: User must register with a valid email
## REQ-102: System rejects users under 18
```

### 2. Tag your tests

```python
@pytest.mark.requirement("REQ-101")
def test_registration_valid_email():
    ...
```

### 3. Run the pipeline

```bash
# Generate coverage + traceability data
pytest --cov=src --cov-context=test --cov-report=json

# Run mutation testing
mutmut run --paths-to-mutate src/

# Bridge results
python -m autotest.mutation_bridge

# Generate report
autotest-report --prd prd.md
```

## CI Integration

```yaml
# .github/workflows/reliability.yml
- run: pytest --cov=src --cov-context=test --cov-report=json
- run: mutmut run --paths-to-mutate src/
- run: python -m autotest.mutation_bridge
- run: autotest-report --prd prd.md --threshold 85
```
````

**Step 3: Commit**

```bash
git add autotest/templates/ README.md
git commit -m "docs: add mutmut_config template and README with usage guide"
```

---

## Verification Plan

After all tasks:

```bash
# Full test suite for the framework itself
pytest tests/ -v
# Expected: all PASSED

# End-to-end via example project
cd example && pytest tests/ --cov=src --cov-context=test --cov-report=json -v
mutmut run --paths-to-mutate src/
cd .. && python -m autotest.mutation_bridge
autotest-report --prd example/prd.md --store example/traceability_store.json
# Expected: report prints, REQ-203 shows UNTESTED
```

---

## What This Framework Does NOT Do

- It does not require Neo4j or any external database
- It does not parse code ASTs for rule extraction (that's domain-specific; see astroq-v2 as reference)
- It does not generate test data / fuzz (bring your own fuzzer)
- It does not replace pytest — it augments it
