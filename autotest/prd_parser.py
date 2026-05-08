import re
from typing import List, Dict

REQ_PATTERN = re.compile(r'^#{1,6}\s+(REQ-\d+):\s*(.+)$', re.MULTILINE)


def parse_requirements(markdown: str) -> List[Dict[str, str]]:
    return [
        {"id": m.group(1), "description": m.group(2).strip()}
        for m in REQ_PATTERN.finditer(markdown)
    ]


def parse_prd_file(path: str) -> List[Dict[str, str]]:
    with open(path) as f:
        return parse_requirements(f.read())
