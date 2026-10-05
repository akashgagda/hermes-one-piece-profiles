#!/usr/bin/env python3
"""Validate persona source JSON files against the collection schema.

Usage:
    python3 tools/check_source.py source/foo.json [source/bar.json ...]
    python3 tools/check_source.py            # checks every file under source/

Exits non-zero and prints every problem found. Imports the same field
contract the builder uses, so a file that passes here builds.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from build_collection import (  # noqa: E402
    ARRAY_FIELDS,
    MIN_ITEMS,
    REQUIRED_FIELDS,
    SERIES_LABELS,
    validate_persona,
)


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    args = sys.argv[1:]
    paths = [pathlib.Path(a) for a in args] or sorted((root / "source").glob("*.json"))
    problems: list[str] = []
    total = 0
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{path}: not valid JSON ({exc})")
            continue
        if not isinstance(data, list):
            problems.append(f"{path}: top level must be an array of persona objects")
            continue
        for persona in data:
            if not isinstance(persona, dict):
                problems.append(f"{path}: every entry must be an object")
                continue
            try:
                validate_persona(persona, path)
            except ValueError as exc:
                problems.append(str(exc))
                continue
            total += 1
            counts = ", ".join(f"{f}={len(persona[f])}" for f in sorted(ARRAY_FIELDS))
            print(f"OK  {persona['series']:<26} {persona['slug']:<28} {counts}")
    if problems:
        print("\nPROBLEMS")
        for item in problems:
            print(f"  - {item}")
        return 1
    print(f"\n{total} persona(s) valid across {len(paths)} file(s).")
    print(f"Allowed series: {', '.join(SERIES_LABELS)}")
    print(f"Minimum items: {MIN_ITEMS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
