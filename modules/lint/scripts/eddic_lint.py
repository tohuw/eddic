# /// script
# requires-python = ">=3.9"
# ///
"""eddic lint — deterministic wiki health reporter.

Usage:
    uv run eddic_lint.py <wiki_dir> [--json] [--strict] [--show-quieted]
                         [--log NAME]

Checks a tree of interlinked markdown pages:

  errors    broken relative links, broken anchors, missing H1,
            malformed operation-log entries, firewall breaches
            (player-visible page links a DM-only page; visibility
            fails closed: no frontmatter marker means DM-only),
            invalid pen-axis markers, merge proposals that name no
            target or claim player visibility
  warnings  stub drift (STUB-marked page grown past stub size),
            orphans (no inbound links), pages unreachable from the
            root index
  info      tiny pages not marked STUB; firewall check skipped
            because the wiki carries no visibility frontmatter yet;
            merge proposals awaiting the DM's adjudication

Checks come in two tiers. **Advisory** checks (ADVISORY below) are
editorial nagging and go quiet on a page that says the pen is held
elsewhere: `curation: human` (a human is answerable for this page),
`lint: off` (the owner's deliberate opt-out), or an open merge
proposal (not canon yet, so not held to canon's standards). Every
other check is **binding** — the firewall, the rights and attribution
machinery, and the structural integrity a build depends on never go
quiet, on any page, for any marker. A new check is binding unless it
is deliberately added to ADVISORY; the tier fails closed like the
visibility axis it protects.

Exit codes: 0 clean (infos allowed), 1 errors (or warnings with
--strict), 2 usage error. --json emits the machine-readable report.
--show-quieted lists what the advisory tier suppressed (each such
finding carries "quieted": true); the summary always counts them, so
quieting is visible even when the findings are not.

Deliberately stdlib-only and deterministic: this is the reporter half
of the reporter/model-triage seam. It never edits anything.
"""

import json
import os
import re
import sys
from pathlib import Path

NON_CONTENT = {"CLAUDE.md", "AGENTS.md", "README.md"}
LOG_TYPES = {"ingest", "reconcile", "lint", "schema", "witness",
             "attribution", "consent", "sever", "merge"}
TRANSACTABILITY = {"transactable", "transactable-with-attribution",
                   "local-only"}
GENERIC_AUTHORSHIP = {"human", "mixed", "agent", "machine", "transcript"}
# The pen axis (DESIGN principle 11, "Who holds the pen"): who writes
# this page next, marked per page. `curation` is who is answerable for
# the page as it stands and is asserted, never inferred — it does NOT
# default from `authorship`, because a human who approves machine prose
# has curated it, not written it.
CURATION = {"human", "agent"}
INGEST = {"literal", "derived"}
LINT_OPTS = {"off"}
# Advisory checks: editorial nagging, quieted where the pen is held
# elsewhere. Everything not listed here is binding and never quiets.
ADVISORY = {"stub-overgrown", "tiny-unstubbed", "orphan", "unreachable"}
LOG_HEADER = re.compile(r"^## \[\d{4}-\d{2}-\d{2}\] (\S+) \| .+$")
STUB_WORD_LIMIT = 150
TINY_WORD_LIMIT = 30

# --- BEGIN SHARED wikilib: link_consts, media_consts, body_consts, split_frontmatter, visibility_of, slugify, strip_code, link_targets, media_targets, page_ref ---
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


# Body shapes the scanners key on: headings become anchors, fences mark the
# code the link scanners must not read.
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
FENCE = re.compile(r"^(```|~~~)")


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


def slugify(heading):
    """GitHub-style anchor slug, computed after inline HTML is stripped.

    The tag strip is load-bearing: the renderer emits heading ids from this
    same text, so a heading like `## The <em>Oath</em>` must slug to
    `the-oath` and not `the-emoathem`. Without it the linter blesses anchors
    the built page does not have and rejects the ones it does."""
    s = re.sub(r"<[^>]+>", "", heading).strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


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


class Page:
    def __init__(self, path, root, rel=None):
        self.path = path
        self.rel = rel or path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        self.frontmatter, body = split_frontmatter(text)
        self.body = strip_code(body)
        self.headings = [m.group(2) for line in self.body.splitlines()
                         if (m := HEADING.match(line))]
        self.anchors = {slugify(h) for h in self.headings}
        self.has_h1 = any(line.startswith("# ") for line in self.body.splitlines())
        self.links = link_targets(self.body)
        self.words = len(re.sub(r"[^\w\s]", " ", self.body).split())
        lines = [ln.strip() for ln in self.body.splitlines() if ln.strip()]
        self.is_stub = bool(lines) and lines[-1] == "STUB"
        fm = self.frontmatter
        self.curation = (fm.get("curation") or "").strip()
        self.ingest = (fm.get("ingest") or "").strip()
        self.lint_opt = (fm.get("lint") or "").strip()
        self.merge_into = (fm.get("proposes-merge-into") or "").strip()
        # What the page claims, and what it effectively gets. An open
        # merge proposal is DM-side however it is marked — unadjudicated
        # lore is not canon — so the firewall reads `visibility` while
        # the marker check reads `declared` and reports the conflict.
        # This mirrors project.py's visibility_of(): the linter must
        # judge a breach exactly as the projection will.
        self.declared = (fm.get("visibility") or "dm").strip()
        self.visibility = "dm" if self.merge_into else self.declared
        # Where the pen is held elsewhere, the advisory tier goes quiet:
        # a human is answerable for the page, the owner opted out, or the
        # page is a proposal and not canon yet.
        self.quiet = bool(self.curation == "human" or self.lint_opt == "off"
                          or self.merge_into)


def lint(root, log_name, contribs=None):
    findings = []

    def add(code, severity, path, detail, line=None):
        findings.append({"code": code, "severity": severity,
                         "path": path, "line": line, "detail": detail})

    pages = {}
    for p in sorted(root.rglob("*.md")):
        if p.name in NON_CONTENT or p.name == log_name:
            continue
        pages[p.relative_to(root).as_posix()] = Page(p, root)

    # Contributor overlays: each contrib file occupies its relative
    # path (or its replaces: target) in the effective wiki. Structural
    # problems are errors; a broken overlay is reported and withheld
    # so the rest of the lint sees the same view a build would refuse.
    if contribs and contribs.is_dir():
        claimed = {}
        for cdir in sorted(p for p in contribs.iterdir() if p.is_dir()):
            for p in sorted(cdir.rglob("*.md")):
                if p.name in NON_CONTENT or p.name == log_name:
                    continue
                pg = Page(p, cdir)
                target = (pg.frontmatter.get("replaces") or pg.rel).strip()
                label = f"{contribs.name}/{cdir.name}/{pg.rel}"
                if target in claimed:
                    add("contrib-conflict", "error", label,
                        f"target {target} already claimed by "
                        f"{claimed[target]}; owner must resolve")
                    continue
                claimed[target] = cdir.name
                if pg.frontmatter.get("replaces") and target not in pages:
                    add("contrib-replaces-missing", "error", label,
                        f"replaces: {target} but no such base page")
                    continue
                if target in pages and not pg.frontmatter.get("replaces"):
                    add("contrib-collision", "error", label,
                        f"lands on existing base page {target} without "
                        f"declaring replaces:")
                    continue
                auth = (pg.frontmatter.get("authorship") or "").strip()
                if not auth or auth in GENERIC_AUTHORSHIP:
                    add("contrib-unattributed", "error", label,
                        "contrib file needs authorship: <contributor-id> "
                        "— attribution is the point of the overlay")
                pg.rel = target
                pages[target] = pg

    inbound = {rel: 0 for rel in pages}
    graph = {rel: set() for rel in pages}

    for rel, page in pages.items():
        if not page.has_h1:
            add("missing-h1", "error", rel, "page has no # H1 title")
        if page.is_stub and page.words > STUB_WORD_LIMIT:
            add("stub-overgrown", "warning", rel,
                f"marked STUB but holds {page.words} words; promote it")
        elif not page.is_stub and page.words < TINY_WORD_LIMIT:
            add("tiny-unstubbed", "info", rel,
                f"only {page.words} words and not marked STUB")

        for line, target in page.links:
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue  # external scheme
            if target.startswith("/"):
                add("absolute-link", "error", rel,
                    f"site-rooted link: {target} — resolves on no Eddic "
                    "surface (projection, corpus, rendered mirror); use a "
                    "page-relative path", line)
                continue
            raw, _, frag = target.partition("#")
            if not raw:  # same-page anchor
                if frag and slugify(frag) not in page.anchors:
                    add("broken-anchor", "error", rel,
                        f"no heading for #{frag}", line)
                continue
            page_md, strict = page_ref(raw)
            if page_md is None:
                continue  # real asset or non-page target; not ours to judge
            # resolve at the page's effective wiki location — for a
            # contrib overlay that is the shadowed path, not the file. A
            # .html or clean/extensionless target resolves to the .md page
            # it renders from and is judged identically; a lenient form
            # that names no page falls through (today's behavior for a
            # non-.md link — no new hard-fail).
            dest = ((root / page.rel).parent / page_md).resolve()
            try:
                dest_rel = dest.relative_to(root.resolve()).as_posix()
            except ValueError:
                if strict:
                    add("broken-link", "error", rel,
                        f"link escapes the wiki: {target}", line)
                continue
            if dest_rel not in pages:
                if strict:
                    add("broken-link", "error", rel,
                        f"target does not exist: {target}", line)
                continue
            inbound[dest_rel] += 1
            graph[rel].add(dest_rel)
            if frag and slugify(frag) not in pages[dest_rel].anchors:
                add("broken-anchor", "error", rel,
                    f"{target}: no heading for #{frag}", line)

    # Firewall: fails closed — a page is DM-only unless visibility: player.
    marked = [pg for pg in pages.values() if "visibility" in pg.frontmatter]
    if marked:
        for rel, page in pages.items():
            if page.visibility != "player":
                continue
            for dest in graph[rel]:
                if pages[dest].visibility != "player":
                    add("firewall-breach", "error", rel,
                        f"player-visible page links DM-only page: {dest}")
    else:
        add("firewall-skipped", "info", ".",
            "no visibility frontmatter anywhere; firewall check skipped")

    # Reachability and orphans. Roots are the catalogs: index.md and,
    # where the campaign keeps a DM catalog, index.dm.md — the player
    # catalog can never link DM pages (firewall), so DM pages are
    # legitimately reachable only via the DM catalog.
    roots = {r for r in ("index.md", "index.dm.md") if r in pages}
    if roots:
        seen, stack = set(roots), list(roots)
        while stack:
            seen.update(nxt := graph[stack.pop()] - seen)
            stack.extend(nxt)
        for rel in pages:
            if rel not in seen:
                add("unreachable", "warning", rel,
                    f"not reachable by links from {' or '.join(sorted(roots))}")
    for rel in pages:
        if inbound[rel] == 0 and rel not in roots:
            add("orphan", "warning", rel, "no inbound links from any page")

    # Operation log format.
    log = root / log_name
    if log.exists():
        for i, line in enumerate(log.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("## "):
                m = LOG_HEADER.match(line)
                if not m:
                    add("log-malformed", "error", log_name,
                        "expected '## [YYYY-MM-DD] <type> | <summary>'", i)
                elif m.group(1) not in LOG_TYPES:
                    add("log-malformed", "error", log_name,
                        f"unknown type '{m.group(1)}' "
                        f"(allowed: {', '.join(sorted(LOG_TYPES))})", i)

    # transaction-arc frontmatter: values valid, derivations resolvable
    for rel in sorted(pages):
        page = pages[rel]
        t = (page.frontmatter.get("transactability") or "").strip()
        if t and t not in TRANSACTABILITY:
            add("invalid-transactability", "error", rel,
                f"'{t}' is not one of {sorted(TRANSACTABILITY)} "
                f"(no marker = local-only)")
        d = (page.frontmatter.get("derived-from") or "").strip()
        if d and d not in pages:
            add("derived-from-missing", "error", rel,
                f"derived-from: {d} names no page in the effective wiki")

    # Assets. The projection ships an asset only when a projected page
    # points at it, so what a player page points at is exactly what
    # reaches the public site — which makes a reference to a DM-marked
    # asset a leak, and a reference to a missing one a broken image
    # nobody would otherwise see until it was live.
    for rel in sorted(pages):
        page = pages[rel]
        if page.visibility != "player":
            continue
        for line, target in link_targets(page.body) + media_targets(page.body):
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            raw = target.partition("#")[0]
            if not raw or raw.startswith("/"):
                continue
            dest = ((root / rel).parent / raw).resolve()
            try:
                dest_rel = dest.relative_to(root.resolve()).as_posix()
            except ValueError:
                continue
            if dest_rel in pages:
                continue                      # a page: judged elsewhere
            # A target whose page candidate names a real page (the .html
            # or clean-URL form of one) is a page reference; the firewall
            # and broken-link checks own it.
            page_md, strict = page_ref(raw)
            if strict:
                continue          # a direct .md link: broken-link owns it
            if page_md is not None:
                cand = ((root / rel).parent / page_md).resolve()
                try:
                    if cand.relative_to(root.resolve()).as_posix() in pages:
                        continue
                except ValueError:
                    pass
            if not (root / dest_rel).is_file():
                if "." in raw.rsplit("/", 1)[-1]:
                    add("asset-missing", "warning", rel,
                        f"{target}: player page points at a file that is "
                        f"not in the wiki", line)
                continue
            if ".dm" in dest_rel:
                add("asset-breach", "error", rel,
                    f"{target}: player-visible page points at a DM-marked "
                    f"asset; the projection refuses to ship it, so this "
                    f"link is a leak on the page and a hole on the site",
                    line)

    # The pen axis: markers valid, proposals answerable and off the
    # player surface. Binding — a page cannot use these markers to
    # silence the check that polices them.
    for rel in sorted(pages):
        page = pages[rel]
        if page.curation and page.curation not in CURATION:
            add("invalid-curation", "error", rel,
                f"'{page.curation}' is not one of {sorted(CURATION)} "
                f"(no marker = agent; curation is asserted, not inferred "
                f"from authorship)")
        if page.ingest and page.ingest not in INGEST:
            add("invalid-ingest", "error", rel,
                f"'{page.ingest}' is not one of {sorted(INGEST)}")
        if page.lint_opt and page.lint_opt not in LINT_OPTS:
            add("invalid-lint", "error", rel,
                f"'{page.lint_opt}' is not one of {sorted(LINT_OPTS)} "
                f"(the opt-out covers advisory checks only)")
        if page.merge_into:
            if page.merge_into not in pages:
                add("merge-target-missing", "error", rel,
                    f"proposes-merge-into: {page.merge_into} names no page "
                    f"in the effective wiki")
            if page.declared == "player":
                add("merge-proposal-visible", "error", rel,
                    "a merge proposal is unadjudicated and may not be "
                    "player-visible; the projection withholds it either "
                    "way, so drop the marker or merge it first")
            add("merge-pending", "info", rel,
                f"awaiting adjudication into {page.merge_into}")

    # Advisory findings go quiet where the pen is held elsewhere; binding
    # ones never do. Quieted findings are returned separately, never
    # dropped — the summary counts them and --show-quieted lists them.
    quiet = {rel for rel, pg in pages.items() if pg.quiet}
    kept, quieted = [], []
    for f in findings:
        (quieted if f["code"] in ADVISORY and f["path"] in quiet
         else kept).append(f)
    return kept, quieted


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}
    log_name = "log.md"
    contribs = None
    if "--log" in argv:
        log_name = argv[argv.index("--log") + 1]
        args = [a for a in args if a != log_name]
    if "--contribs" in argv:
        contribs = Path(argv[argv.index("--contribs") + 1])
        args = [a for a in args if a != str(contribs)]
    if not args and os.environ.get("EDDIC_CONFIG"):
        # Running as a vendored eddic verb: take the wiki from config.
        cfg_path = Path(os.environ["EDDIC_CONFIG"])
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        campaign = cfg_path.parent.parent
        args = [str(campaign / cfg.get("wiki_dir", "wiki"))]
        if "--log" not in argv:
            log_name = cfg.get("log", "log.md")
        if contribs is None:
            contribs = campaign / cfg.get("contribs_dir", "contribs")
    if len(args) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    root = Path(args[0])
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    if contribs is None:
        contribs = root.parent / "contribs"

    binding, quieted = lint(root, log_name, contribs)
    sev_rank = {"error": 0, "warning": 1, "info": 2}
    # Counts drive the exit code, so they come from the binding findings
    # alone: --show-quieted displays what was suppressed, it never
    # revives it into enforcement.
    counts = {s: sum(1 for f in binding if f["severity"] == s) for s in sev_rank}
    counts["quieted"] = len(quieted)
    findings = binding
    if "--show-quieted" in flags:
        findings = binding + [dict(f, quieted=True) for f in quieted]
    findings.sort(key=lambda f: (sev_rank[f["severity"]], f["path"], f["line"] or 0))

    if "--json" in flags:
        print(json.dumps({"findings": findings, "summary": counts}, indent=2))
    else:
        for f in findings:
            loc = f"{f['path']}:{f['line']}" if f["line"] else f["path"]
            mark = " (quieted)" if f.get("quieted") else ""
            print(f"{f['severity']:<8} {f['code']:<16} {loc} — {f['detail']}{mark}")
        print(f"\n{counts['error']} error(s), {counts['warning']} warning(s), "
              f"{counts['info']} info(s)")
        if quieted and "--show-quieted" not in flags:
            print(f"{counts['quieted']} advisory finding(s) quieted on "
                  f"human-curated, opted-out, or proposal pages "
                  f"(--show-quieted to list)")

    if counts["error"] or ("--strict" in flags and counts["warning"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
