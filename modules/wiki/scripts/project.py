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
and never projects. A page carrying `proposes-merge-into` is DM-side
on the same principle — unadjudicated lore is not canon, so it stays
off the player surface however it is marked.

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
or a lie. Assets ship by reachability: a file projects when a page
that projects points at it, and not otherwise, so a map dropped in
`assets/` and linked from nowhere — or linked only from a DM page —
stays home. Any path containing `.dm` never projects regardless, and
a player page pointing at one is a breach the lint names.

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
# --- BEGIN SHARED wikilib: link_consts, media_consts, split_frontmatter, visibility_of, link_targets, media_targets, page_ref ---
# Every link form a wiki page can carry. Inline HTML and reference
# definitions are here because a DM-only target must not be able to hide in
# a form one tool parses and another does not — that was issue #22.
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)\)")
HREF = re.compile(r"""<a\b[^>]*?\shref\s*=\s*["']([^"'>\s]+)["']""", re.I)
REFDEF = re.compile(r"""^\s{0,3}\[[^\]]+\]:\s+<?([^>\s]+)>?""")


# Embedded media. The link regexes deliberately skip images (`(?<!\!)`),
# because an image is not a page and must not be resolved like one — but
# something has to see them, or a map dropped in assets/ ships to the player
# site on nothing but a filename convention.
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
IMG_SRC = re.compile(r"""<img\b[^>]*?\ssrc\s*=\s*["']([^"'>\s]+)["']""", re.I)


def split_frontmatter(text):
    """(frontmatter dict, body) — flat `key: value` pairs only, top level
    only, no YAML dependency. A page with no frontmatter yields ({}, text),
    which is what makes every visibility judgment fail closed."""
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


def visibility_of(fm):
    """Effective visibility, fail-closed: anything that is not exactly
    `player` is DM-only, including a page with no frontmatter at all.

    An open merge proposal is DM-side however it marks itself. It is
    unadjudicated lore the DM has not chosen yet, so it cannot ship to
    players even when someone marks it player-visible; the lint reports that
    contradiction, and this refuses to act on it. Every surface that decides
    what players see reads this — the projection that writes their wiki, the
    lint that judges a breach, the constellation that charts it — so that a
    clean lint means a projection that will build."""
    if (fm.get("proposes-merge-into") or "").strip():
        return "dm"
    return (fm.get("visibility") or "dm").strip()


def link_targets(body):
    """(line_no, target) for every link target in the body: inline
    [text](url), reference definitions [id]: target (whose URL is what a
    [text][id] use resolves to, so harvesting the definitions covers the
    uses without a second pass), and inline HTML <a href>. All three forms
    flow through the same resolution and the same firewall check, so a DM
    target can hide in none of them."""
    out = []
    for i, line in enumerate(body.splitlines()):
        for m in LINK.finditer(line):
            out.append((i + 1, m.group(1)))
        if (m := REFDEF.match(line)):
            out.append((i + 1, m.group(1)))
        for m in HREF.finditer(line):
            out.append((i + 1, m.group(1)))
    return out


def media_targets(body):
    """Every embedded-media target in the body: `![alt](path)` and
    <img src>. Paired with link_targets, this is the full set of things a
    page points at, which is what lets the projection ship exactly the
    assets players can reach instead of everything in the folder."""
    out = []
    for i, line in enumerate(body.splitlines()):
        for m in IMAGE.finditer(line):
            out.append((i + 1, m.group(1)))
        for m in IMG_SRC.finditer(line):
            out.append((i + 1, m.group(1)))
    return out


def page_ref(raw):
    """Map a link's path (its target with any #fragment removed, already
    known to carry no URL scheme and not to be site-rooted) to the wiki page
    it denotes, as (candidate_md, strict), or (None, False) when the target
    names no page.

      foo/bar.md    -> ("foo/bar.md",    True)   a .md link — must resolve
      foo/bar.html  -> ("foo/bar.md",    False)  the page's rendered form
      foo/bar.htm   -> ("foo/bar.md",    False)
      foo/bar       -> ("foo/bar.md",    False)  a clean/extensionless URL
      foo/bar.dm    -> ("foo/bar.dm.md", False)  a .dm twin's clean URL

    `strict` is True only for a direct .md link, whose target must exist — a
    miss is a broken link. Every other shape is lenient: it is judged only
    when its candidate .md page actually exists, so a real asset
    (foo/pic.webp -> foo/pic.webp.md, no such page) and any other non-page
    target fall straight through, exactly as a non-.md link always did. That
    is what catches the .html and clean-URL forms of a real page while
    leaving assets and genuine non-page links alone: a DM page linked in any
    of these forms is the same lie as linking its .md — issue #22."""
    seg = raw.rsplit("/", 1)[-1]
    if not seg:
        return None, False  # empty or directory-style target: not a page
    low = seg.lower()
    if low.endswith(".md"):
        return raw, True
    if low.endswith(".html"):
        return raw[:-5] + ".md", False
    if low.endswith(".htm"):
        return raw[:-4] + ".md", False
    return raw + ".md", False
# --- END SHARED wikilib ---


# Inline HTML anchor and Markdown reference-definition targets — the two
# link forms the inline LINK regex misses. link_targets mirrors
# eddic_lint.py so the firewall sees exactly the links the linter does:
# a DM target can hide in an inline link, a reference definition, or an
# <a href>, and every one trips the same refusal.
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
        pages[rel] = (visibility_of(fm), p)

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
        pages[target] = (visibility_of(fm), p)
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
            page_md, strict = page_ref(raw)
            if page_md is None:
                continue
            # resolve at the page's effective wiki location — for an
            # overlay that is the shadowed path, not the contrib file. A
            # .html or clean/extensionless target resolves to the .md page
            # it renders from and is judged identically; a lenient form
            # that names no page falls through (a legitimate non-page link
            # is not newly refused).
            dest = ((src / rel).parent / page_md).resolve()
            try:
                dest_rel = dest.relative_to(src.resolve()).as_posix()
            except ValueError:
                if strict:
                    breaches.append((rel, target, "escapes the wiki"))
                continue
            if dest_rel not in pages:
                if strict:
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
        # player Constellation rests on the projection's closure). Any other
        # frontmatter key — a DM note, a secret — would otherwise ride
        # verbatim into player hands, so none of it ships.
        _, body = split_frontmatter(
            pages[rel][1].read_text(encoding="utf-8", errors="replace"))
        dest.write_text(body.lstrip("\n"), encoding="utf-8")
    # Assets ship by reachability, not by folder. Every other secrecy
    # decision here is fail-closed; shipping all of assets/ and trusting a
    # filename convention was the one that was not, and it published to a
    # public URL. An asset reaches players only when a projected page
    # points at it. The `.dm` exclusion stays as the second line: a
    # reference to a DM-marked asset is a breach the lint names, and this
    # refuses to copy it either way.
    wanted = set()
    for rel in sorted(player):
        _, path = pages[rel]
        _, body = split_frontmatter(path.read_text(encoding="utf-8",
                                                   errors="replace"))
        for _line, target in link_targets(body) + media_targets(body):
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            raw = target.partition("#")[0]
            if not raw or raw.startswith("/"):
                continue
            dest = ((src / rel).parent / raw).resolve()
            try:
                dest_rel = dest.relative_to(src.resolve()).as_posix()
            except ValueError:
                continue
            if dest_rel in pages or not (src / dest_rel).is_file():
                continue          # a page, or nothing at all
            wanted.add(dest_rel)

    assets = 0
    for rel_asset in sorted(wanted):
        if ".dm" in rel_asset:
            continue
        p = src / rel_asset
        dest = out / rel_asset
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
        assets += 1

    skipped = len(pages) - len(player)
    print(f"projected {len(player)} player page(s) and {assets} asset(s) "
          f"to {out} ({skipped} DM-only page(s) withheld)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
