import json
from pathlib import Path
import pytest
import os

class TraceabilityPlugin:
    def __init__(self, store_path: str = "traceability_store.json"):
        # Make path absolute so it survives directory changes by mutmut
        self.store_path = Path(store_path).absolute()

    def _load(self):
        if self.store_path.exists():
            return json.loads(self.store_path.read_text())
        return {"tests": {}}

    def _save(self, data):
        # Ensure directory exists before saving
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(json.dumps(data, indent=2))

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        report = outcome.get_result()
        if report.when == "call":
            req_ids = [m.args[0] for m in item.iter_markers("requirement")]
            if not req_ids:
                return
            store = self._load()
            store["tests"][report.nodeid] = {
                "outcome": report.outcome,
                "duration": report.duration,
                "requirement_ids": req_ids,
                "surviving_mutants_count": 0,
                "is_weak": False,
            }
            self._save(store)
