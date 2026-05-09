"""
True TDD Delta Manager
Leverages Graphify's manifest to detect exactly which source files changed since the last pipeline run.
Outputs the delta to truetdd_delta.txt, allowing run_pipeline.sh to run lightning-fast targeted mutations.
"""

import json
import sys
from pathlib import Path

import click


def generate_delta(
    manifest_path: str = "graphify-out/manifest.json",
    last_manifest_path: str = "graphify-out/truetdd_last_manifest.json",
    delta_out: str = "truetdd_delta.txt",
) -> None:
    """Detect changed source files since the last pipeline run.

    Args:
        manifest_path: Path to graphify manifest.json (injectable for testing).
        last_manifest_path: Path to the cached last-run manifest (injectable for testing).
        delta_out: Destination file path for the delta list (injectable for testing).
    """
    _manifest = Path(manifest_path)
    _last_manifest = Path(last_manifest_path)
    _delta_out = Path(delta_out)

    if not _manifest.exists():
        print("No graphify manifest found. Running full mutation scope.", file=sys.stderr)
        return

    current = json.loads(_manifest.read_text())
    last = json.loads(_last_manifest.read_text()) if _last_manifest.exists() else {}

    changed_files = []

    for filepath, data in current.items():
        if not filepath.endswith(".py"):
            continue

        # Ignore test files for mutation targeting (mutmut only mutates source)
        if "tests/" in filepath or "test_" in Path(filepath).name:
            continue

        # Ignore infrastructure
        if "conftest.py" in filepath or "sitecustomize.py" in filepath:
            continue

        # If new file or hash changed
        if filepath not in last or last[filepath].get("hash") != data.get("hash"):
            changed_files.append(filepath)

    # Save the delta list
    if changed_files:
        _delta_out.write_text("\n".join(changed_files) + "\n")
        print(f"⚡ Delta Manager: Found {len(changed_files)} changed source files.", file=sys.stderr)
    else:
        _delta_out.write_text("")  # Write empty file to signal "no changes"
        print("⚡ Delta Manager: No source files changed. Targeted scope is empty.", file=sys.stderr)

    # Update the cached manifest for the NEXT run
    _last_manifest.write_text(json.dumps(current, indent=2))


@click.command()
@click.option(
    "--manifest", default="graphify-out/manifest.json", show_default=True, help="Path to graphify manifest.json"
)
@click.option(
    "--last-manifest",
    "last_manifest",
    default="graphify-out/truetdd_last_manifest.json",
    show_default=True,
    help="Path to cached last-run manifest",
)
@click.option("--output", default="truetdd_delta.txt", show_default=True, help="Output path for delta file")
def cli(manifest: str, last_manifest: str, output: str) -> None:
    """Detect changed source files since last pipeline run and write truetdd_delta.txt."""
    generate_delta(manifest_path=manifest, last_manifest_path=last_manifest, delta_out=output)


if __name__ == "__main__":
    cli()
