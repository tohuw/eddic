# /// script
# requires-python = ">=3.9"
# ///
"""eddic — the campaign's vendored deterministic CLI.

This file lives at <campaign>/.eddic/eddic.py, stamped there by the
cli module and recorded in manifest.json. It is the contractual locus
for the campaign's deterministic workflows: patterns are written
against its verbs, not its internals.

Usage:
    uv run .eddic/eddic.py <verb> [args...]

Built-in verbs:
    doctor              preflight: environment and campaign sanity
    manifest show       print the applied-patterns manifest
    manifest check      validate manifest shape and vendored libs
    manifest record --module M --version V [--params JSON]

Every other verb dispatches to .eddic/lib/<verb>.py (vendored by the
module that provides it), run with the same interpreter, remaining
argv, and EDDIC_CONFIG/EDDIC_ROOT set in the environment.
"""

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent      # <campaign>/.eddic
ROOT = HERE.parent                          # <campaign>
LIB = HERE / "lib"
CONFIG = HERE / "config.json"
MANIFEST = HERE / "manifest.json"


def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        print(f"error: {path.name} is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)


def lib_verbs():
    if not LIB.is_dir():
        return {}
    return {p.stem: p for p in sorted(LIB.glob("*.py"))}


def doctor():
    ok = True

    def check(cond, good, bad, fatal=True):
        nonlocal ok
        if cond:
            print(f"  ok    {good}")
        else:
            print(f"  {'FAIL' if fatal else 'warn'}  {bad}")
            if fatal:
                ok = False

    check(sys.version_info >= (3, 9),
          f"python {sys.version.split()[0]}",
          f"python >= 3.9 required, found {sys.version.split()[0]}")
    cfg = load(CONFIG)
    check(cfg is not None, "config.json present", "config.json missing")
    man = load(MANIFEST)
    check(man is not None, "manifest.json present", "manifest.json missing")
    if cfg:
        wiki = ROOT / cfg.get("wiki_dir", "wiki")
        check(wiki.is_dir(), f"wiki dir: {cfg.get('wiki_dir', 'wiki')}",
              f"wiki dir missing: {cfg.get('wiki_dir', 'wiki')}")
    if man:
        for mod, entry in man.get("modules", {}).items():
            for verb in entry.get("verbs", []):
                check((LIB / f"{verb}.py").is_file(),
                      f"verb '{verb}' vendored ({mod})",
                      f"manifest records verb '{verb}' ({mod}) but "
                      f"lib/{verb}.py is missing")
    git = subprocess.run(["git", "--version"], capture_output=True,
                         shell=False).returncode == 0
    check(git, "git available", "git not found (versioning/provenance "
          "features degrade)", fatal=False)
    verbs = ", ".join(lib_verbs()) or "none"
    print(f"  info  lib verbs: {verbs}")
    print("doctor: ok" if ok else "doctor: FAILED")
    return 0 if ok else 1


def manifest(args):
    man = load(MANIFEST) or {"modules": {}}
    if not args or args[0] == "show":
        print(json.dumps(man, indent=2))
        return 0
    if args[0] == "check":
        bad = [m for m, e in man.get("modules", {}).items()
               if not e.get("version") or not e.get("applied")]
        for m in bad:
            print(f"manifest: module '{m}' missing version/applied")
        missing = [v for e in man.get("modules", {}).values()
                   for v in e.get("verbs", []) if not (LIB / f"{v}.py").is_file()]
        for v in missing:
            print(f"manifest: recorded verb '{v}' not vendored in lib/")
        print("manifest: ok" if not bad and not missing else "manifest: FAILED")
        return 0 if not bad and not missing else 1
    if args[0] == "record":
        opts = dict(zip(args[1::2], args[2::2]))
        mod = opts.get("--module")
        ver = opts.get("--version")
        if not mod or not ver:
            print("usage: manifest record --module M --version V "
                  "[--params JSON] [--verbs a,b]", file=sys.stderr)
            return 2
        entry = man["modules"].get(mod, {})
        entry.update({"version": ver, "applied": date.today().isoformat()})
        if "--params" in opts:
            entry["params"] = json.loads(opts["--params"])
        if "--verbs" in opts:
            entry["verbs"] = sorted(set(entry.get("verbs", []))
                                    | set(opts["--verbs"].split(",")))
        man["modules"][mod] = entry
        MANIFEST.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
        print(f"manifest: recorded {mod} {ver}")
        return 0
    print(f"unknown manifest subcommand: {args[0]}", file=sys.stderr)
    return 2


def main(argv):
    if not argv:
        verbs = ["doctor", "manifest"] + list(lib_verbs())
        print(__doc__.strip())
        print(f"\navailable verbs here: {', '.join(verbs)}")
        return 0
    verb, rest = argv[0], argv[1:]
    if verb == "doctor":
        return doctor()
    if verb == "manifest":
        return manifest(rest)
    script = lib_verbs().get(verb)
    if not script:
        print(f"unknown verb: {verb} (lib verbs: "
              f"{', '.join(lib_verbs()) or 'none'})", file=sys.stderr)
        return 2
    env = dict(os.environ, EDDIC_CONFIG=str(CONFIG), EDDIC_ROOT=str(ROOT))
    return subprocess.run([sys.executable, str(script)] + rest,
                          env=env, shell=False).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
