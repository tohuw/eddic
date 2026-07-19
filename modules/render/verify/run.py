# /// script
# requires-python = ">=3.9"
# ///
"""Verify the render module against a planted tree. Runs the renderer
via `uv run` (it has a declared dependency); asserts the HTML mirror,
link rewriting, heading ids, titles, frontmatter stripping, noindex,
and asset copying."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RENDER = Path(__file__).resolve().parent.parent / "scripts" / "render.py"


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def main():
    if not shutil.which("uv"):
        print("SKIP: uv not on PATH (render needs its declared dependency)")
        return 0
    tmp = Path(tempfile.mkdtemp(prefix="eddic-render-verify-"))
    src, out = tmp / "player", tmp / "site"
    write(src, "index.md", "---\nvisibility: player\n---\n\n# Realm\n\n"
          "See [the Warden](characters/warden.md#the-oath) and the "
          "[charter](https://example.com/charter.md).\n")
    write(src, "characters/warden.md",
          "---\nvisibility: player\n---\n\n# The Warden\n\n"
          "Back to [the realm](../index.md).\n\n## The Oath\n\nSpoken once.\n")
    write(src, "assets/map.txt", "map\n")
    write(src, "AGENTS.md", "# never rendered\n")

    proc = subprocess.run(
        ["uv", "run", str(RENDER), "--src", str(src), "--out", str(out),
         "--site-name", "Realm"], capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"FAIL: renderer exit {proc.returncode}\n{proc.stderr}")
        return 1

    index = (out / "index.html").read_text(encoding="utf-8")
    warden = (out / "characters/warden.html").read_text(encoding="utf-8")
    checks = [
        ((out / "404.html").exists() and "Not found" in
         (out / "404.html").read_text(encoding="utf-8"),
         "404.html emitted (disables SPA fallback on static hosts)"),
        ((out / "index.html").exists(), "index.html rendered"),
        ((out / "characters/warden.html").exists(), "nested mirror path"),
        ('href="characters/warden.html#the-oath"' in index,
         ".md link rewritten, fragment preserved"),
        ('href="https://example.com/charter.md"' in index,
         "external .md link untouched"),
        ('href="../index.html"' in warden, "relative parent link rewritten"),
        ('id="the-oath"' in warden, "heading id for fragment landing"),
        ("<title>Realm</title>" in index,
         "root/eponymous title deduped (Name, not Name — Name)"),
        ("<title>The Warden — Realm</title>" in warden,
         "non-eponymous title keeps the site suffix"),
        ("visibility" not in index, "frontmatter stripped"),
        ('name="robots" content="noindex' in index, "noindex present"),
        ((out / "assets/map.txt").exists(), "asset copied"),
        (not (out / "AGENTS.html").exists(), "non-content skipped"),
    ]
    failed = [msg for ok, msg in checks if not ok]
    for ok, msg in checks:
        print(("ok  " if ok else "FAIL"), msg)
    if failed:
        return 1

    # A campaign static/ dir (banner, favicon) is served at /static/.
    # Exercise the EDDIC_CONFIG path: root = cfg_path.parent.parent, and
    # a static/ dir at that root is copied verbatim (minus .DS_Store).
    camp = Path(tempfile.mkdtemp(prefix="eddic-render-static-"))
    cfg_path = camp / ".eddic" / "config.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps({
        "projection_dir": "dist/player", "site_dir": "dist/site",
        "site_name": "Realm"}), encoding="utf-8")
    write(camp, "dist/player/index.md", "# Realm\n\nThe realm.\n")
    write(camp, "static/banner.png", "PNG\n")
    write(camp, "static/.DS_Store", "junk\n")
    env = dict(os.environ, EDDIC_CONFIG=str(cfg_path))
    proc = subprocess.run(["uv", "run", str(RENDER)],
                          capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        print(f"FAIL: renderer (EDDIC_CONFIG) exit {proc.returncode}\n"
              f"{proc.stderr}")
        return 1
    site = camp / "dist" / "site"
    static_checks = [
        ((site / "static" / "banner.png").exists(),
         "campaign static/ file copied to out/static/"),
        (not (site / "static" / ".DS_Store").exists(),
         ".DS_Store excluded from static copy"),
    ]
    for ok, msg in static_checks:
        print(("ok  " if ok else "FAIL"), msg)
    if any(not ok for ok, _ in static_checks):
        return 1

    print("verify ok: render module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
