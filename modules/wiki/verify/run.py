# /// script
# requires-python = ">=3.9"
# ///
"""Verify the wiki module's projection: player pages and safe assets
project, DM pages and .dm assets are withheld, twins behave, and a
firewall breach refuses the whole projection all-or-nothing."""

import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent / "scripts" / "project.py"

PLAYER_FM = "---\nvisibility: player\n---\n\n"


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def run(src, out):
    return subprocess.run(
        [sys.executable, str(PROJECT), "--src", str(src), "--out", str(out)],
        capture_output=True, text=True)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="eddic-wiki-verify-"))
    src, out = tmp / "wiki", tmp / "player"
    write(src, "index.md", PLAYER_FM + "# Realm\n\n"
          "[The Warden](characters/warden.md)\n")
    write(src, "index.dm.md", "# Realm — DM catalog\n\n"
          "[index](index.md), [warden](characters/warden.md), "
          "[warden dm](characters/warden.dm.md)\n")
    write(src, "characters/warden.md", PLAYER_FM + "# The Warden\n\n"
          "Keeper of the gate, sworn to the [realm](../index.md).\n")
    write(src, "characters/warden.dm.md", "# The Warden — full truth\n\n"
          "Secretly the last Reaver. Player twin: [warden](warden.md).\n")
    write(src, "assets/map.txt", "safe player map\n")
    write(src, "assets/lair.dm.txt", "secret lair map\n")

    proc = run(src, out)
    checks = [
        (proc.returncode == 0, f"clean projection exits 0 (got {proc.returncode})"),
        ((out / "index.md").exists(), "player index projected"),
        ((out / "characters/warden.md").exists(), "player twin projected"),
        (not (out / "characters/warden.dm.md").exists(), "DM twin withheld"),
        (not (out / "index.dm.md").exists(), "DM catalog withheld"),
        ((out / "assets/map.txt").exists(), "safe asset projected"),
        (not (out / "assets/lair.dm.txt").exists(), ".dm asset withheld"),
    ]

    # Plant a breach: player page linking the DM twin.
    write(src, "characters/warden.md", PLAYER_FM + "# The Warden\n\n"
          "See [the full truth](warden.dm.md).\n")
    proc2 = run(src, out)
    checks += [
        (proc2.returncode == 1, f"breach refuses with exit 1 (got {proc2.returncode})"),
        ("warden.dm.md" in proc2.stderr, "breach names the offending link"),
        ((out / "characters/warden.md").read_text(encoding="utf-8")
         .count("full truth") == 0,
         "refusal wrote nothing (stale projection untouched)"),
    ]

    # Breach via dangling link: player page linking a missing page.
    write(src, "characters/warden.md", PLAYER_FM + "# The Warden\n\n"
          "See [nowhere](ghost.md).\n")
    proc3 = run(src, out)
    checks.append((proc3.returncode == 1,
                   f"dangling player link refuses (got {proc3.returncode})"))

    failed = [msg for ok, msg in checks if not ok]
    for ok, msg in checks:
        print(("ok  " if ok else "FAIL"), msg)
    if failed:
        print(proc.stderr or "", proc2.stderr or "", sep="\n")
        return 1
    print("verify ok: wiki module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
