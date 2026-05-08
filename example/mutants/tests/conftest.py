import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Register the traceability plugin
from autotest.conftest_plugin import TraceabilityPlugin
import pytest

@pytest.fixture(autouse=True, scope="session")
def _traceability_plugin(request):
    plugin = TraceabilityPlugin(store_path="example/traceability_store.json")
    request.config.pluginmanager.register(plugin)
