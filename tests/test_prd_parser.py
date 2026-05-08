import textwrap
from autotest.prd_parser import parse_requirements, parse_prd_file

PRD = textwrap.dedent("""
    # My Product

    ## REQ-101: User must register with a valid email
    Some body text.

    ### REQ-102: System rejects users under 18

    ## Not a requirement - no REQ prefix
""")


def test_extracts_req_ids():
    reqs = parse_requirements(PRD)
    ids = [r["id"] for r in reqs]
    assert "REQ-101" in ids
    assert "REQ-102" in ids


def test_excludes_non_tagged_headers():
    reqs = parse_requirements(PRD)
    assert len(reqs) == 2


def test_captures_description():
    reqs = parse_requirements(PRD)
    r = next(r for r in reqs if r["id"] == "REQ-101")
    assert "valid email" in r["description"]


def test_empty_prd_returns_empty_list():
    assert parse_requirements("# Title\n\n## No requirements here") == []


def test_parse_prd_file(tmp_path):
    prd_file = tmp_path / "prd.md"
    prd_file.write_text("## REQ-201: File-based requirement\n")
    reqs = parse_prd_file(str(prd_file))
    assert reqs[0]["id"] == "REQ-201"
