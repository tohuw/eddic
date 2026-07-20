# /// script
# requires-python = ">=3.9"
# ///
"""Verify the retrieval module: plant a campaign wiki + projection,
stage the corpora, copy the worker template beside them, then drive
the worker's fetch handler in node (auth, both token styles, tier
isolation, search). Skips gracefully if node is absent (CI has it)."""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MOD = Path(__file__).resolve().parent.parent
PLAYER_FM = "---\nvisibility: player\n---\n\n"


def load(rel, name):
    """Import a module verb (stage.py / suggestions.py) from its file
    path so its pure functions can be unit-tested here without a shell."""
    spec = importlib.util.spec_from_file_location(
        name, MOD / "scripts" / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def unit_checks():
    """Pure-function hardening checks for the two Python verbs. Returns
    the number of failures (0 clean)."""
    fails = 0

    def ck(ok, msg):
        nonlocal fails
        print(("ok   " if ok else "FAIL ") + msg)
        if not ok:
            fails += 1

    stage = load("stage.py", "eddic_stage")
    # bug 4: a hostile site_name must be HTML-escaped in the shell, never
    # land as a live <script> in the rendered companion page.
    page = stage.companion_html(
        stage.FALLBACK_KIT, None, "<script>alert(1)</script>",
        stage.FALLBACK_SHELL)
    ck("<script>alert(1)</script>" not in page,
       "stage: hostile site_name is not emitted raw into the page")
    ck("&lt;script&gt;" in page,
       "stage: hostile site_name is HTML-escaped in the shell/title")
    # bug 4: a javascript: link is not turned into a live href; a safe
    # link is; an href with a quote cannot break out of the attribute.
    ck('href="javascript' not in stage._inline("[x](javascript:alert(1))"),
       "stage: javascript: link is not emitted as a live href")
    ck('<a href="https://ok">x</a>' == stage._inline("[x](https://ok)"),
       "stage: an http(s) link is still rendered")
    ck('<a href="page.md">x</a>' == stage._inline("[x](page.md)"),
       "stage: a relative link is still rendered")
    quoted = stage._inline('[x](http://a"onmouseover=b)')
    ck('href="http://a"onmouseover' not in quoted and "%22" in quoted,
       "stage: a quote in a link URL is neutralized in the href")

    sug = load("suggestions.py", "eddic_suggestions")
    # bug 6: a newline-bearing title must not inject a new frontmatter
    # line; it is quoted into a single YAML scalar.
    doc = sug.render({
        "id": "abcdef12", "kind": "page",
        "title": "Evil\ninjected: pwned", "content": "body",
        "status": "pending", "tier": "player",
        "created": "2026-07-20T00:00:00"})
    fm = doc.split("---")[1]
    fm_lines = [ln for ln in fm.strip().split("\n") if ln.strip()]
    ck(not any(ln.startswith("injected:") for ln in fm_lines),
       "suggestions: a newline in a title injects no frontmatter key")
    ck(len([ln for ln in fm_lines if ln.startswith("title:")]) == 1,
       "suggestions: the title is a single YAML scalar (no line break)")
    # a colon-bearing path is quoted, not emitted as a bare mapping
    doc2 = sug.render({
        "id": "beef", "kind": "edit", "path": "a: b\nfake: x",
        "suggestion": "s", "status": "pending", "tier": "player",
        "created": "2026-07-20T00:00:00"})
    fm2 = [ln for ln in doc2.split("---")[1].strip().split("\n")
           if ln.strip()]
    ck(not any(ln.startswith("fake:") for ln in fm2),
       "suggestions: a newline in a path injects no frontmatter key")

    return fails


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def main():
    if unit_checks():
        return 1
    node = shutil.which("node")
    if not node:
        print("SKIP: node not on PATH (worker harness needs it)")
        return 0
    tmp = Path(tempfile.mkdtemp(prefix="eddic-retrieval-verify-"))
    try:
        wiki, proj, wdir = tmp / "wiki", tmp / "player", tmp / "worker"
        write(wiki, "index.md", PLAYER_FM + "# Realm\n\n[keep](keep.md)\n")
        write(wiki, "keep.md", PLAYER_FM + "# The Keep\n\nA sturdy keep; "
              "its garrison is small and its walls are old.\n")
        write(wiki, "keep.dm.md", "# The Keep — full truth\n\nThe cellars "
              "hold the campaign's midpoint twist.\n")
        # projection = the player subset (as `eddic project` would emit)
        write(proj, "index.md", PLAYER_FM + "# Realm\n\n[keep](keep.md)\n")
        write(proj, "keep.md", PLAYER_FM + "# The Keep\n\nA sturdy keep; "
              "its garrison is small and its walls are old.\n")

        stage = subprocess.run(
            [sys.executable, str(MOD / "scripts" / "stage.py"),
             "--src", str(wiki), "--projection", str(proj),
             "--out", str(wdir)], capture_output=True, text=True)
        if stage.returncode != 0:
            print(f"FAIL: stage exit {stage.returncode}\n{stage.stderr}")
            return 1
        print("ok   staged corpora")

        # refusal path: missing projection refuses
        refuse = subprocess.run(
            [sys.executable, str(MOD / "scripts" / "stage.py"),
             "--src", str(wiki), "--projection", str(tmp / "nope"),
             "--out", str(wdir)], capture_output=True, text=True)
        print(("ok  " if refuse.returncode == 1 else "FAIL"),
              "stage refuses without a projection")
        if refuse.returncode != 1:
            return 1

        spec = json.loads((MOD / "templates" / "openapi.json")
                          .read_text(encoding="utf-8"))
        ops = {op.get("operationId")
               for methods in spec.get("paths", {}).values()
               for op in methods.values()}
        ok_spec = ops == {"listPages", "readPage", "searchWiki"}
        print(("ok  " if ok_spec else "FAIL"),
              "openapi.json parses with the three actions")
        if not ok_spec:
            return 1

        shutil.copyfile(MOD / "templates" / "worker.js", wdir / "worker.js")
        harness = subprocess.run(
            [node, str(MOD / "verify" / "harness.mjs"), str(wdir)])
        if harness.returncode != 0:
            return 1
        print("verify ok: retrieval module")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
