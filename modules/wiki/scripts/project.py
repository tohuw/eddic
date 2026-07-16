# /// script
# requires-python = ">=3.9"
# ///
"""eddic project — deterministic player projection of the DM wiki.

Usage:
    uv run project.py [--src <wiki_dir>] [--out <projection_dir>] [--log NAME]
    (bare, as a vendored eddic verb: paths come from EDDIC_CONFIG)

Copies every page marked `visibility: player` from the DM master into
the projection directory, preserving the tree. Visibility fails
closed: a page without frontmatter, or without the marker, is DM-only
and never projects.

The firewall is checked before a single byte is written, and a breach
refuses the whole projection (all-or-nothing): a player-visible page
that links a non-player page — or links a page that does not exist —
cannot ship, because in the players' hands that link is either a leak
or a lie. Assets: files under `assets/` project wholesale by
convention (never put spoiler assets there); any path containing
`.dm` never projects.

Exit codes: 0 projected, 1 refused (breaches listed), 2 usage error.
No agent judgment is involved anywhere in this file; that is the
point of it.
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path

NON_CONTENT = {"CLAUDE.md", "AGENTS.md", "README.md"}
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)\)")


def split_frontmatter(text):
    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm = {}
                for ln in lines[1:i]:
                    if ":" in ln and not ln.startswith((" ", "\t")):
                        k, _, v = ln.partition(":")
                        fm[k.strip()] = v.strip()
                return fm, "\n".join(lines[i + 1:])
    return {}, text


def main(argv):
    opts = dict(zip(argv, argv[1:]))
    log_name = opts.get("--log", "log.md")
    src = out = None
    if os.environ.get("EDDIC_CONFIG") and "--src" not in opts:
        cfg_path = Path(os.environ["EDDIC_CONFIG"])
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        root = cfg_path.parent.parent
        src = root / cfg.get("wiki_dir", "wiki")
        out = root / cfg.get("projection_dir", "dist/player")
        log_name = opts.get("--log", cfg.get("log", "log.md"))
    if "--src" in opts:
        src = Path(opts["--src"])
    if "--out" in opts:
        out = Path(opts["--out"])
    if not src or not out:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    if not src.is_dir():
        print(f"not a directory: {src}", file=sys.stderr)
        return 2

    pages = {}
    for p in sorted(src.rglob("*.md")):
        if p.name in NON_CONTENT or p.name == log_name:
            continue
        rel = p.relative_to(src).as_posix()
        fm, _ = split_frontmatter(p.read_text(encoding="utf-8",
                                              errors="replace"))
        pages[rel] = ((fm.get("visibility") or "dm").strip(), p)

    player = {rel for rel, (vis, _) in pages.items() if vis == "player"}

    breaches = []
    for rel in sorted(player):
        _, path = pages[rel]
        _, body = split_frontmatter(path.read_text(encoding="utf-8",
                                                   errors="replace"))
        for m in LINK.finditer(body):
            target = m.group(1)
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            raw = target.partition("#")[0]
            if not raw.endswith((".md", ".MD")):
                continue
            dest = (path.parent / raw).resolve()
            try:
                dest_rel = dest.relative_to(src.resolve()).as_posix()
            except ValueError:
                breaches.append((rel, target, "escapes the wiki"))
                continue
            if dest_rel not in pages:
                breaches.append((rel, target, "does not exist"))
            elif dest_rel not in player:
                breaches.append((rel, target, "is DM-only"))

    if breaches:
        print("projection REFUSED — the firewall found breaches; "
              "nothing was written:", file=sys.stderr)
        for rel, target, why in breaches:
            print(f"  {rel} -> {target} ({why})", file=sys.stderr)
        return 1

    if out.exists():
        shutil.rmtree(out)
    for rel in sorted(player):
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pages[rel][1], dest)
    assets = src / "assets"
    if assets.is_dir():
        for p in sorted(assets.rglob("*")):
            if p.is_file() and ".dm" not in p.relative_to(src).as_posix():
                dest = out / p.relative_to(src)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, dest)

    skipped = len(pages) - len(player)
    print(f"projected {len(player)} player page(s) to {out} "
          f"({skipped} DM-only page(s) withheld)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
