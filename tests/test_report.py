import json
from autotest.report import compute_reliability

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


def test_score_is_verified_over_total():
    store = _store(
        {
            "t::a": {
                "outcome": "passed",
                "requirement_ids": ["REQ-101"],
                "is_weak": False,
                "surviving_mutants_count": 0,
            }
        }
    )
    results = compute_reliability(REQUIREMENTS, store)
    verified = sum(1 for r in results.values() if r["status"] == "VERIFIED")
    assert verified == 1
    assert len(results) == 3
