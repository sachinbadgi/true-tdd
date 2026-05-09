# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.2.x   | ✅ Yes    |
| < 0.2   | ❌ No     |

## Reporting a Vulnerability

**Please do not report security vulnerabilities via GitHub Issues.**

Report vulnerabilities by opening a [GitHub Security Advisory](https://github.com/truetdd/true-tdd/security/advisories/new).

Include:
- A description of the vulnerability
- Steps to reproduce
- Python version and `true-tdd` version (`python -c "import truetdd; print(truetdd.__version__)"`)
- Potential impact assessment

You can expect an acknowledgement within **72 hours** and a fix or mitigation within **14 days** for confirmed vulnerabilities.

## Trust Boundaries

true-tdd is a local developer tool. Key trust assumptions:

- **PRD files** (`prd.md`) are trusted developer-authored content. The parser applies a regex pattern to Markdown; no code is executed from PRD content.
- **testdata.yaml** is trusted developer-authored content. YAML is loaded via `yaml.safe_load()` — not `yaml.load()`.
- **graphify** binary must be installed from a trusted source (`uv tool install graphify`). true-tdd invokes it via subprocess with list-form arguments (no `shell=True`).
- **mutmut** binary must be installed in the same virtualenv. Mutation testing by definition modifies source files temporarily — always run in a controlled environment.
- **`.truetdd_backup/`** contains copies of your test files. These are written and read by the injector and are not exposed to the network.

## Security Considerations for CI/CD Use

When using `truetdd-hook` or running `run_pipeline.sh` in CI:
- Ensure `graphify` and `mutmut` are pinned to known versions
- Do not run the pipeline against untrusted third-party source code
- The `truetdd-inject` subcommand temporarily modifies test files — ensure your CI uses a clean working directory
