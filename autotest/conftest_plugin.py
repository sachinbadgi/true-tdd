import json
from pathlib import Path


class TraceabilityPlugin:
    """
    Pytest plugin that writes test results and @pytest.mark.requirement tags
    to a local JSON traceability store after each test call phase.

    Usage — add to your project's conftest.py:

        from autotest.conftest_plugin import TraceabilityPlugin

        def pytest_configure(config):
            config.pluginmanager.register(TraceabilityPlugin())
    """

    def __init__(self, store_path: str = "traceability_store.json"):
        self.store_path = Path(store_path)

    def _load(self) -> dict:
        if self.store_path.exists():
            return json.loads(self.store_path.read_text())
        return {"tests": {}}

    def _save(self, data: dict) -> None:
        self.store_path.write_text(json.dumps(data, indent=2))

    def pytest_runtest_logreport(self, report) -> None:
        if report.when != "call":
            return
        req_ids = [m.args[0] for m in report.item.iter_markers("requirement")]
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
