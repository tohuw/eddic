# /// script
# requires-python = ">=3.9"
# ///
"""Verify the retrieval module: plant a campaign wiki + projection,
stage the corpora, copy the worker template beside them, then drive
the worker's fetch handler in node (auth, both token styles, tier
isolation, search). Skips gracefully if node is absent (CI has it)."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MOD = Path(__file__).resolve().parent.parent
PLAYER_FM = "---\nvisibility: player\n---\n\n"


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def main():
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
