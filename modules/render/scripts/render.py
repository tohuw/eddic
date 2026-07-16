# /// script
# requires-python = ">=3.9"
# dependencies = ["markdown-it-py>=3"]
# ///
"""eddic build — render a markdown wiki tree to a static HTML mirror.

Usage:
    uv run render.py [--src DIR] [--out DIR] [--template FILE]
        [--site-name NAME]
    (bare, as a vendored eddic verb: projection_dir -> site_dir and
     site_name come from EDDIC_CONFIG; the default template is
     .eddic/page.html if present)

Deliberately exactly a wiki renderer and nothing more: each page.md
becomes page.html in the mirrored tree; relative .md links are
rewritten to .html (fragments preserved); headings get slug ids so
fragment links land; the first H1 is the title; frontmatter is
stripped; non-markdown files are copied as-is; CLAUDE.md/AGENTS.md/
README.md and the operation log are never rendered. The template is
one HTML file with {{TITLE}}, {{SITE_NAME}}, and {{BODY}} tokens.
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path

from markdown_it import MarkdownIt

NON_CONTENT = {"CLAUDE.md", "AGENTS.md", "README.md"}
LINK = re.compile(r"(\[[^\]]*\]\()([^)\s]+)(\))")
HTAG = re.compile(r"<(h[1-6])>(.*?)</\1>", re.S)
DEFAULT_TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "page.html"


def split_frontmatter(text):
    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1:])
    return text


def slugify(heading):
    s = re.sub(r"<[^>]+>", "", heading).strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def rewrite_links(md_text):
    def sub(m):
        target = m.group(2)
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
            return m.group(0)
        raw, _, frag = target.partition("#")
        if raw.endswith((".md", ".MD")):
            target = raw[:-3] + ".html" + (f"#{frag}" if frag else "")
        return m.group(1) + target + m.group(3)
    return LINK.sub(sub, md_text)


def add_heading_ids(html):
    return HTAG.sub(lambda m: f'<{m.group(1)} id="{slugify(m.group(2))}">'
                              f"{m.group(2)}</{m.group(1)}>", html)


def main(argv):
    opts = dict(zip(argv, argv[1:]))
    src = out = None
    site = opts.get("--site-name", "")
    template_path = Path(opts["--template"]) if "--template" in opts else None
    log_name = "log.md"
    if os.environ.get("EDDIC_CONFIG") and "--src" not in opts:
        cfg_path = Path(os.environ["EDDIC_CONFIG"])
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        root = cfg_path.parent.parent
        src = root / cfg.get("projection_dir", "dist/player")
        out = root / cfg.get("site_dir", "dist/site")
        site = site or cfg.get("site_name", "")
        log_name = cfg.get("log", "log.md")
        if not template_path and (cfg_path.parent / "page.html").exists():
            template_path = cfg_path.parent / "page.html"
    if "--src" in opts:
        src = Path(opts["--src"])
    if "--out" in opts:
        out = Path(opts["--out"])
    if not src or not out:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    if not src.is_dir():
        print(f"not a directory: {src} (run `eddic project` first?)",
              file=sys.stderr)
        return 2
    template = (template_path or DEFAULT_TEMPLATE).read_text(encoding="utf-8")

    md = MarkdownIt("commonmark", {"typographer": True}).enable(
        ["table", "smartquotes"])
    if out.exists():
        shutil.rmtree(out)
    pages = assets = 0
    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(src)
        if p.suffix.lower() != ".md":
            dest = out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dest)
            assets += 1
            continue
        if p.name in NON_CONTENT or p.name == log_name:
            continue
        body_md = split_frontmatter(p.read_text(encoding="utf-8",
                                                errors="replace"))
        m = re.search(r"^# (.+)$", body_md, re.M)
        title = m.group(1).strip() if m else rel.stem.replace("-", " ").title()
        html = add_heading_ids(md.render(rewrite_links(body_md)))
        page = (template.replace("{{TITLE}}", title)
                        .replace("{{SITE_NAME}}", site)
                        .replace("{{BODY}}", html))
        dest = out / rel.with_suffix(".html")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(page, encoding="utf-8")
        pages += 1
    print(f"rendered {pages} page(s), copied {assets} asset(s) to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
