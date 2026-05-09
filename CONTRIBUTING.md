# Contributing to true-tdd

Thanks for wanting to contribute! This guide explains how to get up and running.

## Development Setup

```bash
git clone https://github.com/truetdd/true-tdd
cd true-tdd
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/        # run all tests
pytest tests/ -v     # verbose output
```

All 49 tests must pass. CI runs across Python 3.10, 3.11, and 3.12.

## Linting & Type Checking

```bash
ruff check truetdd tests     # linting
ruff format truetdd tests    # formatting
mypy truetdd tests           # type checks
```

The project uses zero-configuration ruff and mypy. PRs must be clean on all three.

## Project Layout

```
truetdd/          ← source package
  conftest_plugin.py   ← pytest plugin (traceability)
  correlator.py        ← discovery engine (graph → PRD correlation)
  data_injector.py     ← AST-based testdata injection for mutmut
  delta_manager.py     ← changed-file detection via graphify manifest
  graph_analyzer.py    ← structural analysis of graphify graph.json
  graph_sync.py        ← enriches graph.json with truetdd metrics
  hook.py              ← git post-commit hook management
  init_project.py      ← project bootstrapper (truetdd-init CLI)
  mutation_bridge.py   ← bridges mutmut results → traceability store
  prd_parser.py        ← Markdown PRD requirement parser
  report.py            ← reliability gate (truetdd-report CLI)
  summary_report.py    ← human-readable report (truetdd-summary CLI)
  testdata_suggester.py← WEAK_DATA stub generator

tests/            ← unit tests (pytest)
```

## Adding a New Feature

1. Write a test first (this is a TDD framework — eat your own dog food!)
2. Make it pass
3. Run `ruff check`, `ruff format`, `mypy`
4. Open a PR against `main`

## Submitting a PR

- Keep commits focused and the PR description clear
- Include test coverage for any new behaviour
- Update `README.md` if the user-facing API changes
- Update `CHANGELOG.md` with the change under `[Unreleased]`

## Reporting a Bug

Open a GitHub issue with:
- Python version
- truetdd version (`python -c "import truetdd; print(truetdd.__version__)"`)
- Minimal reproduction steps
