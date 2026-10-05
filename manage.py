#!/usr/bin/env python3
"""Install and update the One Piece Hermes profile collection."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
CATALOG_PATH = ROOT / "catalog.json"
SERIES = ("Straw-Hats", "Worst-Generation", "Marines", "Emperors-and-Warlords", "Allies-and-Revolutionaries")


def load_catalog() -> list[dict[str, Any]]:
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit("catalog.json is missing; run tools/build_collection.py") from exc
    if not isinstance(data, list):
        raise SystemExit("catalog.json is malformed")
    return data


def select_profiles(args: argparse.Namespace, catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_slug = {item["slug"]: item for item in catalog}
    selected: dict[str, dict[str, Any]] = {}
    if args.all:
        selected.update(by_slug)
    for series in args.series or []:
        selected.update({p["slug"]: p for p in catalog if p["series"].lower() == series.lower()})
    for slug in args.targets or []:
        if slug not in by_slug:
            choices = ", ".join(sorted(by_slug))
            raise SystemExit(f"Unknown profile {slug!r}. Available: {choices}")
        selected[slug] = by_slug[slug]
    if not selected:
        raise SystemExit("Select one or more profile slugs, --series SERIES, or --all")
    return sorted(selected.values(), key=lambda p: (SERIES.index(p["series"]), p["name"]))


def print_catalog(catalog: list[dict[str, Any]], series_filter: str | None = None) -> None:
    for series in SERIES:
        if series_filter and series.lower() != series_filter.lower():
            continue
        members = [p for p in catalog if p["series"] == series]
        if not members:
            continue
        print(f"\n{series}")
        print("─" * len(series))
        for p in sorted(members, key=lambda item: item["name"]):
            affinity = "; ".join(p["task_affinities"][:2])
            print(f"  {p['slug']:<24} {p['name']:<24} {affinity}")


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=capture,
            timeout=300,
        )
    except FileNotFoundError as exc:
        raise SystemExit(f"Required command not found: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(f"Command timed out: {' '.join(command)}") from exc


def confirm(action: str, profiles: list[dict[str, Any]], assume_yes: bool) -> None:
    print(f"{action} {len(profiles)} profile(s):")
    for p in profiles:
        print(f"  {p['slug']:<24} {p['name']} ({p['series']})")
    if assume_yes:
        return
    if not sys.stdin.isatty():
        raise SystemExit("Refusing non-interactive operation without --yes")
    answer = input("Continue? [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        raise SystemExit("Cancelled")


def require_hermes(binary: str) -> None:
    if os.path.sep in binary:
        if not Path(binary).is_file():
            raise SystemExit(f"Hermes executable not found: {binary}")
    elif shutil.which(binary) is None:
        raise SystemExit(f"Hermes executable not found on PATH: {binary}")


def profile_digest(profile_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in profile_dir.rglob("*") if p.is_file()):
        digest.update(path.relative_to(profile_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def git_pull() -> None:
    if not (ROOT / ".git").exists():
        print("Collection is not a git checkout; skipping pull.")
        return
    proc = run(["git", "-C", str(ROOT), "pull", "--ff-only"])
    if proc.returncode:
        raise SystemExit("Could not update the collection checkout")


def is_installed(hermes_bin: str, slug: str) -> bool:
    proc = run([hermes_bin, "profile", "info", slug], capture=True)
    return proc.returncode == 0


def install(args: argparse.Namespace, catalog: list[dict[str, Any]]) -> int:
    profiles = select_profiles(args, catalog)
    require_hermes(args.hermes_bin)
    confirm("Install", profiles, args.yes)
    failures: list[str] = []
    for p in profiles:
        command = [
            args.hermes_bin,
            "profile",
            "install",
            str(ROOT / "profiles" / p["slug"]),
            "--name",
            p["slug"],
            "-y",
        ]
        if args.alias:
            command.append("--alias")
        if args.force:
            command.append("--force")
        print(f"\n◆ Installing {p['name']} as {p['slug']}")
        print(f"  Payload SHA-256: {profile_digest(ROOT / 'profiles' / p['slug'])}")
        if run(command).returncode:
            failures.append(p["slug"])
    if failures:
        print(f"\nFailed: {', '.join(failures)}", file=sys.stderr)
        return 1
    print("\nInstalled. Start a new session so the SOUL and skin load together.")
    return 0


def update(args: argparse.Namespace, catalog: list[dict[str, Any]]) -> int:
    require_hermes(args.hermes_bin)
    if args.pull:
        git_pull()
        catalog = load_catalog()
    profiles = select_profiles(args, catalog)
    if args.all:
        profiles = [p for p in profiles if is_installed(args.hermes_bin, p["slug"])]
        if not profiles:
            print("No profiles from this collection are installed.")
            return 0
    confirm("Update", profiles, args.yes)
    failures: list[str] = []
    for p in profiles:
        command = [args.hermes_bin, "profile", "update", p["slug"], "-y"]
        if args.force_config:
            command.append("--force-config")
        print(f"\n◆ Updating {p['name']} ({p['slug']})")
        if run(command).returncode:
            failures.append(p["slug"])
    if failures:
        print(f"\nFailed: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


def add_selection_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("targets", nargs="*", metavar="PROFILE")
    parser.add_argument("--series", action="append", choices=SERIES, help="Select one series; repeatable")
    parser.add_argument("--all", action="store_true", help="Select the whole collection")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip the collection-level confirmation")
    parser.add_argument("--hermes-bin", default=os.environ.get("HERMES_BIN", "hermes"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="List available profiles")
    list_parser.add_argument("--series", choices=SERIES)

    install_parser = sub.add_parser("install", help="Install one or more profiles")
    add_selection_flags(install_parser)
    install_parser.add_argument("--alias", action="store_true", help="Create shell aliases for installed profiles")
    install_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing profile, including config.yaml; memories and sessions survive",
    )

    update_parser = sub.add_parser("update", help="Update installed profiles from this checkout")
    add_selection_flags(update_parser)
    update_parser.add_argument(
        "--pull",
        action="store_true",
        help="Fast-forward this collection checkout before updating profiles",
    )
    update_parser.add_argument("--force-config", action="store_true", help="Replace local profile config and skin selection")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    catalog = load_catalog()
    if args.command == "list":
        print_catalog(catalog, args.series)
        return 0
    if args.command == "install":
        return install(args, catalog)
    if args.command == "update":
        return update(args, catalog)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
