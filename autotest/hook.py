"""
autotest/hook.py
----------------
CLI for installing/uninstalling the autotest git post-commit hook.

Usage:
  python -m autotest.hook install [--project /path/to/project]
  python -m autotest.hook uninstall [--project /path/to/project]
  python -m autotest.hook status [--project /path/to/project]
"""
import click
import shutil
import stat
import subprocess
from pathlib import Path


HOOK_TEMPLATE = Path(__file__).parent / "templates" / "post-commit.hook"
CFG_TEMPLATE = Path(__file__).parent / "templates" / "autotest.cfg"


def _git_root(project: str) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=project, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Not a git repo: {project}")
    return Path(result.stdout.strip())


@click.group()
def cli():
    """Autotest git hook management."""
    pass


@cli.command()
@click.option("--project", default=".", help="Path to target git project root")
def install(project):
    """Install the autotest post-commit hook into a project."""
    try:
        root = _git_root(project)
    except RuntimeError as e:
        click.echo(f"❌ {e}")
        return

    hooks_dir = root / ".git" / "hooks"
    hook_path = hooks_dir / "post-commit"

    # First install graphify's hook (it runs graphify update on commit)
    try:
        subprocess.run(["graphify", "hook", "install"], cwd=str(root), check=True)
        click.echo("  ✅ Graphify hook installed")
    except (subprocess.CalledProcessError, FileNotFoundError):
        click.echo("  ⚠️  graphify not found — skipping graphify hook")

    # Read the graphify-installed hook (or create fresh)
    existing = ""
    if hook_path.exists():
        existing = hook_path.read_text()

    # Append autotest validation block if not already present
    MARKER = "# === autotest gate ==="
    if MARKER in existing:
        click.echo("  ✅ autotest gate already in post-commit hook")
    else:
        autotest_block = "\n" + MARKER + "\n" + HOOK_TEMPLATE.read_text()
        with open(hook_path, "a") as f:
            f.write(autotest_block)
        # Ensure executable
        hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        click.echo("  ✅ autotest gate appended to post-commit hook")

    # Copy autotest.cfg template to project root if not present
    cfg_dst = root / "autotest.cfg"
    if not cfg_dst.exists():
        shutil.copy(CFG_TEMPLATE, cfg_dst)
        click.echo(f"  📋 autotest.cfg written to {cfg_dst} — edit to configure")
    else:
        click.echo(f"  ✅ autotest.cfg already exists at {cfg_dst}")

    click.echo(f"\n  Hook installed in {hook_path}")
    click.echo("  Every `git commit` will now run the autotest reliability gate.")


@cli.command()
@click.option("--project", default=".", help="Path to target git project root")
def uninstall(project):
    """Remove the autotest gate from the post-commit hook."""
    try:
        root = _git_root(project)
    except RuntimeError as e:
        click.echo(f"❌ {e}")
        return

    hook_path = root / ".git" / "hooks" / "post-commit"
    MARKER = "# === autotest gate ==="

    if not hook_path.exists():
        click.echo("  No post-commit hook found.")
        return

    content = hook_path.read_text()
    if MARKER not in content:
        click.echo("  autotest gate is not installed.")
        return

    # Remove everything from the marker onward
    new_content = content[:content.index(MARKER)].rstrip() + "\n"
    hook_path.write_text(new_content)
    click.echo("  ✅ autotest gate removed from post-commit hook.")


@cli.command()
@click.option("--project", default=".", help="Path to target git project root")
def status(project):
    """Check whether the autotest hook is installed."""
    try:
        root = _git_root(project)
    except RuntimeError as e:
        click.echo(f"❌ {e}")
        return

    hook_path = root / ".git" / "hooks" / "post-commit"
    MARKER = "# === autotest gate ==="

    graphify_result = subprocess.run(
        ["graphify", "hook", "status"], cwd=str(root), capture_output=True, text=True
    )
    click.echo(graphify_result.stdout.strip())

    if hook_path.exists() and MARKER in hook_path.read_text():
        click.echo("autotest gate: installed ✅")
    else:
        click.echo("autotest gate: not installed")


if __name__ == "__main__":
    cli()
