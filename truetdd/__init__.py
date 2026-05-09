from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("true-tdd")
except PackageNotFoundError:
    # Package not installed (e.g., running from source without pip install -e .)
    __version__ = "unknown"
