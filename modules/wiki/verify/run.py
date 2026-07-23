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

    # Reference-style links breach the firewall too: the [id]: definition
    # names the DM twin, so it must refuse just like an inline link.
    write(src, "characters/warden.md", PLAYER_FM + "# The Warden\n\n"
          "See [the full truth][t].\n\n[t]: warden.dm.md\n")
    proc_ref = run(src, out)
    checks += [
        (proc_ref.returncode == 1,
         f"reference-style link to DM twin refuses (got {proc_ref.returncode})"),
        ("warden.dm.md" in proc_ref.stderr,
         "reference-style breach names the DM target"),
    ]

    # Inline-HTML anchors breach the firewall too.
    write(src, "characters/warden.md", PLAYER_FM + "# The Warden\n\n"
          'See <a href="warden.dm.md">the full truth</a>.\n')
    proc_html = run(src, out)
    checks += [
        (proc_html.returncode == 1,
         f"inline-HTML link to DM twin refuses (got {proc_html.returncode})"),
        ("warden.dm.md" in proc_html.stderr,
         "inline-HTML breach names the DM target"),
    ]

    # A non-.md link form is judged identically (issue #22): a player
    # page linking the DM twin as its rendered .html, or as a
    # clean/extensionless URL, is the same lie as linking the .md and must
    # refuse — otherwise the leak walks straight through the firewall.
    write(src, "characters/warden.md", PLAYER_FM + "# The Warden\n\n"
          "See [the full truth](warden.dm.html).\n")
    proc_htmlext = run(src, out)
    checks += [
        (proc_htmlext.returncode == 1,
         f".html link to DM twin refuses (got {proc_htmlext.returncode})"),
        ("warden.dm" in proc_htmlext.stderr,
         ".html breach names the DM target"),
    ]
    write(src, "characters/warden.md", PLAYER_FM + "# The Warden\n\n"
          "See [the full truth](warden.dm).\n")
    proc_clean = run(src, out)
    checks += [
        (proc_clean.returncode == 1,
         f"clean/extensionless link to DM twin refuses (got {proc_clean.returncode})"),
        ("warden.dm" in proc_clean.stderr,
         "clean-URL breach names the DM target"),
    ]

    # A non-.md form that names no page is NOT newly refused: a real asset
    # and a clean URL with no .md behind it must both project clean, or the
    # hardening would false-positive legitimate non-page links (issue #22).
    write(src, "characters/warden.md", PLAYER_FM + "# The Warden\n\n"
          "A [sketch](sketch.webp) and a [draft](future-notes), neither a "
          "page, sworn to the [realm](../index.md).\n")
    proc_safe = run(src, out)
    checks += [
        (proc_safe.returncode == 0,
         f"non-page .webp/clean links still project (got {proc_safe.returncode})"),
        ((out / "characters/warden.md").exists(),
         "page with only non-page non-.md links projects normally"),
    ]

    # DM-only frontmatter must never ride into player output: a
    # visibility: player page still projects, but its other keys are
    # stripped so no DM secret reaches the projection.
    write(src, "characters/warden.md",
          "---\nvisibility: player\n"
          "dm_secret: the Warden is secretly the last Reaver\n---\n\n"
          "# The Warden\n\nKeeper of the gate, sworn to the "
          "[realm](../index.md).\n")
    proc_fm = run(src, out)
    projected = (out / "characters/warden.md").read_text(encoding="utf-8")
    checks += [
        (proc_fm.returncode == 0,
         f"page with dm_secret frontmatter still projects (got {proc_fm.returncode})"),
        ("dm_secret" not in projected and "last Reaver" not in projected,
         "dm_secret frontmatter stripped from the projected page"),
        (projected.startswith("# The Warden"),
         "projected page starts at the H1 — frontmatter gone, body intact"),
    ]

    # Contributor overlays: shadow wins on the built surface, base
    # stays in the tree; a second claim on the target refuses.
    write(src, "characters/warden.md", PLAYER_FM + "# The Warden\n\n"
          "Keeper of the gate, sworn to the [realm](../index.md).\n")
    contribs = tmp / "contribs"
    write(contribs, "kestrel/characters/warden.md",
          "---\nvisibility: player\nauthorship: kestrel\n"
          "replaces: characters/warden.md\n---\n\n# The Warden\n\n"
          "Kestrel's retelling, sworn to the [realm](../index.md).\n")
    proc4 = subprocess.run(
        [sys.executable, str(PROJECT), "--src", str(src),
         "--out", str(out), "--contribs", str(contribs)],
        capture_output=True, text=True)
    checks += [
        (proc4.returncode == 0,
         f"overlay projection exits 0 (got {proc4.returncode})"),
        ("Kestrel's retelling" in
         (out / "characters/warden.md").read_text(encoding="utf-8"),
         "overlay shadows the base page on the built surface"),
        ("Kestrel" not in
         (src / "characters/warden.md").read_text(encoding="utf-8"),
         "base page untouched in the tree"),
    ]
    write(contribs, "vagrant/characters/warden.md",
          "---\nvisibility: player\nauthorship: vagrant\n"
          "replaces: characters/warden.md\n---\n\n# The Warden\n\nMine.\n")
    proc5 = subprocess.run(
        [sys.executable, str(PROJECT), "--src", str(src),
         "--out", str(out), "--contribs", str(contribs)],
        capture_output=True, text=True)
    checks.append((proc5.returncode == 1 and "conflict" in proc5.stderr,
                   "conflicting overlay claims refuse the projection"))

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
