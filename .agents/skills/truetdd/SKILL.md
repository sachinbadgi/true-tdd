---
name: truetdd-tdd
description: Use when implementing features in a project using the True TDD reliability framework. Combines RED-GREEN-REFACTOR TDD with deterministic requirement traceability — pytest passing is necessary but NOT sufficient. Every feature must achieve 100% True TDD reliability score before it is complete.
---

# True TDD TDD

## Overview

Standard TDD proves a test passes. **True TDD TDD proves the test maps to a requirement, kills mutants, and leaves no orphaned code.**

The True TDD framework provides a deterministic 3-tier reliability score:

```
Requirement (prd.md) → Test (pytest + @pytest.mark.requirement) → Code Artifact (graphify graph)
```

**Core principle:** A feature is NOT complete until `truetdd-report` scores 100%. `pytest` passing is a necessary condition, not a sufficient one.

## The Extended Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST (Superpowers TDD)
+
NO FEATURE IS COMPLETE UNTIL truetdd-report SCORES 100% (True TDD)
```

Both laws apply. Neither can be skipped.

## When to Use

Use this skill instead of (or alongside) `superpowers:test-driven-development` when:
- The project has a `prd.md` with REQ-IDs
- The project has `truetdd` installed (`pip install -e .` from the True TDD repo)
- You want full traceability from requirement → test → code artifact

## The True TDD-TDD Cycle

```
Baseline Check → RED → GREEN → True TDD Gate → REFACTOR → Repeat
```

### Step 0: Baseline Check

Before touching any code, run the True TDD report to get the current state:

```bash
python -m truetdd.report \
  --prd prd.md \
  --store traceability_store.json \
  --graph graphify-out/graph.json \
  --threshold 100 \
  --json-out loop_feedback.json
```

Read `loop_feedback.json`. It tells you exactly what is wrong:

| Status | Meaning | Action |
|--------|---------|--------|
| `UNTESTED` | Requirement has no tagged test | Write failing test with `@pytest.mark.requirement` |
| `WEAK` | Test passes but mutants survive | Strengthen assertions |
| `WEAK_DATA` | Passing test but no boundary testdata | Fill in `???` in the auto-applied `testdata.yaml` |
| `FAILING` | Test exists but breaks | Fix source code |
| `UNTRACEABLE` in `orphaned_functions` | Code with no structural test caller | Write test that calls it, tag to correct REQ |

### Step 1: RED — Write Failing Test with Requirement Tag

**MANDATORY.** Write the test before any implementation code.

**Python example:**
```python
@pytest.mark.requirement("REQ-203")  # ← MANDATORY tag linking to prd.md
def test_multiply_positive():
    assert multiply(3, 4) == 12  # This MUST fail before you write multiply()
```

**Requirements for the test:**
- Tagged with `@pytest.mark.requirement("REQ-XXX")` matching a REQ-ID in `prd.md`
- Tests real behavior (not mocks)
- One behavior per test
- Name describes the behavior, not just the function

**Watch it fail:**
```bash
cd <project-dir> && PYTHONPATH=.. pytest tests/test_<module>.py::test_multiply_positive -v
```

Confirm:
- Test fails with `ImportError` or `AttributeError` (function doesn't exist yet), OR
- Test fails with `AssertionError` (function exists but wrong behavior)
- NOT: test passes immediately (means you're testing existing behavior — fix test)

### Step 2: GREEN — Minimal Implementation

Write the simplest code that passes the test. Follow `superpowers:test-driven-development` rules exactly:
- No extra parameters, no future-proofing
- YAGNI ruthlessly
- Watch test pass

```bash
cd <project-dir> && PYTHONPATH=.. pytest tests/test_<module>.py::test_multiply_positive -v
```

### Step 3: True TDD Gate — The Additional Check

**This is what separates True TDD TDD from standard TDD.**

After GREEN, run the full deterministic pipeline:

```bash
bash run_pipeline.sh
```

This runs: pytest → coverage → graphify delta → mutmut → mutation bridge → report → graphify discovery.

Outputs to read:
- `loop_feedback.json` — requirement statuses and suggested testdata stubs
- `discovery_suggestions.json` — graph-correlated gaps (`loop_complete: true` = done)
- `reliability_report.md` — human-readable summary

**Gate conditions:**

| `loop_feedback.json` result | Meaning | Next step |
|-----------------------------|---------|-----------|
| `"score": 100.0, "passed": true` | ✅ COMPLETE | Commit and move to next requirement |
| `"orphaned_functions": ["fn()"]` | 👻 Code exists with no test caller | Your test didn't structurally call the function — fix the import or function name |
| `"status": "WEAK"` for your REQ | ⚠️ Mutants survived | Strengthen assertions (see below) |
| `"status": "WEAK_DATA"` for your REQ | 📊 Missing boundary cases | Fill in `???` in `testdata.yaml` (stubs are auto-applied) |
| Other REQ scores dropped | Regression | You broke something — fix before proceeding |

### Fixing Semantic Gaps (WEAK status)

When `mutmut` survivors flag your test as WEAK, it means assertions aren't discriminating enough. Common patterns:

```python
# WEAK: only tests that no exception was raised
def test_multiply():
    result = multiply(3, 4)
    assert result is not None

# STRONG: tests exact value (kills arithmetic mutants)
def test_multiply_positive():
    assert multiply(3, 4) == 12

# STRONGER: tests multiple cases (kills boundary mutants)
def test_multiply_various():
    assert multiply(3, 4) == 12
    assert multiply(-2, 5) == -10
    assert multiply(0, 100) == 0
```

### Fixing Data Gaps (WEAK_DATA status)

When `WEAK_DATA` is flagged, True TDD generates testdata boundary stubs and automatically applies them to `testdata.yaml` using `truetdd-apply`. You just need to open `testdata.yaml`, find the `???` values for the expected results, and fill them in with the correct deterministic answers.

### Step 4: REFACTOR

Clean up code and tests. After refactor, re-run the True TDD Gate. Score must not decrease.

### Step 5: Commit

Only commit when:
- `pytest` is fully green
- `truetdd-report` score is `100.0%`
- No new orphaned functions

```bash
git add -A && git commit -m "feat(REQ-XXX): <description>"
```

The post-commit hook will re-run the True TDD gate automatically if installed.

## Working with `loop_feedback.json`

The feedback file is structured for easy parsing:

```json
{
  "score": 75.0,
  "passed": false,
  "requirements": {
    "REQ-201": { "status": "VERIFIED", "tests": ["tests/test_calc.py::test_add"], "covered_artifacts": ["add()"] },
    "REQ-203": { "status": "UNTESTED",  "tests": [], "covered_artifacts": [] }
  },
  "orphaned_functions": ["multiply()"],
  "god_tests": []
}
```

**Reading the gap list:** Process requirements with `status != "VERIFIED"` first (they directly affect the score), then orphaned functions.

## Integration with `subagent-driven-development`

When using this skill inside a `superpowers:subagent-driven-development` workflow, replace the standard completion check with the True TDD Gate:

**Standard SDD completion:** "All tests pass"
**True TDD SDD completion:** "All tests pass AND `truetdd-report` scores 100%"

The spec-reviewer subagent should verify `loop_feedback.json` exists and shows `"passed": true` before marking a task complete.

## Installing the True TDD Framework

Bootstrap any project with one command:

```bash
pip install True TDD           # or: pip install -e /path/to/truetdd
truetdd-init                  # creates run_pipeline.sh, prd.md, testdata.yaml, setup.cfg, conftest.py
```

Then edit `prd.md` to add your REQ-IDs and run `bash run_pipeline.sh`.

## Verification Checklist (extends superpowers:test-driven-development)

Before marking any feature complete:

- [ ] Test written BEFORE implementation code (RED first)
- [ ] Watched test fail for the right reason
- [ ] Wrote minimal code to pass (GREEN)
- [ ] Test tagged with `@pytest.mark.requirement("REQ-XXX")`
- [ ] REQ-XXX matches an entry in `prd.md`
- [ ] `truetdd-report` scores 100% (no UNTESTED, WEAK, FAILING)
- [ ] No new orphaned functions in `loop_feedback.json`
- [ ] Score did not decrease from previous run

Can't check all boxes? The feature is not complete. Do not commit.

## Red Flags — STOP

- Committing without checking `loop_feedback.json`
- Score of 0% or very low (usually means test is not tagged or conftest not loaded)
- `orphaned_functions` keeps growing (you're writing code faster than tests)
- `WEAK` status persists after strengthening assertions (check mutmut is configured and ran)
- "All my tests pass so it must be 100%" — pytest passing ≠ True TDD score of 100%
