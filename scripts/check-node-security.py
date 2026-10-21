#!/usr/bin/env python3
"""Reject affected or unsupported Node releases before running project tools."""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import date, datetime, timezone


ADVISORY = "https://nodejs.org/en/blog/vulnerability/october-2026-security-releases"
MINIMUM = {22: (22, 23, 4), 24: (24, 22, 1), 26: (26, 12, 1)}
EXPIRY = {22: date(2027, 4, 30), 24: date(2028, 4, 30), 26: date(2029, 4, 30)}


def check_version(value: str, *, today: date | None = None) -> None:
    """Accept supported stable releases containing all October 21 fixes."""
    match = re.fullmatch(r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value)
    if match is None:
        raise ValueError(f"malformed or prerelease Node version: {value!r}")
    version = tuple(int(part) for part in match.groups())
    minimum = MINIMUM.get(version[0])
    if minimum is None:
        raise ValueError(f"unsupported Node major: {version[0]}. Use 22.23.4, 24.22.1, or 26.12.1 or newer in those lines")
    current_date = datetime.now(timezone.utc).date() if today is None else today
    if current_date >= EXPIRY[version[0]]:
        raise ValueError(f"expired Node major {version[0]} as of {EXPIRY[version[0]].isoformat()} UTC: review and upgrade the policy")
    if version < minimum:
        required = ".".join(str(part) for part in minimum)
        raise ValueError(f"affected Node version {value}: require >= {required} in major {version[0]}")


def main() -> int:
    if len(sys.argv) != 1:
        print("FAIL: this guard checks the actual Node executable and accepts no version override", file=sys.stderr)
        return 1
    try:
        result = subprocess.run(
            ["node", "--version"], stdin=subprocess.DEVNULL, capture_output=True,
            text=True, timeout=10, check=True,
        )
        # Only the normal terminal newline is permitted, not arbitrary whitespace.
        version = result.stdout.removesuffix("\n").removesuffix("\r")
        check_version(version)
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        print(f"FAIL: {error}\nNode security policy: {ADVISORY}", file=sys.stderr)
        return 1
    print(f"Node security policy: passed actual runtime {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
