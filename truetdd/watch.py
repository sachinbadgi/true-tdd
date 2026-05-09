#!/usr/bin/env python3
"""
truetdd/watch.py
-----------------
Wraps `graphify watch` with a truetdd pipeline hook.

Whenever graphify detects a code change and rebuilds graph.json,
this script fires the deterministic validation step and prints
a terse reliability summary — giving instant feedback on whether
a new function is covered, required, or orphaned.

Usage::

    truetdd-watch --prd prd.md --threshold 100
"""

import json
import subprocess
import time
from pathlib import Path

import click
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class GraphChangedHandler(FileSystemEventHandler):
    """Fires the truetdd validation pipeline when graph.json is updated."""

    def __init__(self, prd, store, graph, threshold, cooldown=3.0):
        self.prd = prd
        self.store = store
        self.graph = graph
        self.threshold = threshold
        self.cooldown = cooldown
        self._last_fired = 0

    def on_modified(self, event):
        # Only react to graph.json being updated by graphify
        if not event.src_path.endswith("graph.json"):
            return

        now = time.time()
        if now - self._last_fired < self.cooldown:
            return  # debounce
        self._last_fired = now

        print("\n⚡ Graph updated — running truetdd validation...")
        self._run_pytest()
        self._run_mutation_bridge()
        self._run_report()

    def _run_pytest(self):
        result = subprocess.run(
            ["python", "-m", "pytest", "--cov=src", "--cov-context=test", "--cov-report=json", "-q", "--tb=no"],
            capture_output=True,
            text=True,
        )
        lines = [line for line in result.stdout.splitlines() if "passed" in line or "failed" in line or "error" in line]
        print("  pytest: " + (lines[-1] if lines else "no output"))

    def _run_mutation_bridge(self):
        subprocess.run(
            [
                "truetdd-bridge",
                "--meta-dir",
                "mutants",
                "--coverage",
                "coverage.json",
                "--store",
                self.store,
                "--output",
                "mutation_results.json",
            ],
            capture_output=True,
            text=True,
        )

    def _run_report(self):
        result = subprocess.run(
            [
                "python",
                "-m",
                "truetdd.report",
                "--prd",
                self.prd,
                "--store",
                self.store,
                "--graph",
                self.graph,
                "--threshold",
                str(self.threshold),
                "--json-out",
                "loop_feedback.json",
            ],
            capture_output=True,
            text=True,
        )

        # Parse and print summary line
        fb = Path("loop_feedback.json")
        if fb.exists():
            data = json.loads(fb.read_text())
            score = data.get("score", 0)
            passed = data.get("passed", False)
            orphans = data.get("orphaned_functions", [])

            icon = "✅" if passed else "🔴"
            print(f"  {icon} Reliability: {score}% — threshold: {self.threshold}%")
            if orphans:
                print(f"  👻 Untraceable: {', '.join(orphans)}")

            failing = [rid for rid, v in data.get("requirements", {}).items() if v["status"] != "VERIFIED"]
            if failing:
                print(f"  ❌ Non-verified requirements: {', '.join(failing)}")
        else:
            print(result.stdout)


@click.command()
@click.option("--src", default=".", show_default=True, help="Root directory for graphify watch")
@click.option("--prd", required=True, help="Path to PRD markdown")
@click.option("--store", default="traceability_store.json", show_default=True)
@click.option("--graph", default="graphify-out/graph.json", show_default=True)
@click.option("--threshold", type=float, default=100.0, show_default=True)
def cli(src: str, prd: str, store: str, graph: str, threshold: float) -> None:
    """Watch graph.json changes and fire the truetdd reliability gate on each rebuild."""
    handler = GraphChangedHandler(
        prd=prd,
        store=store,
        graph=graph,
        threshold=threshold,
    )

    observer = Observer()
    graph_dir = str(Path(graph).parent)
    observer.schedule(handler, path=graph_dir, recursive=False)
    observer.start()

    click.echo(f"\U0001f52d truetdd-watch running — monitoring: {graph_dir}")
    click.echo(f"   PRD:       {prd}")
    click.echo(f"   Store:     {store}")
    click.echo(f"   Threshold: {threshold}%")
    click.echo("   Ctrl+C to stop\n")

    gw = subprocess.Popen(["graphify", "watch", src])

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        gw.terminate()

    observer.join()


if __name__ == "__main__":
    cli()
