---
description: "Executes the Agentic TDD Loop using the Autotest framework."
---

# Autotest Loop (Agentic TDD)

This workflow orchestrates the closed-loop, LLM-driven development process using the `autotest` reliability framework. It allows Antigravity (you) to autonomously write code, validate it deterministically, and self-correct until a 100% reliability score is achieved.

## Prerequisites
- The project must have a `prd.md` file.
- The project must be configured with `pytest`, `pytest-cov`, and `mutmut`.
- The `autotest` package must be installed.

## Step 1: Run the Deterministic Validation Pipeline
Execute the full autotest pipeline to gather the current structural and semantic baseline.

// turbo-all
```bash
# 1. Generate coverage and traceability data
pytest --cov=src --cov-context=test --cov-report=json

# 2. Update structural graph memory
graphify update .

# 3. Run mutations
mutmut run || true

# 4. Bridge mutations to weak tests
python -m autotest.mutation_bridge --meta-dir mutants --coverage coverage.json --store traceability_store.json --output mutation_results.json

# 5. Generate JSON report feedback
python -m autotest.report --prd prd.md --store traceability_store.json --graph graphify-out/graph.json --threshold 100 --json-out loop_feedback.json
```

## Step 2: Ingest Feedback and Analyze Gaps
Read `loop_feedback.json` using the `view_file` tool.
Analyze the payload to determine the required actions:
1. **Untraceable Code Artifacts (`orphaned_functions`)**: Code exists but lacks tests. Write a test calling this function and tag it with the correct `@pytest.mark.requirement("REQ-XXX")`.
2. **Semantic Gaps (`is_weak`)**: The test structurally calls the code, but the assertions are too weak to kill mutants. Rewrite the test assertions to be stricter.
3. **Failing Requirements (`status == "FAILING"`)**: Fix the underlying source code bug causing the test failure.
4. **Untested Requirements (`status == "UNTESTED"`)**: The requirement exists in `prd.md` but has no code implementation. Write the code and the test.

## Step 3: Generation (Probabilistic Implementation)
Using your code editing tools, implement the fixes identified in Step 2.
- Write new pytest scenarios.
- Modify existing code logic.
- Ensure all tests are tagged with `@pytest.mark.requirement()`.

## Step 4: Loop Validation
Re-run Step 1 to validate your changes. 
- If the output of `autotest.report` is `Reliability Score: 100.0%`, the loop is complete.
- If the score is `< 100.0%`, return to Step 2 and repeat the process.

## Step 5: Finalization
Once 100% reliability is achieved, summarize the iterations and changes made in a response to the user.
