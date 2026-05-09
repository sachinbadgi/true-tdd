import json
import logging
import sqlite3
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import click

logger = logging.getLogger(__name__)

try:
    import yaml as _yaml
except ImportError:
    _yaml = None  # type: ignore


def load_survivors_from_sqlite(cache_path: str = ".mutmut-cache") -> List[Dict]:
    """Read surviving mutants from mutmut 2.x SQLite cache (.mutmut-cache).

    mutmut 2 schema:
      Table: Mutant  (id, line, index, tested_against_hash, status)
      Table: SourceFile (id, filename, hash)
      Table: Line (id, sourcefile, line, line_number)
      Status values: 'ok_killed', 'bad_survived', 'bad_timeout', 'ok_suspicious'
    """
    survivors: List[Dict] = []
    p = Path(cache_path)
    if not p.exists():
        return survivors

    try:
        con = sqlite3.connect(str(p))
        cur = con.cursor()

        # Check which schema we have
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cur.fetchall()}

        if "Mutant" in tables:
            # mutmut 2 schema: Mutant + Line + SourceFile
            cur.execute("""
                SELECT m.id, sf.filename, l.line_number
                FROM Mutant m
                JOIN Line l ON m.line = l.id
                JOIN SourceFile sf ON l.sourcefile = sf.id
                WHERE m.status = 'bad_survived'
            """)
            for row in cur.fetchall():
                mutant_id, filename, line_number = row
                survivors.append(
                    {
                        "mutant_id": str(mutant_id),
                        "filename": filename or "",
                        "line": line_number or 0,
                    }
                )
        elif "MutantRunResult" in tables:
            # mutmut 3 SQLite fallback
            cur.execute("SELECT id, source_path, status FROM MutantRunResult WHERE status = 'survived'")
            for row in cur.fetchall():
                mutant_id, source_path, _ = row
                survivors.append(
                    {
                        "mutant_id": str(mutant_id),
                        "filename": source_path or "",
                        "line": 0,
                    }
                )

        con.close()
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
        logger.debug("mutmut cache unreadable (%s) — falling back to .meta files", e)
    return survivors


def load_survivors_from_meta(meta_dir: str = "mutants") -> List[Dict]:
    """Read surviving mutants from mutmut 3.x .meta files."""
    survivors: List[Dict] = []
    base_path = Path(meta_dir)

    if not base_path.exists():
        return survivors

    for meta_file in base_path.rglob("*.meta"):
        # The mutated filename can be derived from the meta file path
        # e.g. mutants/src/calculator.py.meta -> src/calculator.py
        rel_path = meta_file.relative_to(base_path)
        original_filename = str(rel_path)[:-5]  # remove .meta

        with open(meta_file) as f:
            meta = json.load(f)

        exit_codes = meta.get("exit_code_by_key", {})
        for mutant_key, exit_code in exit_codes.items():
            # In mutmut 3, exit_code == 0 means the mutant SURVIVED (test passed)
            # exit_code > 0 (usually 1) means the mutant was KILLED (test failed)
            if exit_code == 0:
                survivors.append(
                    {
                        "mutant_id": mutant_key,
                        "filename": original_filename,
                        "line": 0,  # Mutmut 3 abstracts away line numbers in meta files, so we map by file/function
                    }
                )
    return survivors


def load_survivors(meta_dir: str = "mutants", cache_path: str = ".mutmut-cache") -> List[Dict]:
    """Auto-detect mutmut version and load survivors from the appropriate format.

    - mutmut 2: reads .mutmut-cache (SQLite)
    - mutmut 3: reads mutants/*.meta (JSON)
    """
    if Path(cache_path).exists():
        survivors = load_survivors_from_sqlite(cache_path)
        if survivors or not Path(meta_dir).exists():
            return survivors
    return load_survivors_from_meta(meta_dir)


def build_weak_test_map(survivors: List[Dict], coverage: Dict) -> Dict:
    """
    For each survivor, find which test functions covered the mutated file.
    A test covering a mutated file but not killing the mutant = weak test.
    Note: Due to mutmut 3's AST-based approach, line numbers are abstracted,
    so we flag tests that cover the file containing the survivor.
    """
    weak_map: Dict[str, Dict] = {}

    # Pre-compute which tests touch which files
    tests_by_file = {}
    for file_key, file_data in coverage.get("files", {}).items():
        tests_touching_file = set()
        for contexts in file_data.get("contexts", {}).values():
            tests_touching_file.update(contexts)
        tests_by_file[file_key] = tests_touching_file

    for s in survivors:
        file_key = s["filename"].lstrip("./")
        contexts = tests_by_file.get(file_key, [])

        for test_name in contexts:
            if test_name not in weak_map:
                weak_map[test_name] = {"surviving_mutants": 0, "mutant_ids": []}
            weak_map[test_name]["surviving_mutants"] += 1
            weak_map[test_name]["mutant_ids"].append(s["mutant_id"])

    return weak_map


def merge_into_traceability(
    scores: Dict,
    store_path: str = "traceability_store.json",
    injected_sets: Optional[Dict] = None,
):
    """Merge weak test metadata back into the main traceability store.

    Args:
        scores: {test_name: {surviving_mutants_count, is_weak}}
        store_path: path to traceability_store.json
        injected_sets: optional output of DataInjector.get_injected_sets().
            When provided, adds a 'testdata' field per test entry:
            {
              "source": "tests/testdata.yaml",
              "set_name": "test_add_positive",
              "case_count": 5,
              "injected_for_mutmut": true
            }
    """
    p = Path(store_path)
    if not p.exists():
        return  # Nothing to merge into — store hasn't been created yet by pytest
    store = json.loads(p.read_text())
    for test_name, data in scores.items():
        if test_name in store["tests"]:
            store["tests"][test_name]["surviving_mutants_count"] = data["surviving_mutants_count"]
            store["tests"][test_name]["is_weak"] = data["is_weak"]

    # Enrich with testdata provenance if injection metadata is available
    if injected_sets:
        suffix_map = {k.split("::")[-1]: k for k in store["tests"]}
        for nodeid, info in injected_sets.items():
            # Try exact match first, then suffix match
            fn_name = nodeid.split("::")[-1]
            matched_key = nodeid if nodeid in store["tests"] else suffix_map.get(fn_name)

            if matched_key:
                store["tests"][matched_key]["testdata"] = {
                    "source": info.get("source", ""),
                    "set_name": info.get("set_name", ""),
                    "case_count": info.get("case_count", 0),
                    "injected_for_mutmut": True,
                }

    p.write_text(json.dumps(store, indent=2))


def _enrich_store_from_testdata(store: dict, testdata_yaml: str) -> None:
    """
    Set the 'testdata' field on matching tests in-memory (no file I/O).
    Matches by stripping the parametrize suffix from the node ID.
    Injection-free path: testdata.yaml declaration is sufficient provenance.
    """
    if _yaml is None:
        return

    td_path = Path(testdata_yaml)
    if not td_path.exists():
        return

    try:
        raw = _yaml.safe_load(td_path.read_text()) or {}
    except Exception:
        return

    case_sets = raw.get("cases", {})
    if not case_sets:
        return

    td_meta = {
        fn_name: {
            "source": str(td_path),
            "set_name": fn_name,
            "case_count": len(cs.get("cases", [])),
        }
        for fn_name, cs in case_sets.items()
    }

    for nodeid, test_data in store.get("tests", {}).items():
        base = nodeid.split("::")[-1].split("[")[0]
        if base in td_meta and not test_data.get("testdata"):
            test_data["testdata"] = td_meta[base]


def run(
    meta_dir: str,
    coverage_json: str,
    store_path: str,
    output: str,
    injected_sets: Optional[Dict] = None,
    cache_path: str = ".mutmut-cache",
    testdata_yaml: Optional[str] = None,
):
    survivors = load_survivors(meta_dir=meta_dir, cache_path=cache_path)
    with open(coverage_json) as f:
        coverage = json.load(f)

    weak_map = build_weak_test_map(survivors, coverage)
    scores = {
        k: {"surviving_mutants_count": v["surviving_mutants"], "is_weak": v["surviving_mutants"] > 0}
        for k, v in weak_map.items()
    }

    # Load store once, apply all enrichments in memory, write once (atomic).
    store_p = Path(store_path)
    if store_p.exists():
        store_data = json.loads(store_p.read_text())

        # 1. Merge mutation weakness scores
        for test_name, data in scores.items():
            if test_name in store_data["tests"]:
                store_data["tests"][test_name]["surviving_mutants_count"] = data["surviving_mutants_count"]
                store_data["tests"][test_name]["is_weak"] = data["is_weak"]

        # 2. Enrich with injected testdata provenance (injection path)
        if injected_sets:
            suffix_map = {k.split("::")[-1]: k for k in store_data["tests"]}
            for nodeid, info in injected_sets.items():
                fn_name = nodeid.split("::")[-1]
                matched_key = nodeid if nodeid in store_data["tests"] else suffix_map.get(fn_name)
                if matched_key:
                    store_data["tests"][matched_key]["testdata"] = {
                        "source": info.get("source", ""),
                        "set_name": info.get("set_name", ""),
                        "case_count": info.get("case_count", 0),
                        "injected_for_mutmut": True,
                    }

        # 3. Enrich with testdata provenance from YAML (injection-free path)
        td_path = testdata_yaml or _find_testdata_yaml()
        if td_path:
            _enrich_store_from_testdata(store_data, td_path)

        # Single atomic write — no partial-state risk
        _write_store_atomic(store_p, store_data)

    result = {"total_surviving_mutants": len(survivors), "weak_tests": scores}
    with open(output, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Survivors: {len(survivors)} | Weak tests: {len(scores)}")


def _write_store_atomic(store_path: Path, store_data: dict) -> None:
    """Write store_data to store_path atomically via a tempfile + rename.

    Prevents a partial-write state if the process is interrupted between
    the mutation-score merge and the testdata-provenance enrichment.
    """
    store_dir = store_path.parent
    store_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=store_dir, suffix=".tmp", delete=False) as tmp:
        json.dump(store_data, tmp, indent=2)
        tmp_path = Path(tmp.name)
    tmp_path.replace(store_path)  # atomic on POSIX; best-effort on Windows


def _find_testdata_yaml() -> Optional[str]:
    """Search standard locations for testdata.yaml. Returns path string or None."""
    for candidate in ["tests/testdata.yaml", "testdata.yaml"]:
        if Path(candidate).exists():
            return candidate
    return None


@click.command("bridge")
@click.option("--meta-dir", default="mutants", show_default=True, help="Directory containing mutmut 3 .meta files.")
@click.option("--cache", default=".mutmut-cache", show_default=True, help="Path to mutmut 2 SQLite cache file.")
@click.option(
    "--coverage", default="coverage.json", show_default=True, help="Path to coverage.json (pytest-cov --json output)."
)
@click.option("--store", default="traceability_store.json", show_default=True, help="Path to traceability_store.json.")
@click.option(
    "--output", default="mutation_results.json", show_default=True, help="Output path for mutation_results.json."
)
@click.option("--testdata", default=None, help="Path to testdata.yaml for boundary case provenance.")
def cli(
    meta_dir: str,
    cache: str,
    coverage: str,
    store: str,
    output: str,
    testdata: str | None,
) -> None:
    """Merge mutmut survivor data into the truetdd traceability store."""
    run(meta_dir, coverage, store, output, cache_path=cache, testdata_yaml=testdata)


if __name__ == "__main__":
    cli()
