# /// script
# requires-python = ">=3.9"
# ///
"""eddic publish — lint, project, build, deploy, and keep the repo in
step with what deployed.

Usage (as a vendored eddic verb):
    eddic.py publish [--project-name NAME] [--dry-run] [--skip-lint]
                     [--target auto|worker|pages] [--no-commit-projection]

The safety pipeline is the point: nothing deploys unless lint passes
(strict), the projection succeeds (firewall), and the render completes.
--dry-run runs the whole pipeline and stops short of deploying, printing
the command instead. Only the player site ever deploys from here.

**Two things this verb has to get right that it once got wrong.**

*Where the site actually lives.* A campaign fronted by the retrieval
worker serves its site from the worker's bundled assets, not from Cloudflare
Pages — the site deploy IS the worker deploy. Publishing to Pages there
updates a project nobody visits and prints success while the live site
is unchanged. `--target auto` (the default) detects a worker whose
wrangler.toml bundles the site directory and deploys that instead.

*What the lore bot sees.* The bot polls the repository's projection for
its corpus and for its "new session page → announce" delta. A publish
that regenerates `dist/` without committing it leaves the live site
ahead of the repo, so a new recap goes up and the table is never
pinged — silent, because everything looks published. After a successful
deploy this commits and pushes the regenerated projection when it is
tracked, and says so loudly when it cannot.

Exit codes: 0 published (or dry-run clean), 1 a stage failed,
2 usage error.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def find_site_worker(root, site_dir):
    """A worker that bundles the built site is the live site, and its
    deploy is the site deploy. Detected by reading wrangler.toml for an
    [assets] directory that resolves to the site dir — a route alone is
    not enough, since a worker can hold a route and serve no assets."""
    for toml in sorted(root.glob("*/wrangler.toml")):
        try:
            text = toml.read_text(encoding="utf-8")
        except OSError:
            continue
        m = re.search(r"^\s*directory\s*=\s*[\"']([^\"']+)[\"']",
                      text, re.M)
        if not m or "[assets]" not in text:
            continue
        try:
            if (toml.parent / m.group(1)).resolve() == site_dir.resolve():
                return toml.parent
        except OSError:
            continue
    return None


def git(root, *args):
    return subprocess.run(["git"] + list(args), cwd=str(root),
                          capture_output=True, text=True)


def report_projection(root, projection_dir, dry_run=False):
    """Keep the repository's projection in step with what just
    deployed, because the lore bot polls the repo rather than the site.
    Refuses quietly only when there is nothing to do; every other
    outcome is stated, since the failure this exists to prevent is a
    silent one."""
    if not (root / ".git").exists():
        return
    rel = projection_dir.relative_to(root).as_posix()
    tracked = git(root, "ls-files", "--error-unmatch", rel)
    if tracked.returncode != 0:
        return                      # projection is not versioned here
    dirty = git(root, "status", "--porcelain", "--", rel).stdout.strip()
    if not dirty:
        print("publish: projection already matches the repo")
        return
    n = len(dirty.splitlines())
    if dry_run:
        print(f"publish: dry run — {n} projection file(s) would be "
              f"committed and pushed")
        return
    add = git(root, "add", "--", rel)
    if add.returncode != 0:
        print(f"publish: WARNING — could not stage {rel}: {add.stderr}",
              file=sys.stderr)
        return
    msg = (f"site: commit the regenerated projection ({n} file(s))\n\n"
           "The lore bot polls this directory, not the deployed site, so "
           "a projection left uncommitted means a published recap that "
           "never reaches the table.")
    com = git(root, "commit", "-m", msg)
    if com.returncode != 0:
        print(f"publish: WARNING — projection not committed: "
              f"{com.stdout or com.stderr}", file=sys.stderr)
        return
    push = git(root, "push")
    if push.returncode != 0:
        print("publish: WARNING — projection committed but NOT pushed; a "
              "repo-polling lore bot will not see this publish until you "
              f"push:\n{push.stderr.strip()}", file=sys.stderr)
        return
    print(f"publish: projection committed and pushed ({n} file(s))")


def main(argv):
    flags = {a for a in argv if a.startswith("--") and "=" not in a}
    opts = dict(zip(argv, argv[1:]))
    cfg_env = os.environ.get("EDDIC_CONFIG")
    if not cfg_env:
        print("publish runs as a vendored eddic verb "
              "(needs EDDIC_CONFIG)", file=sys.stderr)
        return 2
    cfg_path = Path(cfg_env)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    root = cfg_path.parent.parent
    dispatcher = cfg_path.parent / "eddic.py"
    site_dir = root / cfg.get("site_dir", "dist/site")
    projection_dir = root / cfg.get("projection_dir", "dist/player")
    project_name = opts.get("--project-name") or cfg.get("pages_project")
    target = opts.get("--target", "auto")
    if target not in ("auto", "worker", "pages"):
        print(f"--target {target!r} is not auto, worker, or pages",
              file=sys.stderr)
        return 2

    worker_dir = find_site_worker(root, site_dir)
    if target == "auto":
        target = "worker" if worker_dir else "pages"
    if target == "worker" and not worker_dir:
        print("--target worker, but no worker bundles the site directory",
              file=sys.stderr)
        return 2
    if target == "pages" and worker_dir:
        print(f"publish: NOTE — {worker_dir.name}/wrangler.toml bundles "
              f"{site_dir.name} and holds the live route; deploying to "
              f"Pages will not change the live site", file=sys.stderr)
    if target == "pages" and not project_name and "--dry-run" not in flags:
        print("no Pages project name: pass --project-name or set "
              "pages_project in config.json", file=sys.stderr)
        return 2

    def stage(name, args):
        print(f"publish: {name}")
        code = subprocess.run([sys.executable, str(dispatcher)] + args,
                              shell=False).returncode
        if code != 0:
            print(f"publish: REFUSED — {name} failed (exit {code}); "
                  "nothing was deployed", file=sys.stderr)
        return code

    if "--skip-lint" not in flags:
        if stage("lint (strict)", ["lint", "--strict"]) != 0:
            return 1
    if stage("project (firewall)", ["project"]) != 0:
        return 1
    if stage("build", ["build"]) != 0:
        return 1
    if not site_dir.is_dir() or not any(site_dir.rglob("*.html")):
        print("publish: REFUSED — site dir is empty after build",
              file=sys.stderr)
        return 1

    if target == "worker":
        deploy, cwd = ["wrangler", "deploy"], worker_dir
        where = f"worker ({worker_dir.name}/)"
    else:
        deploy, cwd = ["wrangler", "pages", "deploy", str(site_dir),
                       "--project-name", str(project_name or "<name>")], root
        where = f"Pages project {project_name or '<name>'}"

    if "--dry-run" in flags:
        print(f"publish: dry run — pipeline clean; deploy command "
              f"for {where}:")
        print(f"  cd {cwd} && " + " ".join(deploy))
        report_projection(root, projection_dir, dry_run=True)
        return 0
    if not shutil.which("wrangler"):
        print("publish: wrangler not on PATH (npm i -g wrangler, or use "
              "npx wrangler)", file=sys.stderr)
        return 1
    print(f"publish: deploying to {where}")
    code = subprocess.run(deploy, shell=False, cwd=str(cwd)).returncode
    if code != 0:
        print(f"publish: wrangler failed (exit {code})")
        return 1
    print("publish: deployed")

    if "--no-commit-projection" not in flags:
        report_projection(root, projection_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
