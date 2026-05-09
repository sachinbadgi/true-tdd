import re
from pathlib import Path

# Matches both heading-style (## REQ-001: ...) and bold-style (**REQ-001**: ...) PRD formats.
# This is the single source of truth for PRD requirement parsing across the framework.
REQ_PATTERN = re.compile(
    r"^(?:#{1,6}\s+)?(?:-\s+\*\*)?(REQ-\d+)(?:\*\*)?:\s*(.+)$",
    re.MULTILINE,
)


def parse_requirements(markdown: str) -> list[dict[str, str]]:
    return [{"id": m.group(1), "description": m.group(2).strip()} for m in REQ_PATTERN.finditer(markdown)]


def parse_prd_file(path: str) -> list[dict[str, str]]:
    """Parse a Markdown PRD file and return a list of requirement dicts.

    Args:
        path: Path to the PRD Markdown file.

    Returns:
        List of {"id": str, "description": str} dicts.

    Raises:
        FileNotFoundError: If the PRD file does not exist at the given path.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"PRD file not found: '{path}'. Pass --prd with the correct path to your Markdown requirements file."
        )
    return parse_requirements(p.read_text())
