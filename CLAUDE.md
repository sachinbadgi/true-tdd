# True TDD — Project Context for Claude Code

## Active Skills

This project uses the **truetdd-tdd** skill from the local Superpowers fork.

When implementing any feature in this repo:
1. Read `superpowers:test-driven-development` — the base TDD rules
2. Read `superpowers:truetdd-tdd` — the extended rules for True TDD traceability

**The completion criterion for any feature is `truetdd-report` scoring 100%, not just `pytest` passing.**

## Project Layout

| Path | Purpose |
|---|---|
| `truetdd/` | Core framework package |
| `CONCEPT.md` | Core framework design and architecture |
| `example/` | Reference project (calculator) — used for testing the framework |
| `example/prd.md` | Requirements with REQ-IDs |
| `example/traceability_store.json` | Live traceability state |
| `example/graphify-out/graph.json` | Structural call graph |
| `superpowers/` | Local Superpowers fork (our truetdd-tdd skill lives here) |
| `.agents/workflows/truetdd-loop.md` | The `/truetdd-loop` workflow |

## Running the Full Pipeline (from `example/` dir)

```bash
# Full deterministic validation pass:
pytest tests/ --rootdir=. --cov=src --cov-context=test --cov-report=json:coverage.json -q
mutmut run || true
PYTHONPATH=.. python -m truetdd.mutation_bridge \
  --meta-dir mutants --coverage coverage.json \
  --store traceability_store.json --output mutation_results.json
PYTHONPATH=.. python -m truetdd.report \
  --prd prd.md --store traceability_store.json \
  --graph graphify-out/graph.json --threshold 100 \
  --json-out loop_feedback.json
```

## Key Conventions

- All tests must be tagged: `@pytest.mark.requirement("REQ-XXX")`
- REQ-IDs must exist in `example/prd.md`
- `loop_feedback.json` is the source of truth for feature completeness
- Every `git commit` runs the True TDD reliability gate automatically

## Skill: truetdd-tdd

Trigger: `superpowers:truetdd-tdd`
Location: `~/.claude/skills/truetdd-tdd/SKILL.md` (also `superpowers/skills/truetdd-tdd/SKILL.md`)

This skill extends standard TDD with truetdd's deterministic reliability gate.
