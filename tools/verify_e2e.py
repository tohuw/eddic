# /// script
# requires-python = ">=3.9"
# ///
"""End-to-end composition test: a campaign assembled the way the
module index says to — stamp -> schema -> vendor verbs -> content ->
contribute -> lint -> project -> build -> publish dry-run -> stage ->
bundle (refuse, clear, build) — through the vendored dispatcher, the
way a real campaign runs it. Per-module verifies prove parts; this
proves the composition, on every OS CI runs."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULES = ROOT / "modules"

PLAYER = "---\nvisibility: player\ntransactability: transactable\n---\n\n"


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="eddic-e2e-"))
    camp = tmp / "campaign"
    checks = []

    def run(*args, expect=0):
        p = subprocess.run([sys.executable, *map(str, args)],
                           capture_output=True, text=True)
        return p

    def eddic(*args):
        return run(camp / ".eddic" / "eddic.py", *args)

    # 1. cli: stamp with a declared author
    p = run(MODULES / "cli" / "scripts" / "stamp.py", camp,
            "--site-name", "Verify Realm", "--author", "aria")
    checks.append((p.returncode == 0, "stamp exits 0"))
    cfg = json.loads((camp / ".eddic" / "config.json")
                     .read_text(encoding="utf-8"))
    checks.append((cfg.get("author") == "aria",
                   "author declared in config"))

    # 2. wiki schema + seeds
    t = MODULES / "wiki" / "templates"
    for src, dest in (("AGENTS-campaign.md", "AGENTS.md"),
                      ("CLAUDE-stub.md", "CLAUDE.md")):
        body = (t / src).read_text(encoding="utf-8")
        body = body.replace("{{SITE_NAME}}", "Verify Realm")
        body = body.replace("{{LOG}}", "log.md")
        (camp / dest).write_text(body, encoding="utf-8")

    # 3. vendor every verb the composition needs
    verbs = [("lint", MODULES / "lint" / "scripts" / "eddic_lint.py"),
             ("project", MODULES / "wiki" / "scripts" / "project.py"),
             ("build", MODULES / "render" / "scripts" / "render.py"),
             ("publish", MODULES / "publish" / "scripts" / "publish.py"),
             ("stage", MODULES / "retrieval" / "scripts" / "stage.py"),
             ("bundle", MODULES / "contribs" / "scripts" / "bundle.py")]
    lib = camp / ".eddic" / "lib"
    for name, srcpath in verbs:
        (lib / f"{name}.py").write_text(
            srcpath.read_text(encoding="utf-8"), encoding="utf-8")
    (camp / ".eddic" / "page.html").write_text(
        (MODULES / "render" / "templates" / "page.html")
        .read_text(encoding="utf-8"), encoding="utf-8")
    cfg["pages_project"] = "verify-realm"
    (camp / ".eddic" / "config.json").write_text(
        json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

    # 4. content: catalogs, a player page, a DM page
    wiki = camp / "wiki"
    write(wiki, "index.md", PLAYER + "# Verify Realm\n\n"
          "The catalog. [The Keep](keep.md) holds the border; the "
          "realm's history is longer than this test needs it to be, "
          "but the words here keep every page above the tiny "
          "threshold without a stub marker.\n")
    write(wiki, "index.dm.md", "# Verify Realm — DM catalog\n\n"
          "[index](index.md), [keep](keep.md), "
          "[vault](vault.dm.md)\n")
    write(wiki, "keep.md", PLAYER + "# The Keep\n\n"
          "Base garrison text: a squat stone fort on the border "
          "road, its gate argued over by two captains who agree on "
          "nothing except that the gate matters more than they do.\n")
    write(wiki, "vault.dm.md",
          "---\ntransactability: transactable\n---\n\n"
          "# The Vault\n\nDM-only truth about the keep's cellar: the "
          "captains guard a door neither has opened, and the page "
          "that says so never reaches a player surface at all.\n")
    write(wiki, "log.md",
          (t / "log-seed.md").read_text(encoding="utf-8")
          .replace("{{SITE_NAME}}", "Verify Realm"))

    # 5. a contribution, overlaying the player page
    write(camp, "contribs/kestrel/keep.md",
          "---\nvisibility: player\nauthorship: kestrel\n"
          "replaces: keep.md\ntransactability: transactable\n---\n\n"
          "# The Keep\n\nKestrel's rewrite of the garrison: the same "
          "squat fort, but told from the wall-walk at dusk, where "
          "both captains privately come to check the hinges of the "
          "gate they publicly refuse to share.\n")

    # 6-10. the pipeline, through the dispatcher
    p = eddic("lint")
    checks.append((p.returncode == 0,
                   f"lint clean (got {p.returncode}): "
                   f"{(p.stdout + p.stderr).strip()[:150]}"))
    p = eddic("project")
    proj = camp / "dist" / "player" / "keep.md"
    checks.append((p.returncode == 0, "project exits 0"))
    checks.append((proj.exists() and "Kestrel's rewrite" in
                   proj.read_text(encoding="utf-8"),
                   "projection carries the overlay"))
    checks.append((not (camp / "dist" / "player" / "vault.dm.md")
                   .exists(), "DM page withheld from projection"))
    p = eddic("build")
    checks.append((p.returncode == 0 and
                   (camp / "dist" / "site" / "keep.html").exists(),
                   "build renders the projection"))
    p = eddic("publish", "--dry-run")
    checks.append((p.returncode == 0 and
                   "deploy command" in p.stdout + p.stderr,
                   "publish dry-run reaches the deploy command"))
    p = eddic("stage")
    dm_corpus = (camp / "worker" / "corpus_dm.mjs")
    checks.append((p.returncode == 0 and dm_corpus.exists() and
                   "Kestrel's rewrite" in
                   dm_corpus.read_text(encoding="utf-8"),
                   "staged DM corpus sees the effective wiki"))

    # 11. the fence: refuse dirty, clear, bundle
    p = eddic("bundle")
    checks.append((p.returncode == 1 and "kestrel" in p.stderr,
                   "bundle refuses the uncleared contribution"))
    r = eddic("bundle", "--receipts", "kestrel")
    entry = r.stdout[r.stdout.index("## ["):]
    log = wiki / "log.md"
    log.write_text(log.read_text(encoding="utf-8") + "\n"
                   + entry.replace("consent |", "attribution |", 1)
                   + "\n" + entry + "\n", encoding="utf-8")
    p = eddic("bundle")
    bundled = camp / "dist" / "bundle" / "wiki"
    checks.append((p.returncode == 0, "cleared bundle exits 0"))
    checks.append(((bundled / "vault.dm.md").exists() and
                   "Kestrel's rewrite" in
                   (bundled / "keep.md").read_text(encoding="utf-8"),
                   "bundle ships the full truth with the overlay"))
    p = eddic("bundle", "--check")
    checks.append((p.returncode == 0, "full = pure + attribution log"))

    failed = [msg for ok, msg in checks if not ok]
    for ok, msg in checks:
        print(("ok  " if ok else "FAIL"), msg)
    if failed:
        return 1
    print(f"verify_e2e: ok ({len(checks)} checks, "
          "composition proven through the dispatcher)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
