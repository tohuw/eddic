# /// script
# requires-python = ">=3.9"
# ///
"""eddic atlas — render a wiki's cross-link graph as one self-contained,
firewall-safe, interactive map.

Usage:
    uv run graph.py --mode player|dm [--src DIR] [--out FILE]
    (bare, as a vendored eddic verb: --mode is still required; paths
     come from EDDIC_CONFIG)

--mode is explicit and NEVER inferred: it selects the SOURCE TREE.

  player  reads the projection (config `projection_dir`, default
          dist/player) and writes the player Atlas (default
          <site_dir>/atlas.html). The projection is a closed set — a
          player page can only link player pages — so the player Atlas
          cannot contain a DM page or a DM-only edge. That closure,
          not any filtering in this file, is what makes it safe.

  dm      reads the master wiki (config `wiki_dir`, default wiki) and
          writes the DM Atlas (default <campaign>/atlas.dm.html), which
          is DM-local and must never reach a player-facing deploy.

The graph is nodes (pages) and edges (resolved `.md` -> `.md` links).
Both are extracted with a resolver that MIRRORS eddic_lint.py (see
resolve_graph), so the Atlas's edges are exactly the links the linter
validates. Layout is deterministic — a seeded, fixed-math radial
cluster, everything sorted — so the same input tree yields a
byte-identical atlas.html. No Math.random, no clock, no unseeded
ordering, no network, stdlib only.

Exit codes: 0 written, 2 usage error.
"""

import json
import math
import os
import re
import sys
from pathlib import Path

NON_CONTENT = {"CLAUDE.md", "AGENTS.md", "README.md"}
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)\)")
# Inline HTML anchor and Markdown reference-definition targets — the two
# link forms the inline LINK regex misses. Mirrors eddic_lint.py so the
# Atlas's edges stay exactly the links the linter validates.
HREF = re.compile(r"""<a\b[^>]*?\shref\s*=\s*["']([^"'>\s]+)["']""", re.I)
REFDEF = re.compile(r"""^\s{0,3}\[[^\]]+\]:\s+<?([^>\s]+)>?""")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
FENCE = re.compile(r"^(```|~~~)")

# --- resolver: mirrors modules/lint/scripts/eddic_lint.py -------------
# The functions below are a verbatim-behaviour copy of eddic_lint.py's
# Page parsing and link resolution. They are replicated (not imported)
# because that file is vendored under a different module name in each
# campaign (lint.py), so a clean cross-module import is not portable.
# verify/run.py pins this resolver EQUAL to eddic_lint.py on a shared
# case; if lint's resolution changes, that test fails until this
# mirror is updated.


def slugify(heading):
    """GitHub-style anchor slug (mirrors eddic_lint.slugify)."""
    s = heading.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


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
    """Mirrors eddic_lint.link_targets: inline [text](url), reference
    definitions [id]: target, and inline HTML <a href> — every link form
    the resolver must see."""
    out = []
    for i, line in enumerate(body.splitlines()):
        for m in LINK.finditer(line):
            out.append((i + 1, m.group(1)))
        if (m := REFDEF.match(line)):
            out.append((i + 1, m.group(1)))
        for m in HREF.finditer(line):
            out.append((i + 1, m.group(1)))
    return out


class Page:
    """Mirrors eddic_lint.Page (the fields the graph needs)."""

    def __init__(self, path, root):
        self.path = path
        self.rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        self.frontmatter, body = split_frontmatter(text)
        self.body = strip_code(body)
        self.headings = [m.group(2) for line in self.body.splitlines()
                         if (m := HEADING.match(line))]
        self.anchors = {slugify(h) for h in self.headings}
        self.has_h1 = any(line.startswith("# ")
                          for line in self.body.splitlines())
        self.links = link_targets(self.body)
        lines = [ln.strip() for ln in self.body.splitlines() if ln.strip()]
        self.is_stub = bool(lines) and lines[-1] == "STUB"
        self.visibility = (self.frontmatter.get("visibility") or "dm").strip()

    def title(self):
        for line in self.body.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        stem = Path(self.rel).stem
        return stem.replace("-", " ").replace("_", " ").title()


def load_pages(root, log_name):
    """All content pages under root, keyed by relative posix path.
    Mirrors eddic_lint's page collection."""
    pages = {}
    for p in sorted(root.rglob("*.md")):
        if p.name in NON_CONTENT or p.name == log_name:
            continue
        pages[p.relative_to(root).as_posix()] = Page(p, root)
    return pages


def resolve_graph(root, pages):
    """(edges, inbound) where edges is a sorted list of (src, dst) and
    inbound maps rel -> inbound count. Link resolution mirrors the loop
    in eddic_lint.lint(): external schemes, site-rooted (/) links,
    same-page anchors, and non-.md targets yield no edge; a target that
    escapes the wiki or does not exist yields no edge (lint reports it,
    the graph omits it)."""
    inbound = {rel: 0 for rel in pages}
    adj = {rel: set() for rel in pages}
    root_res = root.resolve()
    for rel, page in pages.items():
        for _line, target in page.links:
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue  # external scheme
            if target.startswith("/"):
                continue  # site-rooted: lint errors, no edge
            raw, _, _frag = target.partition("#")
            if not raw:
                continue  # same-page anchor
            if not raw.endswith((".md", ".MD")):
                continue  # asset / non-wiki target
            dest = ((root / page.rel).parent / raw).resolve()
            try:
                dest_rel = dest.relative_to(root_res).as_posix()
            except ValueError:
                continue  # escapes the wiki
            if dest_rel not in pages:
                continue  # broken link
            if dest_rel not in adj[rel]:
                inbound[dest_rel] += 1
                adj[rel].add(dest_rel)
    edges = sorted((s, d) for s in adj for d in adj[s])
    return edges, inbound

# --- graph model ------------------------------------------------------


def category_of(rel):
    """First path segment; top-level pages cluster under 'root'."""
    return rel.split("/")[0] if "/" in rel else "root"


def build_nodes(pages, edges, inbound):
    """Node records with lint-derived flags. Reachability and orphan
    rules mirror eddic_lint: roots are index.md / index.dm.md, orphans
    have no inbound link, unreachable = not reachable from the roots."""
    roots = {r for r in ("index.md", "index.dm.md") if r in pages}
    adj = {rel: set() for rel in pages}
    for s, d in edges:
        adj[s].add(d)
    seen = set()
    if roots:
        seen, stack = set(roots), list(roots)
        while stack:
            nxt = adj[stack.pop()] - seen
            seen.update(nxt)
            stack.extend(sorted(nxt))
    outdeg = {rel: 0 for rel in pages}
    for s, _d in edges:
        outdeg[s] += 1
    nodes = []
    for rel in sorted(pages):
        page = pages[rel]
        degree = outdeg[rel] + inbound[rel]
        nodes.append({
            "id": rel,
            "label": page.title(),
            "category": category_of(rel),
            "degree": degree,
            "is_stub": page.is_stub,
            "is_orphan": inbound[rel] == 0 and rel not in roots,
            "is_unreachable": bool(roots) and rel not in seen,
        })
    return nodes

# --- deterministic layout --------------------------------------------
# Category-clustered radial. Categories are placed evenly around a
# circle (sorted, so the arrangement is fixed). Within a cluster, nodes
# are laid on a phyllotaxis (sunflower) spiral by sorted id — pure math,
# no randomness, no time. Same input tree => identical coordinates.

GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))
CLUSTER_R = 520.0      # distance of a category cluster from the centre
NODE_SPREAD = 46.0     # phyllotaxis packing within a cluster
BASE_RADIUS = 7.0      # smallest node radius
DEGREE_RADIUS = 4.2    # extra radius per sqrt(degree)


def layout(nodes):
    """Assign each node an (x, y). Coordinates are rounded to 2 dp for a
    stable, compact, byte-identical SVG."""
    cats = sorted({n["category"] for n in nodes})
    ncat = len(cats)
    cat_center = {}
    for i, c in enumerate(cats):
        ang = 2.0 * math.pi * i / ncat if ncat else 0.0
        cat_center[c] = (CLUSTER_R * math.cos(ang),
                         CLUSTER_R * math.sin(ang))
    by_cat = {c: [] for c in cats}
    for n in nodes:  # nodes already sorted by id
        by_cat[n["category"]].append(n)
    pos = {}
    for c in cats:
        cx, cy = cat_center[c]
        for j, n in enumerate(by_cat[c]):
            r = NODE_SPREAD * math.sqrt(j)
            theta = j * GOLDEN_ANGLE
            x = cx + r * math.cos(theta)
            y = cy + r * math.sin(theta)
            pos[n["id"]] = (round(x, 2), round(y, 2))
    return pos, cats


def node_radius(degree):
    return round(BASE_RADIUS + DEGREE_RADIUS * math.sqrt(degree), 2)

# --- SVG / HTML emission ---------------------------------------------
# A fixed categorical palette that reads on the parchment/dark shell.
# Categories are coloured by their sorted index (cycled), so colour
# assignment is deterministic.
PALETTE = [
    "#8a5a24", "#3f6f4e", "#6a4a7a", "#9a4b3f", "#3d6a86",
    "#7a6a2a", "#4a5a8a", "#8a4a6a", "#5a7a5a", "#7a5a3a",
    "#556a3a", "#6a3a5a",
]


def esc(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def raw_href(rel):
    """The page-relative .html path a page renders to (unescaped). The
    Atlas sits at the tree root, so this resolves both locally and behind
    the ASSETS binding."""
    return rel[:-3] + ".html" if rel.endswith(".md") else rel


def href_for(rel):
    """HTML-attribute-safe form of raw_href for the inline SVG."""
    return esc(raw_href(rel))


def adjacency(nodes, edges):
    """Per-node inbound/outbound adjacency, computed by inverting the
    already-resolved, already-sorted edge set — no new parsing. Returns
    (inbound, outbound), each mapping node id -> sorted list of node ids.
    Because `edges` is globally sorted by (src, dst), every appended list
    comes out sorted, so the emitted data is byte-stable. This is the
    'what links here' relation: inbound[p] is exactly the pages whose
    resolved links point at p. On the player Atlas the source tree is the
    projection, whose closure guarantees every such page is itself a
    player page — so no DM page is representable here by construction."""
    ids = [n["id"] for n in nodes]
    inbound = {i: [] for i in ids}
    outbound = {i: [] for i in ids}
    for s, d in edges:
        outbound[s].append(d)
        inbound[d].append(s)
    return inbound, outbound


def render_html(nodes, edges, pos, cats, mode, site_name):
    color = {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(cats)}
    xs = [pos[n["id"]][0] for n in nodes] or [0.0]
    ys = [pos[n["id"]][1] for n in nodes] or [0.0]
    pad = 80.0
    minx, maxx = min(xs) - pad, max(xs) + pad
    miny, maxy = min(ys) - pad, max(ys) + pad
    vb = f"{minx:.2f} {miny:.2f} {maxx - minx:.2f} {maxy - miny:.2f}"

    parts = []
    # Edges first (under the nodes), sorted for stable output.
    parts.append('<g class="edges">')
    for s, d in edges:
        x1, y1 = pos[s]
        x2, y2 = pos[d]
        parts.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" '
                     f'x2="{x2:.2f}" y2="{y2:.2f}"/>')
    parts.append('</g>')
    # Nodes, sorted by id (nodes list already sorted).
    parts.append('<g class="nodes">')
    for n in nodes:
        x, y = pos[n["id"]]
        r = node_radius(n["degree"])
        dim = n["is_orphan"] or n["is_stub"] or n["is_unreachable"]
        cls = "node dim" if dim else "node"
        flags = []
        if n["is_stub"]:
            flags.append("stub")
        if n["is_orphan"]:
            flags.append("orphan")
        if n["is_unreachable"]:
            flags.append("unreachable")
        tip = n["label"] + (f" [{', '.join(flags)}]" if flags else "")
        parts.append(
            f'<a class="{cls}" href="{href_for(n["id"])}" '
            f'data-id="{esc(n["id"])}" aria-label="{esc(n["label"])}">'
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" '
            f'fill="{color[n["category"]]}"/>'
            f'<title>{esc(tip)}</title>'
            f'<text x="{x:.2f}" y="{y - r - 3:.2f}">{esc(n["label"])}</text>'
            f'</a>')
    parts.append('</g>')
    svg_body = "\n".join(parts)

    legend = "\n".join(
        f'<span class="key"><i style="background:{color[c]}"></i>'
        f'{esc(c)}</span>' for c in cats)

    # Backlinks data: per-node inbound ("mentioned by") and outbound
    # ("links to") adjacency, inverted from the resolved edge set, plus a
    # label/href lookup. Sorted, ascii-escaped JSON => byte-stable; the
    # "<" escape closes any theoretical </script> breakout in a title.
    inbound, outbound = adjacency(nodes, edges)
    meta = {n["id"]: {"l": n["label"], "h": raw_href(n["id"])} for n in nodes}
    panel_obj = {
        "nodes": meta,
        "in": {k: v for k, v in inbound.items() if v},
        "out": {k: v for k, v in outbound.items() if v},
    }
    panel_data = json.dumps(
        panel_obj, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True).replace("<", "\\u003c")

    title = f"Atlas — {esc(site_name)}" if site_name else f"Atlas ({mode})"
    site_hdr = f" &mdash; {esc(site_name)}" if site_name else ""
    return HTML_TEMPLATE.format(
        title=title, mode=esc(mode), site_hdr=site_hdr,
        node_count=len(nodes), edge_count=len(edges),
        viewbox=vb, svg_body=svg_body, legend=legend, panel_data=panel_data)


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{title}</title>
<style>
  :root {{
    --ink: #26221b; --paper: #f7f2e8; --card: #fffdf7;
    --accent: #8a5a24; --faint: #857d6d; --rule: #ddd3bf;
    --edge: rgba(90,80,60,0.28);
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --ink: #eae3d3; --paper: #141210; --card: #1c1915;
      --accent: #d8ab5e; --faint: #9c937f; --rule: #37311f;
      --edge: rgba(220,200,150,0.20);
    }}
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; height: 100%; }}
  body {{
    background: var(--paper); color: var(--ink);
    font: 15px/1.4 Iowan Old Style, Palatino, Georgia, serif;
    display: flex; flex-direction: column;
  }}
  header {{
    padding: 0.7rem 1rem; border-bottom: 2px double var(--rule);
    display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.4rem 1rem;
  }}
  header h1 {{ margin: 0; font-size: 1.2rem; letter-spacing: 0.04em; }}
  header .meta {{ color: var(--faint); font-size: 0.85rem; }}
  .legend {{ margin-left: auto; display: flex; flex-wrap: wrap; gap: 0.6rem;
    font-size: 0.8rem; }}
  .key {{ display: inline-flex; align-items: center; gap: 0.3rem; }}
  .key i {{ width: 0.8rem; height: 0.8rem; border-radius: 50%;
    display: inline-block; }}
  #atlas {{ flex: 1; width: 100%; touch-action: none;
    background: var(--paper); cursor: grab; }}
  #atlas:active {{ cursor: grabbing; }}
  .edges line {{ stroke: var(--edge); stroke-width: 1; }}
  .node circle {{ stroke: var(--paper); stroke-width: 1.2;
    transition: opacity 0.1s; }}
  .node text {{ fill: var(--ink); font-size: 9px; text-anchor: middle;
    paint-order: stroke; stroke: var(--paper); stroke-width: 2.6px;
    pointer-events: none; opacity: 0; }}
  .node:hover text {{ opacity: 1; }}
  .node.dim circle {{ opacity: 0.4; }}
  .node.dim text {{ font-style: italic; }}
  .node.sel circle {{ stroke: var(--accent); stroke-width: 2.4; }}
  .node.sel text {{ opacity: 1; }}
  #panel {{
    position: absolute; top: 4.2rem; right: 1rem; width: 17rem;
    max-width: calc(100vw - 2rem); max-height: calc(100vh - 6rem);
    overflow: auto; background: var(--card); color: var(--ink);
    border: 1px solid var(--rule); border-radius: 6px;
    box-shadow: 0 4px 18px rgba(0,0,0,0.18); padding: 0.7rem 0.9rem;
    font-size: 0.9rem;
  }}
  #panel[hidden] {{ display: none; }}
  #panel h2 {{ margin: 0 1.4rem 0.15rem 0; font-size: 1rem; }}
  #panel h3 {{ margin: 0.7rem 0 0.2rem; font-size: 0.72rem;
    text-transform: uppercase; letter-spacing: 0.06em; color: var(--faint); }}
  #panel ul {{ margin: 0; padding: 0; list-style: none; }}
  #panel li {{ margin: 0.1rem 0; }}
  #panel a {{ color: var(--accent); text-decoration: none; }}
  #panel a:hover {{ text-decoration: underline; }}
  #panel .open {{ display: inline-block; font-size: 0.82rem; }}
  #panel .empty {{ color: var(--faint); font-style: italic; }}
  #panel-close {{
    position: absolute; top: 0.4rem; right: 0.5rem; border: 0;
    background: none; color: var(--faint); font-size: 1.2rem;
    line-height: 1; cursor: pointer; padding: 0.1rem 0.3rem;
  }}
  #panel-close:hover {{ color: var(--ink); }}
  footer {{ padding: 0.4rem 1rem; border-top: 1px solid var(--rule);
    color: var(--faint); font-size: 0.78rem; }}
</style>
</head>
<body>
<header>
  <h1>Atlas{site_hdr}</h1>
  <span class="meta">{node_count} pages, {edge_count} links &middot; {mode} view</span>
  <span class="legend">{legend}</span>
</header>
<svg id="atlas" viewBox="{viewbox}" preserveAspectRatio="xMidYMid meet"
     xmlns="http://www.w3.org/2000/svg">
<g id="viewport">
{svg_body}
</g>
</svg>
<aside id="panel" hidden>
  <button id="panel-close" type="button" aria-label="Close">&times;</button>
  <h2 id="panel-title"></h2>
  <a id="panel-open" class="open" href="#">Open this page &rarr;</a>
  <section id="panel-in"><h3>Mentioned by</h3><ul></ul></section>
  <section id="panel-out"><h3>Links to</h3><ul></ul></section>
</aside>
<footer>Drag to pan, scroll to zoom, click a page for its backlinks;
open it from the panel. Dimmed = stub, orphan, or unreachable.</footer>
<script>
var ATLAS_DATA = {panel_data};
(function() {{
  var svg = document.getElementById('atlas');
  var vp = document.getElementById('viewport');
  var s = 1, tx = 0, ty = 0, drag = false, moved = false, px = 0, py = 0;
  function apply() {{
    vp.setAttribute('transform', 'translate(' + tx + ' ' + ty +
      ') scale(' + s + ')');
  }}
  svg.addEventListener('wheel', function(e) {{
    e.preventDefault();
    var f = e.deltaY < 0 ? 1.1 : 1 / 1.1;
    var r = svg.getBoundingClientRect();
    var cx = e.clientX - r.left, cy = e.clientY - r.top;
    tx = cx - (cx - tx) * f; ty = cy - (cy - ty) * f; s *= f; apply();
  }}, {{ passive: false }});
  svg.addEventListener('pointerdown', function(e) {{
    drag = true; moved = false; px = e.clientX - tx; py = e.clientY - ty;
  }});
  svg.addEventListener('pointermove', function(e) {{
    if (!drag) return;
    moved = true; tx = e.clientX - px; ty = e.clientY - py; apply();
  }});
  window.addEventListener('pointerup', function() {{ drag = false; }});

  // Backlinks panel: click a node to inspect its inbound ("mentioned
  // by") and outbound ("links to") pages, computed from the inverted
  // edge set. The node's own page opens from the panel, so a plain
  // click no longer navigates — it selects.
  var data = ATLAS_DATA;
  var panel = document.getElementById('panel');
  var pTitle = document.getElementById('panel-title');
  var pOpen = document.getElementById('panel-open');
  var inList = document.querySelector('#panel-in ul');
  var outList = document.querySelector('#panel-out ul');
  var selected = null;
  function fill(ul, ids) {{
    ul.textContent = '';
    if (!ids || !ids.length) {{
      var li = document.createElement('li');
      li.className = 'empty';
      li.textContent = 'none';
      ul.appendChild(li);
      return;
    }}
    ids.forEach(function(id) {{
      var meta = data.nodes[id] || {{ l: id, h: '#' }};
      var li = document.createElement('li');
      var a = document.createElement('a');
      a.setAttribute('href', meta.h);
      a.textContent = meta.l;
      li.appendChild(a);
      ul.appendChild(li);
    }});
  }}
  function select(el) {{
    var id = el.getAttribute('data-id');
    var meta = data.nodes[id];
    if (!meta) return;
    if (selected) selected.classList.remove('sel');
    selected = el;
    el.classList.add('sel');
    pTitle.textContent = meta.l;
    pOpen.setAttribute('href', meta.h);
    fill(inList, data['in'][id]);
    fill(outList, data.out[id]);
    panel.hidden = false;
  }}
  function close() {{
    panel.hidden = true;
    if (selected) {{ selected.classList.remove('sel'); selected = null; }}
  }}
  document.getElementById('panel-close').addEventListener('click', close);
  document.querySelectorAll('a.node').forEach(function(a) {{
    a.addEventListener('click', function(e) {{
      e.preventDefault();
      if (!moved) {{ e.stopPropagation(); select(a); }}
    }});
  }});
  svg.addEventListener('click', function() {{ if (!moved) close(); }});
}})();
</script>
</body>
</html>
"""

# --- CLI --------------------------------------------------------------


def resolve_paths(argv):
    """Return (mode, src, out, log_name, site_name) or raise SystemExit
    on a usage error. --mode is required and never inferred."""
    opts = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--mode", "--src", "--out"):
            if i + 1 >= len(argv):
                raise Usage(f"{a} needs a value")
            opts[a] = argv[i + 1]
            i += 2
        else:
            raise Usage(f"unknown argument: {a}")
    mode = opts.get("--mode")
    if mode not in ("player", "dm"):
        raise Usage("--mode player|dm is required (never inferred)")

    src = Path(opts["--src"]) if "--src" in opts else None
    out = Path(opts["--out"]) if "--out" in opts else None
    log_name = "log.md"
    site_name = ""
    if os.environ.get("EDDIC_CONFIG") and src is None:
        cfg_path = Path(os.environ["EDDIC_CONFIG"])
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        root = cfg_path.parent.parent
        log_name = cfg.get("log", "log.md")
        site_name = cfg.get("site_name", "")
        if mode == "player":
            src = root / cfg.get("projection_dir", "dist/player")
            if out is None:
                out = root / cfg.get("site_dir", "dist/site") / "atlas.html"
        else:
            src = root / cfg.get("wiki_dir", "wiki")
            if out is None:
                out = root / "atlas.dm.html"
    if src is None:
        raise Usage("no --src and no EDDIC_CONFIG; cannot locate the wiki")
    if out is None:
        out = src.parent / ("atlas.html" if mode == "player"
                            else "atlas.dm.html")
    return mode, src, out, log_name, site_name


class Usage(Exception):
    pass


def main(argv):
    try:
        mode, src, out, log_name, site_name = resolve_paths(argv)
    except Usage as e:
        print(f"error: {e}\n", file=sys.stderr)
        print(__doc__.strip(), file=sys.stderr)
        return 2
    if not src.is_dir():
        print(f"not a directory: {src} "
              f"(run `eddic project` first for --mode player?)",
              file=sys.stderr)
        return 2

    pages = load_pages(src, log_name)
    edges, inbound = resolve_graph(src, pages)
    nodes = build_nodes(pages, edges, inbound)
    pos, cats = layout(nodes)
    html = render_html(nodes, edges, pos, cats, mode, site_name)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"atlas ({mode}): {len(nodes)} node(s), {len(edges)} edge(s) "
          f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
