import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Register the traceability plugin
from autotest.conftest_plugin import TraceabilityPlugin
import pytest

# Resolve the store path relative to this conftest's directory so it
# works whether pytest is run from the repo root or from example/.
_STORE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "traceability_store.json")

@pytest.fixture(autouse=True, scope="session")
def _traceability_plugin(request):
    plugin = TraceabilityPlugin(store_path=_STORE_PATH)
    request.config.pluginmanager.register(plugin)
