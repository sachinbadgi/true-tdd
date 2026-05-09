import json
import multiprocessing
import platform
from pathlib import Path

import pytest


def pytest_configure(config):
    """Pre-set multiprocessing start method to 'fork' on macOS.

    mutmut 3 calls multiprocessing.set_start_method('fork') at module-import
    time inside mutmut/__main__.py (line 1152).  On macOS + Python 3.11+,
    the default start method is 'spawn'.  Once pytest or pytest-cov touches
    multiprocessing during setup, the context locks and mutmut's import
    raises RuntimeError: context has already been set.

    Setting 'fork' here (with force=True so it survives subsequent calls)
    makes the mutmut 3 trampoline import succeed without error.
    """
    if platform.system() == "Darwin":
        try:
            multiprocessing.set_start_method("fork", force=True)
        except (RuntimeError, AttributeError):
            pass  # Python version doesn't support force= — skip silently


class TraceabilityPlugin:
    def __init__(self, store_path: str = "traceability_store.json"):
        # Make path absolute so it survives directory changes by mutmut
        self.store_path = Path(store_path).absolute()
        # Accumulate results in memory — flushed once at session end
        self._pending: dict = {}

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        report = outcome.get_result()
        if report.when != "call":
            return
        req_ids = [m.args[0] for m in item.iter_markers("requirement")]
        if not req_ids:
            return
        # Buffer the result — no disk I/O here
        self._pending[report.nodeid] = {
            "outcome": report.outcome,
            "duration": report.duration,
            "requirement_ids": req_ids,
            "surviving_mutants_count": 0,
            "is_weak": False,
        }

    def pytest_sessionfinish(self, session, exitstatus):
        """Merge this session's results into the on-disk store (single write)."""
        if not self._pending:
            return
        # Load existing store to preserve mutation bridge data and previous runs
        if self.store_path.exists():
            store = json.loads(self.store_path.read_text())
        else:
            store = {"tests": {}}
        store["tests"].update(self._pending)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(json.dumps(store, indent=2))
