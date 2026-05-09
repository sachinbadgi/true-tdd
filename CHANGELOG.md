# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `[tool.mypy]` and `[tool.ruff]` configuration sections in `pyproject.toml`
- Minimum version pins for all runtime dependencies
- `Changelog` URL in `[project.urls]`
- PyPI release GitHub Actions workflow (`.github/workflows/release.yml`)
- `workflow_dispatch` trigger to CI workflow for manual runs
- `.github/dependabot.yml` for automated dependency updates
- `SECURITY.md` with vulnerability reporting guidelines
- `CHANGELOG.md` (this file)
- `Makefile` with `test`, `lint`, `typecheck`, and `all` targets
- GitHub issue and PR templates
- Injected-path parameters to `correlator.generate_suggestions()` and `delta_manager.generate_delta()`
- Tests for `delta_manager` and `graph_sync` modules
- CLI tests for `report.py` and `hook.py` via `click.testing.CliRunner`

### Changed
- `correlator.py`: `generate_suggestions()` now accepts injectable `graph_path`, `store_path`, and `feedback_path` params
- `delta_manager.py`: `generate_delta()` now accepts injectable `manifest_path`, `last_manifest_path`, and `delta_out` params
- `hook.py`: Extracted `_HOOK_MARKER` module constant (was repeated 3×)
- `data_injector.py`: Replaced `/dev/null` sentinel with `os.devnull` (cross-platform)
- `graph_analyzer.py`: Path segment detection uses `Path.parts` instead of string `in` checks
- `init_project.py`: Generated `conftest.py` uses explicit imports instead of wildcard star import
- `graph_sync.py`: Replaced walrus-operator dict comprehension with readable loop
- `report.py` / `mutation_bridge.py`: Bare `except Exception: pass` now logs via `logging.debug()`
- `requirements.txt`: Fixed header comment (was incorrectly branded `autotest`)
- `README.md`: Fixed `pip install truetdd` → `pip install true-tdd` in "Adding to an Existing Project"

### Fixed
- N/A

## [0.2.0] — 2026-05-09

### Added
- Data-aware mutation testing (`truetdd-inject prepare/restore/run`)
- Discovery Engine (`truetdd-discover`) — semantic gap analysis against PRD
- Delta Manager (`truetdd-delta`) — changed-file detection via graphify manifest
- Summary Report (`truetdd-summary`) — deterministic reliability improvement report
- Phase progression format for `truetdd-summary --phases`
- Testdata suggester (auto-generates `testdata.yaml` stubs for WEAK_DATA requirements)
- Graph sync module (`graph_sync.py`) — injects mutation metrics into Graphify graph
- `truetdd-hook install/uninstall/status` for post-commit gate management
- `truetdd-init` project bootstrapper

### Changed
- Project renamed from `autotest` to `true-tdd`
- Reliability statuses: `VERIFIED`, `WEAK`, `WEAK_DATA`, `FAILING`, `UNTESTED`
- Added structural analysis via Graphify (orphaned functions, god tests)

## [0.1.0] — Initial release

### Added
- Core reliability framework: PRD parser, traceability plugin, mutation bridge, report CLI
- `@pytest.mark.requirement` marker for requirement tagging
- `traceability_store.json` schema
- Basic reliability score computation
