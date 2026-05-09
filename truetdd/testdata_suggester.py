"""
truetdd/testdata_suggester.py

Deterministic testdata stub generator for WEAK_DATA requirements.

When truetdd-report finds a test is WEAK_DATA (passes, no mutants survive,
but no testdata.yaml boundary cases declared), this module:

  1. AST-parses the test file to find the function call inside the test
  2. Extracts the parameter names from the call arguments
  3. Generates a ready-to-paste testdata.yaml stub with boundary case templates

The stub is appended to loop_feedback.json under 'suggested_testdata' so the
LLM loop can apply it directly — zero reasoning required.

Boundary case heuristics (deterministic):
  - Zero values for numeric args (kills constant-return mutants)
  - Negative values (kills abs() wrapping mutants)
  - Commutative/asymmetric pairs (kills swap-args mutants)
  - One original case from the existing test (baseline)
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── AST extraction ──────────────────────────────────────────────────────────


def _extract_call_from_test(test_file: Path, fn_name: str) -> Optional[Tuple[str, List, Any]]:
    """
    Parse test_file and find the function call inside fn_name.
    Returns (called_fn_name, arg_values, expected_value) or None.

    Looks for: assert fn(a, b) == result
    """
    try:
        source = test_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception:
        return None

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name != fn_name:
            continue

        # Find the first assert with a comparison
        for stmt in ast.walk(node):
            if not isinstance(stmt, ast.Assert):
                continue
            test = stmt.test
            if not isinstance(test, ast.Compare):
                continue
            if not isinstance(test.left, ast.Call):
                continue

            call = test.left
            called = (
                call.func.id
                if isinstance(call.func, ast.Name)
                else (call.func.attr if isinstance(call.func, ast.Attribute) else None)
            )
            if not called:
                continue

            # Extract arg values from the call (constants only, for baseline)
            args = []
            for arg in call.args:
                if isinstance(arg, ast.Constant):
                    args.append(arg.value)
                elif isinstance(arg, ast.UnaryOp) and isinstance(arg.op, ast.USub):
                    if isinstance(arg.operand, ast.Constant) and isinstance(arg.operand.value, (int, float)):
                        args.append(-arg.operand.value)
                    else:
                        args.append(None)
                else:
                    args.append(None)

            # Get comparator value
            rhs = test.comparators[-1]
            expected = (
                rhs.value
                if isinstance(rhs, ast.Constant)
                else (
                    -rhs.operand.value
                    if isinstance(rhs, ast.UnaryOp)
                    and isinstance(rhs.op, ast.USub)
                    and isinstance(rhs.operand, ast.Constant)
                    and isinstance(rhs.operand.value, (int, float))
                    else None
                )
            )

            return called, args, expected

    return None


# ── Boundary case heuristics ─────────────────────────────────────────────────


def _generate_boundary_cases(
    baseline_args: List,
    baseline_expected: Any,
    param_names: List[str],
) -> List[Dict]:
    """
    Generate deterministic boundary case stubs.

    NOTE: Cases include a '_comment' key for human readability in loop_feedback.json.
    This key MUST be stripped before pasting into testdata.yaml — the injector
    treats every key as a parameter name and would inject '_comment' into the
    function signature.
    """
    cases = []

    # 1. Baseline case (from existing test)
    if all(v is not None for v in baseline_args) and baseline_expected is not None:
        base = dict(zip(param_names, baseline_args))
        base["expected"] = baseline_expected
        cases.append({**base, "_comment": "baseline — from existing test"})

    # 2. Zero inputs (kills constant-return mutants)
    zero: Dict[str, Any] = {p: 0 for p in param_names}
    zero["expected"] = "???"
    zero["_comment"] = "zero inputs — kills constant-return mutants"
    cases.append(zero)

    # 3. Identity input if 2 args (kills commutative bugs)
    if len(param_names) == 2:
        one_case: Dict[str, Any] = {param_names[0]: 1, param_names[1]: 1}
        one_case["expected"] = "???"
        one_case["_comment"] = "identity — kills a+b vs a*b confusion"
        cases.append(one_case)

    # 4. Negative first arg (kills abs() wrapping)
    if len(param_names) >= 1 and all(v is not None for v in baseline_args):
        neg: Dict[str, Any] = dict(zip(param_names, baseline_args))
        neg[param_names[0]] = -abs(baseline_args[0]) if baseline_args[0] != 0 else -1
        neg["expected"] = "???"
        neg["_comment"] = "negative arg — kills abs() wrapping"
        cases.append(neg)

    return cases


def _infer_param_names(called_fn: str, baseline_args: List) -> List[str]:
    """Infer parameter names from function name conventions."""
    n = len(baseline_args)
    # Common conventions
    if n == 2:
        return ["a", "b"]
    if n == 3:
        return ["a", "b", "c"]
    if n == 1:
        return ["value"]
    return [f"arg{i}" for i in range(n)]


# ── Public API ───────────────────────────────────────────────────────────────


def suggest_testdata_for_weak_tests(
    weak_data_reqs: Dict[str, Dict],
    store: Dict,
    tests_dir: str = "tests",
) -> Dict[str, Dict]:
    """
    For each WEAK_DATA requirement, attempt to generate a testdata.yaml stub.

    Args:
        weak_data_reqs: {req_id: {status, tests: [nodeids], ...}}
        store: traceability_store content
        tests_dir: path to tests directory

    Returns:
        {fn_name: {description, cases: [...], _note: str}}
        Ready to be merged into testdata.yaml 'cases:' block.
    """
    tests_path = Path(tests_dir)
    suggestions: Dict[str, Dict] = {}

    for req_id, req_data in weak_data_reqs.items():
        if req_data.get("status") != "WEAK_DATA":
            continue

        for nodeid in req_data.get("tests", []):
            # nodeid: "tests/test_foo.py::test_bar" or "tests/test_foo.py::test_bar[x-y]"
            # Strip parametrize suffix
            base_nodeid = nodeid.split("[")[0]
            parts = base_nodeid.split("::")
            if len(parts) < 2:
                continue

            test_file_rel = parts[0]
            fn_name = parts[-1]

            if fn_name in suggestions:
                continue  # Already generated for this function

            test_file = Path(test_file_rel)
            if not test_file.exists():
                test_file = tests_path / Path(test_file_rel).name
            if not test_file.exists():
                continue

            result = _extract_call_from_test(test_file, fn_name)
            if not result:
                continue

            called_fn, baseline_args, baseline_expected = result
            if not baseline_args:
                continue

            param_names = _infer_param_names(called_fn, baseline_args)
            cases = _generate_boundary_cases(baseline_args, baseline_expected, param_names)

            suggestions[fn_name] = {
                "description": f"Boundary stubs for {fn_name}() → {called_fn}(). Fill ??? values.",
                "cases": cases,
                "_note": (
                    "STUB: Strip '_comment' keys before pasting into testdata.yaml — "
                    "the injector treats every key as a parameter name."
                ),
            }

    return suggestions
