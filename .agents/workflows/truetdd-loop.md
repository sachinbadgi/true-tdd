---
description: "Executes the Agentic TDD Loop using the True TDD framework."
---

# True TDD Loop (Agentic TDD)

This workflow orchestrates the closed-loop, LLM-driven development process using the `truetdd` reliability framework. It allows Antigravity (you) to autonomously write code, validate it deterministically against boundary data, and self-correct until a 100% reliability score is achieved.

## Prerequisites
- The project must have a `prd.md` file.
- The project must have the `run_pipeline.sh` script properly configured for phased snapshots.
- The `truetdd` package must be installed.

## Step 1: Run the Deterministic Validation Pipeline
Execute the full True TDD pipeline to gather the current structural and semantic baseline across all 4 phases (pytest -> tagging -> mutation -> reliability gate).

// turbo-all
```bash
# Execute the full pipeline
bash run_pipeline.sh
```

## Step 2: Ingest Feedback and Analyze Gaps
Read `reliability_report.md` using the `view_file` tool.
Focus specifically on the "Reliability Score" section at the bottom, which lists gaps by Requirement ID. Analyze the payloads to determine the required actions:

1. **Untracked / Untested (`UNTESTED` / `UNTRACKED`)**: The requirement exists in `prd.md` but has no test tagged with `@pytest.mark.requirement("REQ-XXX")`. 
   - *CRITICAL:* Read `discovery_suggestions.json` (if it exists). Graphify's semantic correlator may have already found the exact function that fulfills this requirement. If a high-confidence match is found, just write the test for that function. If no match is found, write the implementation code and the test.
2. **Semantic Gaps (`WEAK`)**: The test structurally covers the code, but the assertions are too weak to kill mutants. Rewrite the test assertions to be stricter against the returned values.
3. **Data Boundary Gaps (`WEAK_DATA`)**: The tests pass and kill mutants, but they lack explicit boundary condition declarations. You MUST create a `testdata.yaml` sidecar file (or run `truetdd-inject`) to declare the specific boundary edge-cases for these tests to prove data-awareness.
4. **Failing Requirements (`FAILING`)**: Fix the underlying source code bug causing the standard pytest failure.

## Step 3: Generation (Probabilistic Implementation)
Using your code editing tools, implement the fixes identified in Step 2.
- Write new pytest scenarios or modify existing code logic.
- Ensure all tests are tagged with `@pytest.mark.requirement()`.
- Inject `testdata.yaml` sidecar files where `WEAK_DATA` is reported.

## Step 4: Loop Validation
Re-run Step 1 to validate your changes. 
- If the output of the report shows `Reliability Score: 100.0%`, the loop is complete.
- If the score is `< 100.0%`, return to Step 2 and repeat the process.

## Step 5: Finalization
Once 100% reliability is achieved, summarize the iterations and changes made in a response to the user.
