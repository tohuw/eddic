# /// script
# requires-python = ">=3.9"
# ///
"""eddic bundle — the sale-build fence for transactable campaigns.

Usage:
    uv run bundle.py [--src WIKI] [--contribs DIR] [--out DIR]
                     [--log NAME] [--author ID]
                     [--check] [--receipts CONTRIBUTOR]
    (bare, as a vendored eddic verb: paths come from EDDIC_CONFIG)

Builds the transactable package: every page whose transactability
marker and derivation ancestry clear it for sale, DM pages included —
visibility never filters a sale; the buyer becomes their own table's
DM. Refuses loudly, all-or-nothing, when: no author is declared; a
page is marked transactable but its ancestry reaches an uncleared
contributor; a clearance is stale (the contributor's file changed
after sign-off — hashes pin what was consented to); or nothing is
transactable at all. `local-only` (and unmarked — same thing) is
silently excluded: that is the fence working, not an error.

Rights status is computed, never judged: a page is clear iff nothing
in its ancestry (its own authorship, its overlay's contributor, its
derived-from chain) traces to a contributor other than the author
who lacks a valid consent entry. `authorship: transcript` pages are
multi-author by nature and clear only under a table-wide consent
entry (`consent | table ...`).

--receipts <id> prints the contributor's current fragments with
hashes plus a ready-to-append consent entry — the concrete sign-off
artifact. --check verifies the attribution log against the tree
(every contrib file logged, every hash current) without building.

Exit codes: 0 ok, 1 refused (reasons listed), 2 usage error.
"""

import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

NON_CONTENT = {"CLAUDE.md", "AGENTS.md", "README.md"}
GENERIC = {"human", "agent", "machine", "transcript"}
SELLABLE = {"transactable", "transactable-with-attribution"}
ENTRY = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\] (\w+) \| (.+)$", re.M)
FRAGMENT = re.compile(r"^- (\S+) sha256:([0-9a-f]{16})$", re.M)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def split_frontmatter(text):
    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm = {}
                for ln in lines[1:i]:
                    if ":" in ln and not ln.startswith((" ", "\t")):
                        k, _, v = ln.partition(":")
                        fm[k.strip()] = v.strip()
                return fm, "\n".join(lines[i + 1:])
    return {}, text


def load_effective(src, contribs, log_name):
    """Effective wiki: rel -> {file, fm, contributor}. Contributor is
    set for overlay/added contrib pages, None for base pages."""
    pages, problems = {}, []
    for p in sorted(src.rglob("*.md")):
        if p.name in NON_CONTENT or p.name == log_name:
            continue
        fm, _ = split_frontmatter(p.read_text(encoding="utf-8",
                                              errors="replace"))
        pages[p.relative_to(src).as_posix()] = {
            "file": p, "fm": fm, "contributor": None}
    if contribs and contribs.is_dir():
        claimed = {}
        for cdir in sorted(d for d in contribs.iterdir() if d.is_dir()):
            for p in sorted(cdir.rglob("*.md")):
                if p.name in NON_CONTENT or p.name == log_name:
                    continue
                fm, _ = split_frontmatter(
                    p.read_text(encoding="utf-8", errors="replace"))
                target = (fm.get("replaces")
                          or p.relative_to(cdir).as_posix())
                if target in claimed:
                    problems.append(f"contribs conflict on {target}: "
                                    f"{claimed[target]} vs {cdir.name}")
                    continue
                claimed[target] = cdir.name
                pages[target] = {"file": p, "fm": fm,
                                 "contributor": cdir.name}
    return pages, problems


def log_entries(log_path, kind):
    """[(id, {path: hash})] for entries of the given type; the id is
    the first word of the summary."""
    if not log_path.is_file():
        return []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    out = []
    entries = list(ENTRY.finditer(text))
    for i, m in enumerate(entries):
        if m.group(2) != kind:
            continue
        end = entries[i + 1].start() if i + 1 < len(entries) else len(text)
        body = text[m.end():end]
        frags = {p: h for p, h in FRAGMENT.findall(body)}
        out.append((m.group(3).split()[0], frags))
    return out


def cleared_contributors(pages, log_path):
    """Contributors whose latest consent entry covers every one of
    their current files at current hashes. Fail-closed on drift."""
    current = {}
    for rel, e in pages.items():
        if e["contributor"]:
            current.setdefault(e["contributor"], {})[rel] = \
                digest(e["file"])
    consents = {}
    for who, frags in log_entries(log_path, "consent"):
        consents[who] = frags          # later entries win
    cleared, stale = set(), {}
    for who, files in current.items():
        have = consents.get(who, {})
        missing = {rel: h for rel, h in files.items()
                   if have.get(rel) != h}
        if missing:
            if who in consents:
                stale[who] = sorted(missing)
        else:
            cleared.add(who)
    if "table" in consents:
        cleared.add("table")
    return cleared, stale


def taint(rel, pages, author, cleared, memo):
    """The uncleared contributor this page's ancestry reaches, or
    None. Fail-closed: unknown ancestry is taint."""
    if rel in memo:
        return memo[rel]
    memo[rel] = None                    # cycle guard
    e = pages.get(rel)
    if e is None:
        memo[rel] = "unresolvable ancestry"
        return memo[rel]
    sources = []
    auth = (e["fm"].get("authorship") or "").strip()
    if auth == "transcript" and "table" not in cleared:
        sources.append("table (transcript pages need full-table consent)")
    if auth and auth not in GENERIC and auth != author \
            and auth not in cleared:
        sources.append(auth)
    who = e["contributor"]
    if who and who != author and who not in cleared:
        sources.append(who)
    parent = (e["fm"].get("derived-from") or "").strip()
    if parent:
        up = taint(parent, pages, author, cleared, memo)
        if up:
            sources.append(up)
    memo[rel] = sources[0] if sources else None
    return memo[rel]


def main(argv):
    opts = dict(zip(argv, argv[1:]))
    flags = {a for a in argv if a.startswith("--")}
    src = contribs = out = None
    log_name, author = "log.md", None
    if os.environ.get("EDDIC_CONFIG") and "--src" not in opts:
        cfg_path = Path(os.environ["EDDIC_CONFIG"])
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        root = cfg_path.parent.parent
        src = root / cfg.get("wiki_dir", "wiki")
        contribs = root / cfg.get("contribs_dir", "contribs")
        out = root / "dist" / "bundle"
        log_name = cfg.get("log", "log.md")
        author = cfg.get("author")
    if "--src" in opts:
        src = Path(opts["--src"])
        if contribs is None:
            contribs = src.parent / "contribs"
        if out is None:
            out = src.parent / "dist" / "bundle"
    if "--contribs" in opts:
        contribs = Path(opts["--contribs"])
    if "--out" in opts:
        out = Path(opts["--out"])
    if "--log" in opts:
        log_name = opts["--log"]
    if "--author" in opts:
        author = opts["--author"]
    if not src or not src.is_dir():
        print(__doc__.strip(), file=sys.stderr)
        return 2

    pages, problems = load_effective(src, contribs, log_name)
    log_path = src / log_name

    if "--receipts" in opts:
        who = opts["--receipts"]
        files = {rel: e for rel, e in sorted(pages.items())
                 if e["contributor"] == who}
        if not files:
            print(f"no current contributions from '{who}'",
                  file=sys.stderr)
            return 1
        print(f"consent receipt — {who}, {len(files)} fragment(s):\n")
        for rel, e in files.items():
            print(f"=== {rel} (sha256:{digest(e['file'])})")
            print(e["file"].read_text(encoding="utf-8",
                                      errors="replace").strip(), "\n")
        print("ready-to-append consent entry (log it verbatim after "
              "the contributor approves):\n")
        from datetime import date
        print(f"## [{date.today().isoformat()}] consent | {who} "
              f"cleared {len(files)} fragment(s)\n")
        for rel, e in files.items():
            print(f"- {rel} sha256:{digest(e['file'])}")
        return 0

    refusals = list(problems)
    cleared, stale = cleared_contributors(pages, log_path)
    for who, paths in sorted(stale.items()):
        refusals.append(
            f"stale clearance: {who}'s content changed after sign-off "
            f"({', '.join(paths)}) — re-run --receipts {who}")

    if "--check" in flags:
        logged = {}
        for who, frags in log_entries(log_path, "attribution"):
            logged.setdefault(who, {}).update(frags)
        for rel, e in sorted(pages.items()):
            who = e["contributor"]
            if not who:
                continue
            h = digest(e["file"])
            if logged.get(who, {}).get(rel) != h:
                refusals.append(
                    f"attribution drift: {who}'s {rel} (sha256:{h}) "
                    f"has no matching attribution log entry")
        if refusals:
            print("check FAILED:", file=sys.stderr)
            for r in refusals:
                print(f"  {r}", file=sys.stderr)
            return 1
        print(f"check ok: full corpus = pure corpus + attribution log "
              f"({sum(1 for e in pages.values() if e['contributor'])} "
              f"contributed page(s) accounted for)")
        return 0

    if not author:
        refusals.append("no author declared — transaction rights have "
                        "no holder; set author in .eddic/config.json "
                        "(stamp.py --author) before any sale build")

    memo = {}
    included, credits = {}, []
    for rel, e in sorted(pages.items()):
        t = (e["fm"].get("transactability") or "local-only").strip()
        if t not in SELLABLE:
            continue
        reason = taint(rel, pages, author, cleared, memo)
        if reason:
            refusals.append(f"{rel}: marked {t} but ancestry reaches "
                            f"uncleared {reason}")
            continue
        included[rel] = e
        if t == "transactable-with-attribution":
            credit = e["fm"].get("attribution") or f"(missing credit: {rel})"
            credits.append(f"- {rel}: {credit}")
    if not included and not refusals:
        refusals.append("nothing is marked transactable — the fence "
                        "ships nothing by default; mark pages "
                        "deliberately")

    if refusals:
        print("bundle REFUSED — nothing was written:", file=sys.stderr)
        for r in refusals:
            print(f"  {r}", file=sys.stderr)
        return 1

    if out.exists():
        shutil.rmtree(out)
    wiki_out = out / "wiki"
    for rel, e in included.items():
        dest = wiki_out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(e["file"], dest)
    assets = src / "assets"
    if assets.is_dir():
        for p in sorted(assets.rglob("*")):
            if p.is_file():
                dest = wiki_out / p.relative_to(src)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, dest)
    campaign = src.parent
    for name in ("AGENTS.md", "CLAUDE.md"):
        if (campaign / name).is_file():
            shutil.copyfile(campaign / name, out / name)
    if credits:
        (out / "CREDITS.md").write_text(
            "# Required attribution\n\nThis campaign includes material "
            "used under attribution-bearing licenses:\n\n"
            + "\n".join(credits) + "\n", encoding="utf-8")
    print(f"bundled {len(included)} page(s) to {out} "
          f"(author: {author}; "
          f"{len(credits)} attribution credit(s) injected)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
