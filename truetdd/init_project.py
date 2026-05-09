"""
truetdd/init_project.py

truetdd-init — Bootstrap a project to use the truetdd reliability framework.

Usage:
    truetdd-init [--project /path/to/project] [--src src] [--tests tests]

What it does:
    1. Copies run_pipeline.sh into the project root (executable)
    2. Copies prd.md stub if none exists
    3. Copies tests/testdata.yaml stub if none exists
    4. Creates/updates setup.cfg with required mutmut + pytest + coverage settings
    5. Prints next steps

The project must already have a Python virtualenv (.venv) with truetdd installed.
"""

import shutil
import stat
import sys
import textwrap
from pathlib import Path

import click

TEMPLATES = Path(__file__).parent / "templates"


def _copy_template(src: Path, dest: Path, overwrite: bool = False) -> bool:
    """Copy src to dest. Returns True if copied, False if skipped."""
    if dest.exists() and not overwrite:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return True


def _ensure_executable(path: Path) -> None:
    current = path.stat().st_mode
    path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _write_setup_cfg(project: Path, src_dir: str, tests_dir: str) -> bool:
    """
    Write setup.cfg with the minimal mutmut + pytest + coverage config needed
    by run_pipeline.sh. Does not overwrite an existing file.
    """
    cfg_path = project / "setup.cfg"
    if cfg_path.exists():
        return False  # Respect existing config

    cfg = textwrap.dedent(f"""\
        [mutmut]
        paths_to_mutate={src_dir}/
        tests_dir={tests_dir}/
        runner=.venv/bin/python -m pytest {tests_dir}/ -x -q

        [tool:pytest]
        testpaths = {tests_dir}
        norecursedirs = mutants .venv __pycache__
        markers =
            requirement: REQ-ID this test validates

        [coverage:run]
        dynamic_context = test_function
    """)
    cfg_path.write_text(cfg)
    return True


def _write_conftest(project: Path, tests_dir: str) -> bool:
    """Write a conftest.py that activates the truetdd pytest plugin."""
    conftest = project / tests_dir / "conftest.py"
    if conftest.exists():
        return False

    conftest.parent.mkdir(parents=True, exist_ok=True)
    conftest.write_text(
        textwrap.dedent("""\
        # truetdd: reliability traceability plugin
        # Registers the TraceabilityPlugin which writes traceability_store.json
        # and sets the macOS multiprocessing start method for mutmut compatibility.
        from truetdd.conftest_plugin import TraceabilityPlugin, pytest_configure  # noqa: F401

        def pytest_configure(config):  # type: ignore[no-redef]
            from truetdd.conftest_plugin import pytest_configure as _ttdd_configure
            _ttdd_configure(config)
            config.pluginmanager.register(TraceabilityPlugin())
    """)
    )
    return True


@click.command()
@click.option("--project", default=".", show_default=True, help="Path to the project root to initialise.")
@click.option("--src", default="src", show_default=True, help="Source directory (relative to project root).")
@click.option("--tests", default="tests", show_default=True, help="Tests directory (relative to project root).")
@click.option("--force", is_flag=True, default=False, help="Overwrite existing prd.md and testdata.yaml.")
def cli(project: str, src: str, tests: str, force: bool) -> None:
    """Bootstrap a project for the truetdd reliability framework.

    Creates run_pipeline.sh, prd.md, tests/testdata.yaml, setup.cfg,
    and tests/conftest.py with sane defaults for mutation + traceability testing.
    """
    root = Path(project).resolve()

    if not root.exists():
        click.echo(f"❌  Project path does not exist: {root}", err=True)
        sys.exit(1)

    results = []

    # 1. run_pipeline.sh
    pipeline_dest = root / "run_pipeline.sh"
    copied = _copy_template(TEMPLATES / "run_pipeline.sh", pipeline_dest, overwrite=False)
    if copied:
        _ensure_executable(pipeline_dest)
        results.append(("✅", "run_pipeline.sh", "created"))
    else:
        results.append(("⏭️ ", "run_pipeline.sh", "already exists — skipped"))

    # 2. prd.md
    prd_dest = root / "prd.md"
    copied = _copy_template(TEMPLATES / "prd.md", prd_dest, overwrite=force)
    results.append(("✅", "prd.md", "created") if copied else ("⏭️ ", "prd.md", "already exists — skipped"))

    # 3. tests/testdata.yaml
    td_dest = root / tests / "testdata.yaml"
    copied = _copy_template(TEMPLATES / "testdata.yaml", td_dest, overwrite=force)
    results.append(
        ("✅", f"{tests}/testdata.yaml", "created")
        if copied
        else ("⏭️ ", f"{tests}/testdata.yaml", "already exists — skipped")
    )

    # 4. setup.cfg
    cfg_written = _write_setup_cfg(root, src, tests)
    results.append(
        ("✅", "setup.cfg", f"created (src={src}/, tests={tests}/)")
        if cfg_written
        else ("⏭️ ", "setup.cfg", "already exists — skipped")
    )

    # 5. conftest.py
    conftest_written = _write_conftest(root, tests)
    results.append(
        ("✅", f"{tests}/conftest.py", "created")
        if conftest_written
        else ("⏭️ ", f"{tests}/conftest.py", "already exists — skipped")
    )

    # Print results
    click.echo(f"\n  truetdd-init — {root}\n")
    for icon, name, status in results:
        click.echo(f"  {icon}  {name:30s} {status}")

    click.echo(
        textwrap.dedent("""
  ─────────────────────────────────────────
  Next steps:

  1. Create a virtualenv if you haven't:
       python3 -m venv .venv
       .venv/bin/pip install truetdd

  2. Edit prd.md — add your requirements:
       REQ-101: My first requirement
       REQ-102: My second requirement

  3. Tag your tests:
       @pytest.mark.requirement('REQ-101')
       def test_my_feature(): ...

  4. Run the pipeline:
       bash run_pipeline.sh

  5. Read the output:
       cat reliability_report.md
       cat discovery_suggestions.json   # graph intelligence
       cat loop_feedback.json           # LLM loop entry point
  ─────────────────────────────────────────
    """)
    )
