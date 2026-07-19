# /// script
# requires-python = ">=3.9"
# ///
"""eddic stage — build the retrieval worker's bundled corpora and the
player companion page.

Usage:
    uv run stage.py [--src WIKI] [--projection DIR] [--out WORKER_DIR]
                    [--companion DIR] [--shell FILE]
    (bare, as a vendored eddic verb: paths come from EDDIC_CONFIG;
     output defaults to <campaign>/worker/)

Writes corpus_dm.mjs (every content page of the DM master) and
corpus_player.mjs (every page of the projection) next to worker.js.
Corpora are ES modules bundled into the deployed script — DM content
never sits at a fetchable URL. Refuses if the projection is missing
or stale-empty: the player tier must come from `eddic project`, never
assembled here, so this script cannot make a visibility decision.

Also writes companion.mjs: the player companion page (persona, setup
steps, and the player's connector URL), rendered once from the
companion module's single-source `player-kit.md`. The page carries a
`{{PLAYER_MCP_URL}}` sentinel the worker fills per request from the
authenticated token, so no token is ever baked into a bundled asset.
When no companion source is vendored (e.g. the retrieval verify
harness), a minimal placeholder page is written so the worker's import
always resolves.

Exit codes: 0 staged, 1 refused, 2 usage error.
"""

import html as _html
import json
import os
import re
import sys
from pathlib import Path

NON_CONTENT = {"CLAUDE.md", "AGENTS.md", "README.md"}

FALLBACK_SHELL = (
    "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
    "\n<meta name=\"robots\" content=\"noindex, nofollow\">\n"
    "<title>{{TITLE}} — {{SITE_NAME}}</title>\n</head>\n<body>\n<main>\n"
    "{{BODY}}\n</main>\n</body>\n</html>\n")

FALLBACK_KIT = (
    "# Your companion\n\nConnect an AI assistant to this campaign with "
    "your personal link:\n\n    {{PLAYER_MCP_URL}}\n")

# A little CSS scoped to the companion body, using the shell's own
# palette variables so the page matches the campaign site whether the
# real page.html shell or the fallback is in play.
COMPANION_STYLE = (
    "<style>\n"
    ".companion-pre, .persona { white-space: pre-wrap; word-break: "
    "break-word; overflow-x: auto; background: var(--card, #f4f4f4); "
    "border: 1px solid var(--rule-strong, #ccc); border-radius: 4px; "
    "padding: 0.9rem 1.1rem; font-size: 0.62em; line-height: 1.5; "
    "font-family: ui-monospace, monospace; }\n"
    ".persona { font-family: inherit; font-size: 0.66em; }\n"
    ".copy-cta { margin: 1.3rem 0 2rem; display: flex; flex-wrap: wrap; "
    "align-items: center; gap: 0.6rem 0.9rem; }\n"
    "#copy-link { cursor: pointer; font: inherit; font-size: 0.74em; "
    "font-weight: 600; padding: 0.75rem 1.5rem; color: var(--paper, #fff); "
    "background: var(--accent, #8a5a24); border: 0; border-radius: 7px; "
    "letter-spacing: 0.02em; }\n"
    "#copy-link:hover { background: var(--glow, #b07d3a); }\n"
    "#copy-link.copied { background: var(--faint, #857d6d); }\n"
    ".copy-hint { font-size: 0.6em; color: var(--faint, #857d6d); }\n"
    ".copy-wrap { position: relative; }\n"
    ".copy-wrap > .companion-pre, .copy-wrap > .persona { margin: 0; "
    "padding-right: 3.2rem; }\n"
    ".copy-icon { position: absolute; top: 0.5rem; right: 0.5rem; "
    "display: inline-flex; align-items: center; justify-content: center; "
    "width: 2rem; height: 2rem; padding: 0; cursor: pointer; "
    "color: var(--paper, #fff); background: var(--accent, #8a5a24); "
    "border: 0; border-radius: 6px; line-height: 0; }\n"
    ".copy-icon:hover { background: var(--glow, #b07d3a); }\n"
    ".copy-icon.copied { background: var(--faint, #857d6d); }\n"
    ".copy-icon svg { width: 1.05rem; height: 1.05rem; display: block; }\n"
    "</style>\n")

# A prominent copy-to-clipboard button that copies THIS page's own live
# URL (window.location.href — the /<token>/companion capability URL,
# token already in the path). The whole player instruction: copy, paste
# into your assistant. Inline JS; the worker sets its own headers (no
# CSP), so this runs. clipboard API with an execCommand fallback.
COMPANION_COPY = (
    '<div class="copy-cta">\n'
    '<button id="copy-link" type="button">Copy my link</button>\n'
    '<span class="copy-hint">then paste it into your AI assistant</span>\n'
    "</div>\n"
    "<script>\n"
    "(function(){var b=document.getElementById('copy-link');if(!b)return;"
    "var label=b.textContent;"
    "function flash(){b.textContent='Copied!';b.classList.add('copied');"
    "setTimeout(function(){b.textContent=label;"
    "b.classList.remove('copied');},2000);}"
    "function fallback(u){var t=document.createElement('textarea');"
    "t.value=u;t.setAttribute('readonly','');t.style.position='absolute';"
    "t.style.left='-9999px';document.body.appendChild(t);t.select();"
    "try{document.execCommand('copy');}catch(e){}"
    "document.body.removeChild(t);}"
    "b.addEventListener('click',function(){var u=window.location.href;"
    "if(navigator.clipboard&&navigator.clipboard.writeText){"
    "navigator.clipboard.writeText(u).then(flash,function(){"
    "fallback(u);flash();});}else{fallback(u);flash();}});})();\n"
    "</script>\n")

# The stacked-pages "copy code" glyph, inline so the strict artifact-
# style CSP a served page runs under never blocks an external asset.
COPY_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2">'
    '</rect><path d="M5 15V5a2 2 0 0 1 2-2h8"></path></svg>')

# Delegated handler for the inline copy-icon buttons on the two
# copyable blocks (persona, connection URL). Copies the associated
# block's textContent — the exact string, no markup — with an
# execCommand fallback, and flips the icon to a check for ~2s.
COMPANION_ICON_JS = (
    "<script>\n"
    "(function(){var CHECK='<svg viewBox=\"0 0 24 24\" fill=\"none\" "
    "stroke=\"currentColor\" stroke-width=\"2.5\" stroke-linecap=\"round\" "
    "stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M20 6 9 17l"
    "-5-5\"></path></svg>';"
    "function fb(x){var t=document.createElement('textarea');t.value=x;"
    "t.setAttribute('readonly','');t.style.position='absolute';"
    "t.style.left='-9999px';document.body.appendChild(t);t.select();"
    "try{document.execCommand('copy');}catch(e){}"
    "document.body.removeChild(t);}"
    "document.addEventListener('click',function(e){"
    "var btn=e.target.closest&&e.target.closest('.copy-icon');if(!btn)return;"
    "var blk=btn.parentElement.querySelector('.persona,.companion-pre');"
    "if(!blk)return;var txt=blk.textContent.replace(/\\s+$/,'');"
    "var orig=btn.innerHTML;"
    "function done(){btn.classList.add('copied');btn.innerHTML=CHECK;"
    "setTimeout(function(){btn.classList.remove('copied');"
    "btn.innerHTML=orig;},2000);}"
    "if(navigator.clipboard&&navigator.clipboard.writeText){"
    "navigator.clipboard.writeText(txt).then(done,function(){"
    "fb(txt);done();});}else{fb(txt);done();}});})();\n"
    "</script>\n")


def copy_block(inner, label):
    """Wrap a copyable block (a <pre>) in a positioned container with an
    inline copy-icon button. The button copies the block's own
    textContent at click time, so the wired target is exactly the
    block's text — including the runtime-filled MCP URL — never markup."""
    return ('<div class="copy-wrap">' + inner
            + '<button class="copy-icon" type="button" aria-label="'
            + label + '" title="' + label + '">' + COPY_SVG
            + "</button></div>")


def split_frontmatter(text):
    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1:])
    return text


def frontmatter_field(text, key):
    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                break
            if lines[i].startswith(f"{key}:"):
                return lines[i].partition(":")[2].strip()
    return ""


def _inline(s):
    """Inline markdown on already-escaped text: code, bold, links."""
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', s)
    return s


def _special(line):
    return (line.startswith(("#", ">", "<", "    "))
            or line.lstrip().startswith("- "))


def render_md(text):
    """A deliberately small markdown->HTML renderer, stdlib-only, for
    the companion page: headings, paragraphs, blockquotes, unordered
    lists, indented code blocks, raw-HTML passthrough blocks (an HTML
    comment or an injected block), and inline code/bold/links. The
    companion source is authored to this subset on purpose — no
    dependency, works under `uv run` and a bare interpreter alike."""
    esc = lambda x: _html.escape(x, quote=False)
    lines = text.split("\n")
    out, i, n = [], 0, len(text.split("\n"))
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.lstrip().startswith("<"):          # raw HTML passthrough
            buf = []
            while i < n and lines[i].strip():
                buf.append(lines[i])
                i += 1
            out.append("\n".join(buf))
            continue
        if line.startswith("    "):                # indented code block
            buf = []
            while i < n and lines[i].startswith("    "):
                buf.append(lines[i][4:])
                i += 1
            out.append('<pre class="companion-pre"><code>'
                       + esc("\n".join(buf)) + "</code></pre>")
            continue
        if line.startswith("## "):
            out.append("<h2>" + _inline(esc(line[3:].strip())) + "</h2>")
            i += 1
            continue
        if line.startswith("# "):
            out.append("<h1>" + _inline(esc(line[2:].strip())) + "</h1>")
            i += 1
            continue
        if line.startswith(">"):                   # blockquote
            buf = []
            while i < n and lines[i].startswith(">"):
                buf.append(lines[i].lstrip(">").strip())
                i += 1
            out.append("<blockquote>" + _inline(esc(" ".join(buf)))
                       + "</blockquote>")
            continue
        if line.lstrip().startswith("- "):         # unordered list
            items = []
            while i < n and lines[i].lstrip().startswith("- "):
                item = lines[i].lstrip()[2:]
                i += 1
                while (i < n and lines[i].strip()
                       and lines[i].startswith(" ")
                       and not lines[i].lstrip().startswith("- ")):
                    item += " " + lines[i].strip()
                    i += 1
                items.append("<li>" + _inline(esc(item)) + "</li>")
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        buf = []                                   # paragraph
        while i < n and lines[i].strip() and not _special(lines[i]):
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>" + _inline(esc(" ".join(buf))) + "</p>")
    return "\n".join(out)


def companion_html(kit_md, persona_md, site, shell):
    """Render the single-source player kit to a full HTML page. Fills
    {{SITE_NAME}} now; leaves {{PLAYER_MCP_URL}} for the worker to fill
    per request; inlines the persona (its own single source) into a
    copyable block. Returns HTML carrying the runtime sentinel."""
    kit = kit_md.replace("{{SITE_NAME}}", site)
    body = render_md(kit)
    if persona_md is not None:
        persona = persona_md.replace("{{SITE_NAME}}", site).strip()
        block = ('<pre class="persona">'
                 + _html.escape(persona, quote=False) + "</pre>")
        body = body.replace("<p>{{PLAYER_COMPANION}}</p>",
                            copy_block(block, "Copy the personality text"))
    # The manual-path connection URL block (rendered from the kit's
    # indented {{PLAYER_MCP_URL}} code block) gets its own copy icon; the
    # worker fills the sentinel per request, so the icon copies the real
    # /<token>/mcp URL at click time.
    mcp_pre = ('<pre class="companion-pre"><code>{{PLAYER_MCP_URL}}'
               "</code></pre>")
    if mcp_pre in body:
        body = body.replace(
            mcp_pre, copy_block(mcp_pre, "Copy the connection link"), 1)
    # The primary Copy-my-link button is the whole main instruction —
    # put it right under the first heading, prominent near the very top.
    if "</h1>" in body:
        body = body.replace("</h1>", "</h1>\n" + COMPANION_COPY, 1)
    else:
        body = COMPANION_COPY + body
    body = COMPANION_STYLE + body + COMPANION_ICON_JS
    return (shell.replace("{{TITLE}}", "Your companion")
                 .replace("{{SITE_NAME}}", site)
                 .replace("{{BODY}}", body))


def stage_companion(out, site, comp_dir, shell_path):
    """Write worker/companion.mjs. Uses the vendored companion kit +
    persona when present; otherwise a minimal placeholder page so the
    worker's static import always resolves. The MCP URL is never baked
    in — the page keeps a {{PLAYER_MCP_URL}} sentinel."""
    shell = (shell_path.read_text(encoding="utf-8")
             if shell_path and shell_path.is_file() else FALLBACK_SHELL)
    kit_path = comp_dir / "player-kit.md" if comp_dir else None
    persona_path = comp_dir / "player-companion.md" if comp_dir else None
    if kit_path and kit_path.is_file():
        kit_md = kit_path.read_text(encoding="utf-8")
        persona_md = (persona_path.read_text(encoding="utf-8")
                      if persona_path and persona_path.is_file() else None)
        source = "player-kit.md"
    else:
        kit_md, persona_md, source = FALLBACK_KIT, None, "placeholder"
    page = companion_html(kit_md, persona_md, site, shell)
    (out / "companion.mjs").write_text(
        "export default " + json.dumps({"html": page}, ensure_ascii=False)
        + ";\n", encoding="utf-8")
    print(f"staged companion.mjs: {len(page) // 1024} KB ({source})")


def page_entry(path, rel, pages):
    body = split_frontmatter(path.read_text(encoding="utf-8",
                                            errors="replace")).strip()
    m = re.search(r"^# (.+)$", body, re.M)
    title = (m.group(1).strip() if m
             else Path(rel).stem.replace("-", " ").title())
    pages[rel] = {"title": title, "text": body}


def corpus(root, log_name, site, contribs=None):
    """Effective corpus: base pages, then contributor overlays applied
    at their targets (a broken overlay set is a build error upstream —
    lint and project refuse it; here the last consistent write wins
    the same way project.py resolved it)."""
    pages = {}
    for p in sorted(root.rglob("*.md")):
        if p.name in NON_CONTENT or p.name == log_name:
            continue
        page_entry(p, p.relative_to(root).as_posix(), pages)
    if contribs and contribs.is_dir():
        for cdir in sorted(d for d in contribs.iterdir() if d.is_dir()):
            for p in sorted(cdir.rglob("*.md")):
                if p.name in NON_CONTENT or p.name == log_name:
                    continue
                text = p.read_text(encoding="utf-8", errors="replace")
                target = (frontmatter_field(text, "replaces")
                          or p.relative_to(cdir).as_posix())
                page_entry(p, target, pages)
    return {"site": site, "pages": pages}


def main(argv):
    opts = dict(zip(argv, argv[1:]))
    src = projection = out = contribs = comp_dir = shell_path = None
    site, log_name = "campaign", "log.md"
    if os.environ.get("EDDIC_CONFIG") and "--src" not in opts:
        cfg_path = Path(os.environ["EDDIC_CONFIG"])
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        root = cfg_path.parent.parent
        src = root / cfg.get("wiki_dir", "wiki")
        projection = root / cfg.get("projection_dir", "dist/player")
        contribs = root / cfg.get("contribs_dir", "contribs")
        out = root / "worker"
        site = cfg.get("site_name", site)
        log_name = cfg.get("log", log_name)
        # Companion page source is vendored beside the CLI, so the same
        # single-source kit renders the hosted page; the site shell is
        # the render module's vendored page.html when present.
        comp_dir = cfg_path.parent / "companion"
        shell_path = cfg_path.parent / "page.html"
    if "--src" in opts:
        src = Path(opts["--src"])
        if contribs is None:
            contribs = src.parent / "contribs"
    if "--contribs" in opts:
        contribs = Path(opts["--contribs"])
    if "--projection" in opts:
        projection = Path(opts["--projection"])
    if "--out" in opts:
        out = Path(opts["--out"])
    if "--companion" in opts:
        comp_dir = Path(opts["--companion"])
    if "--shell" in opts:
        shell_path = Path(opts["--shell"])
    if not src or not projection or not out:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    if not src.is_dir():
        print(f"not a directory: {src}", file=sys.stderr)
        return 2
    if not projection.is_dir() or not any(projection.rglob("*.md")):
        print("stage: REFUSED — projection missing or empty; run "
              "`eddic project` first (the player tier only ever comes "
              "from the projection)", file=sys.stderr)
        return 1

    out.mkdir(parents=True, exist_ok=True)
    # DM corpus sees the effective wiki (overlays applied); the player
    # corpus comes from the projection, which already applied them.
    for name, tree, cdir in (("corpus_dm.mjs", src, contribs),
                             ("corpus_player.mjs", projection, None)):
        data = corpus(tree, log_name, site, cdir)
        (out / name).write_text(
            "export default " + json.dumps(data, ensure_ascii=False,
                                           indent=1) + ";\n",
            encoding="utf-8")
        size = (out / name).stat().st_size
        print(f"staged {name}: {len(data['pages'])} page(s), "
              f"{size // 1024} KB")
        if size > 900_000:
            print(f"warning: {name} nears the 1 MB free-tier bundle "
                  "limit; a KV-backed corpus is the growth path",
                  file=sys.stderr)
    stage_companion(out, site, comp_dir, shell_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
