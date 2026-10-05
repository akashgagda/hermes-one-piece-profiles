#!/usr/bin/env python3
"""Exercise every generated distribution through the installed Hermes CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )


def main() -> int:
    hermes = os.environ.get("HERMES_BIN", "hermes")
    if shutil.which(hermes) is None:
        raise SystemExit(f"Hermes executable not found: {hermes}")
    # SAFETY: on Hermes 0.21.x the profiles root resolves from the DEFAULT Hermes home
    # (``~/.hermes/profiles``), not from HERMES_HOME, so this script installs real
    # profiles into the real profiles root even though it points HERMES_HOME at a temp
    # dir. That is fine in CI (a throwaway runner home) and destructive to a dev
    # machine's profile list. Require an explicit opt-in.
    if os.environ.get("HERMES_OP_E2E") != "1":
        print(
            "Refusing to run: this script installs {n} real Hermes profiles into the "
            "resolved profiles root (on 0.21.x that is the default Hermes home, not "
            "HERMES_HOME). Run it in a container or a throwaway machine, then re-run "
            "with HERMES_OP_E2E=1.".format(n=len(json.loads((ROOT / "catalog.json").read_text(encoding="utf-8")))),
            file=sys.stderr,
        )
        return 2
    catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="onepiece_profiles_e2e_") as temp:
        home = Path(temp) / "hermes"
        home.mkdir()
        env = dict(os.environ)
        env.update({"HERMES_HOME": str(home), "BWS_ACCESS_TOKEN": ""})
        for persona in catalog:
            slug = persona["slug"]
            proc = run(
                [
                    hermes,
                    "profile",
                    "install",
                    str(ROOT / "profiles" / slug),
                    "--name",
                    slug,
                    "-y",
                ],
                env=env,
            )
            if proc.returncode:
                raise SystemExit(f"Install failed for {slug}:\n{proc.stdout}\n{proc.stderr}")
            installed = home / "profiles" / slug
            soul = (installed / "SOUL.md").read_text(encoding="utf-8")
            config = yaml.safe_load((installed / "config.yaml").read_text(encoding="utf-8"))
            skin = yaml.safe_load((installed / "skins" / f"{slug}.yaml").read_text(encoding="utf-8"))
            assert persona["name"] in soul
            assert config == {"model": "", "display": {"skin": slug}}
            assert skin["branding"]["agent_name"] == persona["name"]

        sample = home / "profiles" / "monkey-d-luffy"
        (sample / "memories" / "MEMORY.md").write_text("LOCAL MEMORY\n", encoding="utf-8")
        (sample / "config.yaml").write_text("model: local-model\ndisplay:\n  skin: local-skin\n", encoding="utf-8")
        (sample / "SOUL.md").write_text("STALE\n", encoding="utf-8")
        proc = run([hermes, "profile", "update", "monkey-d-luffy", "-y"], env=env)
        if proc.returncode:
            raise SystemExit(f"Update failed:\n{proc.stdout}\n{proc.stderr}")
        assert "straw-hat" in (sample / "SOUL.md").read_text(encoding="utf-8").lower()
        assert "local-model" in (sample / "config.yaml").read_text(encoding="utf-8")
        assert (sample / "memories" / "MEMORY.md").read_text(encoding="utf-8") == "LOCAL MEMORY\n"

    print(f"E2E validated {len(catalog)} profile installs and one preserving update")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
