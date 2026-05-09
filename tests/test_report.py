import json

from click.testing import CliRunner

from truetdd.report import cli, compute_reliability

REQUIREMENTS = [
    {"id": "REQ-101", "description": "valid email"},
    {"id": "REQ-102", "description": "age check"},
    {"id": "REQ-103", "description": "untested feature"},
]


def _store(tests_dict):
    return {"tests": tests_dict}


def test_verified_when_passing_and_not_weak():
    store = _store(
        {
            "t::a": {
                "outcome": "passed",
                "requirement_ids": ["REQ-101"],
                "is_weak": False,
                "surviving_mutants_count": 0,
                "testdata": {"source": "tests/testdata.yaml", "set_name": "test_a", "case_count": 3},
            }
        }
    )
    results = compute_reliability(REQUIREMENTS, store)
    assert results["REQ-101"]["status"] == "VERIFIED"


def test_weak_when_surviving_mutants():
    store = _store(
        {
            "t::a": {
                "outcome": "passed",
                "requirement_ids": ["REQ-102"],
                "is_weak": True,
                "surviving_mutants_count": 2,
            }
        }
    )
    results = compute_reliability(REQUIREMENTS, store)
    assert results["REQ-102"]["status"] == "WEAK"


def test_failing_when_test_failed():
    store = _store(
        {
            "t::a": {
                "outcome": "failed",
                "requirement_ids": ["REQ-101"],
                "is_weak": False,
                "surviving_mutants_count": 0,
            }
        }
    )
    results = compute_reliability(REQUIREMENTS, store)
    assert results["REQ-101"]["status"] == "FAILING"


def test_untested_when_no_test_tagged():
    store = _store({})
    results = compute_reliability(REQUIREMENTS, store)
    assert results["REQ-103"]["status"] == "UNTESTED"


def test_weak_data_when_no_testdata_declared():
    """Passing test with zero survivors but no testdata.yaml → WEAK_DATA status."""
    store = _store(
        {
            "t::a": {
                "outcome": "passed",
                "requirement_ids": ["REQ-101"],
                "is_weak": False,
                "surviving_mutants_count": 0,
                # No 'testdata' key — data coverage gap
            }
        }
    )
    results = compute_reliability(REQUIREMENTS, store)
    assert results["REQ-101"]["status"] == "WEAK_DATA"


def test_score_is_verified_over_total():
    store = _store(
        {
            "t::a": {
                "outcome": "passed",
                "requirement_ids": ["REQ-101"],
                "is_weak": False,
                "surviving_mutants_count": 0,
                "testdata": {"source": "tests/testdata.yaml", "set_name": "test_a", "case_count": 3},
            }
        }
    )
    results = compute_reliability(REQUIREMENTS, store)
    verified = sum(1 for r in results.values() if r["status"] == "VERIFIED")
    assert verified == 1
    assert len(results) == 3


# ─────────────────────────────────────────────────────────────────────────────
# CLI tests — tests the `truetdd-report` entrypoint via CliRunner
# ─────────────────────────────────────────────────────────────────────────────


def _make_prd(tmp_path, content="## REQ-001: Test requirement\n"):
    prd = tmp_path / "prd.md"
    prd.write_text(content)
    return str(prd)


def _make_store(tmp_path, tests_dict):
    store = tmp_path / "store.json"
    store.write_text(json.dumps({"tests": tests_dict}))
    return str(store)


class TestReportCLI:
    def test_cli_exits_1_below_threshold(self, tmp_path):
        """CLI must exit with code 1 when score is below threshold."""
        prd = _make_prd(tmp_path)
        store = _make_store(tmp_path, {})  # no tests → score 0%
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--prd",
                prd,
                "--store",
                store,
                "--threshold",
                "90",
            ],
        )
        assert result.exit_code == 1

    def test_cli_exits_0_when_above_threshold(self, tmp_path):
        """CLI exits 0 when all requirements are VERIFIED and score >= threshold."""
        prd = _make_prd(tmp_path)
        store = _make_store(
            tmp_path,
            {
                "tests/test_x.py::test_foo": {
                    "outcome": "passed",
                    "requirement_ids": ["REQ-001"],
                    "is_weak": False,
                    "surviving_mutants_count": 0,
                    "testdata": {"source": "tests/testdata.yaml", "set_name": "test_foo", "case_count": 2},
                }
            },
        )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--prd",
                prd,
                "--store",
                store,
                "--threshold",
                "50",
            ],
        )
        assert result.exit_code == 0

    def test_cli_writes_json_output(self, tmp_path):
        """--json-out produces a machine-readable JSON file."""
        prd = _make_prd(tmp_path)
        store = _make_store(tmp_path, {})
        json_out = tmp_path / "out.json"
        runner = CliRunner()
        runner.invoke(
            cli,
            [
                "--prd",
                prd,
                "--store",
                str(store),
                "--json-out",
                str(json_out),
                "--threshold",
                "0",
            ],
        )
        assert json_out.exists()
        data = json.loads(json_out.read_text())
        assert "score" in data
        assert "requirements" in data

    def test_cli_output_contains_score(self, tmp_path):
        """CLI output must include a Reliability Score line."""
        prd = _make_prd(tmp_path)
        store = _make_store(tmp_path, {})
        runner = CliRunner()
        result = runner.invoke(cli, ["--prd", prd, "--store", store, "--threshold", "0"])
        assert "Reliability Score" in result.output

    def test_cli_missing_prd_fails_gracefully(self, tmp_path):
        """CLI handles missing PRD file without an unhandled exception."""
        store = _make_store(tmp_path, {})
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--prd",
                str(tmp_path / "nonexistent.md"),
                "--store",
                store,
            ],
        )
        # Should not raise — click will catch the FileNotFoundError
        assert result.exit_code != 0
