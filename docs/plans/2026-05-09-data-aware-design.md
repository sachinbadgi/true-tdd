# Autotest Data-Aware Design

**Date:** 2026-05-09  
**Status:** Approved  
**Goal:** Externalize and configure test data values used during mutmut mutation testing execution, without requiring permanent changes to test files.

---

## Problem Statement

Tests with hardcoded literal values (e.g. `assert add(2, 3) == 5`) can fail to kill mutants when the input happens to be a degenerate case. For example:

- `add(0, 0) == 0` does **not** kill a `return a - b` mutant (because `-0 == 0`)
- `multiply(1, 1) == 1` does **not** kill a `return a + b` mutant

The test data itself affects mutation kill rates, but today it is invisible to autotest. This feature makes autotest "data-aware" by allowing richer test case sets to be declared externally and injected during mutmut runs.

---

## Approach: C1 (Sidecar YAML) + C2 (Inline Marker Override)

**Primary:** A `testdata.yaml` sidecar file declared next to the test file. Matched to tests by function name automatically.

**Optional override:** `@pytest.mark.testdata("set_name")` on a test to explicitly reference a named case set. This produces an `EXTRACTED` (confidence 1.0) edge in the Graphify graph vs the weaker `INFERRED` edge from proximity alone.

**Injection mechanism:** Approach A (Test File Rewriter) — autotest augments the test file with `@pytest.mark.parametrize` before mutmut runs, then restores the original after. Zero permanent changes to test files.

---

## Design

### 1. Sidecar YAML Schema

File: `tests/testdata.yaml` (co-located with test files)

```yaml
version: 1

cases:
  # Key = test function name (auto-matched fallback)
  test_add_positive:
    description: "Boundary cases to strengthen mutation kill rate"
    cases:
      - {a: 2, b: 3, expected: 5}          # original
      - {a: 0, b: 0, expected: 0}           # zero trap (catches a-b mutant)
      - {a: -5, b: 5, expected: 0}          # symmetric
      - {a: 1, b: -1, expected: 0}          # negative addend
      - {a: 100, b: -100, expected: 0}      # large symmetric

  # Key = named set (used by @pytest.mark.testdata("add_cases"))
  add_cases:
    description: "Shared add cases reused across multiple tests"
    cases:
      - {a: 2, b: 3, expected: 5}
      - {a: 0, b: 0, expected: 0}

  test_divide_normal:
    description: "Division edge cases"
    cases:
      - {a: 10, b: 2, expected: 5.0}
      - {a: 1, b: 1, expected: 1.0}
      - {a: -10, b: 2, expected: -5.0}
```

**Resolution rules (in priority order):**
1. If the test has `@pytest.mark.testdata("set_name")` → look up `cases["set_name"]`
2. Otherwise → look up `cases[test_function_name]`
3. If neither found → test runs unchanged (graceful passthrough, no error)

**`raises` cases** are supported with a special key:
```yaml
  test_divide_by_zero_raises:
    cases:
      - {a: 10, b: 0, raises: "ValueError"}
      - {a: -5, b: 0, raises: "ValueError"}
```

---

### 2. Rewriter Module — `autotest/data_injector.py`

#### Transformation

Given original test:
```python
@pytest.mark.requirement("REQ-201")
def test_add_positive():
    assert add(2, 3) == 5
```

Rewriter produces augmented version:
```python
@pytest.mark.requirement("REQ-201")
@pytest.mark.parametrize("a,b,expected", [
    (2, 3, 5),
    (0, 0, 0),
    (-5, 5, 0),
    (1, -1, 0),
    (100, -100, 0),
])
def test_add_positive(a, b, expected):
    assert add(a, b) == expected
```

For `raises` cases:
```python
@pytest.mark.parametrize("a,b", [(10, 0), (-5, 0)])
def test_divide_by_zero_raises(a, b):
    with pytest.raises(ValueError):
        divide(a, b)
```

#### AST Strategy

Uses Python's `ast` module + `ast.unparse()` (Python 3.9+). No regex on source. Steps:
1. `ast.parse()` the test file
2. Walk `FunctionDef` nodes, match against loaded case sets
3. Inject `@pytest.mark.parametrize` decorator node
4. Update function signature to include case parameters
5. Update assertion body to use parameter names
6. `ast.unparse()` back to source

#### Backup / Restore Safety

```
tests/
├── test_calculator.py              ← active file (augmented during mutmut run)
└── .autotest_backup/
    ├── test_calculator.py.bak      ← original, always preserved before augmentation
    └── .autotest_lock              ← sentinel file (presence = augmentation is active)
```

**Crash recovery:** On any invocation, `DataInjector.__init__()` checks for `.autotest_lock`. If found → calls `restore_all()` before proceeding. No data loss path.

#### Module Interface

```python
class DataInjector:
    def __init__(self, testdata_yaml: Path, backup_dir: Path): ...

    def load(self) -> dict
    """Parse testdata.yaml. Returns {set_name: [{case_dict}, ...]}."""

    def prepare(self, test_file: Path) -> bool
    """Backup original, write augmented file. Returns True if any cases injected."""

    def restore(self, test_file: Path) -> None
    """Restore from backup. Idempotent."""

    def restore_all(self) -> None
    """Restore all backed-up files. Used for crash recovery."""

    def get_injected_sets(self) -> dict
    """Return {test_nodeid: {set_name, case_count}} for traceability enrichment."""
```

---

### 3. Traceability Store Extension

`mutation_bridge.py` enriches `traceability_store.json` with a `testdata` field per test:

```json
{
  "tests": {
    "tests/test_calculator.py::test_add_positive": {
      "outcome": "passed",
      "requirement_ids": ["REQ-201"],
      "surviving_mutants_count": 0,
      "is_weak": false,
      "testdata": {
        "source": "tests/testdata.yaml",
        "set_name": "test_add_positive",
        "case_count": 5,
        "injected_for_mutmut": true
      }
    }
  }
}
```

---

### 4. Graphify Integration

No changes to Graphify required. When `/graphify` is re-run on the `tests/` directory:

- `testdata.yaml` is processed by the **semantic extractor** → creates named case set nodes
- `@pytest.mark.testdata("add_cases")` in test files → AST extractor creates an **EXTRACTED** edge (confidence 1.0) from the test function to the named set
- Without the marker, Graphify infers a proximity-based **INFERRED** edge (confidence ~0.75) from co-location

Resulting graph substructure:
```
test_add_positive() ──references──▶ testdata_add_cases  [EXTRACTED, 1.0]
testdata.yaml       ──contains───▶ testdata_add_cases   [EXTRACTED, 1.0]
testdata_add_cases  ──provides───▶ test_add_positive()  [INFERRED,  0.85]
```

`autotest/graph_analyzer.py` gets two new methods:

```python
def get_testdata_nodes(self) -> List[Dict]:
    """Return all nodes sourced from testdata.yaml files."""
    return [n for n in self.graph["nodes"] if "testdata" in n.get("source_file", "")]

def get_testdata_coverage(self, test_node_id: str) -> Optional[str]:
    """Return the testdata set node linked to a test node, if any."""
    for link in self.graph["links"]:
        if link["source"] == test_node_id and "testdata" in link.get("target", ""):
            return link["target"]
    return None
```

---

### 5. CLI Integration

New entrypoint in `pyproject.toml`:
```toml
autotest-inject = "autotest.data_injector:cli"
```

Usage:
```bash
# Prepare: backup originals, write augmented test files
autotest-inject prepare --tests tests/ --testdata tests/testdata.yaml

# Run mutmut against augmented files
mutmut run --paths-to-mutate src/

# Restore: swap originals back + bridge results
autotest-inject restore --tests tests/

# Or: full pipeline in one command
autotest-inject run \
  --tests tests/ \
  --testdata tests/testdata.yaml \
  --mutate src/ \
  --store traceability_store.json
```

`autotest.cfg` additions:
```ini
AUTOTEST_TESTDATA="tests/testdata.yaml"
AUTOTEST_INJECT="1"                       # set 0 to disable
```

---

### 6. Updated Reliability Report Statuses

| Status | Meaning |
|---|---|
| `VERIFIED` | Passing + `testdata.yaml` cases exist + zero surviving mutants |
| `WEAK_DATA` | Passing + **no sidecar cases declared** + zero survivors — data coverage gap |
| `WEAK` | Passing + sidecar cases exist + surviving mutants — assertion gap |
| `FAILING` | Test outcome is failed or error |
| `UNTESTED` | No test tagged to this requirement |

Sample output:
```
============================================================
  Reliability Score: 75.0% (3/4 VERIFIED)
============================================================
  ⚠️  REQ-201: WEAK_DATA — test_add_positive has no testdata.yaml cases
  ❌  REQ-204: UNTESTED — subtract requirements have no tagged test
```

---

### 7. Updated Full Pipeline

```bash
# 1. Baseline coverage run
pytest --cov=src --cov-context=test --cov-report=json

# 2. Inject richer test data (backs up originals, augments test files)
autotest-inject prepare --tests tests/ --testdata tests/testdata.yaml

# 3. Run mutmut against augmented tests
mutmut run --paths-to-mutate src/

# 4. Restore originals + bridge results
autotest-inject restore --tests tests/
python -m autotest.mutation_bridge \
  --meta-dir mutants \
  --coverage coverage.json \
  --store traceability_store.json \
  --output mutation_results.json

# 5. Generate reliability report (now data-aware)
autotest-report --prd prd.md --store traceability_store.json --threshold 80
```

---

## New Files

| File | Purpose |
|---|---|
| `autotest/data_injector.py` | Core rewriter + CLI |
| `tests/test_data_injector.py` | Unit tests for rewriter |
| `example/tests/testdata.yaml` | Example sidecar data file |

## Modified Files

| File | Change |
|---|---|
| `autotest/mutation_bridge.py` | Enrich store with `testdata` field |
| `autotest/report.py` | Add `WEAK_DATA` status |
| `autotest/graph_analyzer.py` | Add `get_testdata_nodes()`, `get_testdata_coverage()` |
| `pyproject.toml` | Add `autotest-inject` entrypoint |
| `autotest.cfg` | Add `AUTOTEST_TESTDATA`, `AUTOTEST_INJECT` |

---

## Future Features (Not in Scope)

### A — Data Registry / Catalog (deferred)

Declare test data sets in a central file and have autotest generate or parameterize pytest cases from them automatically. The registry becomes the single source of truth for all test inputs, queried by requirement ID rather than test function name.

### B — Mutation-Aware Data Advisor (deferred)

After a mutant survives, analyze *why* the test data was too weak and suggest stronger alternative inputs. Would require comparing the mutated operator against the input values to determine if any existing case would expose the fault, and generating targeted boundary values if not.
