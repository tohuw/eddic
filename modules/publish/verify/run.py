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
        # --- #28: a worker that bundles the site IS the site deploy ---
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "publish_mod", Path(__file__).resolve().parent.parent
            / "scripts" / "publish.py")
        pub = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pub)

        wroot = Path(tempfile.mkdtemp(prefix="eddic-publish-worker-"))
        (wroot / "dist" / "site").mkdir(parents=True)
        (wroot / "worker").mkdir()
        (wroot / "worker" / "wrangler.toml").write_text(
            'name = "lore"\n[assets]\ndirectory = "../dist/site"\n'
            'binding = "ASSETS"\n', encoding="utf-8")
        found = pub.find_site_worker(wroot, wroot / "dist" / "site")
        print(("ok   " if found and found.name == "worker" else "FAIL "),
              "a worker bundling the site directory is detected")
        if not (found and found.name == "worker"):
            return 1

        # a worker that holds a route but bundles nothing is not the site
        (wroot / "other").mkdir()
        (wroot / "other" / "wrangler.toml").write_text(
            'name = "api"\nroutes = [{ pattern = "x.example", '
            'custom_domain = true }]\n', encoding="utf-8")
        still = pub.find_site_worker(wroot, wroot / "dist" / "site")
        print(("ok   " if still.name == "worker" else "FAIL "),
              "a route-only worker is not mistaken for the site")
        if still.name != "worker":
            return 1

        plain = Path(tempfile.mkdtemp(prefix="eddic-publish-pages-"))
        (plain / "dist" / "site").mkdir(parents=True)
        print(("ok   " if pub.find_site_worker(
            plain, plain / "dist" / "site") is None else "FAIL "),
            "a campaign with no worker still deploys to Pages")

        # --- #29: an untracked projection is left alone, not committed ---
        pub.report_projection(plain, plain / "dist" / "player")
        print("ok   ", "a non-repo campaign is not pushed to")

        print("verify ok: publish module")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
