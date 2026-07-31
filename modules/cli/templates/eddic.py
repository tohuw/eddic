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
    upgrade [<checkout>]  diff the manifest against an Eddic checkout and
                        report what to re-apply; reports only, never
                        mutates the campaign. Exits 1 if anything needs
                        attention, so a routine can run it.
    run [<service>]     launch a local service (a session-time process
                        like the recorder bot) with its pinned runtime;
                        no name lists the services. Foreground: Ctrl-C
                        stops it, so exactly one copy runs by construction.

Every other verb dispatches to .eddic/lib/<verb>.py (vendored by the
module that provides it), run with the same interpreter, remaining
argv, and EDDIC_CONFIG/EDDIC_ROOT set in the environment.
"""

import json
import os
import re
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
    import shutil
    # Gate on which() like uv is gated in run()/main(): invoking a
    # missing git raises FileNotFoundError, and doctor must degrade
    # gracefully (warn, not crash) when git isn't on PATH.
    git = shutil.which("git") is not None
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
            try:
                entry["params"] = json.loads(opts["--params"])
            except json.JSONDecodeError as e:
                print(f"error: --params is not valid JSON: {e}",
                      file=sys.stderr)
                return 2
        if "--verbs" in opts:
            entry["verbs"] = sorted(set(entry.get("verbs", []))
                                    | set(opts["--verbs"].split(",")))
        man["modules"][mod] = entry
        MANIFEST.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
        print(f"manifest: recorded {mod} {ver}")
        return 0
    print(f"unknown manifest subcommand: {args[0]}", file=sys.stderr)
    return 2


UPGRADE_USAGE = ("usage: upgrade [<eddic_checkout>] — or set "
                 "\"eddic_checkout\" in config.json, or EDDIC_HOME in the "
                 "environment")


def yaml_scalar(text, key):
    """A top-level scalar from a module.yaml. Deliberately naive: the
    vendored CLI is stdlib-only, module.yaml is ours, and the fields
    read here (name, version, renamed_from) are always flat."""
    m = re.search(r"^%s:[ \t]*(\S.*?)\s*$" % key, text, re.M)
    return m.group(1).strip() if m else None


def yaml_names(text, key):
    """A key's values whether written inline (`key: a` or `key: a, b`)
    or as a block list of `- name` lines."""
    inline = yaml_scalar(text, key)
    if inline:
        return [v.strip() for v in inline.strip("[]").split(",") if v.strip()]
    block = re.search(r"^%s:[ \t]*$\n((?:[ \t]*-[^\n]*\n?)+)" % key, text, re.M)
    return ([ln.strip().lstrip("-").strip() for ln in
             block.group(1).splitlines() if ln.strip()] if block else [])


def version_key(text):
    """Comparable key for a SemVer-ish version string; missing or
    non-numeric parts sort as 0, so 0.4 < 0.4.1 < 0.5."""
    nums = [int(n) for n in re.findall(r"\d+", text or "")][:3]
    return tuple(nums + [0] * (3 - len(nums)))


def checkout_modules(root):
    """Read <checkout>/modules/*/module.yaml. Returns None when the
    path is not an Eddic checkout."""
    mdir = Path(root) / "modules"
    if not mdir.is_dir():
        return None
    mods = {}
    for yml in sorted(mdir.glob("*/module.yaml")):
        text = yml.read_text(encoding="utf-8", errors="replace")
        name = yaml_scalar(text, "name") or yml.parent.name
        mods[name] = {
            "version": yaml_scalar(text, "version") or "",
            "renamed_from": yaml_names(text, "renamed_from"),
            # verbs a module declares it touches, e.g. .eddic/lib/graph.py
            "verbs": sorted(set(re.findall(r"lib/([\w-]+)\.py", text))),
        }
    return mods


def upgrade(args):
    """Diff the applied-patterns manifest against an Eddic checkout.

    Reports only. Applying a pattern is an agent's job — it reads the
    campaign, asks at decision points, and writes files a script cannot
    reason about — so this verb never mutates the campaign; it names the
    patterns to re-apply and the manifest line to record afterwards."""
    cfg = load(CONFIG) or {}
    where = (args[0] if args and not args[0].startswith("-")
             else cfg.get("eddic_checkout") or os.environ.get("EDDIC_HOME"))
    if not where:
        print(UPGRADE_USAGE, file=sys.stderr)
        return 2
    repo = Path(where).expanduser()
    mods = checkout_modules(repo)
    if mods is None:
        print(f"upgrade: no modules/ directory under {repo} — point this "
              f"at an Eddic checkout", file=sys.stderr)
        return 2

    recorded = (load(MANIFEST) or {}).get("modules", {})
    renames = {old: new for new, e in mods.items() for old in e["renamed_from"]}
    lines, notes, attention = [], [], 0
    actions = {}                       # module -> version, insertion-ordered

    for name in sorted(recorded):
        have = str(recorded[name].get("version") or "")
        if name in mods:
            want = mods[name]["version"]
            if not have:
                lines.append(f"  attention   {name}: no version recorded "
                             f"(checkout has {want})")
                actions[name] = want
                attention += 1
            elif version_key(have) < version_key(want):
                lines.append(f"  upgradable  {name}: {have} -> {want}")
                actions[name] = want
                attention += 1
            elif version_key(have) > version_key(want):
                lines.append(f"  ahead       {name}: {have} recorded, the "
                             f"checkout has {want} — update the checkout")
                attention += 1
            else:
                lines.append(f"  ok          {name}: {have}")
        elif name in renames:
            new = renames[name]
            lines.append(f"  renamed     {name} is now {new}: {have} "
                         f"recorded as {name}, checkout has {new} "
                         f"{mods[new]['version']}")
            actions[new] = mods[new]["version"]
            notes.append(f"  delete the stale '{name}' entry from "
                         f".eddic/manifest.json once {new} is recorded")
            attention += 1
        else:
            lines.append(f"  gone        {name}: {have} recorded, no such "
                         f"module in the checkout (renamed without a "
                         f"renamed_from, or retired)")
            attention += 1

    # Installed but unrecorded, cheaply: a vendored lib verb that no
    # manifest entry claims. Attribution is a hint from the checkout.
    claimed = {v for e in recorded.values() for v in e.get("verbs", [])}
    owner = {}
    for name, e in mods.items():
        for verb in e["verbs"] + [name]:
            owner.setdefault(verb, name)
    for verb in sorted(lib_verbs()):
        if verb in claimed:
            continue
        src = owner.get(verb)
        lines.append(f"  unrecorded  lib/{verb}.py is vendored but no "
                     f"manifest entry claims it"
                     + (f" (looks like {src})" if src else ""))
        if src and src not in recorded:
            actions[src] = mods[src]["version"]
        attention += 1

    print(f"upgrade: {len(recorded)} recorded module(s) against {repo}")
    for line in lines:
        print(line)
    if actions:
        print("\nre-apply these patterns (an agent's job, not this "
              "script's) — read each, apply it here, then record it:")
        for name, ver in actions.items():
            print(f"  {Path(repo) / 'modules' / name / 'PATTERN.md'}")
            print(f"    uv run .eddic/eddic.py manifest record "
                  f"--module {name} --version {ver}")
    for note in notes:
        print(note)
    print("upgrade: ok" if not attention
          else f"upgrade: {attention} need attention")
    return 1 if attention else 0


def service_command(spec):
    """Build the uv-run argv for a service spec. Pure: no exec, so it
    is unit-testable. A service is a local process with pinned deps —
    entry (default bot.py), python (optional), with (deps list)."""
    cmd = ["uv", "run"]
    if spec.get("python"):
        cmd += ["--python", str(spec["python"])]
    for dep in spec.get("with", []):
        cmd += ["--with", dep]
    cmd.append(spec.get("entry", "bot.py"))
    return cmd


def run(args):
    cfg = load(CONFIG) or {}
    services = cfg.get("services", {})
    if not args:
        if not services:
            print("no services configured (a module that ships one "
                  "adds it to config.json's `services`)")
            return 0
        print("services:")
        for name, spec in services.items():
            print(f"  {name} — {spec.get('dir', '.')}/"
                  f"{spec.get('entry', 'bot.py')}")
        return 0
    name = args[0]
    spec = services.get(name)
    if not spec:
        print(f"unknown service: {name} (configured: "
              f"{', '.join(services) or 'none'})", file=sys.stderr)
        return 2
    import shutil
    if not shutil.which("uv"):
        print("uv is required to launch a service with pinned deps; "
              "install it first (one-line installer).", file=sys.stderr)
        return 1
    workdir = ROOT / spec.get("dir", ".")
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    print(f"launching {name} in {workdir} — Ctrl-C to stop")
    return subprocess.run(service_command(spec), cwd=workdir, env=env,
                          shell=False).returncode


def main(argv):
    if not argv:
        verbs = ["doctor", "manifest", "upgrade", "run"] + list(lib_verbs())
        print(__doc__.strip())
        print(f"\navailable verbs here: {', '.join(verbs)}")
        return 0
    verb, rest = argv[0], argv[1:]
    if verb == "doctor":
        return doctor()
    if verb == "manifest":
        return manifest(rest)
    if verb == "upgrade":
        return upgrade(rest)
    if verb == "run":
        return run(rest)
    script = lib_verbs().get(verb)
    if not script:
        print(f"unknown verb: {verb} (lib verbs: "
              f"{', '.join(lib_verbs()) or 'none'})", file=sys.stderr)
        return 2
    env = dict(os.environ, EDDIC_CONFIG=str(CONFIG), EDDIC_ROOT=str(ROOT))
    # Prefer uv so a verb's inline (PEP 723) dependencies resolve;
    # stdlib-only verbs work either way.
    import shutil
    runner = (["uv", "run", str(script)] if shutil.which("uv")
              else [sys.executable, str(script)])
    return subprocess.run(runner + rest, env=env, shell=False).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
