# /// script
# requires-python = ">=3.9"
# ///
"""eddic stage — build the retrieval worker's bundled corpora.

Usage:
    uv run stage.py [--src WIKI] [--projection DIR] [--out WORKER_DIR]
    (bare, as a vendored eddic verb: paths come from EDDIC_CONFIG;
     output defaults to <campaign>/worker/)

Writes corpus_dm.mjs (every content page of the DM master) and
corpus_player.mjs (every page of the projection) next to worker.js.
Corpora are ES modules bundled into the deployed script — DM content
never sits at a fetchable URL. Refuses if the projection is missing
or stale-empty: the player tier must come from `eddic project`, never
assembled here, so this script cannot make a visibility decision.

Exit codes: 0 staged, 1 refused, 2 usage error.
"""

import json
import os
import re
import sys
from pathlib import Path

NON_CONTENT = {"CLAUDE.md", "AGENTS.md", "README.md"}


def split_frontmatter(text):
    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1:])
    return text


def corpus(root, log_name, site):
    pages = {}
    for p in sorted(root.rglob("*.md")):
        if p.name in NON_CONTENT or p.name == log_name:
            continue
        body = split_frontmatter(p.read_text(encoding="utf-8",
                                             errors="replace")).strip()
        m = re.search(r"^# (.+)$", body, re.M)
        title = (m.group(1).strip() if m
                 else p.stem.replace("-", " ").title())
        pages[p.relative_to(root).as_posix()] = {"title": title,
                                                 "text": body}
    return {"site": site, "pages": pages}


def main(argv):
    opts = dict(zip(argv, argv[1:]))
    src = projection = out = None
    site, log_name = "campaign", "log.md"
    if os.environ.get("EDDIC_CONFIG") and "--src" not in opts:
        cfg_path = Path(os.environ["EDDIC_CONFIG"])
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        root = cfg_path.parent.parent
        src = root / cfg.get("wiki_dir", "wiki")
        projection = root / cfg.get("projection_dir", "dist/player")
        out = root / "worker"
        site = cfg.get("site_name", site)
        log_name = cfg.get("log", log_name)
    if "--src" in opts:
        src = Path(opts["--src"])
    if "--projection" in opts:
        projection = Path(opts["--projection"])
    if "--out" in opts:
        out = Path(opts["--out"])
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
    for name, tree in (("corpus_dm.mjs", src),
                       ("corpus_player.mjs", projection)):
        data = corpus(tree, log_name, site)
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
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
