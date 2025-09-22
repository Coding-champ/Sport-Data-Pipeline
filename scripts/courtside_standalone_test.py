"""DEPRECATED: courtside_standalone_test.py

Use unified CLI instead:
  python scripts/courtside_debug.py --mode fixtures
"""

from __future__ import annotations


def main() -> None:  # pragma: no cover
    raise RuntimeError(
        "courtside_standalone_test.py deprecated. Use 'python scripts/courtside_debug.py --mode fixtures'."
    )


if __name__ == "__main__":  # pragma: no cover
    main()
