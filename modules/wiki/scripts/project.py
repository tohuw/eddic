# /// script
# requires-python = ">=3.9"
# ///
"""eddic project — deterministic player projection of the DM wiki.

Usage:
    uv run project.py [--src <wiki_dir>] [--out <projection_dir>] [--log NAME]
    (bare, as a vendored eddic verb: paths come from EDDIC_CONFIG)

Copies every page marked `visibility: player` from the DM master into
the projection directory, preserving the tree, with frontmatter
stripped so no DM-only key rides into player output. Visibility fails
closed: a page without frontmatter, or without the marker, is DM-only
and never projects.

Contributor overlays (`contribs/<id>/...`) are applied first: a
contrib file occupies its relative path in the wiki, or the page
named by its `replaces:` frontmatter — shadowing the base page on
every built surface while the base stays in the tree. Two contribs
claiming one target, or a contrib landing on a base page without
declaring `replaces:`, refuses the projection. An overlay's own
frontmatter governs its visibility (fail-closed like any page);
its links resolve as if the file sat at its effective wiki path.

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
# Inline HTML anchor and Markdown reference-definition targets — the two
# link forms the inline LINK regex misses. link_targets mirrors
# eddic_lint.py so the firewall sees exactly the links the linter does:
# a DM target can hide in an inline link, a reference definition, or an
# <a href>, and every one trips the same refusal.
HREF = re.compile(r"""<a\b[^>]*?\shref\s*=\s*["']([^"'>\s]+)["']""", re.I)
REFDEF = re.compile(r"""^\s{0,3}\[[^\]]+\]:\s+<?([^>\s]+)>?""")


def link_targets(body):
    """(line_no, target) for every link target: inline [text](url),
    reference definitions [id]: target (which carry the URL a [text][id]
    use resolves to), and inline HTML <a href>. Mirrors
    eddic_lint.link_targets so projection and lint cannot diverge."""
    out = []
    for i, line in enumerate(body.splitlines()):
        for m in LINK.finditer(line):
            out.append((i + 1, m.group(1)))
        if (m := REFDEF.match(line)):
            out.append((i + 1, m.group(1)))
        for m in HREF.finditer(line):
            out.append((i + 1, m.group(1)))
    return out


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


def load_overlays(contribs, log_name):
    """Map effective wiki path -> (contributor, file path). Conflicts
    are fatal to the caller; returned separately."""
    overlays, conflicts = {}, []
    if not contribs or not contribs.is_dir():
        return overlays, conflicts
    for cdir in sorted(p for p in contribs.iterdir() if p.is_dir()):
        for p in sorted(cdir.rglob("*.md")):
            if p.name in NON_CONTENT or p.name == log_name:
                continue
            fm, _ = split_frontmatter(p.read_text(encoding="utf-8",
                                                  errors="replace"))
            target = (fm.get("replaces") or
                      p.relative_to(cdir).as_posix())
            if target in overlays:
                conflicts.append((target, overlays[target][0], cdir.name))
                continue
            overlays[target] = (cdir.name, p)
    return overlays, conflicts


def main(argv):
    opts = dict(zip(argv, argv[1:]))
    log_name = opts.get("--log", "log.md")
    src = out = contribs = None
    if os.environ.get("EDDIC_CONFIG") and "--src" not in opts:
        cfg_path = Path(os.environ["EDDIC_CONFIG"])
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        root = cfg_path.parent.parent
        src = root / cfg.get("wiki_dir", "wiki")
        out = root / cfg.get("projection_dir", "dist/player")
        contribs = root / cfg.get("contribs_dir", "contribs")
        log_name = opts.get("--log", cfg.get("log", "log.md"))
    if "--src" in opts:
        src = Path(opts["--src"])
        if contribs is None:
            contribs = src.parent / "contribs"
    if "--out" in opts:
        out = Path(opts["--out"])
    if "--contribs" in opts:
        contribs = Path(opts["--contribs"])
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

    overlays, conflicts = load_overlays(contribs, log_name)
    overlay_errors = [
        f"contribs conflict: {t} claimed by both {a} and {b}"
        for t, a, b in conflicts]
    for target, (who, p) in sorted(overlays.items()):
        fm, _ = split_frontmatter(p.read_text(encoding="utf-8",
                                              errors="replace"))
        if target in pages and not fm.get("replaces"):
            overlay_errors.append(
                f"contribs collision: {who}'s {target} lands on an "
                f"existing base page without declaring replaces:")
            continue
        if fm.get("replaces") and target not in pages:
            overlay_errors.append(
                f"contribs: {who}'s replaces target {target} "
                f"does not exist in the wiki")
            continue
        pages[target] = ((fm.get("visibility") or "dm").strip(), p)
    if overlay_errors:
        print("projection REFUSED — contributor overlays are "
              "inconsistent; nothing was written:", file=sys.stderr)
        for e in overlay_errors:
            print(f"  {e}", file=sys.stderr)
        return 1

    player = {rel for rel, (vis, _) in pages.items() if vis == "player"}

    breaches = []
    for rel in sorted(player):
        _, path = pages[rel]
        _, body = split_frontmatter(path.read_text(encoding="utf-8",
                                                   errors="replace"))
        for _line, target in link_targets(body):
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            raw = target.partition("#")[0]
            if not raw.endswith((".md", ".MD")):
                continue
            # resolve at the page's effective wiki location — for an
            # overlay that is the shadowed path, not the contrib file
            dest = ((src / rel).parent / raw).resolve()
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
        # Strip frontmatter: projected pages are player output. Only
        # `visibility` was ever read, and downstream consumers take the
        # body alone (render uses the H1, the corpus uses the body, the
        # player Atlas rests on the projection's closure). Any other
        # frontmatter key — a DM note, a secret — would otherwise ride
        # verbatim into player hands, so none of it ships.
        _, body = split_frontmatter(
            pages[rel][1].read_text(encoding="utf-8", errors="replace"))
        dest.write_text(body.lstrip("\n"), encoding="utf-8")
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
