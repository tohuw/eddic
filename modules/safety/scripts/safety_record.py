# /// script
# requires-python = ">=3.9"
# ///
"""eddic safety - the table's safety record, rendered and audited.

Usage:
    uv run safety.py render [--src <wiki_dir>]
    uv run safety.py check  [--src <wiki_dir>] [--surface <dir>]...
    (bare, as a vendored eddic verb: paths come from EDDIC_CONFIG)

Two files, one truth. `systems/safety.dm.md` is the master: every line
and every veil the table has set, each one carrying who asked for it.
It is a `.dm` page, so it cannot project - the firewall handles that
without being asked. `systems/safety.md` is the table's copy, and it is
*generated* from the master, never written by hand: the render drops
the `from:` field and every entry the asker did not want shared, so the
table reads the rule without learning whose it is.

That split is the whole design. A line has to reach the table (players
write backstory, propose lore, and pitch scenes; a rule only the DM
knows is a rule only the DM can keep), and the person who set it has to
stay out of it. Making the player page a pure function of the master is
what turns "remember not to mention who asked" from a discipline into a
property: there is no hand-editing step where a name could get typed.

`check` proves three things and refuses to pretend at a fourth:

  schema      every entry has a kind (line/veil), a share (table or
              dm-only), a note, a unique topic, and at most a
              single-token `from:`; the master is not player-visible;
              the rendered page is.
  render      the page on disk is byte-identical to what the master
              renders. A stale page and a hand-edited page fail the
              same way, which is the point - a name added by hand to
              the player page is a failing check, not a leak.
  attribution no contributor id used as a `from:` anywhere in the
              record appears on the rendered page, in the projection,
              or in any other surface named with --surface.

What it does not check is whether the DM actually honoured a veil in
prose. That is judgment, it lives in the pattern's rules for agents,
and a script claiming it would be lying.

Exit codes: 0 clean, 1 violations (listed), 2 usage error.
"""

import json
import os
import re
import sys
from pathlib import Path

MASTER_REL = "systems/safety.dm.md"
PLAYER_REL = "systems/safety.md"

KINDS = ("line", "veil")
SHARES = ("table", "dm-only")
ID = re.compile(r"^[\w-]+$")
FIELD = re.compile(r"^([a-z][\w-]*):\s*(.*)$")

# Prose the render supplies when the master does not override it. The
# master overrides by carrying its own `## Preamble` / `## Signals`
# section, which is copied verbatim - a mechanical relay, so a table
# that has re-voiced or translated its own signal set keeps its words.
PREAMBLE = (
    "This page is the table's record of what this campaign does not put "
    "on screen. It was set at session zero and it changes whenever "
    "anyone wants it to. Entries carry no names: who asked for a line is "
    "not recorded here.")
LINES_INTRO = (
    "A line is never in the game, in any form - not on screen, not off "
    "screen, not in description, art, handouts, or backstory.")
VEILS_INTRO = (
    "A veil can exist in the world but is never played out. The scene "
    "cuts and the table picks up at the aftermath.")
NO_LINES = "The table has set no lines."
NO_VEILS = "The table has set no veils."
SIGNALS = (
    "Anyone can stop or rewind a scene at any time, without giving a "
    "reason and without saying which entry it was.\n"
    "\n"
    "- Say it out loud: \"X-card\", or \"let's veil that\".\n"
    "- Type X in the table's text channel. Nobody has to speak.\n"
    "- React with the agreed reaction on the pinned signal post. "
    "Nobody has to type.\n"
    "- Send the DM a private message. Nobody else sees that it happened.\n"
    "\n"
    "All four do the same thing: play stops, the scene backs up to "
    "before the material, and it goes differently. No one asks what it "
    "was about, at the time or afterwards. Leaving the call is also a "
    "signal and needs no explanation.")
CHANGING = (
    "To add or remove an entry, tell the DM privately. Nothing needs a "
    "reason and nothing is negotiated. Additions appear here without "
    "announcement. The DM re-sends the session-zero questions from time "
    "to time so nobody has to raise it cold.")

# --- BEGIN SHARED wikilib: split_frontmatter, visibility_of ---
def split_frontmatter(text):
    """(frontmatter dict, body) — flat `key: value` pairs only, top level
    only, no YAML dependency. A page with no frontmatter yields ({}, text),
    which is what makes every visibility judgment fail closed."""
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


def visibility_of(fm):
    """Effective visibility, fail-closed: anything that is not exactly
    `player` is DM-only, including a page with no frontmatter at all.

    An open merge proposal is DM-side however it marks itself. It is
    unadjudicated lore the DM has not chosen yet, so it cannot ship to
    players even when someone marks it player-visible; the lint reports that
    contradiction, and this refuses to act on it. Every surface that decides
    what players see reads this — the projection that writes their wiki, the
    lint that judges a breach, the constellation that charts it — so that a
    clean lint means a projection that will build."""
    if (fm.get("proposes-merge-into") or "").strip():
        return "dm"
    return (fm.get("visibility") or "dm").strip()
# --- END SHARED wikilib ---


def sections(body):
    """(ordered {heading: [lines]}, ) for the master's `## ` sections."""
    out, name = {}, None
    for line in body.splitlines():
        m = re.match(r"^##\s+(.*?)\s*$", line)
        if m and not line.startswith("###"):
            name = m.group(1).strip().lower()
            out.setdefault(name, [])
            continue
        if name is not None:
            out[name].append(line)
    return out


def parse_entries(lines):
    """Entries from the master's `## Record` section.

    An entry is `### <topic>` followed by flat `key: value` fields. A
    line that is neither a field nor a heading continues the previous
    field, so a long note can wrap. Returns (entries, errors); entries
    are dicts with `topic` plus whatever fields were declared, in the
    order the DM wrote them.
    """
    entries, errors, cur, key = [], [], None, None
    for n, raw in enumerate(lines, 1):
        line = raw.rstrip()
        m = re.match(r"^###\s+(.*?)\s*$", line)
        if m:
            cur = {"topic": m.group(1).strip(), "line": n}
            entries.append(cur)
            key = None
            continue
        if not line.strip():
            key = None
            continue
        if cur is None:
            errors.append(f"record: text before the first entry: "
                          f"{line.strip()[:50]}")
            continue
        f = FIELD.match(line.strip())
        if f:
            key = f.group(1)
            if key in cur:
                errors.append(f"{cur['topic']}: field '{key}' set twice")
            cur[key] = f.group(2).strip()
        elif key:
            cur[key] = (cur[key] + " " + line.strip()).strip()
        else:
            errors.append(f"{cur['topic']}: stray text with no field: "
                          f"{line.strip()[:50]}")
    return entries, errors


def validate(fm, entries):
    """Schema errors in the master. Fail-closed on every axis: an
    unparseable entry is never silently dropped from the player page,
    because a dropped entry is a line the table stops seeing."""
    errors = []
    if visibility_of(fm) == "player":
        errors.append(f"{MASTER_REL} is marked visibility: player - the "
                      f"master holds attribution and must stay DM-only")
    seen = {}
    for e in entries:
        topic = e.get("topic", "")
        where = topic or f"line {e.get('line')}"
        if not topic:
            errors.append(f"entry at line {e.get('line')} has no topic")
        low = topic.lower()
        if low in seen:
            errors.append(f"{where}: topic repeats an earlier entry")
        seen[low] = True
        kind = e.get("kind", "")
        if kind not in KINDS:
            errors.append(f"{where}: kind '{kind}' is not one of {KINDS}")
        share = e.get("share", "")
        if share not in SHARES:
            errors.append(f"{where}: share '{share}' is not one of {SHARES}")
        if not e.get("note", "").strip():
            errors.append(f"{where}: no note - say what the entry means "
                          f"in play, or the DM is guessing at it")
        frm = e.get("from", "").strip()
        if frm and not ID.match(frm):
            errors.append(f"{where}: from '{frm}' is not a single "
                          f"contributor id (use an id, or 'anonymous')")
    return errors


def attributions(entries):
    """Contributor ids the record can attribute an entry to. `anonymous`
    is not one: it attributes nothing, so it can never leak."""
    return sorted({e.get("from", "").strip().lower() for e in entries
                   if e.get("from", "").strip().lower()
                   not in ("", "anonymous")})


def prose(secs, name, default):
    text = "\n".join(secs.get(name, [])).strip()
    return text if text else default


def render(secs, entries):
    """The player page: a pure function of the master. Nothing here can
    emit a `from:` value, because nothing here reads one."""
    shared = [e for e in entries if e.get("share") == "table"]
    out = ["---", "visibility: player", "authorship: machine", "---", "",
           "# Table safety", "", prose(secs, "preamble", PREAMBLE), ""]
    for kind, intro, empty in (("line", LINES_INTRO, NO_LINES),
                               ("veil", VEILS_INTRO, NO_VEILS)):
        picked = [e for e in shared if e.get("kind") == kind]
        out += [f"## {'Lines' if kind == 'line' else 'Veils'}", "", intro, ""]
        if picked:
            out += [f"- {e['topic']} — {e['note']}" for e in picked]
        else:
            out.append(empty)
        out.append("")
    out += ["## Signals", "", prose(secs, "signals", SIGNALS), "",
            "## Changing this", "", prose(secs, "changing this", CHANGING),
            ""]
    return "\n".join(out)


def read(path):
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def load(src):
    """(frontmatter, sections, entries, errors) from the master."""
    master = src / MASTER_REL
    if not master.is_file():
        return None, None, None, [f"no safety record at {MASTER_REL} - "
                                  f"stamp the seed template first"]
    fm, body = split_frontmatter(read(master))
    secs = sections(body)
    if "record" not in secs:
        return fm, secs, [], [f"{MASTER_REL} has no '## Record' section"]
    entries, errors = parse_entries(secs["record"])
    return fm, secs, entries, errors + validate(fm, entries)


def do_render(src):
    fm, secs, entries, errors = load(src)
    if errors:
        for e in errors:
            print(f"safety: {e}")
        return 1
    target = src / PLAYER_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    text = render(secs, entries)
    if target.is_file() and read(target) == text:
        print(f"safety: {PLAYER_REL} already current "
              f"({len(entries)} entries)")
        return 0
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    shared = sum(1 for e in entries if e.get("share") == "table")
    print(f"safety: wrote {PLAYER_REL} ({shared} of {len(entries)} "
          f"entries shared with the table)")
    return 0


def sweep(ids, files):
    """Every (path, id) where an attributable contributor id reaches a
    file that players can read."""
    hits = []
    for path in files:
        try:
            text = read(path)
        except (OSError, UnicodeDecodeError):
            continue
        for cid in ids:
            if re.search(rf"\b{re.escape(cid)}\b", text, re.I):
                hits.append((path, cid))
    return hits


def surface_files(dirs):
    out = []
    for d in dirs:
        if d and d.is_dir():
            out += [p for p in sorted(d.rglob("*")) if p.is_file()]
    return out


def do_check(src, surfaces):
    problems = []
    fm, secs, entries, errors = load(src)
    problems += errors
    player = src / PLAYER_REL
    if entries is not None and not errors:
        if not player.is_file():
            problems.append(f"no {PLAYER_REL} - run `eddic safety render`")
        else:
            want, got = render(secs, entries), read(player)
            if want != got:
                problems.append(
                    f"{PLAYER_REL} is not what the master renders. It is "
                    f"stale or it was edited by hand; either way re-run "
                    f"`eddic safety render` and put the change in "
                    f"{MASTER_REL} instead")
            pfm, _ = split_frontmatter(got)
            if visibility_of(pfm) != "player":
                problems.append(f"{PLAYER_REL} is not marked "
                                f"visibility: player, so the table "
                                f"cannot read its own record")
            for e in entries:
                if e.get("share") != "dm-only":
                    continue
                low = got.lower()
                if e["topic"].lower() in low or (
                        e.get("note", "").strip().lower() in low
                        and e.get("note", "").strip()):
                    problems.append(
                        f"{PLAYER_REL} carries the dm-only entry "
                        f"'{e['topic']}' - that entry was set on the "
                        f"understanding the table would not see it")

    ids = attributions(entries or [])
    targets = ([player] if player.is_file() else []) + surface_files(surfaces)
    for path, cid in sweep(ids, targets):
        problems.append(f"attribution leak: contributor id '{cid}' appears "
                        f"in {path} - a player-facing surface must never "
                        f"say who set an entry")

    for p in problems:
        print(f"safety: {p}")
    print(f"safety check: {'ok' if not problems else 'FAILED'} "
          f"({len(entries or [])} entries, {len(ids)} attributed, "
          f"{len(targets)} player-facing files swept)")
    return 1 if problems else 0


def main(argv):
    if not argv or argv[0] not in ("render", "check"):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    mode, rest = argv[0], argv[1:]
    src, surfaces, i = None, [], 0
    while i < len(rest):
        if rest[i] == "--src" and i + 1 < len(rest):
            src = Path(rest[i + 1])
        elif rest[i] == "--surface" and i + 1 < len(rest):
            surfaces.append(Path(rest[i + 1]))
        else:
            print(f"unknown argument: {rest[i]}", file=sys.stderr)
            return 2
        i += 2
    if src is None and os.environ.get("EDDIC_CONFIG"):
        cfg_path = Path(os.environ["EDDIC_CONFIG"])
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        root = cfg_path.parent.parent
        src = root / cfg.get("wiki_dir", "wiki")
        if not surfaces:
            surfaces = [root / cfg.get("projection_dir", "dist/player")]
    if src is None:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    if not src.is_dir():
        print(f"not a directory: {src}", file=sys.stderr)
        return 2
    if mode == "check" and not surfaces:
        surfaces = [src.parent / "dist" / "player"]
    return do_render(src) if mode == "render" else do_check(src, surfaces)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
