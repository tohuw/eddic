# /// script
# requires-python = ">=3.9"
# ///
"""Verify the publish module: assemble a complete campaign in a temp
dir (stamp + vendor lint/project/build/publish + seed wiki), run the
dry-run pipeline end to end, then plant a firewall breach and assert
the publish refuses at the projection stage."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MODULES = Path(__file__).resolve().parent.parent.parent
PLAYER_FM = "---\nvisibility: player\n---\n\n"


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def main():
    if not shutil.which("uv"):
        print("SKIP: uv not on PATH (build stage needs it)")
        return 0
    tmp = Path(tempfile.mkdtemp(prefix="eddic-publish-verify-"))
    try:
        camp = tmp / "campaign"
        subprocess.run([sys.executable,
                        str(MODULES / "cli/scripts/stamp.py"), str(camp),
                        "--site-name", "Publish Realm"],
                       check=True, capture_output=True)
        lib = camp / ".eddic" / "lib"
        shutil.copyfile(MODULES / "lint/scripts/eddic_lint.py", lib / "lint.py")
        shutil.copyfile(MODULES / "wiki/scripts/project.py", lib / "project.py")
        shutil.copyfile(MODULES / "render/scripts/render.py", lib / "build.py")
        shutil.copyfile(MODULES / "publish/scripts/publish.py",
                        lib / "publish.py")
        shutil.copyfile(MODULES / "render/templates/page.html",
                        camp / ".eddic" / "page.html")
        write(camp, "wiki/index.md", PLAYER_FM + "# Publish Realm\n\n"
              "The realm has one page beyond this catalog: "
              "[the keep](keep.md), which guards the northern pass "
              "and appears in every traveler's tale of the region.\n")
        write(camp, "wiki/keep.md", PLAYER_FM + "# The Keep\n\n"
              "A sturdy keep above the pass, returned to in "
              "[the catalog](index.md). Its garrison is small, its "
              "walls are old, and its cellars are deeper than the "
              "garrison admits to visitors who ask about them.\n")
        write(camp, "wiki/keep.dm.md", "# The Keep — full truth\n\n"
              "The cellars hold the campaign's midpoint twist. Player "
              "twin: [the keep](keep.md).\n")
        write(camp, "wiki/index.dm.md", "# Publish Realm — DM catalog\n\n"
              "Every page: [the catalog](index.md), [the keep](keep.md), "
              "[the keep, full truth](keep.dm.md). This catalog exists "
              "so the linter can see DM pages woven into the graph "
              "without the player catalog ever touching them.\n")

        cli = [sys.executable, str(camp / ".eddic" / "eddic.py")]
        proc = subprocess.run(cli + ["publish", "--dry-run"],
                              capture_output=True, text=True)
        site = camp / "dist" / "site"
        checks = [
            (proc.returncode == 0,
             f"dry-run pipeline exits 0 (got {proc.returncode})"),
            ("wrangler pages deploy" in proc.stdout,
             "deploy command printed"),
            ((site / "index.html").exists(), "site rendered"),
            (not (site / "keep.dm.html").exists(), "DM twin not in site"),
        ]
        if proc.returncode != 0:
            print(proc.stdout, proc.stderr, sep="\n")

        write(camp, "wiki/keep.md", PLAYER_FM + "# The Keep\n\n"
              "See [the full truth](keep.dm.md).\n")
        proc2 = subprocess.run(cli + ["publish", "--dry-run"],
                               capture_output=True, text=True)
        checks += [
            (proc2.returncode == 1,
             f"breach refuses the publish (got {proc2.returncode})"),
            ("REFUSED" in proc2.stderr, "refusal is loud"),
        ]

        failed = [msg for ok, msg in checks if not ok]
        for ok, msg in checks:
            print(("ok  " if ok else "FAIL"), msg)
        if failed:
            print(proc2.stdout, proc2.stderr, sep="\n")
            return 1
        print("verify ok: publish module")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
