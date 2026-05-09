"""
truetdd/data_injector.py

Data-aware mutation testing layer for truetdd.

Loads a testdata.yaml sidecar, augments test files with
@pytest.mark.parametrize before mutmut runs, then restores originals.

Usage (CLI):
    truetdd-inject prepare --tests tests/ --testdata tests/testdata.yaml
    truetdd-inject restore --tests tests/
    truetdd-inject run --tests tests/ --testdata tests/testdata.yaml \\
                        --mutate src/ --store traceability_store.json
"""

from __future__ import annotations

import ast
import copy
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

import click
import yaml

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# YAML schema helpers
# ──────────────────────────────────────────────────────────────────────────────

LOCK_FILENAME = ".truetdd_lock"
BACKUP_DIR_NAME = ".truetdd_backup"


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


# ──────────────────────────────────────────────────────────────────────────────
# AST Rewriter
# ──────────────────────────────────────────────────────────────────────────────


def _parametrize_decorator_node(param_str: str, cases: list[dict], param_keys: list[str]) -> ast.expr:
    """Build a valid ast decorator node for @pytest.mark.parametrize."""
    tuple_elts: list[ast.expr] = []
    for case in cases:
        values = [case[k] for k in param_keys]
        if len(values) == 1:
            tuple_elts.append(ast.Constant(value=values[0]))
        else:
            tuple_elts.append(
                ast.Tuple(
                    elts=[ast.Constant(value=v) for v in values],
                    ctx=ast.Load(),
                )
            )

    cases_list = ast.List(elts=tuple_elts, ctx=ast.Load())

    parametrize_attr = ast.Attribute(
        value=ast.Attribute(
            value=ast.Name(id="pytest", ctx=ast.Load()),
            attr="mark",
            ctx=ast.Load(),
        ),
        attr="parametrize",
        ctx=ast.Load(),
    )

    return ast.Call(
        func=parametrize_attr,
        args=[ast.Constant(value=param_str), cases_list],
        keywords=[],
    )


def _has_raises(cases: list[dict]) -> bool:
    return any("raises" in c for c in cases)


def _rewrite_function(
    func_node: ast.FunctionDef,
    case_set: dict,
) -> ast.FunctionDef | None:
    """
    Inject @pytest.mark.parametrize into a FunctionDef.
    Returns modified node, or None if injection not applicable.

    Handles two modes:
    - Normal cases: adds (param...) arguments + updates assert body
    - Raises cases: adds (input_param...) arguments + wraps body in pytest.raises
    """
    cases = case_set.get("cases", [])
    if not cases:
        return None

    func = copy.deepcopy(func_node)

    if _has_raises(cases):
        return _rewrite_raises_function(func, cases)
    else:
        return _rewrite_normal_function(func, cases)


def _rewrite_normal_function(func: ast.FunctionDef, cases: list[dict]) -> ast.FunctionDef | None:
    """Augment a regular assert-style test with parametrize."""
    # Infer parameter names from the first case (exclude 'expected' last)
    first = cases[0]
    if "expected" not in first:
        return None  # Cannot safely rewrite without knowing expected

    param_keys = [k for k in first.keys() if k != "expected"] + ["expected"]
    param_str = ",".join(param_keys)

    # Prepend @pytest.mark.parametrize decorator
    deco = _parametrize_decorator_node(param_str, cases, param_keys)
    func.decorator_list = [deco] + func.decorator_list

    # Update function signature
    func.args.args = [ast.arg(arg=k) for k in param_keys]

    # Replace the function body with a parametrized assertion
    # Strategy: look for simple assert statements and replace the literals
    # with parameter references. For complex bodies, we replace wholesale.
    new_body = _parametrize_body(func.body, param_keys, first)
    if new_body:
        func.body = new_body

    ast.fix_missing_locations(func)
    return func


def _parametrize_body(
    body: list[ast.stmt],
    param_keys: list[str],
    first_case: dict,
) -> list[ast.stmt] | None:
    """
    Attempt to replace literal constants in assert statements with
    parameter name references.

    Returns rewritten body or None if transformation is too complex.
    """
    new_body: list[ast.stmt] = []
    for stmt in body:
        if isinstance(stmt, ast.Assert):
            new_body.append(_rewrite_assert(stmt, param_keys))
        else:
            new_body.append(stmt)
    return new_body


def _rewrite_assert(assert_node: ast.Assert, param_keys: list[str]) -> ast.Assert:
    """Replace the RHS of an assert comparison with the 'expected' param."""
    test = assert_node.test
    if isinstance(test, ast.Compare):
        # Replace all Name references in comparator left side with param names
        new_test = _replace_literals_with_params(test, param_keys)
        return ast.Assert(test=new_test, msg=assert_node.msg)
    return assert_node


def _replace_literals_with_params(node: ast.expr, param_keys: list[str]) -> ast.expr:
    """
    Walk the AST node and replace:
      - The last comparator (expected value) → ast.Name("expected")
      - Input argument positions → ast.Name(param_name)
    This is best-effort for simple binary comparison expressions.
    """
    node = copy.deepcopy(node)

    if isinstance(node, ast.Compare) and node.comparators:
        # Replace the last comparator with `expected`
        node.comparators[-1] = ast.Name(id="expected", ctx=ast.Load())

        # Replace call args in the left side with param names
        if isinstance(node.left, ast.Call):
            input_params = [k for k in param_keys if k != "expected"]
            node.left.args = [ast.Name(id=p, ctx=ast.Load()) for p in input_params]

    return node


def _rewrite_raises_function(func: ast.FunctionDef, cases: list[dict]) -> ast.FunctionDef | None:
    """Augment a pytest.raises-style test with parametrize."""
    first = cases[0]
    input_keys = [k for k in first.keys() if k != "raises"]
    if not input_keys:
        return None

    param_str = ",".join(input_keys)

    # Build cases without the 'raises' key (just input values)
    input_cases = [{k: c[k] for k in input_keys} for c in cases]
    deco = _parametrize_decorator_node(param_str, input_cases, input_keys)
    func.decorator_list = [deco] + func.decorator_list

    # Update signature
    func.args.args = [ast.arg(arg=k) for k in input_keys]

    # Replace call args inside pytest.raises block
    func.body = _rewrite_raises_body(func.body, input_keys)

    ast.fix_missing_locations(func)
    return func


def _rewrite_raises_body(body: list[ast.stmt], input_keys: list[str]) -> list[ast.stmt]:
    """Replace literal args inside a pytest.raises with clause with params."""
    new_body: list[ast.stmt] = []
    for stmt in body:
        if isinstance(stmt, ast.With) and stmt.items:
            new_stmt = _rewrite_with_raises(stmt, input_keys)
            new_body.append(new_stmt)
        else:
            new_body.append(stmt)
    return new_body


def _rewrite_with_raises(with_node: ast.With, input_keys: list[str]) -> ast.With:
    """Replace literal call args in with pytest.raises(...): body."""
    node = copy.deepcopy(with_node)
    for item in node.body:
        if isinstance(item, ast.Expr) and isinstance(item.value, ast.Call):
            item.value.args = [ast.Name(id=k, ctx=ast.Load()) for k in input_keys]
    return node


# ──────────────────────────────────────────────────────────────────────────────
# Marker extraction helper
# ──────────────────────────────────────────────────────────────────────────────


def _get_testdata_marker(func: ast.FunctionDef) -> str | None:
    """
    Return the set_name from @pytest.mark.testdata("set_name") if present,
    else None.
    """
    for deco in func.decorator_list:
        if not isinstance(deco, ast.Call):
            continue
        func_attr = deco.func
        # Match: pytest.mark.testdata(...)
        if (
            isinstance(func_attr, ast.Attribute)
            and func_attr.attr == "testdata"
            and isinstance(func_attr.value, ast.Attribute)
            and func_attr.value.attr == "mark"
        ):
            if deco.args and isinstance(deco.args[0], ast.Constant):
                return str(deco.args[0].value)
    return None


# ──────────────────────────────────────────────────────────────────────────────
# DataInjector
# ──────────────────────────────────────────────────────────────────────────────


class DataInjector:
    """
    Manages the lifecycle of test data injection for mutation testing.

    Workflow:
      injector = DataInjector(testdata_yaml, backup_dir)
      injector.load()
      injector.prepare(test_file)      # backup + augment
      # ... run mutmut ...
      injector.restore(test_file)      # restore original
    """

    def __init__(self, testdata_yaml: Path, backup_dir: Path):
        self.testdata_yaml = Path(testdata_yaml)
        self.backup_dir = Path(backup_dir)
        self._case_sets: dict[str, dict] = {}
        self._injected: dict[str, dict] = {}  # test_nodeid -> {set_name, case_count}

        # Crash recovery: if lock file exists, restore everything first
        lock = self.backup_dir / LOCK_FILENAME
        if lock.exists():
            self.restore_all()

    # ── Public API ─────────────────────────────────────────────────────────────

    def load(self) -> dict:
        """Parse testdata.yaml. Returns {set_name: case_set_dict}."""
        if not self.testdata_yaml.exists():
            return {}
        raw = _load_yaml(self.testdata_yaml)
        self._case_sets = raw.get("cases", {})
        return self._case_sets

    def prepare(self, test_file: Path) -> bool:
        """
        Backup original test_file, write augmented version.
        Returns True if at least one test was augmented.
        """
        test_file = Path(test_file)
        if not test_file.exists():
            return False

        if not self._case_sets:
            self.load()

        source = test_file.read_text(encoding="utf-8")
        augmented, injected = self._augment_source(source, test_file)

        if not injected:
            return False  # Nothing to inject

        # Ensure backup dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Write backup
        bak_path = self.backup_dir / (test_file.name + ".bak")
        shutil.copy2(test_file, bak_path)

        # Write lock
        (self.backup_dir / LOCK_FILENAME).touch()

        # Write augmented file
        test_file.write_text(augmented, encoding="utf-8")

        # Track injected sets
        for fn_name, info in injected.items():
            nodeid = f"{test_file}::{fn_name}"
            self._injected[nodeid] = info

        return True

    def restore(self, test_file: Path) -> None:
        """Restore test_file from backup. Idempotent."""
        test_file = Path(test_file)
        bak_path = self.backup_dir / (test_file.name + ".bak")
        if bak_path.exists():
            shutil.copy2(bak_path, test_file)
            bak_path.unlink()

        # Remove lock if all backups are gone
        remaining = list(self.backup_dir.glob("*.bak"))
        if not remaining:
            lock = self.backup_dir / LOCK_FILENAME
            if lock.exists():
                lock.unlink()

    def restore_all(self) -> None:
        """Restore all backed-up files. Used for crash recovery."""
        if not self.backup_dir.exists():
            return
        for bak_path in self.backup_dir.glob("*.bak"):
            original_name = bak_path.stem  # e.g. test_calculator.py
            # The original is one directory up from backup_dir
            original_path = self.backup_dir.parent / original_name
            # Always restore, even if the original was deleted during a crash
            shutil.copy2(bak_path, original_path)
            bak_path.unlink()

        lock = self.backup_dir / LOCK_FILENAME
        if lock.exists():
            lock.unlink()

    def get_injected_sets(self) -> dict:
        """Return {test_nodeid: {set_name, case_count}} for traceability."""
        return dict(self._injected)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _augment_source(self, source: str, test_file: Path) -> tuple[str, dict]:
        """
        Parse source, inject parametrize decorators, return (new_source, injected_map).
        injected_map = {fn_name: {"set_name": str, "case_count": int}}

        NOTE: ast.unparse() is used to re-serialise the modified AST. This strips
        all comments, docstrings, and blank-line formatting from the augmented file.
        The original is always backed up before augmentation and restored after mutmut
        runs. If the process is interrupted, crash recovery via the lock file will
        restore the original on the next invocation.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source, {}

        injected: dict = {}
        modified = False

        for i, node in enumerate(tree.body):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not node.name.startswith("test_"):
                continue

            # Resolve which case set to use
            marker_set = _get_testdata_marker(node)
            if marker_set and marker_set in self._case_sets:
                set_name = marker_set
                edge_type = "EXTRACTED"
            elif node.name in self._case_sets:
                set_name = node.name
                edge_type = "INFERRED"
            else:
                continue

            case_set = self._case_sets[set_name]
            rewritten = _rewrite_function(node, case_set)
            if rewritten is None:
                continue

            tree.body[i] = rewritten
            modified = True
            injected[node.name] = {
                "set_name": set_name,
                "case_count": len(case_set.get("cases", [])),
                "edge_type": edge_type,
                "source": str(self.testdata_yaml),
            }

        if not modified:
            return source, {}

        try:
            new_source = ast.unparse(tree)
        except Exception as exc:
            logger.warning(
                "ast.unparse failed for %s: %s — testdata injection skipped for this file.",
                test_file,
                exc,
            )
            return source, {}

        # ast.unparse strips leading comments/docstrings — prepend import if needed
        if "import pytest" not in new_source and "import pytest" in source:
            new_source = "import pytest\n" + new_source

        return new_source, injected


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────


@click.group()
def cli():
    """truetdd-inject: Data-aware mutation testing injector."""
    pass


@cli.command("prepare")
@click.option("--tests", required=True, type=click.Path(exists=True), help="Path to test directory")
@click.option("--testdata", required=True, type=click.Path(exists=True), help="Path to testdata.yaml")
def cmd_prepare(tests: str, testdata: str):
    """Backup originals and write augmented test files.

    Note: augmented files are re-serialised via ast.unparse, which strips
    comments, docstrings, and blank-line formatting. The originals are
    backed up automatically and restored by `truetdd-inject restore`.
    """
    tests_dir = Path(tests)
    backup_dir = tests_dir / BACKUP_DIR_NAME
    injector = DataInjector(Path(testdata), backup_dir)
    injector.load()

    total_injected = 0
    for test_file in tests_dir.glob("test_*.py"):
        if injector.prepare(test_file):
            click.echo(f"  ✅  Augmented: {test_file.name}")
            total_injected += 1
        else:
            click.echo(f"  ⏭️   No cases: {test_file.name}")

    click.echo(f"\n✔ Prepared {total_injected} file(s) with testdata injection.")


@cli.command("restore")
@click.option("--tests", required=True, type=click.Path(exists=True), help="Path to test directory")
def cmd_restore(tests: str):
    """Restore original test files from backups."""
    tests_dir = Path(tests)
    backup_dir = tests_dir / BACKUP_DIR_NAME
    injector = DataInjector(Path(os.devnull), backup_dir)  # yaml not needed for restore

    restored = 0
    if backup_dir.exists():
        for bak in backup_dir.glob("*.bak"):
            original = tests_dir / bak.stem
            injector.restore(original)
            click.echo(f"  ↩️   Restored: {original.name}")
            restored += 1

    click.echo(f"\n✔ Restored {restored} file(s).")


@cli.command("run")
@click.option("--tests", required=True, type=click.Path(exists=True))
@click.option("--testdata", required=True, type=click.Path(exists=True))
@click.option("--mutate", required=True, type=click.Path(exists=True))
@click.option("--store", default="traceability_store.json")
def cmd_run(tests: str, testdata: str, mutate: str, store: str):
    """Full pipeline: prepare → mutmut → restore → bridge."""
    tests_dir = Path(tests)
    backup_dir = tests_dir / BACKUP_DIR_NAME

    click.echo("⚙️  Step 1: Preparing augmented test files…")
    injector = DataInjector(Path(testdata), backup_dir)
    injector.load()
    for test_file in tests_dir.glob("test_*.py"):
        injector.prepare(test_file)

    click.echo("⚙️  Step 2: Running mutmut…")
    result = subprocess.run(
        ["mutmut", "run", f"--paths-to-mutate={mutate}"],
        capture_output=False,
    )

    click.echo("⚙️  Step 3: Restoring original test files…")
    for bak in backup_dir.glob("*.bak"):
        injector.restore(tests_dir / bak.stem)

    if result.returncode not in (0, 1):
        click.echo(f"❌ mutmut exited with code {result.returncode}", err=True)
        sys.exit(result.returncode)

    click.echo("✔ Pipeline complete.")


if __name__ == "__main__":
    cli()
