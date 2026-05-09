"""
tests/test_graph_sync.py

Unit tests for truetdd.graph_sync.sync_graph().

Since sync_graph() uses module-level Path constants (CANONICAL_GRAPH / ENRICHED_GRAPH),
tests use monkeypatch to redirect file I/O to tmp_path.
"""

import json

import pytest

from truetdd import graph_sync as gs


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


@pytest.fixture(autouse=True)
def patch_paths(tmp_path, monkeypatch):
    """Redirect CANONICAL_GRAPH and ENRICHED_GRAPH to tmp_path."""
    canonical = tmp_path / "graphify-out" / "graph.json"
    enriched = tmp_path / "graphify-out" / "graph_enriched.json"
    monkeypatch.setattr(gs, "CANONICAL_GRAPH", canonical)
    monkeypatch.setattr(gs, "ENRICHED_GRAPH", enriched)
    return {"canonical": canonical, "enriched": enriched, "tmp": tmp_path}


class TestSyncGraphNoArtifacts:
    def test_no_graph_json_prints_warning(self, capsys):
        """sync_graph() exits gracefully when graph.json is missing."""
        gs.sync_graph()
        assert "No graph.json found" in capsys.readouterr().err

    def test_no_mutation_results_still_writes_graph(self, tmp_path, patch_paths):
        """sync_graph() with no mutation_results.json still writes the graph unchanged."""
        canonical = patch_paths["canonical"]
        graph_data = {"nodes": [{"id": "1", "label": "add()"}], "links": []}
        _write_json(canonical, graph_data)

        gs.sync_graph()

        assert canonical.exists()
        written = json.loads(canonical.read_text())
        assert written["nodes"][0]["label"] == "add()"


class TestSyncGraphEnrichment:
    def test_enriched_backup_written(self, tmp_path, patch_paths):
        """sync_graph() writes a backup to graph_enriched.json."""
        canonical = patch_paths["canonical"]
        enriched = patch_paths["enriched"]
        _write_json(canonical, {"nodes": [], "links": []})

        gs.sync_graph()

        assert enriched.exists()

    def test_canonical_and_enriched_have_same_content(self, tmp_path, patch_paths):
        """Both graph.json and graph_enriched.json should be identical after sync."""
        canonical = patch_paths["canonical"]
        enriched = patch_paths["enriched"]
        _write_json(canonical, {"nodes": [{"id": "x"}], "links": []})

        gs.sync_graph()

        assert canonical.read_text() == enriched.read_text()

    def test_req_status_injected_into_test_node(self, tmp_path, patch_paths, monkeypatch):
        """Requirement status from loop_feedback.json is injected onto matching test nodes."""
        canonical = patch_paths["canonical"]
        _write_json(
            canonical,
            {
                "nodes": [
                    {
                        "id": "1",
                        "label": "test_add()",
                        "source_file": "tests/test_calc.py",
                        "file_type": "code",
                    }
                ],
                "links": [],
            },
        )

        # Write traceability store
        store = {
            "tests": {
                "tests/test_calc.py::test_add": {
                    "requirement_ids": ["REQ-101"],
                }
            }
        }
        fb = {
            "requirements": {
                "REQ-101": {"status": "VERIFIED"},
            }
        }
        _write_json(tmp_path / "traceability_store.json", store)
        _write_json(tmp_path / "loop_feedback.json", fb)

        # Patch file I/O to read from tmp_path
        monkeypatch.chdir(tmp_path)
        gs.sync_graph()

        result = json.loads(canonical.read_text())
        node = result["nodes"][0]
        # The node should now have truetdd_req_status injected
        assert "truetdd_req_status" in node
        assert node["truetdd_req_status"] == "VERIFIED"

    def test_idempotent_on_double_run(self, tmp_path, patch_paths, monkeypatch):
        """Running sync_graph() twice produces the same result (no double-enrichment)."""
        canonical = patch_paths["canonical"]
        _write_json(canonical, {"nodes": [{"id": "1", "label": "fn()"}], "links": []})
        monkeypatch.chdir(tmp_path)

        gs.sync_graph()
        content_after_first = canonical.read_text()
        gs.sync_graph()
        content_after_second = canonical.read_text()

        assert content_after_first == content_after_second
