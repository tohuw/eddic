# /// script
# requires-python = ">=3.9"
# ///
"""eddic lint — deterministic wiki health reporter.

Usage:
    uv run eddic_lint.py <wiki_dir> [--json] [--strict] [--log NAME]

Checks a tree of interlinked markdown pages:

  errors    broken relative links, broken anchors, missing H1,
            malformed operation-log entries, firewall breaches
            (player-visible page links a DM-only page; visibility
            fails closed: no frontmatter marker means DM-only)
  warnings  stub drift (STUB-marked page grown past stub size),
            orphans (no inbound links), pages unreachable from the
            root index
  info      tiny pages not marked STUB; firewall check skipped
            because the wiki carries no visibility frontmatter yet

Exit codes: 0 clean (infos allowed), 1 errors (or warnings with
--strict), 2 usage error. --json emits the machine-readable report.

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
             "attribution", "consent", "sever"}
TRANSACTABILITY = {"transactable", "transactable-with-attribution",
                   "local-only"}
GENERIC_AUTHORSHIP = {"human", "agent", "machine", "transcript"}
LOG_HEADER = re.compile(r"^## \[\d{4}-\d{2}-\d{2}\] (\S+) \| .+$")
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)\)")
# Inline HTML anchor and Markdown reference-definition targets. These
# are the two link forms the inline LINK regex misses; both can name a
# DM page just as an inline link can, so both must feed the firewall.
HREF = re.compile(r"""<a\b[^>]*?\shref\s*=\s*["']([^"'>\s]+)["']""", re.I)
REFDEF = re.compile(r"""^\s{0,3}\[[^\]]+\]:\s+<?([^>\s]+)>?""")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
FENCE = re.compile(r"^(```|~~~)")
STUB_WORD_LIMIT = 150
TINY_WORD_LIMIT = 30


def slugify(heading):
    """GitHub-style anchor slug."""
    s = heading.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


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
        self.visibility = (self.frontmatter.get("visibility") or "dm").strip()


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


def strip_code(body):
    out, fenced = [], False
    for line in body.splitlines():
        if FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            out.append(re.sub(r"`[^`]*`", "", line))
    return "\n".join(out)


def link_targets(body):
    """(line_no, target) pairs for every link target in the body: inline
    [text](url), reference definitions [id]: target (whose URL is what a
    [text][id] use resolves to, so harvesting the definitions covers the
    uses without a second pass), and inline HTML <a href>. All three
    forms flow through the same resolution and firewall check, so a DM
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
            if not raw.endswith((".md", ".MD")):
                continue  # static asset or non-wiki target; not ours to judge
            # resolve at the page's effective wiki location — for a
            # contrib overlay that is the shadowed path, not the file
            dest = ((root / page.rel).parent / raw).resolve()
            try:
                dest_rel = dest.relative_to(root.resolve()).as_posix()
            except ValueError:
                add("broken-link", "error", rel,
                    f"link escapes the wiki: {target}", line)
                continue
            if dest_rel not in pages:
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

    return findings


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

    findings = lint(root, log_name, contribs)
    sev_rank = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: (sev_rank[f["severity"]], f["path"], f["line"] or 0))
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in sev_rank}

    if "--json" in flags:
        print(json.dumps({"findings": findings, "summary": counts}, indent=2))
    else:
        for f in findings:
            loc = f"{f['path']}:{f['line']}" if f["line"] else f["path"]
            print(f"{f['severity']:<8} {f['code']:<16} {loc} — {f['detail']}")
        print(f"\n{counts['error']} error(s), {counts['warning']} warning(s), "
              f"{counts['info']} info(s)")

    if counts["error"] or ("--strict" in flags and counts["warning"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
