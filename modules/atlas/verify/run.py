# /// script
# requires-python = ">=3.9"
# ///
"""Verify the atlas module against a planted fixture. Deterministic and
offline. Asserts:

  (a) node/edge extraction matches a golden;
  (b) the player-mode Atlas, built from the projection, contains NO
      DM page and NO DM-only edge — a planted DM->player breach in the
      master cannot reach the player build (the projection's closure);
  (c) determinism — the same input yields a byte-identical atlas.html
      across two runs;
  (d) the resolver matches eddic_lint.py: orphan and unreachable sets
      (pure functions of the resolved edge graph) agree, and the shared
      primitives (slugify, split_frontmatter, strip_code, link_targets)
      are identical.
"""

import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GRAPH_PY = HERE.parent / "scripts" / "graph.py"
LINT_PY = HERE.parent.parent / "lint" / "scripts" / "eddic_lint.py"
PROJECT_PY = HERE.parent.parent / "wiki" / "scripts" / "project.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def plant(root):
    # index (player) -> warden (player); warden -> index. ghost is a
    # player stub nobody links (orphan + unreachable). secret is DM-only
    # (no visibility marker) and links a player page: a DM->player edge,
    # the planted breach that must never reach the player build.
    write(root, "index.md",
          "---\nvisibility: player\n---\n\n# Realm\n\n"
          "See [the Warden](characters/warden.md).\n")
    write(root, "characters/warden.md",
          "---\nvisibility: player\n---\n\n# The Warden\n\n"
          "Back to [the realm](../index.md).\n")
    write(root, "characters/ghost.md", "# Ghost\n\nSTUB\n")
    write(root, "lore/secret.md",
          "# The Sunken City\n\nA DM secret linking [the realm](../index.md).\n")


GOLDEN_EDGES = [
    ("characters/warden.md", "index.md"),
    ("index.md", "characters/warden.md"),
    ("lore/secret.md", "index.md"),
]
GOLDEN_NODES = {
    "characters/ghost.md": ("characters", 0, True, True, True),
    "characters/warden.md": ("characters", 2, False, False, False),
    "index.md": ("root", 3, False, False, False),
    "lore/secret.md": ("lore", 1, False, True, True),
}


def check(results, ok, msg):
    results.append((bool(ok), msg))
    return bool(ok)


def main():
    if not shutil.which("uv"):
        print("SKIP: uv not on PATH")
        return 0
    graph = load(GRAPH_PY, "atlas_graph")
    lint = load(LINT_PY, "eddic_lint")
    tmp = Path(tempfile.mkdtemp(prefix="eddic-atlas-verify-"))
    master = tmp / "wiki"
    plant(master)
    results = []

    # (a) node/edge extraction matches golden (over the full master).
    pages = graph.load_pages(master, "log.md")
    edges, inbound = graph.resolve_graph(master, pages)
    nodes = graph.build_nodes(pages, edges, inbound)
    check(results, edges == GOLDEN_EDGES, f"golden edges (got {edges})")
    got_nodes = {n["id"]: (n["category"], n["degree"], n["is_stub"],
                           n["is_orphan"], n["is_unreachable"]) for n in nodes}
    check(results, got_nodes == GOLDEN_NODES, f"golden nodes (got {got_nodes})")

    # (d) resolver matches eddic_lint.py on the shared master.
    findings = lint.lint(master, "log.md")
    lint_orphan = {f["path"] for f in findings if f["code"] == "orphan"}
    lint_unreach = {f["path"] for f in findings if f["code"] == "unreachable"}
    graph_orphan = {n["id"] for n in nodes if n["is_orphan"]}
    graph_unreach = {n["id"] for n in nodes if n["is_unreachable"]}
    check(results, lint_orphan == graph_orphan,
          f"resolver: orphan sets agree ({lint_orphan} vs {graph_orphan})")
    check(results, lint_unreach == graph_unreach,
          f"resolver: unreachable sets agree "
          f"({lint_unreach} vs {graph_unreach})")
    # shared primitives are identical
    prim_ok = (graph.slugify("The Oath!") == lint.slugify("The Oath!")
               and graph.strip_code("`x` a") == lint.strip_code("`x` a")
               and graph.split_frontmatter("---\nvisibility: player\n---\nB")
               == lint.split_frontmatter("---\nvisibility: player\n---\nB")
               and graph.link_targets("[a](b.md) [c](d.md)")
               == lint.link_targets("[a](b.md) [c](d.md)"))
    check(results, prim_ok, "resolver: shared primitives identical")

    # (b) player-mode Atlas built from the projection excludes DM pages.
    proj = tmp / "dist" / "player"
    pr = subprocess.run(
        ["uv", "run", str(PROJECT_PY), "--src", str(master),
         "--out", str(proj)], capture_output=True, text=True)
    check(results, pr.returncode == 0,
          f"projection succeeds ({pr.stderr.strip()})")
    check(results, not (proj / "lore" / "secret.md").exists(),
          "projection withholds the DM page")
    player_atlas = tmp / "dist" / "site" / "atlas.html"
    ar = subprocess.run(
        ["uv", "run", str(GRAPH_PY), "--mode", "player", "--src", str(proj),
         "--out", str(player_atlas)], capture_output=True, text=True)
    check(results, ar.returncode == 0, f"player atlas builds ({ar.stderr.strip()})")
    html = player_atlas.read_text(encoding="utf-8")
    check(results, "secret" not in html and "Sunken City" not in html,
          "player Atlas contains NO DM page")
    check(results, "warden.html" in html,
          "player Atlas does contain a player page node")
    # the DM->player edge cannot exist because its source node is gone
    ppages = graph.load_pages(proj, "log.md")
    pedges, _ = graph.resolve_graph(proj, ppages)
    check(results, all(s != "lore/secret.md" for s, _ in pedges),
          "player Atlas contains NO DM-only edge")

    # a DM-mode atlas over the master, by contrast, DOES see the breach,
    # proving mode selection (source-tree choice) is the firewall.
    dm_atlas = tmp / "atlas.dm.html"
    dr = subprocess.run(
        ["uv", "run", str(GRAPH_PY), "--mode", "dm", "--src", str(master),
         "--out", str(dm_atlas)], capture_output=True, text=True)
    check(results, dr.returncode == 0 and "secret.html" in
          dm_atlas.read_text(encoding="utf-8"),
          "DM Atlas (master source) does see the DM page — mode is the seam")

    # (c) determinism — same input, byte-identical output across runs.
    a1, a2 = tmp / "d1.html", tmp / "d2.html"
    for out in (a1, a2):
        subprocess.run(["uv", "run", str(GRAPH_PY), "--mode", "dm",
                        "--src", str(master), "--out", str(out)],
                       capture_output=True, text=True)
    check(results, a1.read_bytes() == a2.read_bytes(),
          "determinism: byte-identical across two runs")

    # --mode is required and never inferred.
    nomode = subprocess.run(
        ["uv", "run", str(GRAPH_PY), "--src", str(master),
         "--out", str(tmp / "x.html")], capture_output=True, text=True)
    check(results, nomode.returncode == 2, "--mode is required (exit 2)")

    for ok, msg in results:
        print(("ok  " if ok else "FAIL"), msg)
    if any(not ok for ok, _ in results):
        return 1
    print("verify ok: atlas module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
