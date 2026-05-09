# True TDD — Python Reliability Shield

> **Map PRD requirements to tests. Find weak assertions with mutation testing. Score your codebase.**

True TDD is a zero-infrastructure reliability framework for Python projects. It links your Product Requirements Document to your test suite, finds tests that pass but don't actually kill code mutations, and produces a **reliability score** with a per-requirement breakdown — all from local JSON and files, no database required.

---

## How It Works

```
PRD (Markdown)          Test Suite (pytest)
      │                       │
      │   @pytest.mark.requirement("REQ-X")
      │                       │
      ▼                       ▼
 prd_parser.py       conftest_plugin.py
      │                       │  writes outcomes
      │               traceability_store.json
      │                       │
      │              mutation_bridge.py ◄── mutmut .meta files
      │                       │  enriches with survivors
      │               traceability_store.json
      │                       │
      └───────► report.py ◄───┘
                     │
              Reliability Score
         VERIFIED / WEAK / WEAK_DATA / FAILING / UNTESTED
```

**Reliability statuses explained:**

| Status | Meaning |
|--------|---------|
| ✅ `VERIFIED` | Passing test + `testdata.yaml` cases declared + zero surviving mutants |
| ⚠️ `WEAK` | Passing test + surviving mutants — assertion gap |
| 📊 `WEAK_DATA` | Passing test + no `testdata.yaml` cases — data coverage gap |
| 🔴 `FAILING` | Test exists but outcome is failed or error |
| ❌ `UNTESTED` | No test tagged to this requirement |

---

## Installation

```bash
pip install true-tdd           # or: pip install -e /path/to/truetdd
```

**Python dependencies installed automatically:** `pytest`, `pytest-cov`, `mutmut`, `click`, `pyyaml`, `watchdog`

**Global tool prerequisite — install once per machine:**

```bash
uv tool install graphify       # provides the 'graphify' command used by run_pipeline.sh
```

> `graphify` is a structural graph analysis tool, not a per-project pip package.
> If you don't have `uv`: `pip install uv` first, or download from [astral.sh/uv](https://astral.sh/uv).

---

## Quick Start (2 minutes)

### Step 0 — Bootstrap your project

```bash
pip install true-tdd           # or: pip install -e /path/to/truetdd
truetdd-init                  # run inside your project root
```

This creates everything you need:

```
your-project/
├── run_pipeline.sh            ← one command to run the full pipeline
├── prd.md                     ← stub — add your REQ-IDs here
├── tests/
│   ├── conftest.py            ← plugin auto-registered
│   └── testdata.yaml          ← stub — add boundary cases here
└── setup.cfg                  ← mutmut + pytest + coverage config
```

Options: `truetdd-init --project /path/to/project --force`

### Step 1 — Tag your PRD

Write a Markdown PRD file using `## REQ-XXX:` headers:

```markdown
# Product Requirements

## REQ-101: User must register with a valid email address
## REQ-102: System must reject users under 18
## REQ-103: Password must be at least 8 characters
```

### Step 2 — Tag your tests

Register the `requirement` marker in your `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = ["requirement: REQ-ID this test validates"]
```

Apply markers to your test functions:

```python
import pytest

@pytest.mark.requirement("REQ-101")
def test_valid_email_accepted():
    assert validate_email("user@example.com") is True

@pytest.mark.requirement("REQ-101")
def test_invalid_email_rejected():
    assert validate_email("not-an-email") is False

@pytest.mark.requirement("REQ-102")
def test_minor_rejected():
    with pytest.raises(ValueError):
        register_user(age=16)
```

### Step 3 — Register the traceability plugin

In your project's `conftest.py`:

```python
# conftest.py
from truetdd.conftest_plugin import TraceabilityPlugin

def pytest_configure(config):
    config.pluginmanager.register(
        TraceabilityPlugin(store_path="traceability_store.json")
    )
```

### Step 4 — Configure mutmut scope

In your `pyproject.toml`:

```toml
[tool.mutmut]
mutate_only_covered_lines = true

[tool.coverage.run]
dynamic_context = "test_function"
```

### Step 5 — Run the pipeline

```bash
# 1. Generate coverage + traceability data
pytest --cov=src --cov-context=test --cov-report=json

# 2. Run mutation testing
mutmut run --paths-to-mutate src/

# 3. Bridge mutation results to traceability store
python -m truetdd.mutation_bridge \
  --meta-dir mutants \
  --coverage coverage.json \
  --store traceability_store.json \
  --output mutation_results.json

# 4. Generate reliability report
truetdd-report --prd prd.md --store traceability_store.json --threshold 80
```

**Sample output:**

```
======================================================================
  Reliability Score: 75.0% (3/4 VERIFIED)
======================================================================
  📊 REQ-101: WEAK_DATA — no testdata.yaml cases declared
  ❌ REQ-103: UNTESTED — no test tagged to this requirement
```

---

## Data-Aware Mutation Testing

Plain tests with hardcoded values like `assert add(2, 3) == 5` often fail to kill mutants. For example, `add(0, 0) == 0` does **not** kill a `return a - b` mutant because `-0 == 0`.

truetdd solves this with **data-aware injection**: declare richer boundary cases in a sidecar YAML, and True TDD automatically injects them as `@pytest.mark.parametrize` during mutmut runs — then restores your original files cleanly.

### Create a testdata.yaml sidecar

Place it next to your test file:

```
tests/
├── test_calculator.py
└── testdata.yaml          ← add this
```

```yaml
# tests/testdata.yaml
version: 1

cases:
  # Auto-matched to test_add_positive() by function name
  test_add_positive:
    description: "Boundary cases to strengthen mutation kill rate"
    cases:
      - {a: 2, b: 3, expected: 5}       # baseline
      - {a: 0, b: 0, expected: 0}        # kills 'return a - b' mutant
      - {a: -5, b: 5, expected: 0}       # symmetric zero
      - {a: 1, b: -1, expected: 0}       # negative addend

  # Named set — reference via @pytest.mark.testdata("add_cases")
  add_cases:
    description: "Shared set reusable by multiple tests"
    cases:
      - {a: 2, b: 3, expected: 5}
      - {a: 0, b: 0, expected: 0}

  # Raises-style cases use the 'raises' key
  test_divide_by_zero_raises:
    cases:
      - {a: 10, b: 0, raises: "ValueError"}
      - {a: -5, b: 0, raises: "ValueError"}
```

**Resolution priority:**
1. `@pytest.mark.testdata("set_name")` on the test → looks up `cases["set_name"]`
2. Auto-match by function name → looks up `cases["test_function_name"]`
3. No match → test runs unchanged (graceful passthrough)

### Run the data-aware pipeline

```bash
# 1. Inject boundary cases before mutmut
truetdd-inject prepare --tests tests/ --testdata tests/testdata.yaml

# 2. Run mutmut against the augmented tests
mutmut run --paths-to-mutate src/

# 3. Restore original test files
truetdd-inject restore --tests tests/

# Or run all three steps in one command:
truetdd-inject run \
  --tests tests/ \
  --testdata tests/testdata.yaml \
  --mutate src/ \
  --store traceability_store.json
```

**Crash safety:** If the process is interrupted, True TDD detects the `.truetdd_lock` sentinel on next run and automatically restores all backed-up files before proceeding. No data loss path.

### Optional: explicit marker for stronger graph edges

```python
@pytest.mark.requirement("REQ-201")
@pytest.mark.testdata("add_cases")   # EXTRACTED edge (conf 1.0) vs INFERRED (conf 0.75)
def test_add_with_shared_cases():
    assert add(2, 3) == 5
```

---

## Full Pipeline Reference

### Minimal pipeline (no data injection)

```bash
eval $(python -m truetdd.discovery)
pytest --cov=. --cov-omit="$TEST_FILES" --cov-context=test --cov-report=json
mutmut run --paths-to-mutate "$SRC_FILES"
python -m truetdd.mutation_bridge \
  --meta-dir mutants --coverage coverage.json \
  --store traceability_store.json --output mutation_results.json
truetdd-report --prd prd.md --store traceability_store.json
```

### Full pipeline (with data-aware injection)

```bash
# Step 1: Discover files
eval $(python -m truetdd.discovery)

# Step 2: Baseline coverage
pytest --cov=. --cov-omit="$TEST_FILES" --cov-context=test --cov-report=json

# Step 3: Inject richer test data
truetdd-inject prepare --tests "$TEST_FILES" --testdata testdata.yaml

# Step 4: Run mutmut against augmented tests
mutmut run --paths-to-mutate "$SRC_FILES"

# Step 5: Restore originals + bridge results
truetdd-inject restore --tests "$TEST_FILES"
python -m truetdd.mutation_bridge \
  --meta-dir mutants --coverage coverage.json \
  --store traceability_store.json --output mutation_results.json

# Step 6: Generate data-aware reliability report
truetdd-report --prd prd.md --store traceability_store.json --threshold 80

# Step 7: Auto-apply suggested testdata
truetdd-apply --feedback loop_feedback.json --testdata testdata.yaml
```

### With Graphify structural analysis (optional)

```bash
# Run graphify first to get graph.json
graphify run tests/ src/

truetdd-report \
  --prd prd.md \
  --store traceability_store.json \
  --graph graphify-out/graph.json \
  --threshold 80 \
  --json-out validation_matrix.json
```

---

## Discovery Engine (Graph Intelligence)

After each pipeline run, True TDD produces `discovery_suggestions.json` — a ranked list of gaps found by correlating the Graphify structural graph against your PRD and traceability store. This is the signal the LLM loop reads to decide what to do next.

**Three signal types:**

| Signal | What it means | LLM action |
|--------|--------------|------------|
| `UNTESTED_REQ` | PRD requirement has no test; graph found likely implementing function | Write a tagged test |
| `ORPHANED_FN` | Source function exists in `src/` but has zero test coverage | Add PRD entry + test |
| `WEAK_COVERAGE` | Requirement is WEAK/WEAK_DATA; graph identifies the implementing function | Add `testdata.yaml` cases |

Each signal includes a `confidence` score (0–1) and an `llm_action` field with a specific instruction.

**Loop termination flag:**
```json
{ "_summary": { "loop_complete": true } }
```
When `loop_complete` is `true`, no gaps remain — the LLM loop can stop.

**Suggested testdata stubs** (`loop_feedback.json → suggested_testdata`):

For every `WEAK_DATA` requirement, True TDD auto-generates ready-to-paste testdata stubs via AST analysis of the existing test:

```json
"test_add_positive": {
  "cases": [
    {"a": 2, "b": 3, "expected": 5,   "_comment": "baseline from existing test"},
    {"a": 0, "b": 0, "expected": "???","_comment": "zero inputs — kills constant-return mutants"},
    {"a": 1, "b": 1, "expected": "???","_comment": "identity — kills a+b vs a*b confusion"}
  ],
  "_note": "Strip '_comment' keys before pasting into testdata.yaml"
}
```

The framework automatically applies these stubs to `testdata.yaml` via the `truetdd-apply` command. The LLM simply needs to fill in the `???` values natively in the file. No YAML reasoning required.

---

## LLM Loop Architecture

True TDD is designed for an **LLM as the outermost loop**:

```
LLM reads loop_feedback.json + discovery_suggestions.json
  │
  ├── score < 100% or loop_complete: false
  │     → LLM writes testdata.yaml / new tests / PRD entries
  │     → re-runs: bash run_pipeline.sh
  │     → repeat
  │
  └── score == 100% AND loop_complete: true
        → loop terminates
```

**What is deterministic (pipeline):**
- Finding WEAK/WEAK_DATA/UNTESTED requirements
- Computing correlation confidence scores (graph → PRD)
- Generating testdata stubs from AST analysis
- Marking `loop_complete`

**What requires LLM reasoning:**
- Deciding whether an ORPHANED_FN link is semantically meaningful
- Writing TDD tests for newly discovered functions
- Evaluating whether a new PRD entry is warranted
- Filling `???` expected values in testdata stubs

Install True TDD as a post-commit gate — it runs the reliability check after every commit and warns if scores drop below threshold:

```bash
# Install hook into current repo
truetdd-hook install

# Install into a different repo
truetdd-hook install --project /path/to/your/project

# Check status
truetdd-hook status

# Remove
truetdd-hook uninstall
```

Configure the gate via `truetdd.cfg` (written to your project root on install):

```ini
# True TDD.cfg
AUTOTEST_PRD="prd.md"
AUTOTEST_SRC="src"
AUTOTEST_STORE="traceability_store.json"
AUTOTEST_GRAPH=""                          # leave empty if not using Graphify
AUTOTEST_THRESHOLD="80"                    # minimum score to pass
AUTOTEST_ENABLED="1"                       # set 0 to temporarily disable
AUTOTEST_TESTDATA="tests/testdata.yaml"    # path to sidecar YAML
AUTOTEST_INJECT="1"                        # set 0 to disable data injection
```

---

## CLI Reference

| Command | Purpose |
|---------|---------|
| `truetdd-init` | **Bootstrap a project** — creates run_pipeline.sh, prd.md, testdata.yaml, setup.cfg, conftest.py |
| `truetdd-report` | Generate reliability report + loop_feedback.json |
| `truetdd-hook install` | Install post-commit gate |
| `truetdd-hook uninstall` | Remove post-commit gate |
| `truetdd-hook status` | Check hook installation |
| `truetdd-inject prepare` | Backup + augment test files with testdata |
| `truetdd-inject restore` | Restore original test files from backup |
| `truetdd-apply` | Automatically merge generated testdata stubs into testdata.yaml |

```
truetdd-report --help

  --prd PATH         Path to Markdown PRD file [required]
  --store PATH       Path to traceability store [default: traceability_store.json]
  --graph PATH       Path to Graphify graph.json [optional]
  --threshold FLOAT  Minimum reliability % to pass [default: 90.0]
  --json-out PATH    Write machine-readable validation matrix JSON [optional]
```

---

## Project Layout

After running True TDD on your project, you will have:

```
your-project/
├── src/                        # source code
├── tests/
│   ├── conftest.py             # registers TraceabilityPlugin
│   ├── test_*.py               # tests with @pytest.mark.requirement
│   └── testdata.yaml           # sidecar boundary cases (optional)
├── prd.md                      # requirements document
├── traceability_store.json     # test outcomes + mutation scores (auto-written)
├── coverage.json               # per-test line coverage (from pytest-cov)
├── mutation_results.json       # mutation bridge output
├── mutants/                    # mutmut output directory
├── truetdd.cfg                # True TDD gate configuration
└── pyproject.toml              # mutmut + coverage + pytest config
```

---

## Adding to an Existing Project

1. `pip install true-tdd` (or `pip install -e /path/to/true-tdd`)
2. Run `truetdd-init` in your project root — creates all scaffolding in one step
3. Edit `prd.md` to add your `REQ-XXX:` requirements
4. Add `@pytest.mark.requirement("REQ-X")` to your test functions
5. Run `bash run_pipeline.sh` to establish baseline
6. Read `loop_feedback.json` and `discovery_suggestions.json` for gaps
7. Optionally: `truetdd-hook install` to add the post-commit gate

---

## Reliability Score Thresholds

| Score | Rating | Suggested action |
|-------|--------|-----------------|
| ≥ 90% | 🟢 Green | Release-ready |
| ≥ 75% | 🟡 Yellow | Review WEAK + WEAK_DATA items before release |
| ≥ 60% | 🟠 Orange | Significant assertion gaps — add testdata.yaml cases |
| < 60% | 🔴 Red | Untested requirements or failing tests block release |

---

## How True TDD Differs from Coverage

Coverage tells you *which lines* were executed. True TDD tells you *which requirements* are actually validated and *how strongly*.

| Question | Coverage | True TDD |
|---------|----------|---------|
| Which lines ran? | ✅ | — |
| Which requirements have tests? | — | ✅ |
| Do assertions actually catch bugs? | — | ✅ (mutation) |
| Will the test data expose mutations? | — | ✅ (data-aware) |
| Which code has no tests at all? | Partial | ✅ (Graphify graph) |

---

## Custom Mutation Configuration

Copy `truetdd/templates/mutmut_config.py` to your project root to exclude low-value targets (logging, `__repr__`, etc.) and route mutations to focused test files for faster runs:

```python
# mutmut_config.py
def pre_mutation(context):
    if any(s in context.current_source_line for s in ["logger.", "print(", "__repr__"]):
        context.skip = True
```
