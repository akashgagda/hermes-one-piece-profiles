#!/usr/bin/env python3
"""Structural and content checks for generated profile distributions."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog.json"
PROFILES = ROOT / "profiles"
EXPECTED_SERIES = {"Straw-Hats", "Worst-Generation", "Marines", "Emperors-and-Warlords", "Allies-and-Revolutionaries"}
REQUIRED_FILES = {"distribution.yaml", "SOUL.md", "config.yaml", "README.md"}
FORBIDDEN_TRACKED_NAMES = {
    ".env", ".env.EXAMPLE", "auth.json", "state.db", "state.db-wal",
    "state.db-shm", "hermes_state.db", "response_store.db", "gateway.pid",
    "gateway_state.json", "processes.json", "auth.lock", ".update_check",
    "errors.log", ".hermes_history",
}
FORBIDDEN_TRACKED_DIRS = {
    "memories", "sessions", "logs", "plans", "workspace", "home", "local",
    "browser_screenshots", "state-snapshots", "checkpoints", "sandboxes",
    "backups", "cache", "node_modules",
}
SOUL_SECTIONS = {
    "## Identity",
    "## Non-Negotiable Boundaries",
    "## Relationship With the User",
    "## Voice",
    "## Worldview",
    "## Operating Method",
    "## Strengths to Emphasize",
    "## Under Pressure",
    "## Disagreement",
    "## Behavioral Rules",
    "## Canon Anchors",
    "## Blind Spots",
    "## Avoid",
    "## Baseline Hermes Contract",
}
SOUL_INVARIANTS = {
    "Never claim to be the fictional person",
    "Treat the user as a competent collaborator",
    "grant no real-world credentials",
    "authorization only for its clearly stated scope",
    "require a clearly identified user-controlled target or credible authorization",
    "Respect the autonomy, privacy, safety, and rights of third parties",
    "Never use coercion, covert persuasion, impersonation, fabricated evidence",
    "Never cultivate emotional or romantic exclusivity, dependency, or isolation",
    "preserve platform approval controls",
    "avoid diagnosis, prescription, guarantees, or certification",
    "rather than fabricating success or silently changing the goal",
    "Use tools when they improve correctness",
}


def fail(message: str) -> None:
    raise SystemExit(message)


def load_catalog() -> list[dict[str, Any]]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        fail("catalog.json must be a non-empty array")
    return data


def validate() -> None:
    catalog = load_catalog()
    slugs = [p["slug"] for p in catalog]
    if len(slugs) != len(set(slugs)):
        fail("catalog has duplicate slugs")
    series_counts = Counter(p["series"] for p in catalog)
    if set(series_counts) != EXPECTED_SERIES:
        fail(f"series mismatch: {series_counts}")

    profile_dirs = {p.name for p in PROFILES.iterdir() if p.is_dir()}
    if profile_dirs != set(slugs):
        fail(f"profile directory mismatch: missing={set(slugs)-profile_dirs}, extra={profile_dirs-set(slugs)}")

    all_souls: dict[str, str] = {}
    for persona in catalog:
        slug = persona["slug"]
        root = PROFILES / slug
        missing = [name for name in REQUIRED_FILES if not (root / name).is_file()]
        if missing:
            fail(f"{slug}: missing {missing}")
        forbidden = [p for p in root.rglob("*") if p.is_file() and p.name in FORBIDDEN_TRACKED_NAMES]
        if forbidden:
            fail(f"{slug}: forbidden files: {forbidden}")
        forbidden_dirs = [p for p in root.rglob("*") if p.is_dir() and p.name in FORBIDDEN_TRACKED_DIRS]
        if forbidden_dirs:
            fail(f"{slug}: forbidden directories: {forbidden_dirs}")
        symlinks = [p for p in root.rglob("*") if p.is_symlink()]
        if symlinks:
            fail(f"{slug}: symlinks are not allowed: {symlinks}")

        manifest = yaml.safe_load((root / "distribution.yaml").read_text(encoding="utf-8"))
        if manifest.get("name") != slug:
            fail(f"{slug}: manifest name mismatch")
        if manifest.get("version") != "1.0.0":
            fail(f"{slug}: unexpected version")
        if manifest.get("author") != "akashgagda":
            fail(f"{slug}: unexpected author")
        if manifest.get("distribution_owned") != ["SOUL.md", "config.yaml", "distribution.yaml"]:
            fail(f"{slug}: unsafe distribution_owned contract")

        if (root / "skins").exists():
            fail(f"{slug}: the collection ships no skins; remove the skins directory")

        config = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
        if config != {"model": ""}:
            fail(f"{slug}: config should leave model unset and impose no skin")

        soul = (root / "SOUL.md").read_text(encoding="utf-8")
        if len(soul) < 3000:
            fail(f"{slug}: SOUL is too shallow ({len(soul)} chars)")
        missing_sections = SOUL_SECTIONS - set(re.findall(r"^## .+$", soul, flags=re.MULTILINE))
        if missing_sections:
            fail(f"{slug}: SOUL missing sections {sorted(missing_sections)}")
        missing_invariants = {text for text in SOUL_INVARIANTS if text not in soul}
        if missing_invariants:
            fail(f"{slug}: SOUL missing invariants {sorted(missing_invariants)}")
        all_souls[slug] = soul

    # Profiles must differ by substance rather than only character names.
    normalized = {
        slug: re.sub(r"[^a-z]+", " ", text.lower())
        for slug, text in all_souls.items()
    }
    for slug, text in normalized.items():
        if len(set(text.split())) < 180:
            fail(f"{slug}: vocabulary is too thin for a comprehensive persona")

    print(f"Validated {len(catalog)} profiles: " + ", ".join(f"{s}={series_counts[s]}" for s in sorted(EXPECTED_SERIES)))


if __name__ == "__main__":
    validate()
