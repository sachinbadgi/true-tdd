# autotest — Project Context for Claude Code

## Active Skills

This project uses the **autotest-tdd** skill from the local Superpowers fork.

When implementing any feature in this repo:
1. Read `superpowers:test-driven-development` — the base TDD rules
2. Read `superpowers:autotest-tdd` — the extended rules for autotest traceability

**The completion criterion for any feature is `autotest-report` scoring 100%, not just `pytest` passing.**

## Project Layout

| Path | Purpose |
|---|---|
| `autotest/` | Core framework package |
| `example/` | Reference project (calculator) — used for testing the framework |
| `example/prd.md` | Requirements with REQ-IDs |
| `example/traceability_store.json` | Live traceability state |
| `example/graphify-out/graph.json` | Structural call graph |
| `superpowers/` | Local Superpowers fork (our autotest-tdd skill lives here) |
| `.agents/workflows/autotest-loop.md` | The `/autotest-loop` workflow |

## Running the Full Pipeline (from `example/` dir)

```bash
# Full deterministic validation pass:
pytest tests/ --rootdir=. --cov=src --cov-context=test --cov-report=json:coverage.json -q
mutmut run || true
PYTHONPATH=.. python -m autotest.mutation_bridge \
  --meta-dir mutants --coverage coverage.json \
  --store traceability_store.json --output mutation_results.json
PYTHONPATH=.. python -m autotest.report \
  --prd prd.md --store traceability_store.json \
  --graph graphify-out/graph.json --threshold 100 \
  --json-out loop_feedback.json
```

## Key Conventions

- All tests must be tagged: `@pytest.mark.requirement("REQ-XXX")`
- REQ-IDs must exist in `example/prd.md`
- `loop_feedback.json` is the source of truth for feature completeness
- Every `git commit` runs the autotest reliability gate automatically

## Skill: autotest-tdd

Trigger: `superpowers:autotest-tdd`
Location: `~/.claude/skills/autotest-tdd/SKILL.md` (also `superpowers/skills/autotest-tdd/SKILL.md`)

This skill extends standard TDD with autotest's deterministic reliability gate.
