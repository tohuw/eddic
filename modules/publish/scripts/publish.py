# /// script
# requires-python = ">=3.9"
# ///
"""eddic publish — lint, project, build, deploy.

Usage (as a vendored eddic verb):
    eddic.py publish --project-name NAME [--dry-run] [--skip-lint]

The safety pipeline is the point: nothing deploys unless lint passes
(strict), the projection succeeds (firewall), and the render
completes. --dry-run runs the whole pipeline and stops short of
wrangler, printing the deploy command instead. Only the player site
ever deploys from here.

Exit codes: 0 published (or dry-run clean), 1 a stage failed,
2 usage error.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


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
    project_name = opts.get("--project-name") or cfg.get("pages_project")
    if not project_name and "--dry-run" not in flags:
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

    deploy = ["wrangler", "pages", "deploy", str(site_dir),
              "--project-name", str(project_name or "<name>")]
    if "--dry-run" in flags:
        print("publish: dry run — pipeline clean; deploy command:")
        print("  " + " ".join(deploy))
        return 0
    if not shutil.which("wrangler"):
        print("publish: wrangler not on PATH (npm i -g wrangler, or use "
              "npx wrangler)", file=sys.stderr)
        return 1
    code = subprocess.run(deploy, shell=False).returncode
    print("publish: deployed" if code == 0 else
          f"publish: wrangler failed (exit {code})")
    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
