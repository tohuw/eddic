"""Canonical source for the primitives that decide what a wiki link means
and what reaches players.

These live in more than one script on purpose. Every deterministic verb is
vendored into a campaign as a single standalone `.eddic/lib/<verb>.py` and
run by itself under `uv run`, so a shared import would mean either a second
file every vendoring step has to carry, a `sys.path` fixup in every script,
or a symlink — and the contract bans symlinks. Copies are the cost of that
install story.

What is not acceptable is copies that drift. So the copies are *generated*:
each consumer carries a stamped block, `tools/sync_shared.py` writes it from
here, and `tools/floor.py` fails the push if any copy differs from what this
file would produce or if a rostered name is defined outside a stamped block.
Edit here, run the sync, never hand-edit a stamped block.

The stakes are not uniform. `visibility_of` decides whether DM material
reaches players, so a divergence there is a leak; `slugify` decides whether
an anchor the linter blesses is one the rendered page actually has; the rest
decide whether three tools agree about what a link points at. Issue #22 was
that last class going wrong.

Consumers must `import re` themselves; the block assumes it.
"""

import re

# >>> link_consts
# Every link form a wiki page can carry. Inline HTML and reference
# definitions are here because a DM-only target must not be able to hide in
# a form one tool parses and another does not — that was issue #22.
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)\)")
HREF = re.compile(r"""<a\b[^>]*?\shref\s*=\s*["']([^"'>\s]+)["']""", re.I)
REFDEF = re.compile(r"""^\s{0,3}\[[^\]]+\]:\s+<?([^>\s]+)>?""")
# <<<

# >>> provenance_consts
# A claim's citation back to the line that justifies it, written as an
# HTML comment so it never renders and never reaches a player: the
# projection strips it. `<!-- src: sessions/s4-transcript.md#t=1:14:22 -->`
SRC_MARK = re.compile(
    r"<!--\s*src:\s*([^\s#>]+)(?:#t=(\d+:\d{2}:\d{2}))?\s*-->")
# <<<

# >>> media_consts
# Embedded media. The link regexes deliberately skip images (`(?<!\!)`),
# because an image is not a page and must not be resolved like one — but
# something has to see them, or a map dropped in assets/ ships to the player
# site on nothing but a filename convention.
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
IMG_SRC = re.compile(r"""<img\b[^>]*?\ssrc\s*=\s*["']([^"'>\s]+)["']""", re.I)
# <<<

# >>> media_targets
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
# <<<

# >>> body_consts
# Body shapes the scanners key on: headings become anchors, fences mark the
# code the link scanners must not read.
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
FENCE = re.compile(r"^(```|~~~)")
# <<<

# >>> split_frontmatter
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
# <<<

# >>> visibility_of
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
# <<<

# >>> slugify
def slugify(heading):
    """GitHub-style anchor slug, computed after inline HTML is stripped.

    The tag strip is load-bearing: the renderer emits heading ids from this
    same text, so a heading like `## The <em>Oath</em>` must slug to
    `the-oath` and not `the-emoathem`. Without it the linter blesses anchors
    the built page does not have and rejects the ones it does."""
    s = re.sub(r"<[^>]+>", "", heading).strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")
# <<<

# >>> strip_code
def strip_code(body):
    """Body with fenced blocks dropped and inline code spans blanked, so a
    link-shaped string inside an example is not mistaken for a link."""
    out, fenced = [], False
    for line in body.splitlines():
        if FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            out.append(re.sub(r"`[^`]*`", "", line))
    return "\n".join(out)
# <<<

# >>> link_targets
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
# <<<

# >>> page_ref
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
# <<<
