# True TDD — Python Reliability Shield
## Concept & Architecture

True TDD is a developer-facing test quality framework that maps domain requirements to executable code and validates them using semantic tracing, data-aware mutation testing, and graph-correlated discovery.

Unlike standard TDD which only proves that code satisfies a test, **True TDD proves that the test maps to a requirement, the code is structurally verified by the test, and the test assertions are strong enough to kill semantic mutations.**

---

## 1. The Core USP: Deterministic Reliability

Standard TDD has three major blind spots:
1. **The Traceability Gap**: You don't know which requirement a test actually covers.
2. **The Assertion Gap**: A test can pass while being too weak to catch bugs (solved by mutation testing).
3. **The Shadow Code Gap**: Code can exist that is "covered" by a test but never actually called by it (solved by structural graph analysis).

True TDD solves these by building a **3-Tier Bridge**:
`Requirement (PRD) ↔ Test (Pytest) ↔ Code Artifact (AST Graph)`

---

## 2. Technical Stack

| Role | Component | Status |
|---|---|---|
| **Traceability** | `pytest.mark.requirement` tagging + `conftest_plugin` | ✅ Done |
| **Mutation Engine** | `mutmut` + `truetdd.mutation_bridge` | ✅ Done |
| **Structural Intelligence** | `Graphify` (local `graph.json` integration) | ✅ Done |
| **Data Injection** | `truetdd.data_injector` (Sidecar YAML + AST Rewriting) | ✅ Done |
| **Discovery Engine** | `truetdd.correlator` (Semantic gap detection) | ✅ Done |
| **Reporting** | `truetdd.report` (Reliability scoring) | ✅ Done |
| **Orchestration** | `run_pipeline.sh` (Deterministic Gate) | ✅ Done |

---

## 3. Architecture & Data Flow

True TDD operates as a zero-infrastructure local pipeline. It persists state in JSON files, requiring no database or external services.

### 3.1 The Deterministic Pipeline
The `run_pipeline.sh` script executes a multi-stage validation pass:

1. **Test & Trace**: `pytest` runs with the `truetdd` plugin. It records test outcomes and requirement tags into `traceability_store.json`.
2. **Mutation Pass**: `mutmut` runs code mutations. `truetdd.mutation_bridge` correlates surviving mutants with coverage data to identify **WEAK** tests.
3. **Data Injection**: For requirements flagged as `WEAK_DATA`, `truetdd-inject` prepares the test suite with boundary cases from `testdata.yaml`.
4. **Structural Analysis**: `graphify update` extracts the codebase AST.
5. **Discovery**: The `correlator` compares the structural graph against the requirements and test results to find **ORPHANED** functions or untested requirements.
6. **Report**: `truetdd-report` calculates the final reliability score.

### 3.2 Data-Aware Mutation Testing
True TDD is "data-aware": it can externalize and inject richer test data values during mutation runs to improve kill rates without permanently modifying source files.

- **`testdata.yaml`**: A sidecar file declaring named case sets.
- **AST Rewriting**: Before a run, `truetdd-inject` rewrites test files with `@pytest.mark.parametrize` calls, then restores the original files cleanly afterward.
- **Status: `WEAK_DATA`**: A test that passes but has no sidecar cases declared, signaling a data coverage gap.

---

## 4. Reliability Scoring Definition

True TDD replaces "Line Coverage" with a high-fidelity **Reliability Score**:

`Reliability Score (%) = (VERIFIED Requirements / Total Requirements) × 100`

### Requirement Statuses:
- **✅ VERIFIED**: At least one passing test is tagged to the requirement AND no surviving mutants were found on the code paths it covers.
- **⚠️ WEAK**: Tests pass, but mutation testing found survivors (assertions are too weak).
- **📊 WEAK_DATA**: Tests pass and mutants are killed, but no boundary cases are defined in `testdata.yaml`.
- **🔴 FAILING**: Tests tagged to the requirement are failing.
- **❌ UNTESTED**: No test in the suite is tagged with this requirement ID.

---

## 5. Agentic Loop Integration

True TDD is designed with an **AI Agent as the outermost loop**. 

The framework produces `loop_feedback.json` and `discovery_suggestions.json`. These files are designed to be read by AI coding assistants (like Antigravity or Claude) to:
1. **Identify the next task**: "Requirement REQ-101 is UNTESTED. Write a test."
2. **Auto-generate boundary data**: "Mutant 42 survived in `multiply()`. Here is a suggested test case for `testdata.yaml`."
3. **Prune dead code**: "Function `old_calc()` is ORPHANED. It has no test caller and no requirement mapping. Delete it."

---

## 6. Future Roadmap

### 6.1 Multi-Language Support
While the initial implementation is Python-focused, the architecture is language-agnostic. The local JSON stores (`traceability_store.json`, `graph.json`) allow for a **Java (JUnit)** or **Go** bridge to be implemented while keeping the same reporting and discovery logic.

### 6.2 Mutation-Aware Data Advisor
An AI-driven component that analyzes *why* a mutant survived by comparing the mutated operator against current test inputs, automatically proposing the exact boundary values needed to kill it.

### 6.3 Requirement Discovery (Auto-PRD)
Analyzing the structural graph and existing comments to suggest missing requirements in the `prd.md`, effectively reverse-engineering a specification for legacy codebases.