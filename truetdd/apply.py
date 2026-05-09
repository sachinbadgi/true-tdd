"""
truetdd/apply.py

Automatically merges generated testdata stubs from loop_feedback.json into testdata.yaml.
This closes the WEAK_DATA loop by prepopulating boundary cases so the LLM loop just
has to fill in the expected values (???).

Usage:
  truetdd-apply --feedback loop_feedback.json --testdata testdata.yaml
"""

import json
from pathlib import Path

import click
import yaml
from typing import Any


@click.command()
@click.option("--feedback", required=True, help="Path to loop_feedback.json")
@click.option("--testdata", required=True, help="Path to testdata.yaml")
def cli(feedback: str, testdata: str):
    """Auto-apply suggested testdata from loop_feedback.json into testdata.yaml."""
    fb_path = Path(feedback)
    if not fb_path.exists():
        click.echo(f"Feedback file not found: {feedback}")
        return

    try:
        data = json.loads(fb_path.read_text())
    except Exception as e:
        click.echo(f"Failed to parse {feedback}: {e}")
        return

    suggested = data.get("suggested_testdata", {})
    if not suggested:
        click.echo("No suggested testdata to apply.")
        return

    td_path = Path(testdata)

    # Load existing testdata if it exists
    existing_data: dict[str, Any] = {}
    if td_path.exists():
        try:
            with open(td_path, "r") as f:
                existing_data = yaml.safe_load(f) or {}
        except Exception as e:
            click.echo(f"Failed to parse existing {testdata}: {e}")
            return

    if "cases" not in existing_data:
        existing_data["cases"] = {}

    cases_block = existing_data["cases"]
    applied_count = 0

    for fn_name, stub in suggested.items():
        if fn_name in cases_block:
            continue  # Do not overwrite existing cases

        # Remove the _note before writing, but we leave _comment keys in the cases
        # so the LLM loop can see what they are.
        # Actually, the suggester outputs `_comment` inside cases and `_note` at the top level.
        # We can write it as is, and the LLM loop can strip `_comment`.
        cases_block[fn_name] = stub
        applied_count += 1

    if applied_count > 0:
        td_path.parent.mkdir(parents=True, exist_ok=True)
        # Using yaml.dump with default_flow_style=False to produce readable YAML
        with open(td_path, "w") as f:
            yaml.dump(existing_data, f, default_flow_style=False, sort_keys=False)
        click.echo(f"✅ Auto-applied {applied_count} testdata stubs into {testdata}")
    else:
        click.echo("No new testdata stubs were needed.")


if __name__ == "__main__":
    cli()
