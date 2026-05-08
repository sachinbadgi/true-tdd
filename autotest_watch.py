#!/usr/bin/env python3
"""
autotest_watch.py
-----------------
Wraps `graphify watch` with an autotest pipeline hook.

Whenever graphify detects a code change and rebuilds graph.json,
this script fires the deterministic validation step and prints
a terse reliability summary — giving instant feedback on whether
a new function is covered, required, or orphaned.

Usage (from within your project directory):
  python autotest_watch.py \
    --src example \
    --prd example/prd.md \
    --store example/traceability_store.json \
    --graph example/graphify-out/graph.json \
    --threshold 100
"""

import subprocess
import time
import json
import sys
import argparse
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class GraphChangedHandler(FileSystemEventHandler):
    """Fires the autotest validation pipeline when graph.json is updated."""

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

        print("\n⚡ Graph updated — running autotest validation...")
        self._run_pytest()
        self._run_mutation_bridge()
        self._run_report()

    def _run_pytest(self):
        result = subprocess.run(
            ["python", "-m", "pytest",
             "--cov=src", "--cov-context=test", "--cov-report=json", "-q", "--tb=no"],
            capture_output=True, text=True
        )
        lines = [l for l in result.stdout.splitlines() if "passed" in l or "failed" in l or "error" in l]
        print("  pytest: " + (lines[-1] if lines else "no output"))

    def _run_mutation_bridge(self):
        subprocess.run(
            ["python", "-m", "autotest.mutation_bridge",
             "--meta-dir", "mutants",
             "--coverage", "coverage.json",
             "--store", self.store,
             "--output", "mutation_results.json"],
            capture_output=True, text=True
        )

    def _run_report(self):
        result = subprocess.run(
            ["python", "-m", "autotest.report",
             "--prd", self.prd,
             "--store", self.store,
             "--graph", self.graph,
             "--threshold", str(self.threshold),
             "--json-out", "loop_feedback.json"],
            capture_output=True, text=True
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
            
            failing = [rid for rid, v in data.get("requirements", {}).items()
                       if v["status"] != "VERIFIED"]
            if failing:
                print(f"  ❌ Non-verified requirements: {', '.join(failing)}")
        else:
            print(result.stdout)


def main():
    parser = argparse.ArgumentParser(description="Autotest Watch — Graph-triggered validation")
    parser.add_argument("--src", default=".", help="Root directory for graphify watch")
    parser.add_argument("--prd", required=True, help="Path to PRD markdown")
    parser.add_argument("--store", default="traceability_store.json")
    parser.add_argument("--graph", default="graphify-out/graph.json")
    parser.add_argument("--threshold", type=float, default=100.0)
    args = parser.parse_args()

    handler = GraphChangedHandler(
        prd=args.prd,
        store=args.store,
        graph=args.graph,
        threshold=args.threshold
    )

    observer = Observer()
    # Watch the graphify-out directory for graph.json changes
    graph_dir = str(Path(args.graph).parent)
    observer.schedule(handler, path=graph_dir, recursive=False)
    observer.start()

    print(f"🔭 autotest-watch running — monitoring: {graph_dir}")
    print(f"   PRD:       {args.prd}")
    print(f"   Store:     {args.store}")
    print(f"   Threshold: {args.threshold}%")
    print("   Ctrl+C to stop\n")

    # Launch graphify watch in background
    gw = subprocess.Popen(["graphify", "watch", args.src])

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        gw.terminate()

    observer.join()


if __name__ == "__main__":
    main()
