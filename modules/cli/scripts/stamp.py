# /// script
# requires-python = ">=3.9"
# ///
"""Stamp the vendored eddic CLI into a campaign.

Usage:
    uv run stamp.py <campaign_dir> --site-name NAME
        [--wiki-dir wiki] [--projection-dir dist/player]
        [--site-dir dist/site] [--log log.md]
        [--contribs-dir contribs] [--author CONTRIBUTOR_ID]

--author declares who holds transaction rights (may differ from the
DM; a campaign runs fine without it, but the sale build refuses until
an author is declared — fail closed).

Creates <campaign>/.eddic/ with the dispatcher, config.json, an
initialized manifest.json recording the cli module, and an empty lib/.
Idempotent: re-stamping refreshes eddic.py and re-records cli, but
never overwrites an existing config.json or other modules' manifest
entries."""

import json
import shutil
import sys
from datetime import date
from pathlib import Path

VERSION = "0.2.0"
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "eddic.py"
DEFAULTS = {"wiki_dir": "wiki", "projection_dir": "dist/player",
            "site_dir": "dist/site", "log": "log.md",
            "contribs_dir": "contribs"}


def main(argv):
    pos, opts, i = [], {}, 0
    while i < len(argv):
        if argv[i].startswith("--"):
            if i + 1 >= len(argv):
                print(f"missing value for {argv[i]}", file=sys.stderr)
                return 2
            opts[argv[i]] = argv[i + 1]
            i += 2
        else:
            pos.append(argv[i])
            i += 1
    if len(pos) != 1 or "--site-name" not in opts:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    root = Path(pos[0])
    root.mkdir(parents=True, exist_ok=True)
    dot = root / ".eddic"
    (dot / "lib").mkdir(parents=True, exist_ok=True)

    shutil.copyfile(TEMPLATE, dot / "eddic.py")

    config = dot / "config.json"
    if not config.exists():
        cfg = {"site_name": opts["--site-name"]}
        for key, default in DEFAULTS.items():
            cfg[key] = opts.get(f"--{key.replace('_', '-')}", default)
        if "--author" in opts:
            cfg["author"] = opts["--author"]
        config.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        (root / cfg["wiki_dir"]).mkdir(parents=True, exist_ok=True)
    elif "--author" in opts:
        cfg = json.loads(config.read_text(encoding="utf-8"))
        cfg["author"] = opts["--author"]
        config.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

    manifest = dot / "manifest.json"
    man = (json.loads(manifest.read_text(encoding="utf-8"))
           if manifest.exists() else {"modules": {}})
    man["modules"].setdefault("cli", {})
    man["modules"]["cli"].update(
        {"version": VERSION, "applied": date.today().isoformat()})
    manifest.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")

    print(f"stamped eddic {VERSION} into {dot}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
