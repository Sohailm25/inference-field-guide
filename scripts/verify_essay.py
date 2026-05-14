#!/usr/bin/env python3
# ABOUTME: Deprecated. Essay-vs-calculator consistency is now a parametrized pytest.
# ABOUTME: See calculator/tests/test_essay_consistency.py.

"""Deprecated entry point.

Essay numerical-claim verification has moved to a proper pytest module:

    calculator/tests/test_essay_consistency.py

Run it with:

    .venv/bin/pytest calculator/tests/test_essay_consistency.py -v

The new test parametrizes every ClaimSpec, so an essay drift surfaces as
the specific failing claim rather than a single StopIteration crash.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "scripts/verify_essay.py is deprecated.\n"
        "Run the replacement pytest instead:\n"
        "  .venv/bin/pytest calculator/tests/test_essay_consistency.py -v",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
